import os
import sys
import json
import requests
import subprocess
import re
from mistralai.client import MistralClient

# Инициализация Mistral AI клиента
client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

# Получаем информацию о PR
pr_number = os.environ.get("PR_NUMBER")
repository = os.environ.get("GITHUB_REPOSITORY")
github_token = os.environ.get("GITHUB_TOKEN")

# Получаем список измененных файлов
base_sha = os.environ.get("BASE_SHA")
head_sha = os.environ.get("HEAD_SHA")
result = subprocess.run(
    f"git diff --name-only {base_sha} {head_sha}",
    shell=True,
    capture_output=True,
    text=True
)
files = [f for f in result.stdout.strip().split("\n") if f.endswith(('.py', '.js', '.ts', '.go', '.java', '.cs', '.cpp', '.h', '.c'))]

if not files:
    print("Нет файлов для ревью")
    sys.exit(0)

def parse_diff(diff_text):
    """Парсит diff и возвращает изменения с информацией о строках"""
    changes = []
    current_hunk = None
    lines = diff_text.split('\n')
    file_path = None
    
    for line in lines:
        # Новый файл или измененный файл
        if line.startswith('diff --git'):
            file_path = line.split(' ')[2][2:]  # извлекаем путь файла
        
        # Начало нового блока изменений
        elif line.startswith('@@'):
            # Парсим информацию о строках: @@ -start,count +start,count @@
            hunk_info = line.split('@@')[1].strip()
            matches = re.match(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', hunk_info)
            if matches:
                old_start = int(matches.group(1))
                new_start = int(matches.group(2))
                current_hunk = {
                    'header': line,
                    'old_start': old_start,
                    'new_start': new_start,
                    'lines': [],
                    'context': hunk_info
                }
                changes.append(current_hunk)
        
        # Строки с изменениями
        elif current_hunk is not None:
            current_hunk['lines'].append(line)
    
    return changes

def parse_line_comments(review_text):
    """Парсит текст ревью и извлекает комментарии к строкам"""
    line_comments = []
    
    # Регулярное выражение для поиска комментариев в формате "СТРОКА X: комментарий"
    pattern = r'СТРОКА (\d+)(?:-(\d+))?: (.*?)(?=\nСТРОКА|\n\n|$)'
    matches = re.finditer(pattern, review_text, re.DOTALL)
    
    for match in matches:
        start_line = int(match.group(1))
        end_line = int(match.group(2)) if match.group(2) else start_line
        comment = match.group(3).strip()
        
        line_comments.append({
            'start_line': start_line,
            'end_line': end_line,
            'comment': comment
        })
    
    return line_comments

def get_commit_id():
    """Получает последний коммит в PR"""
    commits_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/commits"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(commits_url, headers=headers)
    if response.status_code == 200:
        commits = response.json()
        if commits:
            return commits[-1]['sha']
    
    return head_sha

def create_review_with_comments(file_comments, commit_id):
    """Создает ревью с комментариями к конкретным строкам кода"""
    review_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Сначала получаем файлы, измененные в PR для определения правильных position
    files_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
    files_response = requests.get(files_url, headers=headers)
    pr_files = {}
    
    if files_response.status_code == 200:
        for file_info in files_response.json():
            pr_files[file_info['filename']] = file_info
    
    # Подготавливаем комментарии в нужном формате
    review_comments = []
    for file_path, comments in file_comments.items():
        if file_path not in pr_files:
            print(f"Файл {file_path} не найден в PR")
            continue
            
        # Получаем patch для определения position
        patch = pr_files[file_path].get('patch', '')
        
        # Создаем map номеров строк в файле -> позиция в diff
        line_position_map = {}
        position = 0
        new_line_num = 0
        
        if patch:
            for line in patch.split('\n'):
                position += 1
                if line.startswith('+'):
                    new_line_num += 1
                    line_position_map[new_line_num] = position
                elif line.startswith(' '):  # Контекстная строка
                    new_line_num += 1
        
        for comment in comments:
            start_line = comment['start_line']
            comment_body = comment['comment']
            
            # Пытаемся найти позицию в diff
            if start_line in line_position_map:
                position = line_position_map[start_line]
                
                review_comments.append({
                    "path": file_path,
                    "position": position,
                    "body": comment_body
                })
            else:
                print(f"Не удалось определить position для строки {start_line} в файле {file_path}")
    
    if not review_comments:
        print("Нет комментариев для добавления")
        return False
    
    # Создаем ревью
    review_data = {
        "commit_id": commit_id,
        "event": "COMMENT",
        "comments": review_comments
    }
    
    response = requests.post(review_url, headers=headers, json=review_data)
    if response.status_code not in [200, 201]:
        print(f"Ошибка при создании ревью: {response.status_code} - {response.text}")
        return False
    
    return True

# Собираем все комментарии по файлам
all_file_comments = {}
full_review = "## Ревью кода с помощью Mistral AI\n\n"

for file_path in files:
    if not os.path.exists(file_path):
        continue
        
    # Получаем diff для файла
    diff_result = subprocess.run(
        f"git diff {base_sha} {head_sha} -- {file_path}",
        shell=True,
        capture_output=True,
        text=True
    )
    diff = diff_result.stdout
    
    if not diff.strip():
        continue
    
    # Парсим diff чтобы выделить изменения
    changes = parse_diff(diff)
    
    if not changes:
        continue
    
    # Формируем промпт для Mistral AI с фокусом только на изменениях
    prompt = f"""Ты выполняешь ревью кода для pull request. Напиши комментарии ТОЛЬКО по измененным строкам кода, НЕ весь файл.

Имя файла: {file_path}

Изменения (diff):
```
{diff}
```

Инструкции:
1. Пиши комментарии на РУССКОМ языке.
2. Анализируй ТОЛЬКО строки, начинающиеся с '+' (добавленные) и измененный контекст.
3. Комментируй каждое значимое изменение отдельно с привязкой к номеру строки.
4. Не комментируй удаленные строки (начинающиеся с '-').
5. Проверь на:
   - Ошибки и потенциальные баги
   - Возможности оптимизации и улучшения производительности
   - Проблемы безопасности
   - Соответствие стандартам кодирования и улучшения читаемости
6. Структурируй ответ в формате:
   ```
   СТРОКА 123: Твой комментарий о проблеме или предложение улучшения
   СТРОКА 125-128: Комментарий к блоку кода
   ```
7. Если изменение хорошее - тоже отметь это.
8. Добавь в конце общую оценку изменений от 1 до 5, где 5 - отлично.
9. Убедись, что номера строк соответствуют итоговому файлу (строки с '+'), а не diff.
"""
    
    # Запрос к Mistral AI
    try:
        chat_response = client.chat(
            model="mistral-small",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        review_text = chat_response.choices[0].message.content
        
        # Парсим комментарии к строкам
        line_comments = parse_line_comments(review_text)
        if line_comments:
            all_file_comments[file_path] = line_comments
        
        # Добавляем ревью в общий отчет с информацией о файле
        full_review += f"### Ревью для файла: `{file_path}`\n\n{review_text}\n\n---\n\n"
    except Exception as e:
        print(f"Ошибка при анализе {file_path}: {e}")
        full_review += f"### Ошибка при анализе файла `{file_path}`\n\n---\n\n"

# Сохраняем полный обзор в файл
with open("review.txt", "w", encoding="utf-8") as f:
    f.write(full_review)

# Создаем ревью с комментариями к конкретным строкам кода
if all_file_comments:
    commit_id = get_commit_id()
    create_review_with_comments(all_file_comments, commit_id)
else:
    print("Не найдено комментариев к строкам кода") 
