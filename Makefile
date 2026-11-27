.PHONY: install test format format-check run

install:
	pip install -r requirements.txt -r requirements-testing.txt

test:
	pytest

format:
	black .

format-check:
	black --check .

run:
	python manage.py runserver
