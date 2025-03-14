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

def extract_file_content(file_path):
    """Извлекает содержимое файла из репозитория"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        return []

def create_review_with_comments(file_comments, commit_id):
    """Создает ревью с комментариями к конкретным строкам кода"""
    # Подготавливаем комментарии
    total_comments = 0
    placed_comments = 0
    
    # Создаем структурированный комментарий для PR
    summary = "# Ревью кода от Mistral AI\n\n"
    
    # Добавляем информацию о коммите
    summary += f"**Коммит:** `{commit_id[:7]}`\n\n"
    
    # Добавляем комментарии по файлам
    for file_path, comments in file_comments.items():
        total_comments += len(comments)
        
        print(f"Добавляем комментарии для файла: {file_path}")
        
        file_section = f"## Файл: `{file_path}`\n\n"
        
        # Добавляем все комментарии для этого файла
        for comment in comments:
            start_line = comment['start_line']
            comment_body = comment['comment']
            
            file_section += f"### Строка {start_line}\n\n{comment_body}\n\n"
            placed_comments += 1
        
        summary += file_section + "---\n\n"
    
    # Статистика
    print(f"Всего комментариев: {total_comments}")
    print(f"Размещено комментариев: {placed_comments}")
    
    if placed_comments == 0:
        print("Нет комментариев для добавления")
        return False
    
    # Создаем комментарий к PR
    comments_url = f"https://api.github.com/repos/{repository}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    comment_data = {
        "body": summary
    }
    
    print(f"Создаем комментарий к PR с {placed_comments} замечаниями")
    
    response = requests.post(comments_url, headers=headers, json=comment_data)
    if response.status_code not in [200, 201]:
        print(f"Ошибка при создании комментария: {response.status_code} - {response.text}")
        return False
    
    print(f"Комментарий успешно создан")
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
10. Не используй в СТРОКАХ диапазоны, указывай конкретные номера строк для каждого комментария.
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
