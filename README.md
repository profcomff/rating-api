# Рейтинг преподавателей

Хранение и работа с рейтингом преподавателей и отзывами на них.

[<img src="https://cdn.profcomff.com/easycode/easycode.svg" width="200"></img>](https://easycode.profcomff.com/templates/docker-fastapi/workspace?mode=manual&param.Repository+URL=https://github.com/profcomff/rating-api.git&param.Working+directory=rating-api)

## Запуск

1. Перейдите в папку проекта

2. Создайте виртуальное окружение командой и активируйте его:
    ```console
    foo@bar:~$ python3 -m venv venv
    foo@bar:~$ source ./venv/bin/activate  # На MacOS и Linux
    foo@bar:~$ venv\Scripts\activate  # На Windows
    ```

3. Установите библиотеки
    ```console
    foo@bar:~$ pip install -r requirements.txt
    ```
4. Запускайте приложение!
    ```console
    foo@bar:~$ python -m rating_api
    ```

## ENV-file description
-  – Данные для подключения к БД`DB_DSN=postgresql://postgres@localhost:5432/postgres`
