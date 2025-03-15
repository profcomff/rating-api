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
        
        # Проверяем, есть ли patch
        if not patch:
            print(f"Отсутствует patch для файла {file_path}, добавляем комментарии в общий список")
            # Добавляем все комментарии в группу файловых комментариев
            file_level_comments = []
            for comment in comments:
                file_level_comments.append(f"**Комментарий к строке {comment['start_line']}**: {comment['comment']}")
            
            if file_level_comments:
                review_comments.append({
                    "path": file_path,
                    "position": 1,  # Используем первую позицию, если нет patch
                    "body": "\n\n".join(file_level_comments)
                })
                placed_comments += 1
            continue
        
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
        
        # Создаем различные карты для соответствия строк и позиций
        line_position_maps = {}
        
        # 1. Карта на основе git diff
        line_position_map_git = {}
        line_num = 0
        position = 0
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
                line_position_map_git[line_num] = position
            elif line.startswith(' '):
                line_num += 1
        
        line_position_maps['git'] = line_position_map_git
        
        # 2. Карта на основе GitHub API patch
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
        
        # 3. Создаем дополнительные карты для поиска по контексту
        # Карта содержимого строк
        line_content_map = {}
        if file_content:
            for i, line in enumerate(file_content):
                line_content_map[i+1] = line.strip()
        
        # Группируем комментарии по файлам, если не удается найти позицию
        file_level_comments = []
        file_comments_added = 0
        
        # Для валидации позиций перед отправкой
        valid_positions = set()
        for line in patch.split('\n'):
            if not line.startswith('-'):  # Все строки кроме удаленных
                valid_positions.add(position)
        
        # Добавляем новый алгоритм для определения позиции
        for comment in comments:
            start_line = comment['start_line']
            comment_body = comment['comment']
            position_found = False
            position = None
            
            # Проходим по всем картам в порядке точности
            for map_name, position_map in line_position_maps.items():
                if start_line in position_map:
                    position = position_map[start_line]
                    position_found = True
                    print(f"Найдена позиция для строки {start_line} в карте {map_name}: {position}")
                    break
            
            # Если не найдено прямое соответствие, пробуем поиск по контексту
            if not position_found and file_content and 0 < start_line <= len(file_content):
                # 1. Поиск по точному совпадению содержимого строки
                target_line = file_content[start_line - 1].rstrip()
                context_line = target_line.strip()
                
                if context_line:
                    # Ищем в diff
                    lines = full_diff.split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('+') and context_line in line.strip():
                            position = i + 1
                            position_found = True
                            print(f"Найдена позиция для строки {start_line} через точное совпадение контекста: {position}")
                            break
                
                # 2. Поиск по окружающему контексту (±2 строки)
                if not position_found:
                    context_lines = []
                    for offset in range(-2, 3):
                        idx = start_line - 1 + offset
                        if 0 <= idx < len(file_content):
                            context_lines.append(file_content[idx].strip())
                    
                    # Ищем последовательность строк в diff
                    if context_lines:
                        lines = full_diff.split('\n')
                        for i in range(len(lines) - len(context_lines) + 1):
                            match_count = 0
                            for j, context in enumerate(context_lines):
                                if context and i+j < len(lines) and context in lines[i+j].strip():
                                    match_count += 1
                            
                            # Если нашли достаточно совпадений
                            if match_count >= 2:  # Минимум 2 совпадения из 5 строк
                                # Позиция соответствует середине контекста
                                position = i + 2  # +2 для учета середины контекста
                                position_found = True
                                print(f"Найдена позиция для строки {start_line} через окружающий контекст: {position}")
                                break
                
                # 3. Поиск ближайшей измененной строки (для комментариев к строкам рядом с измененными)
                if not position_found:
                    nearest_line = None
                    min_distance = float('inf')
                    
                    for line_num in line_position_map_git.keys():
                        distance = abs(line_num - start_line)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_line = line_num
                    
                    if nearest_line and min_distance <= 3:  # Максимум 3 строки отличия
                        position = line_position_map_git[nearest_line]
                        position_found = True
                        print(f"Найдена позиция для строки {start_line} через ближайшую измененную строку {nearest_line}: {position}")
            
            # Проверяем, что позиция валидна
            if position_found:
                # Если позиция указывает на удаленную строку, корректируем
                if position > 0 and not position in valid_positions:
                    patch_lines = patch.split('\n')
                    # Ищем ближайшую неудаленную строку
                    for i in range(1, 5):  # Проверяем в радиусе 5 строк
                        if position + i in valid_positions:
                            position = position + i
                            break
                        elif position - i in valid_positions:
                            position = position - i
                            break
                    
                    print(f"Скорректирована позиция для строки {start_line}: {position}")
                
                # Проверяем на выход за пределы диапазона
                if position < 1:
                    position = 1  # Минимальная позиция
                
                review_comments.append({
                    "path": file_path,
                    "position": position,
                    "body": comment_body
                })
                placed_comments += 1
                file_comments_added += 1
            else:
                # Если не удалось найти позицию, добавляем комментарий к группе файловых комментариев
                print(f"Не удалось определить позицию для строки {start_line} в файле {file_path}, добавлен комментарий к файлу")
                file_level_comments.append(f"**Комментарий к строке {start_line}**: {comment_body}")
        
        # Добавляем сгруппированные комментарии к файлу на первую доступную позицию
        if file_level_comments:
            # Для файлов без успешных комментариев
            if file_comments_added == 0:
                first_position = file_first_positions.get(file_path, 1)
                review_comments.append({
                    "path": file_path,
                    "position": first_position,
                    "body": "# Комментарии к файлу\n\n" + "\n\n".join(file_level_comments)
                })
                placed_comments += 1
            else:
                # Если есть успешные комментарии, добавляем файловые комментарии к первому из них
                for comment in review_comments:
                    if comment["path"] == file_path:
                        comment["body"] = comment["body"] + "\n\n# Дополнительные комментарии\n\n" + "\n\n".join(file_level_comments)
                        break
    
    # Статистика
    print(f"Всего комментариев: {total_comments}")
    print(f"Размещено комментариев: {placed_comments}")
    
    if not review_comments:
        print("Нет комментариев для добавления")
        return False

    # Валидация и восстановление: проверяем каждый комментарий перед отправкой
    valid_review_comments = []
    for comment in review_comments:
        # Проверка обязательных полей
        if "path" not in comment or "position" not in comment or comment["position"] is None:
            print(f"Пропускаем невалидный комментарий к файлу {comment.get('path', 'неизвестный')}: отсутствует позиция")
            continue
            
        # Проверка на валидность пути файла
        if comment["path"] not in pr_files:
            print(f"Пропускаем невалидный комментарий к файлу {comment['path']}: файл не найден в PR")
            continue
            
        # Добавляем валидный комментарий
        valid_review_comments.append(comment)
        
    # Если после валидации комментариев не осталось, используем общий комментарий
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
    
    # Создаем ревью с валидными комментариями
    review_data = {
        "commit_id": commit_id,
        "event": "COMMENT",
        "comments": valid_review_comments
    }
    
    print(f"Отправляем запрос на создание ревью с {len(valid_review_comments)} комментариями")
    for i, comment in enumerate(valid_review_comments):
        print(f"Комментарий {i+1}: файл={comment['path']}, позиция={comment['position']}")
    
    # Увеличиваем вероятность успеха, отправляя комментарии по одному, если их много
    if len(valid_review_comments) > 5:
        print("Много комментариев, отправляем по одному для увеличения вероятности успеха")
        successful_comments = 0
        
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
                print(f"Ошибка при создании комментария {i+1}: {single_response.status_code} - {single_response.text}")
        
        if successful_comments > 0:
            print(f"Успешно создано {successful_comments} из {len(valid_review_comments)} комментариев")
            return True
        else:
            # Если не удалось создать ни один комментарий, создаем общий комментарий
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
        # Если комментариев не много, отправляем все сразу
        response = requests.post(review_url, headers=headers, json=review_data)
        if response.status_code not in [200, 201]:
            print(f"Ошибка при создании ревью: {response.status_code} - {response.text}")
            
            # Пробуем создать ревью без линейных комментариев
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
