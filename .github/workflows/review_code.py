import os
import sys
import json
import requests
import subprocess
import re
from mistralai.client import MistralClient

client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

pr_number = os.environ.get("PR_NUMBER")
repository = os.environ.get("GITHUB_REPOSITORY")
github_token = os.environ.get("GITHUB_TOKEN")

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
    changes = []
    current_hunk = None
    lines = diff_text.split('\n')
    file_path = None
    
    for line in lines:
        if line.startswith('diff --git'):
            file_path = line.split(' ')[2][2:]
        
        elif line.startswith('@@'):
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
        
        elif current_hunk is not None:
            current_hunk['lines'].append(line)
    
    return changes

def parse_line_comments(review_text):
    line_comments = []
    
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
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception as e:
        print(f"Ошибка при чтении файла {file_path}: {e}")
        return []

def get_diff_hunk_for_position(patch, position):
    lines = patch.split('\n')
    if 0 <= position < len(lines):
        start_idx = position
        while start_idx > 0 and not lines[start_idx].startswith('@@'):
            start_idx -= 1
            
        if start_idx < 0 or not lines[start_idx].startswith('@@'):
            return None
        
        end_idx = position
        while end_idx < len(lines) and not (end_idx > position and lines[end_idx].startswith('@@')):
            end_idx += 1
            
        hunk_lines = lines[start_idx:end_idx]
        return '\n'.join(hunk_lines)
    
    return None

def validate_position(patch, position):
    if position <= 0:
        return False
        
    lines = patch.split('\n')
    if position >= len(lines):
        return False
        
    diff_hunk = get_diff_hunk_for_position(patch, position)
    if not diff_hunk:
        return False
        
    if position < len(lines) and lines[position].startswith('-'):
        return False
        
    return True

def find_position_by_content(patch, content, line_num, vicinity=2):
    lines = patch.split('\n')
    content = content.strip()
    
    if not content:
        return None
        
    for i, line in enumerate(lines):
        if (line.startswith('+') or line.startswith(' ')) and content in line.strip():
            if get_diff_hunk_for_position(patch, i):
                return i
    
    for i, line in enumerate(lines):
        if line.startswith('+') or line.startswith(' '):
            content_parts = content.split()
            if content_parts and any(part in line for part in content_parts if len(part) > 3):
                if get_diff_hunk_for_position(patch, i):
                    return i
    
    return None

