run:
	. ./venv/bin/activate && uvicorn --reload --log-config logging_dev.conf rating_api.routes.base:app

configure: venv
	. ./venv/bin/activate && pip install -r requirements.dev.txt -r requirements.txt

venv:
	python3 -m venv venv

format:
	autoflake -r --in-place --remove-all-unused-imports ./rating_api
	isort ./rating_api
	black ./rating_api

db:
	docker run -d -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust --name db-rating_api postgres:15

migrate:
	alembic upgrade head
