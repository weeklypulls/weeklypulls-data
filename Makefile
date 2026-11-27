.PHONY: install lock upgrade test format format-check run

install:
	pip install -r requirements.txt -r requirements-testing.txt

# Re-pin requirements*.txt from the *.in files after editing them.
LOCK = uv pip compile -q --python-version 3.13 --universal --custom-compile-command "make lock"
lock:
	$(LOCK) requirements.in -o requirements.txt
	$(LOCK) requirements-testing.in -o requirements-testing.txt

# Move every pin to the newest version the *.in ranges allow.
upgrade:
	$(LOCK) --upgrade requirements.in -o requirements.txt
	$(LOCK) --upgrade requirements-testing.in -o requirements-testing.txt

test:
	pytest

format:
	black .

format-check:
	black --check .

run:
	python manage.py runserver