def create_review_with_comments(file_comments, commit_id):
    """Создает ревью с комментариями к конкретным строкам кода"""
    review_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    pr_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}"
    pr_response = requests.get(pr_url, headers=headers)
    pr_info = {}
    if pr_response.status_code == 200:
        pr_info = pr_response.json()
    
    files_url = f"https://api.github.com/repos/{repository}/pulls/{pr_number}/files"
    files_response = requests.get(files_url, headers=headers)
    pr_files = {}
    
    if files_response.status_code == 200:
        for file_info in files_response.json():
            pr_files[file_info['filename']] = file_info
    
    review_comments = []
    total_comments = 0
    placed_comments = 0
    
    file_first_positions = {}
    file_diff_hunks = {}
    
    for file_path, file_info in pr_files.items():
        patch = file_info.get('patch', '')
        
        if patch:
            lines = patch.split('\n')
            if len(lines) > 0:
                file_first_positions[file_path] = 1
                
                for i, line in enumerate(lines):
                    if line.startswith('+'):
                        file_first_positions[file_path] = i + 1
                        break
                
                file_diff_hunks[file_path] = get_diff_hunk_for_position(patch, file_first_positions[file_path])
        else:
            file_first_positions[file_path] = 1
            file_diff_hunks[file_path] = None
    
    for file_path, comments in file_comments.items():
        total_comments += len(comments)
        
        print(f"Обрабатываем комментарии для файла: {file_path}")
        if file_path not in pr_files:
            print(f"Файл {file_path} не найден в PR")
            continue
            
        patch = pr_files[file_path].get('patch', '')
        
        if not patch:
            print(f"Отсутствует patch для файла {file_path}, добавляем комментарии в общий список")
            file_level_comments = []
            for comment in comments:
                file_level_comments.append(f"**Комментарий к строке {comment['start_line']}**: {comment['comment']}")
            
            if file_level_comments:
                review_comments.append({
                    "path": file_path,
                    "position": 1,
                    "body": "\n\n".join(file_level_comments)
                })
                placed_comments += 1
            continue
        
        pr_files[file_path]['parsed_patch'] = patch
        
        diff_result = subprocess.run(
            f"git diff {base_sha} {head_sha} -- {file_path}",
            shell=True,
            capture_output=True,
            text=True
        )
        full_diff = diff_result.stdout
        
        file_content = extract_file_content(file_path)
        
        line_position_maps = {}
        
        line_position_map_git = {}
        line_num = 0
        position = 0
        for line in full_diff.split('\n'):
            position += 1
            
            if line.startswith('@@'):
                hunk_info = line.split('@@')[1].strip()
                matches = re.match(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', hunk_info)
                if matches:
                    line_num = int(matches.group(2)) - 1
            
            if line.startswith('+'):
                line_num += 1
                line_position_map_git[line_num] = position
            elif line.startswith(' '):
                line_num += 1
        
        line_position_maps['git'] = line_position_map_git
        
        line_position_map_api = {}
        line_num = 0
        position = 0
        for line in patch.split('\n'):
            position += 1
            
            if line.startswith('@@'):
                matches = re.match(r'-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?', line.split('@@')[1].strip())
                if matches:
                    line_num = int(matches.group(2)) - 1
            
            if line.startswith('+'):
                line_num += 1
                line_position_map_api[line_num] = position
            elif line.startswith(' '):
                line_num += 1
        
        line_position_maps['api'] = line_position_map_api
        
        line_content_map = {}
        if file_content:
            for i, line in enumerate(file_content):
                line_content_map[i+1] = line.strip()
        
        position_hunk_map = {}
        for pos in range(len(patch.split('\n'))):
            hunk = get_diff_hunk_for_position(patch, pos)
            if hunk:
                position_hunk_map[pos] = hunk
        
        file_level_comments = []
        file_comments_added = 0
        
        valid_positions = set()
        position_hunk_mapping = {}
        
        lines = patch.split('\n')
        for pos, line in enumerate(lines):
            if not line.startswith('-'):
                if validate_position(patch, pos):
                    valid_positions.add(pos)
                    hunk = get_diff_hunk_for_position(patch, pos)
                    if hunk:
                        position_hunk_mapping[pos] = hunk
        
        for comment in comments:
            start_line = comment['start_line']
            comment_body = comment['comment']
            position_found = False
            position = None
            diff_hunk = None
            
            for map_name, position_map in line_position_maps.items():
                if start_line in position_map:
                    position = position_map[start_line]
                    if position in valid_positions:
                        diff_hunk = position_hunk_mapping.get(position)
                        if diff_hunk:
                            position_found = True
                            print(f"Найдена позиция для строки {start_line} в карте {map_name}: {position} с валидным diff_hunk")
                            break
                    else:
                        print(f"Найдена позиция {position} для строки {start_line} в карте {map_name}, но она невалидна")
            
            if not position_found and file_content and 0 < start_line <= len(file_content):
                target_line = file_content[start_line - 1].rstrip()
                context_line = target_line.strip()
                
                if context_line:
                    position = find_position_by_content(patch, context_line, start_line)
                    if position is not None and position in valid_positions:
                        diff_hunk = position_hunk_mapping.get(position)
                        if diff_hunk:
                            position_found = True
                            print(f"Найдена позиция для строки {start_line} через точное совпадение контекста: {position} с валидным diff_hunk")
                
                if not position_found:
                    context_lines = []
                    for offset in range(-5, 6):
                        idx = start_line - 1 + offset
                        if 0 <= idx < len(file_content):
                            context_lines.append(file_content[idx].strip())
                    
                    for i, context in enumerate(context_lines):
                        if context and offset != 0:
                            position = find_position_by_content(patch, context, start_line - 5 + i)
                            if position is not None and position in valid_positions:
                                diff_hunk = position_hunk_mapping.get(position)
                                if diff_hunk:
                                    position_found = True
                                    print(f"Найдена позиция для строки {start_line} через окружающий контекст (строка {start_line - 5 + i}): {position} с валидным diff_hunk")
                                    break
                
                if not position_found and valid_positions:
                    nearest_line = None
                    nearest_position = None
                    min_distance = float('inf')
                    
                    for line_num, pos in line_position_map_api.items():
                        if pos in valid_positions:
                            distance = abs(line_num - start_line)
                            if distance < min_distance:
                                min_distance = distance
                                nearest_line = line_num
                                nearest_position = pos
                    
                    if nearest_position and min_distance <= 5:
                        position = nearest_position
                        diff_hunk = position_hunk_mapping.get(position)
                        if diff_hunk:
                            position_found = True
                            print(f"Найдена ближайшая валидная позиция для строки {start_line} (строка {nearest_line}): {position} с diff_hunk")
            
            if not position_found:
                for pos in sorted(valid_positions):
                    diff_hunk = position_hunk_mapping.get(pos)
                    if diff_hunk:
                        position = pos
                        position_found = True
                        print(f"Используем первую валидную позицию {position} для строки {start_line} с diff_hunk")
                        break
            
            if position_found and position is not None and diff_hunk:
                review_comments.append({
                    "path": file_path,
                    "position": position,
                    "body": comment_body,
                    "diff_hunk": diff_hunk
                })
                placed_comments += 1
                file_comments_added += 1
                print(f"✅ Успешно определена позиция {position} с diff_hunk для строки {start_line}")
            else:
                print(f"❌ Не удалось определить валидную позицию для строки {start_line} в файле {file_path}, добавлен комментарий к файлу")
                file_level_comments.append(f"**Комментарий к строке {start_line}**: {comment_body}")
        
        if file_level_comments:
            if file_comments_added == 0:
                first_position = file_first_positions.get(file_path, 1)
                first_hunk = file_diff_hunks.get(file_path)
                
                comment_data = {
                    "path": file_path,
                    "position": first_position,
                    "body": "# Комментарии к файлу\n\n" + "\n\n".join(file_level_comments)
                }
                
                if first_hunk:
                    comment_data["diff_hunk"] = first_hunk
                
                review_comments.append(comment_data)
                placed_comments += 1
            else:
                for comment in review_comments:
                    if comment["path"] == file_path:
                        comment["body"] = comment["body"] + "\n\n# Дополнительные комментарии\n\n" + "\n\n".join(file_level_comments)
                        break
    
    print(f"Всего комментариев: {total_comments}")
    print(f"Размещено комментариев: {placed_comments}")
    
    if not review_comments:
        print("Нет комментариев для добавления")
        return False

    valid_review_comments = []
    for comment in review_comments:

        if "path" not in comment or "position" not in comment or comment["position"] is None:
            print(f"Пропускаем невалидный комментарий к файлу {comment.get('path', 'неизвестный')}: отсутствует позиция")
            continue
            
        if comment["path"] not in pr_files:
            print(f"Пропускаем невалидный комментарий к файлу {comment['path']}: файл не найден в PR")
            continue
            
        if "diff_hunk" not in comment and comment["path"] in pr_files and pr_files[comment["path"]].get('patch'):
            hunk = get_diff_hunk_for_position(pr_files[comment["path"]]['parsed_patch'], comment["position"])
            if hunk:
                comment["diff_hunk"] = hunk
            else:
                print(f"Пропускаем комментарий к файлу {comment['path']}: не удалось найти diff_hunk")
                continue
                
        if "diff_hunk" in comment:
            del comment["diff_hunk"]
            
        valid_review_comments.append(comment)
        
    if not valid_review_comments:
        print("После валидации не осталось валидных комментариев, создаем общий комментарий")
        summary = "# Комментарии к коду\n\n"
        
        for file_path, comments in file_comments.items():
            summary += f"## Файл: {file_path}\n\n"
            for comment in comments:
                summary += f"**Строка {comment['start_line']}**: {comment['comment']}\n\n"
            summary += "---\n\n"
        
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
    
    review_data = {
        "commit_id": commit_id,
        "event": "COMMENT",
        "comments": valid_review_comments
    }
    
    print(f"Отправляем запрос на создание ревью с {len(valid_review_comments)} комментариями")
    for i, comment in enumerate(valid_review_comments):
        print(f"Комментарий {i+1}: файл={comment['path']}, позиция={comment['position']}")
    
    if len(valid_review_comments) > 3:
        print("Много комментариев, отправляем по одному для увеличения вероятности успеха")
        successful_comments = 0
        failed_comments = []
        
        for i, comment in enumerate(valid_review_comments):
            single_review_data = {
                "commit_id": commit_id,
                "event": "COMMENT",
                "comments": [comment]
            }
            
            single_response = requests.post(review_url, headers=headers, json=single_review_data)
            if single_response.status_code in [200, 201]:
                successful_comments += 1
                print(f"Успешно создан комментарий {i+1}/{len(valid_review_comments)}")
            else:
                failed_comments.append(comment)
                print(f"Ошибка при создании комментария {i+1}: {single_response.status_code} - {single_response.text}")
        
        if successful_comments > 0:
            print(f"Успешно создано {successful_comments} из {len(valid_review_comments)} комментариев")
            
            if failed_comments:
                print(f"Создаем общий комментарий для {len(failed_comments)} неудачных комментариев")
                summary = "# Дополнительные комментарии\n\n"
                
                for comment in failed_comments:
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
                    print(f"Ошибка при создании общего комментария для неудачных комментариев: {response.status_code} - {response.text}")
                else:
                    print("Общий комментарий для неудачных комментариев успешно создан.")
            
            return True
        else:
            print("Не удалось создать ни один комментарий, создаем общий комментарий")
            summary = "# Комментарии к коду\n\n"
            
            for comment in valid_review_comments:
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
    else:
        response = requests.post(review_url, headers=headers, json=review_data)
        if response.status_code not in [200, 201]:
            print(f"Ошибка при создании ревью: {response.status_code} - {response.text}")
            
            print("Пробуем создать общий комментарий к PR...")
            summary = "# Комментарии к коду\n\n"
            
            for comment in valid_review_comments:
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
        
        print(f"Ревью успешно создано с {len(valid_review_comments)} комментариями")
        return True

all_file_comments = {}
full_review = "## Ревью кода с помощью Mistral AI\n\n"

for file_path in files:
    if not os.path.exists(file_path):
        continue
        
    diff_result = subprocess.run(
        f"git diff {base_sha} {head_sha} -- {file_path}",
        shell=True,
        capture_output=True,
        text=True
    )
    diff = diff_result.stdout
    
    if not diff.strip():
        continue
    
    changes = parse_diff(diff)
    
    if not changes:
        continue
    
    prompt = f"""# Задача: Экспертное ревью кода для Pull Request

## Файл для анализа
{file_path}

## Изменения в формате diff
```diff
{diff}
```

## Твоя роль и цели
Ты - старший разработчик с большим опытом, проводящий детальное ревью кода. Твоя задача:
1. Тщательно проанализировать изменения кода
2. Выявить проблемы разного уровня критичности, от блокирующих до мелких стилистических
3. Предлагать конкретные, практические решения для каждой обнаруженной проблемы
4. Оценить общее качество изменений

## Инструкции

### Что анализировать:
1. Анализируй весь код файла для полного понимания контекста
2. Оставляй комментарии ТОЛЬКО к строкам, которые были изменены (отмечены + в diff)
3. Игнорируй удаленные строки (начинающиеся с '-')

### На что обращать внимание:
1. **Критические проблемы:**
   - Баги и логические ошибки
   - Потенциальные исключения и ошибки выполнения
   - Проблемы безопасности и уязвимости
   - Утечки ресурсов
   
2. **Производительность:**
   - Неэффективные алгоритмы (O(n²) вместо O(n))
   - Избыточные операции
   - Проблемы с использованием памяти
   - Неоптимальные запросы к БД
   
3. **Качество кода:**
   - Дублирование кода
   - Нарушение принципов SOLID, DRY, KISS
   - Нарушение стилевых соглашений
   - Сложность и читаемость
   
4. **Архитектура и дизайн:**
   - Соответствие архитектурным паттернам
   - Правильное разделение ответственности
   - Возможность переиспользования компонентов

### Формат комментариев:
Для каждой проблемы или предложения используй следующий формат:
```
СТРОКА X: [критичность] Краткое описание проблемы

Подробное описание, почему это проблема и как её исправить. Приведи конкретный пример исправления:

```python
# Исправленный пример кода
твой_код_исправления()
```
```

Где [критичность] - одно из:
- [КРИТИЧНО] - требует немедленного исправления
- [ВАЖНО] - серьезная проблема
- [УЛУЧШЕНИЕ] - предложение по улучшению
- [СТИЛЬ] - стилистическое замечание

Пример:
```
СТРОКА 42: [КРИТИЧНО] Возможно деление на ноль

Переменная `divisor` может быть равна нулю, что приведет к исключению. Добавь проверку:

```python
if divisor != 0:
    result = number / divisor
else:
    result = default_value
```
```

### Требования к формату:
1. Номер строки должен соответствовать итоговому файлу после изменений
2. Указывай только конкретное число без диапазонов (например, "СТРОКА 42:", а не "СТРОКИ 42-45:")
3. Каждый комментарий должен начинаться с новой строки с префикса "СТРОКА X:"
4. Пиши на РУССКОМ языке

### Итоговая оценка:
В конце добавь общую оценку качества изменений по шкале от 1 до 5:
- 5: отличный код, без замечаний
- 4: хороший код с незначительными замечаниями
- 3: удовлетворительный код, есть важные замечания
- 2: плохой код, требуются существенные улучшения
- 1: критически плохой код, требует полной переработки

Добавь 2-3 предложения с пояснением оценки и общими рекомендациями.
"""
    
    try:
        chat_response = client.chat(
            model="mistral-large-latest",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        review_text = chat_response.choices[0].message.content
        
        line_comments = parse_line_comments(review_text)
        if line_comments:
            all_file_comments[file_path] = line_comments
        
        full_review += f"### Ревью для файла: `{file_path}`\n\n{review_text}\n\n---\n\n"
    except Exception as e:
        print(f"Ошибка при анализе {file_path}: {e}")
        full_review += f"### Ошибка при анализе файла `{file_path}`\n\n---\n\n"

with open("review.txt", "w", encoding="utf-8") as f:
    f.write(full_review)

if all_file_comments:
    commit_id = get_commit_id()
    create_review_with_comments(all_file_comments, commit_id)
else:
    print("Не найдено комментариев к строкам кода") 
