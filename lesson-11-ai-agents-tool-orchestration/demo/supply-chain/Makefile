.PHONY: install demo clean

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo ""
	@echo "Готово. Додай OPENROUTER_API_KEY у .env і запусти 'make demo'."

demo:
	$(VENV)/bin/streamlit run app.py

clean:
	rm -rf $(VENV) __pycache__ */__pycache__ */*/__pycache__
