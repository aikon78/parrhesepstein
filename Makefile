VENV := .venv
PYTHON := $(VENV)/bin/python
DEPS_STAMP := $(VENV)/.deps-installed
SYSTEM_PYTHON := /usr/local/bin/python3

.PHONY: build run build-run mongo-check clean


$(PYTHON):
	rm -rf $(VENV)
	$(SYSTEM_PYTHON) -m venv $(VENV)

$(DEPS_STAMP): requirements.txt | $(PYTHON)
	@if ! $(PYTHON) -m ensurepip --upgrade >/dev/null 2>&1; then \
		echo "⚠️  Virtualenv non valida, ricreazione in corso..."; \
		rm -rf $(VENV); \
		$(SYSTEM_PYTHON) -m venv $(VENV); \
		$(PYTHON) -m ensurepip --upgrade; \
	fi
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	touch $(DEPS_STAMP)

build: $(DEPS_STAMP)

run: build
	$(PYTHON) app/run.py

build-run: run

mongo-check:
	@if [ ! -x "$(PYTHON)" ]; then \
		echo "❌ .venv non trovata. Esegui prima: make build"; \
		exit 1; \
	fi
	@MONGO_URI=$${MONGO_URI:-mongodb://localhost:27017/} $(PYTHON) -c "import os; from pymongo import MongoClient; uri=os.getenv('MONGO_URI'); MongoClient(uri, serverSelectionTimeoutMS=3000).admin.command('ping'); print(f'✅ MongoDB raggiungibile su {uri}')"

clean:
	rm -rf $(VENV)
