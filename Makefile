.PHONY: install setup seed train serve app test lint docker-build docker-up clean

# Detectar Python e pip do venv automaticamente
PYTHON := .venv/bin/python
PIP := .venv/bin/pip
PYTHONPATH := src

# Instalação completa: venv + dependências + .env + popular banco
# Após esse comando, basta rodar `make serve` e `make app` em terminais separados.
install:
	@echo "▶ Criando venv com Python 3.11 (sobrescreve se já existir)..."
	uv venv --python 3.11 --allow-existing
	@echo "▶ Instalando dependências (modo editável + dev)..."
	. .venv/bin/activate && uv pip install -e ".[dev]"
	@if [ ! -f .env ]; then \
		echo "▶ Criando .env a partir do .env.example..."; \
		cp .env.example .env; \
	fi
	@if grep -qE '^GEMINI_API_KEY=(sua_chave_aqui)?[[:space:]]*$$' .env; then \
		echo ""; \
		echo "🔑 Configure sua GEMINI_API_KEY (https://aistudio.google.com/app/apikey)"; \
		printf "   Cole a chave agora (ou Enter para pular e editar manualmente): "; \
		read -r gemini_key; \
		if [ -n "$$gemini_key" ]; then \
			sed -i.bak "s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=$$gemini_key|" .env && rm -f .env.bak; \
			echo "   ✅ GEMINI_API_KEY salva em .env"; \
		else \
			echo "   ⚠️  Pulado — edite .env antes de usar a LLM"; \
		fi; \
	fi
	@echo ""
	@echo "▶ Populando banco SQLite com o dataset versionado..."
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m scripts.seed_db
	@echo ""
	@echo "✅ Setup completo! Próximos passos:"
	@echo "   1. Em um terminal:  make serve    (API + MLflow UI)"
	@echo "   2. Em outro:        make app      (Streamlit)"
	@echo "   → App:    http://localhost:8501"
	@echo "   → API:    http://localhost:8000/docs"
	@echo "   → MLflow: http://localhost:5000"

# Popular banco de dados com CSV (útil para reset ou reseed)
seed:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m scripts.seed_db

# Treinar modelos com Optuna + MLflow
train:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m scripts.train

# Rodar predição para todos os colaboradores
predict-all:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m scripts.predict_all

# Subir API FastAPI + MLflow UI (background). Ctrl+C encerra ambos via trap.
# MLflow UI precisa apontar pro mesmo backend (sqlite) que a API usa, senão
# não enxerga os experimentos nem os traces gerados pelo autolog.
serve:
	@echo "▶ Iniciando MLflow UI em http://localhost:5000 (backend sqlite)"
	@PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mlflow ui --port 5000 \
		--backend-store-uri sqlite:///mlflow.db > /tmp/mlflow_ui.log 2>&1 & \
	MLFLOW_PID=$$!; \
	trap "echo ''; echo '🛑 Encerrando MLflow (PID '$$MLFLOW_PID')'; kill $$MLFLOW_PID 2>/dev/null || true" EXIT INT TERM; \
	echo "▶ Iniciando API FastAPI em http://localhost:8000"; \
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m uvicorn hr_analytics.api.main:app --host 0.0.0.0 --port 8000 --reload

# Subir Streamlit
app:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m streamlit run app/People_Analytics.py --server.port 8501

# Rodar testes com cobertura
test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m pytest --cov=src/hr_analytics --cov-report=term-missing --cov-report=html -v

# Linting e type checking
lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m ruff format --check src/ tests/

# Formatar código
format:
	$(PYTHON) -m ruff check --fix src/ tests/
	$(PYTHON) -m ruff format src/ tests/

# MLflow UI (standalone) — mesmo backend que a API grava
mlflow-ui:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mlflow ui --port 5000 --backend-store-uri sqlite:///mlflow.db

# Docker
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Limpar artefatos
clean:
	rm -rf __pycache__ .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
