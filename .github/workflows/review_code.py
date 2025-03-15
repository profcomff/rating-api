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
    review_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Получаем информацию о PR
    pr_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}"
    pr_response = requests.get(pr_url, headers=headers)
    pr_info = {}
    if pr_response.status_code == 200:
        pr_info = pr_response.json()
    
    # Сначала получаем файлы, измененные в PR для определения правильных position
    files_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
    files_response = requests.get(files_url, headers=headers)
    pr_files = {}
    
    if files_response.status_code == 200:
        for file_info in files_response.json():
            pr_files[file_info['filename']] = file_info
    
    # Подготавливаем комментарии
    review_comments = []
    total_comments = 0
    placed_comments = 0

    # Словарь для хранения первых позиций в каждом файле (для файловых комментариев)
    file_first_positions = {}

    # Сначала найдем первую позицию для каждого файла
    for file_path, file_info in pr_files.items():
        patch = file_info.get('patch', '')
        
        # Попробуем получить первую позицию из patch
        if patch:
            lines = patch.split('\n')
            if len(lines) > 0:
                file_first_positions[file_path] = 1  # Первая строка patch всегда подходит
                
                # Ищем первое изменение (строка с +)
                for i, line in enumerate(lines):
                    if line.startswith('+'):
                        file_first_positions[file_path] = i + 1  # +1 потому что позиции в GitHub начинаются с 1
                        break
        else:
            # Если нет patch, используем позицию 1
            file_first_positions[file_path] = 1


    for file_path, comments in file_comments.items():
        total_comments += len(comments)

        print(f"Обрабатываем комментарии для файла: {file_path}")
        if file_path not in pr_files:
            print(f"Файл {file_path} не найден в PR")
            continue
            
        # Получаем patch и diff для определения position
        patch = pr_files[file_path].get('patch', '')
        
        # Используем git diff для получения более точной информации
        diff_result = subprocess.run(
            f"git diff {base_sha} {head_sha} -- {file_path}",
            shell=True,
            capture_output=True,
            text=True
        )
        full_diff = diff_result.stdout
        
        # Получаем содержимое файла для дополнительной проверки
        file_content = extract_file_content(file_path)
        
        # Создаем карту номеров строк и позиций
        line_position_map = {}
        line_num = 0
        position = 0
        
        # Если это первый файл, убедимся, что он имеет позицию
        if file_path not in file_first_positions:
            file_first_positions[file_path] = 1
        
        # Парсим diff для определения позиций
        for line in full_diff.split('\n'):
            position += 1
            
            if line.startswith('@@'):
                # Парсим информацию о строках: @@ -start,count +start,count @@
                hunk_info = line.split('@@')[1].strip()
                matches = re.match(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', hunk_info)
                if matches:
                    line_num = int(matches.group(2)) - 1  # -1 чтобы начать с правильного номера для следующей строки
            
            if line.startswith('+'):
                line_num += 1
                line_position_map[line_num] = position
            elif line.startswith(' '):
                line_num += 1

        # Также создаем альтернативную карту из patch в API
        api_line_position_map = {}
        line_num = 0
        position = 0

        if patch:
            for line in patch.split('\n'):
                if line.startswith('@@'):
                    matches = re.match(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', line.split('@@')[1].strip())
                    if matches:
                        line_num = int(matches.group(2)) - 1
                
                position += 1
                
                if line.startswith('+'):
                    line_num += 1
                    api_line_position_map[line_num] = position
                elif line.startswith(' '):
                    line_num += 1
        
        # Группируем комментарии по файлам, если не удается найти позицию
        file_level_comments = []
        
        # Добавляем новый метод для определения позиции: поиск контекста
        for comment in comments:
            start_line = comment['start_line']
            comment_body = comment['comment']
            position_found = False

            # 1. Попробуем найти прямое соответствие в нашей карте из diff
            if start_line in line_position_map:
                position = line_position_map[start_line]
                position_found = True
                print(f"Найдена позиция для строки {start_line} в карте из diff: {position}")
            
            # 2. Попробуем найти в карте из API
            elif start_line in api_line_position_map:
                position = api_line_position_map[start_line]
                position_found = True
                print(f"Найдена позиция для строки {start_line} в карте из API: {position}")
            
            # 3. Если все еще не найдено, попробуем использовать относительную позицию
            elif file_content and 0 < start_line <= len(file_content):
                # Найдем контекст строки в файле
                target_line = file_content[start_line - 1].rstrip()
                context_line = target_line.strip()
                
                if context_line:
                    # Ищем эту строку в diff
                    lines = full_diff.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('+') and context_line in line.strip():
                            # Вычисляем position относительно начала diff
                            position = i + 1  # +1 потому что позиции в GitHub начинаются с 1
                            position_found = True
                            print(f"Найдена позиция для строки {start_line} через контекст: {position}")
                            break
            
            if position_found:
                review_comments.append({
                    "path": file_path,
                    "position": position,
                    "body": comment_body
                })
                placed_comments += 1
            else:
                # Если не удалось найти позицию, добавляем комментарий к группе файловых комментариев
                print(f"Не удалось определить position для строки {start_line} в файле {file_path}, добавлен комментарий к файлу")
                file_level_comments.append(f"**Комментарий к строке {start_line}**: {comment_body}")

        # Добавляем сгруппированные комментарии к файлу на первую доступную позицию
        if file_level_comments:
            first_position = file_first_positions.get(file_path, 1)  # Если нет позиции, используем 1
            review_comments.append({
                "path": file_path,
                "position": first_position,
                "body": "\n\n".join(file_level_comments)
            })
            placed_comments += 1

    # Статистика
    print(f"Всего комментариев: {total_comments}")
    print(f"Размещено комментариев: {placed_comments}")

    if not review_comments:
        print("Нет комментариев для добавления")
        return False

    # Проверка, что все комментарии имеют позицию
    for i, comment in enumerate(review_comments):
        if "position" not in comment or comment["position"] is None:
            # Если позиция отсутствует, установим её в 1
            print(f"Исправляем отсутствующую позицию для комментария {i} к файлу {comment['path']}")
            comment["position"] = 1

    # Создаем ревью
    review_data = {
        "commit_id": commit_id,
        "event": "COMMENT",
        "comments": review_comments
    }

    print(f"Отправляем запрос на создание ревью с {len(review_comments)} комментариями")
    for i, comment in enumerate(review_comments):
        print(f"Комментарий {i+1}: файл={comment['path']}, позиция={comment['position']}")

    response = requests.post(review_url, headers=headers, json=review_data)
    if response.status_code not in [200, 201]:
        print(f"Ошибка при создании ревью: {response.status_code} - {response.text}")
        
        # Пробуем создать ревью без линейных комментариев
        if "comments" in review_data:
            print("Пробуем создать общий комментарий к PR...")
            summary = "# Комментарии к коду\n\n"
            
            for comment in review_comments:
                file_path = comment.get("path", "неизвестный файл")
                body = comment.get("body", "")
                summary += f"## Файл: {file_path}\n\n{body}\n\n---\n\n"
            
            review_data = {
                "commit_id": commit_id,
                "event": "COMMENT",
                "body": summary
            }
            
            response = requests.post(
                f"https://api.github.com/repos/{repository}/pulls/{pr_number}/reviews",
                headers=headers,
                json=review_data
            )
            
            if response.status_code not in [200, 201]:
                print(f"Ошибка при создании общего комментария: {response.status_code} - {response.text}")
                return False
            else:
                print("Общий комментарий к PR успешно создан.")
                return True
        
        return False

    print(f"Ревью успешно создано с {len(review_comments)} комментариями")
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
            model="open-codestral-mamba",
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
