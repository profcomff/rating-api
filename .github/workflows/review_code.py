import os
import sys
import json
import requests
import subprocess
from mistralai.client import MistralClient

# Инициализация Mistral AI клиента
client = MistralClient(api_key=os.environ.get("MISTRAL_API_KEY"))

# Получаем информацию о PR
pr_number = os.environ.get("PR_NUMBER")
repository = os.environ.get("GITHUB_REPOSITORY")

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

full_review = "## Ревью кода с помощью Mistral AI\n\n"

for file_path in files:
    if not os.path.exists(file_path):
        continue
        
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        try:
            code_content = f.read()
        except Exception as e:
            print(f"Ошибка при чтении {file_path}: {e}")
            continue
    
    # Пропускаем пустые файлы
    if not code_content.strip():
        continue
    
    # Получаем diff для файла
    diff_result = subprocess.run(
        f"git diff {base_sha} {head_sha} -- {file_path}",
        shell=True,
        capture_output=True,
        text=True
    )
    diff = diff_result.stdout
    
    # Формируем промпт для Mistral AI
    prompt = f"""Проанализируй изменения в файле и предоставь краткое ревью кода.
    
    Имя файла: {file_path}
    
    Изменения (diff):
    ```
    {diff}
    ```
    
    Полный код файла:
    ```
    {code_content[:10000] if len(code_content) > 10000 else code_content}
    ```
    
    Пожалуйста, проанализируй код и найди:
    1. Потенциальные баги или проблемы
    2. Улучшения производительности
    3. Проблемы безопасности
    4. Улучшения читаемости и структуры кода
    
    Дай конкретные рекомендации. Если изменения хорошие, также отметь это.
    """
    
    # Запрос к Mistral AI
    try:
        chat_response = client.chat(
            model="mistral-small",  # Можно использовать mistral-medium или mistral-small для более быстрого анализа
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        review_text = chat_response.choices[0].message.content
        
        # Добавляем ревью в общий отчет
        full_review += f"### Ревью для файла: `{file_path}`\n\n{review_text}\n\n---\n\n"
    except Exception as e:
        print(f"Ошибка при анализе {file_path}: {e}")
        full_review += f"### Ошибка при анализе файла `{file_path}`\n\n---\n\n"

# Сохраняем полный обзор в файл
with open("review.txt", "w", encoding="utf-8") as f:
    f.write(full_review) 
