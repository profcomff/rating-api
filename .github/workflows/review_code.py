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

# Получаем общую информацию о проекте для контекста
project_context = ""
try:
    print("Собираем информацию о проекте...")
    
    # Создаем функцию для анализа зависимостей между файлами
    def analyze_imports(file_path):
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Ищем импорты Python
                if file_path.endswith('.py'):
                    import_lines = [line.strip() for line in content.split('\n') 
                                   if line.strip().startswith(('import ', 'from ')) 
                                   and not line.strip().startswith('#')]
                    imports = import_lines
                    
                # Можно добавить анализ импортов для других языков
        except Exception:
            pass
        return imports
    
    # Поиск всех файлов проекта для контекста
    find_files_cmd = subprocess.run(
        "find . -type f -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.go' -o -name '*.java' | grep -v '__pycache__' | grep -v '.git/' | sort",
        shell=True,
        capture_output=True,
        text=True
    )
    project_files = find_files_cmd.stdout.strip().split("\n")
    
    # Создаем краткое описание структуры проекта
    project_context = "## Структура проекта\n\n"
    
    # Группируем файлы по директориям для лучшего понимания структуры
    dirs = {}
    for file_path in project_files:
        if not file_path:
            continue
        parts = file_path.split('/')
        if len(parts) > 1:
            dir_path = '/'.join(parts[:-1])
            if dir_path not in dirs:
                dirs[dir_path] = []
            dirs[dir_path].append(parts[-1])
    
    # Формируем структуру для промпта
    project_context += "### Директории и файлы\n\n"
    for dir_path, files in dirs.items():
        project_context += f"📁 **{dir_path}/**\n"
        for file in files[:10]:  # Увеличиваем количество файлов для каждой директории
            project_context += f"  • {file}\n"
        if len(files) > 10:
            project_context += f"  • ... и ещё {len(files) - 10} файлов\n"
        project_context += "\n"
    
    # Анализируем зависимости между файлами
    dependencies = {}
    for file_path in project_files:
        if file_path.endswith('.py'):
            imports = analyze_imports(file_path)
            if imports:
                dependencies[file_path] = imports
    
    # Определяем ключевые файлы по количеству импортов (наиболее используемые модули)
    imported_counts = {}
    for file_path, imports in dependencies.items():
        for imp in imports:
            # Попытка извлечь имя модуля из импорта
            if 'from ' in imp:
                module = imp.split('from ')[1].split(' import')[0].strip()
                # Конвертируем относительный импорт в возможный путь файла
                if module.startswith('.'):
                    file_dir = os.path.dirname(file_path)
                    rel_parts = module.count('.')
                    if rel_parts > 0:
                        module = os.path.join(os.path.dirname(file_dir), module[rel_parts:])
                    else:
                        module = os.path.join(file_dir, module[1:])
                
                if module:
                    imported_counts[module] = imported_counts.get(module, 0) + 1
            elif 'import ' in imp:
                module = imp.split('import ')[1].split(' as')[0].strip().split(',')[0].strip()
                imported_counts[module] = imported_counts.get(module, 0) + 1
    
    # Добавляем информацию о зависимостях
    project_context += "### Ключевые модули и их зависимости\n\n"
    
    # Сортируем по количеству импортов
    top_modules = sorted([(k, v) for k, v in imported_counts.items() if v > 1], 
                          key=lambda x: x[1], reverse=True)[:10]
    
    for module, count in top_modules:
        if '.' in module:  # Пропускаем стандартные библиотеки
            project_context += f"- **{module}** - импортируется {count} раз\n"
    
    project_context += "\n"
    
    # Добавляем важные файлы целиком для контекста
    important_files_context = "## Ключевые файлы проекта\n\n"
    important_files_found = False
    
    # Определяем какие файлы важны на основе имени и размера
    important_patterns = [
        'models.py', 'schemas.py', 'interfaces.py', 'types.py', 'config.py', 
        'utils.py', 'constants.py', 'settings.py', 'base.py', 'app.py', 'main.py'
    ]
    
    # Сначала проверяем наиболее важные файлы
    for pattern in important_patterns:
        matching_files = [f for f in project_files if f.endswith(pattern)]
        for important_file in matching_files[:2]:  # Не более 2 файлов каждого типа
            if os.path.exists(important_file) and os.path.getsize(important_file) < 15000:  # Увеличиваем лимит до 15KB
                try:
                    with open(important_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        important_files_context += f"### 📄 **{important_file}**\n```python\n{content}\n```\n\n"
                        important_files_found = True
                except Exception:
                    pass
    
    # Дополнительно находим часто импортируемые файлы, которые не попали в основной список
    for module, count in top_modules[:5]:  # Берем топ-5 импортируемых модулей
        # Попытаемся найти соответствующий файл
        potential_files = [f for f in project_files if module.replace('.', '/') in f]
        for potential_file in potential_files:
            if (os.path.exists(potential_file) and 
                os.path.getsize(potential_file) < 10000 and  # До 10KB
                potential_file not in important_files_context):  # Не дублируем
                try:
                    with open(potential_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        important_files_context += f"### 📄 **{potential_file}** (часто импортируемый модуль)\n```python\n{content}\n```\n\n"
                        important_files_found = True
                except Exception:
                    pass
    
    if important_files_found:
        project_context += important_files_context
    
    # Анализируем архитектуру проекта
    project_context += "## Архитектурные особенности\n\n"
    
    # Определяем паттерны архитектуры на основе структуры директорий и файлов
    architecture_patterns = []
    
    # Проверка на MVC/MVT структуру
    has_models = any('models.py' in f or '/models/' in f for f in project_files)
    has_views = any('views.py' in f or '/views/' in f for f in project_files)
    has_controllers = any('controllers.py' in f or '/controllers/' in f for f in project_files)
    has_templates = any('/templates/' in f for f in project_files)
    
    if has_models and has_views and has_controllers:
        architecture_patterns.append("MVC (Model-View-Controller)")
    elif has_models and has_views and has_templates:
        architecture_patterns.append("MVT (Model-View-Template)")
        
    # Проверка на наличие сервисного слоя
    has_services = any('services.py' in f or '/services/' in f for f in project_files)
    if has_services:
        architecture_patterns.append("Сервисный слой")
        
    # Проверка на наличие репозиториев
    has_repositories = any('repository.py' in f or 'repositories.py' in f or '/repositories/' in f for f in project_files)
    if has_repositories:
        architecture_patterns.append("Репозиторный паттерн")
        
    # Проверка на наличие фабрик
    has_factories = any('factory.py' in f or 'factories.py' in f or '/factories/' in f for f in project_files)
    if has_factories:
        architecture_patterns.append("Фабричный метод")
    
    # Добавляем найденные паттерны в контекст
    if architecture_patterns:
        project_context += "Обнаруженные архитектурные паттерны:\n"
        for pattern in architecture_patterns:
            project_context += f"- {pattern}\n"
    else:
        project_context += "Чёткие архитектурные паттерны не обнаружены. Возможно, используется специфическая или смешанная архитектура.\n"
    
    project_context += "\nДанная информация призвана помочь в понимании общей структуры проекта и взаимосвязей между компонентами.\n"
    
except Exception as e:
    print(f"Ошибка при создании контекста проекта: {e}")
    project_context = "Не удалось получить подробную информацию о структуре проекта."

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

## Контекст проекта
{project_context}

## Твоя роль и цели
Ты - старший разработчик с большим опытом, проводящий детальное ревью кода. Твоя задача:
1. Тщательно проанализировать изменения кода, понимая их в контексте всего проекта
2. Выявить проблемы разного уровня критичности, от блокирующих до мелких стилистических
3. Предлагать конкретные, практические решения для каждой обнаруженной проблемы
4. Оценить, как изменения вписываются в архитектуру и парадигмы существующего кода
5. Сделать полезные рекомендации для улучшения кода с учётом best practices современной разработки

## Инструкции

### Методология анализа:
1. Сначала изучи весь код файла и связи с другими частями проекта для полного понимания контекста
2. Обрати особое внимание на внесенные изменения (строки с '+' в diff)
3. При анализе используй знание о структуре проекта, существующих паттернах и стиле кодирования
4. Учитывай возможные взаимодействия с другими компонентами проекта
5. Проверь код как с точки зрения функциональности, так и с точки зрения поддерживаемости
6. Рассмотри, как изменения могут повлиять на производительность, безопасность, масштабируемость

### Что необходимо проверить (в порядке важности):

1. **Критические проблемы:**
   - Логические ошибки, приводящие к неправильному поведению
   - Необработанные исключения и граничные случаи
   - Потенциальные уязвимости безопасности (инъекции, XSS, утечки данных)
   - Race conditions и проблемы многопоточности
   - Утечки ресурсов (memory leaks, незакрытые соединения)
   
2. **Производительность и оптимизация:**
   - Неэффективные алгоритмы (O(n²) вместо O(n))
   - Избыточные вычисления и проблемы с кэшированием
   - Неоптимальные запросы к БД (N+1 проблема)
   - Блокировки UI/нарушения отзывчивости интерфейса
   - Проблемы с памятью и избыточное использование ресурсов
   
3. **Качество кода и best practices:**
   - Нарушение принципов SOLID, DRY, KISS
   - Дублирование кода и copy-paste
   - Чрезмерная сложность и запутанность
   - Плохие абстракции и интерфейсы
   - Отсутствие или недостаточное покрытие тестами
   
4. **Архитектура и дизайн:**
   - Несоответствие существующим архитектурным паттернам проекта
   - Нарушение слоистой архитектуры и разделения ответственности
   - Несоответствие принципам domain-driven design (если применимо)
   - Нарушение инкапсуляции и абстракции
   - Жесткие зависимости вместо слабых связей
   
5. **Согласованность и конвенции:**
   - Несоответствие принятым в проекте стилевым соглашениям
   - Несоответствие соглашениям об именовании
   - Отсутствие или недостаточность документации
   - Противоречия с остальными частями кодовой базы
   - Проблемы с форматированием и читаемостью

### Формат комментариев:
Для каждой проблемы или предложения СТРОГО используй следующий формат:
```
СТРОКА X: [критичность] Краткое описание проблемы

Подробное описание проблемы и её возможных последствий. Объяснение, почему это является проблемой в контексте проекта.

Рекомендуемое решение:
```python
# Пример исправленного кода
исправленный_код()
```

При необходимости укажи связи с другими частями проекта, на которые это может повлиять.
```

Где [критичность] - одно из:
- [КРИТИЧНО] - блокирующая проблема, требующая немедленного исправления
- [ВАЖНО] - серьезная проблема, которая может привести к багам
- [СРЕДНЕ] - проблема, ухудшающая качество кода
- [УЛУЧШЕНИЕ] - предложение по улучшению кода
- [СТИЛЬ] - стилистическое замечание
- [АРХИТЕКТУРА] - проблема, связанная с архитектурой или дизайном

### Примеры различных типов комментариев:

1. **Пример критической проблемы:**
```
СТРОКА 42: [КРИТИЧНО] Потенциальный NullPointerException

Переменная `user` может быть null, если пользователь не найден, но проверка на null отсутствует перед обращением к свойству `user.id`. Это приведёт к краху приложения в production.

Рекомендуемое решение:
```python
if user is not None:
    user_id = user.id
    process_user(user_id)
else:
    log.error("Пользователь не найден")
    return None
```
```

2. **Пример проблемы с производительностью:**
```
СТРОКА 78: [ВАЖНО] Неэффективный алгоритм с O(n²) сложностью

Текущая реализация использует вложенные циклы для поиска дубликатов, что имеет квадратичную сложность. На больших наборах данных это создаст серьёзные проблемы с производительностью.

Рекомендуемое решение:
```python
# Используем множество для O(n) сложности
seen = set()
duplicates = []

for item in items:
    if item in seen:
        duplicates.append(item)
    else:
        seen.add(item)
```
Это улучшит производительность с O(n²) до O(n).
```

3. **Пример архитектурной проблемы:**
```
СТРОКА 103: [АРХИТЕКТУРА] Нарушение принципа единственной ответственности

Этот класс выполняет слишком много разных функций: обработку запросов, бизнес-логику и доступ к данным. В проекте в других модулях (например, в `services/user.py`) используется разделение на слои.

Рекомендуемое решение:
Разделить на отдельные классы по ответственности:
```python
class UserController:
    def __init__(self, user_service):
        self.user_service = user_service
    
    def handle_request(self, request):
        # Только обработка запросов
        
class UserService:
    def __init__(self, user_repository):
        self.user_repository = user_repository
    
    # Бизнес-логика
    
class UserRepository:
    # Доступ к данным
```
```

### Требования к формату:
1. Для КАЖДОГО комментария ОБЯЗАТЕЛЬНО указывай конкретный номер строки соответствующий итоговому файлу после изменений
2. Точно придерживайся формата "СТРОКА X:", где X - число без диапазонов
3. Каждый комментарий должен начинаться с новой строки и иметь префикс "СТРОКА X:"
4. Пиши на РУССКОМ языке
5. Когда ссылаешься на другие файлы проекта, указывай полный путь
6. Для каждой проблемы предлагай конкретное решение с примером кода
7. Формат строго должен соответствовать шаблону, иначе комментарии не будут правильно распознаны

### Итоговая оценка:
В конце обязательно добавь итоговую оценку и рекомендации в следующем формате:

---
## Итоговая оценка: X/5

Где X - оценка от 1 до 5:
- 5: Отличный код, без замечаний или с минимальными стилистическими замечаниями. Хорошо вписывается в общую архитектуру.
- 4: Хороший код с незначительными проблемами. В целом соответствует стандартам проекта.
- 3: Средний код с несколькими важными проблемами, требующими внимания.
- 2: Плохой код со значительными проблемами. Требует серьезной доработки.
- 1: Критически плохой код. Рекомендуется полная переработка.

Добавь 3-5 предложений с пояснением оценки, включая:
1. Основные сильные стороны изменений
2. Ключевые проблемы, требующие внимания
3. Как изменения вписываются в общую архитектуру проекта
4. Рекомендации по улучшению
"""
    
    # Запрос к Mistral AI
    try:
        chat_response = client.chat(
            model="mistral-large",
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
