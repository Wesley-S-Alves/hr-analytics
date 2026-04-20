# 👥 HR Analytics — People Analytics com IA

Sistema de People Analytics que prediz risco de saída de colaboradores, gera insights automatizados com LLM e permite interação via agente conversacional.

## Funcionalidades

- **Machine Learning**: 4 modelos individuais (LogReg, RF, XGBoost, LightGBM) otimizados via Optuna — treino com MLflow, explicabilidade via SHAP
- **LLM (Gemini)**: insights estruturados em batch async (padrão semaphore + multi-item prompts) com output JSON
- **Agente conversacional**: LangChain ReAct com 5 tools, guardrails 3-camadas, memória de conversação e auto-geração de gráficos
- **Frontend Streamlit (9 páginas)**:
  1. **Dashboard** — KPIs, filtros, drivers de risco, ranking paginado
  2. **Colaborador** — perfil individual, gauge, SHAP, análise IA detalhada, export PDF
  3. **Chat** — agente conversacional com histórico e gráficos automáticos
  4. **Cadastro** — criação manual/IA/batch por CSV + listagem com filtros
  5. **Relatório** — PDF consolidado de retenção (top N, manual ou por departamento)
  6. **Comparador** — 2-3 colaboradores lado a lado com fatores principais
  7. **Simulador** — "E se?" com 12 atributos ajustáveis via dry-run
  8. **Monitoramento** — PSI por feature, saúde do modelo, link para MLflow UI
  9. **Observabilidade** — latência, tokens, custos por tipo de chamada
- **API FastAPI**: 13 endpoints REST (predict, simulate, CRUD, agente, insights, monitoring)
- **Observabilidade**: PSI para drift + métricas operacionais (latência, tokens, custos) + tracing automático de GenAI no MLflow (LangChain + Gemini autolog)
- **Qualidade**: 93 testes, cobertura ≥80%, logging estruturado em JSON, CI via GitHub Actions

## Setup Rápido

### Pré-requisitos

- Python 3.11+
- Chave da API Google Gemini

### Instalação e execução

```bash
# 1. Clonar e entrar no diretório
git clone <repo-url>
cd hr-analytics

# 2. Setup completo (venv + deps + .env + pede GEMINI_API_KEY + popula SQLite)
make install

# 3. Subir API + MLflow UI (terminal 1 — encerra com Ctrl+C)
make serve

# 4. Subir Streamlit (terminal 2)
make app
```

> O `make install` cria o `.env` automaticamente e pede sua `GEMINI_API_KEY` ([como obter](https://aistudio.google.com/app/apikey)). Pode colar a chave ou dar Enter para pular e editar depois.

URLs:
- App: http://localhost:8501
- API: http://localhost:8000/docs (Swagger)
- MLflow UI: http://localhost:5000

O modelo pré-treinado (`artifacts/models/xgboost_20260419_202829/`) já vem versionado — o sistema funciona sem precisar retreinar. Para treinar do zero (gera novos artefatos + experimentos no MLflow), rode `make train`.

### Dados

O dataset [IBM HR Analytics Employee Attrition](https://www.kaggle.com/datasets/pavansubhasht/ibm-hr-analytics-attrition-dataset) (1.470 linhas, 35 features, ~223 KB) já está versionado em `data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv`.

### Docker

```bash
docker compose up
# API: http://localhost:8000/docs
# Streamlit: http://localhost:8501
```

### Testes

```bash
make test     # pytest com cobertura
make lint     # ruff check + format
```

## Variáveis de Ambiente

Principais chaves do `.env` (lista completa em `.env.example`):

| Variável | Descrição | Default |
|----------|-----------|---------|
| `GEMINI_API_KEY` | Chave do Google Gemini | — |
| `MLFLOW_TRACKING_URI` | Backend do MLflow | `sqlite:///mlflow.db` |
| `MLFLOW_GENAI_EXPERIMENT` | Experimento MLflow para traces de GenAI | `hr-genai-traces` |
| `MLFLOW_UI_URL` | URL da UI do MLflow (mostrada no Monitoramento) | `http://localhost:5000` |
| `DATABASE_URL` | Connection string do banco | `sqlite:///data/hr_analytics.db` |
| `CORS_ALLOWED_ORIGINS` | Origens permitidas (separado por vírgula) | `http://localhost:8501,http://127.0.0.1:8501` |
| `LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR | `INFO` |
| `LOG_FORMAT` | `text` ou `json` | `text` |
| `DRIFT_WEBHOOK_URL` | Webhook Slack/Discord para alerta de drift | — |
| `OPTUNA_N_TRIALS` | Trials por modelo no treino | `50` |
| `CV_FOLDS` | Folds do cross-validation | `5` |

## Estrutura do Projeto

```
src/hr_analytics/
├── config.py              # Configurações (Pydantic Settings)
├── logging_config.py      # Logging estruturado (JSON ou texto)
├── tracing.py             # MLflow autolog GenAI (LangChain + Gemini)
├── data/                  # Loader, preprocessing, feature engineering, database
├── models/                # Trainer (Optuna+MLflow), registry, explainer (SHAP), ORM
├── monitoring/            # PSI/drift, observabilidade, alertas webhook
├── inference/             # Predictor singleton, schemas Pydantic, utils compartilhados
├── llm/                   # Client Gemini, batch async, prompts, schemas
├── agent/                 # Orchestrator LangChain, 5 tools, guardrails, memory
└── api/                   # FastAPI app, errors, routes (13 endpoints)

app/                       # Streamlit (9 páginas)
├── People_Analytics.py    # Home com cards de módulos
├── pages/                 # 1_Dashboard … 9_Observabilidade
└── components/            # translations.py, pdf_report.py, sidebar, charts

scripts/                   # CLI: seed, train, predict_all
notebooks/01_eda.ipynb     # Análise exploratória
docs/                      # Arquitetura, decisões técnicas, liderança
tests/                     # pytest — 93 testes (API, agent, LLM, ML)
```

## Documentação

- [Arquitetura da Solução](docs/arquitetura.md)
- [Decisões Técnicas](docs/decisoes_tecnicas.md)
- [Liderança Técnica e Mentoria](docs/lideranca.md)

## Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| ML | scikit-learn, XGBoost, LightGBM, Optuna, MLflow, SHAP, imbalanced-learn |
| LLM | Google Gemini (async batch + autolog MLflow) |
| Agente | LangChain ReAct + guardrails 3-camadas |
| API | FastAPI + Pydantic v2 |
| DB | SQLite + DuckDB |
| Frontend | Streamlit + Plotly |
| Observabilidade | MLflow traces (LangChain + Gemini) + structured logging JSON |
| CI/CD | GitHub Actions (lint → type check → test → docker) |
| Container | Docker multi-stage |
| PDF | ReportLab |

## Nota sobre Banco de Dados

SQLite foi escolhido por simplicidade no contexto do desafio. Em produção com centenas de milhares de funcionários, a recomendação é migrar para **PostgreSQL** (concorrência, connection pooling, índices avançados). A camada de dados já usa SQLAlchemy 2.0, tornando a migração uma mudança de connection string.
