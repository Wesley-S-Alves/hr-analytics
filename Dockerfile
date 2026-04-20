# === Stage 1: Builder ===
FROM python:3.11-slim AS builder

WORKDIR /app

# Instalar dependências de build
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copiar dependências e código do pacote (setuptools precisa de src/ para resolver)
COPY pyproject.toml .
COPY src/ src/

# Instalar no local default (/usr/local) — mais confiável que --prefix
# para resolver dependências transitivas (ex: packaging requerido por matplotlib)
RUN pip install --no-cache-dir .

# === Stage 2: Runtime ===
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copiar site-packages e binários instalados pelo pip
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copiar código fonte
COPY src/ src/
COPY app/ app/
COPY scripts/ scripts/
COPY .env.example .env

# Criar diretórios necessários
RUN mkdir -p data/raw data/processed artifacts/models artifacts/metrics artifacts/figures

# Variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Porta padrão (FastAPI)
EXPOSE 8000

# Comando padrão: FastAPI
CMD ["uvicorn", "hr_analytics.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
