# Decisões Técnicas

Este documento justifica as principais escolhas técnicas do projeto.

## 1. Dataset: IBM HR Analytics

**Escolha**: IBM HR Analytics Employee Attrition Dataset (1.470 linhas, 35 features).

**Por quê**: dataset público mais utilizado para problemas de attrition, com mix de features numéricas, ordinais e categóricas. Tamanho adequado para demonstrar o pipeline sem necessidade de infraestrutura pesada.

## 2. Banco de Dados: SQLite + DuckDB

**Escolha**: SQLite para CRUD transacional, DuckDB para queries analíticas.

**Por quê**: SQLite simplifica o setup (sem servidor), enquanto DuckDB oferece performance 100-1000x superior para aggregações e batch processing via Parquet.

**Produção**: recomendamos PostgreSQL com asyncpg para concorrência real com centenas de milhares de registros.

## 3. Modelos: 4 algoritmos individuais com Optuna

**Escolha**: LogisticRegression, RandomForest, XGBoost, LightGBM.

**Por quê**:
- **LogReg**: baseline interpretável, coeficientes diretos
- **RF**: robusto a outliers, feature importance nativa
- **XGBoost/LightGBM**: estado da arte para dados tabulares

**Optuna** (busca bayesiana) foi escolhido sobre grid search por convergir mais rápido e encontrar melhores hiperparâmetros com menos trials.

> **Nota sobre ensembles**: pra um dataset de 1.470 linhas, técnicas de ensemble (weighted average, stacking) não trazem vantagem real — o ganho de ROC-AUC fica dentro do ruído estatístico da métrica (~±0.02) e introduz complexidade sem benefício. Com volume significativamente maior (>10k colaboradores), o trade-off muda e o ensemble passa a fazer sentido.

### Comparação dos 4 Modelos

**Resultados típicos** (5-fold CV + threshold via Youden's J — oscila ±0.005 entre runs por ruído de SMOTE/Optuna):

| Modelo | ROC-AUC | PR-AUC | F1 |
|--------|---------|--------|----|
| **XGBoost** ⭐ | ~0.833 | ~0.62 | ~0.57 |
| LogisticRegression | ~0.825 | ~0.60 | ~0.51 |
| LightGBM | ~0.819 | ~0.58 | ~0.57 |
| RandomForest | ~0.815 | ~0.56 | ~0.52 |

**Por que XGBoost vence consistentemente**:

1. **Maior ROC-AUC e PR-AUC** — PR-AUC é especialmente relevante em datasets desbalanceados (16% positivos)
2. **Explicabilidade direta via `shap.TreeExplainer`** — rápido (ms por colaborador) e retorna contribuições exatas por feature
3. **Simplicidade operacional** — um único modelo é mais fácil de servir, debugar e versionar
4. **Latência baixa** — predição de um colaborador em ~1-2ms, compatível com uso em tempo real

## 4. SMOTE por Fold (não global)

**Escolha**: SMOTE aplicado dentro de cada fold do cross-validation.

**Por quê**: aplicar SMOTE antes do split causa data leakage — amostras sintéticas do treino podem ser semelhantes às do validation, inflando as métricas artificialmente.

## 5. Threshold: Youden's J (não 0.5)

**Escolha**: threshold otimizado via Youden's J statistic (maximiza TPR - FPR).

**Por quê**: com 16% de attrition (desbalanceado), o threshold padrão de 0.5 gera muitos falsos negativos. Youden's J encontra o ponto que melhor equilibra sensibilidade e especificidade.

## 6. SHAP para Explicabilidade

**Escolha**: SHAP (TreeExplainer para modelos de árvore).

**Por quê**: SHAP é o método mais robusto de explicabilidade — tem base teórica sólida (Shapley values), funciona para qualquer modelo, e permite explicação global e individual.

## 7. LangChain para Agente

**Escolha**: LangChain com create_react_agent.

**Por quê**: framework maduro com ReAct nativo, tools como decorators, memória de conversação e integração com Gemini. 

## 8. Batch LLM

**Escolha**: async + semaphore + multi-item prompts.

**Por quê**: enviar 1 colaborador por request desperdiça tokens repetindo o system prompt. Multi-item batching (10 colaboradores/request) economiza ~90% de tokens de instrução, e concorrência async (10 requests simultâneos) maximiza throughput.

## 9. Guardrails em 3 Camadas

**Escolha**: input validation + system prompt restritivo + output validation.

**Por quê**: um LLM sem guardrails pode ser manipulado para responder qualquer coisa. As 3 camadas garantem que:
- Perguntas fora do domínio são rejeitadas antes de consumir tokens
- O system prompt reforça o escopo permitido
- Respostas fora do escopo são interceptadas antes de chegar ao usuário

## 10. MLflow para Experiment Tracking

**Escolha**: MLflow com SQLite backend local.

**Por quê**: registra automaticamente parâmetros, métricas e artefatos de cada run. Permite comparação visual de modelos e reprodutibilidade completa do treino.

## 11. PSI para Drift Monitoring

**Escolha**: PSI (Population Stability Index) por feature.

**Por quê**: PSI é o método padrão da indústria para detectar drift em features numéricas. Thresholds bem definidos (<0.1 OK, 0.1-0.2 atenção, >0.2 retreinar) facilitam automação de alertas.

## 12. Observabilidade Persistida

**Escolha**: métricas de latência, tokens e custos em SQLite com dashboard dedicado.

**Por quê**: em produção, saber quanto o sistema custa (tokens LLM) e quanto demora (latência de inferência) é essencial para sustentabilidade. Buffer em memória + flush periódico minimiza impacto na performance.

## 13. Docker Multi-Stage

**Escolha**: Dockerfile com builder e runtime stages.

**Por quê**: a stage de build instala dependências (grande), e a runtime copia apenas o necessário resultando em uma imagem final ~3x menor que single-stage.

## 14. CI/CD com GitHub Actions

**Escolha**: pipeline de 3 etapas (lint → test → docker build).

**Por quê**: garante que todo PR passa por lint (ruff), testes com cobertura (pytest), e que a imagem Docker builda sem erro antes de merge.

## 15. Structured Logging (JSON opcional)

**Escolha**: `logging_config.py` com `JsonFormatter` ativado via env var `LOG_FORMAT=json`.

**Por quê**: em produção, logs precisam ser parseáveis por coletores (Splunk Datadog, CloudWatch, Loki, ELK). Usar stdlib `logging.Formatter` em vez de `structlog` mantém zero deps externas e é compatível com qualquer infra. Em dev, o modo `text` é mais legível no terminal.

## 16. Tracing de GenAI no MLflow

**Escolha**: `mlflow.langchain.autolog()` + `mlflow.gemini.autolog()` configurados no startup da API.

**Por quê**: observabilidade de LLM é diferente de logs normais — precisa de spans aninhados (agent.invoke → tool call → Gemini API) com input/output, tokens e latência por nível. O MLflow 3.x já traz autolog nativo pros dois casos, então não precisamos instrumentar manualmente. Experimento dedicado (`hr-genai-traces`) separa traces operacionais dos experimentos de treino.

## 17. CORS e Whitelist de Campos

**Escolha**: CORS restrito via env var (`CORS_ALLOWED_ORIGINS`) e whitelist explícita de campos em `PUT /employees/{id}` (`ALLOWED_UPDATE_FIELDS`).

**Por quê**: `allow_origins=["*"]` é aceitável em dev mas inaceitável em produção — qualquer origem pode fazer requests com credenciais. Similarmente, `setattr(employee, field, value)` sem whitelist permite que um client alterado ou malicioso modifique campos sensíveis (`id`, `is_active`, `created_at`). Whitelist explícita é defesa em profundidade, mesmo já tendo Pydantic validando.

## 18. SQL Injection Hardening no Agente

**Escolha**: múltiplas camadas em `query_employees_analytics`:

1. Remoção de comentários SQL (`--`, `/* */`) antes do parsing
2. Bloqueio de **multi-statement** (apenas 1 query por chamada)
3. Whitelist de tabelas (`employees` + CTEs auto-detectadas)
4. Regex de bloqueio para DDL/DML (`\bINSERT\b`, `\bUPDATE\b`, `\bDROP\b`, `\bATTACH\b`, `\bPRAGMA\b`...)
5. `LIMIT 500` automático se ausente

**Por quê**: uma tool de agente que aceita SQL arbitrária é vetor de ataque evidente. O padrão simples `SELECT * FROM employees; DROP TABLE employees` passa por validação ingênua (regex em `startswith`). As camadas combinadas cobrem os vetores mais comuns sem limitar a expressividade para queries analíticas legítimas (CTEs, GROUP BY, JOINs entre aliases).

## 19. Dry-Run Endpoint para Simulação

**Escolha**: `POST /predict/simulate` com `{"employee_id": int, "overrides": dict}`.

**Por quê**: o Simulador precisa calcular risco com valores hipotéticos. O endpoint dry-run carrega o colaborador, aplica overrides apenas no DataFrame em memória e prediz — sem nunca tocar no banco.

## 20. Padronização de Erros (`api/errors.py`)

**Escolha**: `HRAnalyticsError` base + subclasses (`NotFoundError`, `ValidationError`, `ForbiddenError`, `ExternalServiceError`) e função `error_json()` para tools.

**Por quê**: rotas FastAPI precisam lançar `HTTPException(status_code=...)` enquanto tools do agente precisam retornar dicts serializáveis. Ter uma única classe de erro que converte pra ambos formatos mantém consistência sem forçar cada chamador a conhecer os detalhes.

## 21. Canary Deployment de Modelos

**Decisão**: não implementar canary no escopo atual.

**Por quê**: o sistema opera com um único modelo em produção. Canary é uma infraestrutura de comparação entre versões concorrentes; sem uma segunda versão para comparar, a implementação seria inerte.

### Como seria implementado

Quando houver um modelo candidato para substituir o atual em produção, o canary seria montado com os seguintes componentes:

| Componente | Responsabilidade |
|------------|------------------|
| MLflow Model Registry com aliases | Substituir o symlink `latest` por aliases `@production` e `@staging` |
| Routing layer no `ModelService` | Decidir qual modelo atende cada request com base em `CANARY_TRAFFIC_PCT` e hash do `employee_id` |
| Logging com `model_version` | Cada predição registra a versão que a atendeu, para análise offline |
| Guardrails de rollback | Auto-desativação do canary ao violar thresholds de erro, latência ou PSI |
| Feature flag por env var | Ativação e ajuste do percentual sem redeploy |

### Roteamento

Split determinístico por `employee_id`:

```
hash(employee_id) % 100 < CANARY_TRAFFIC_PCT  →  modelo @staging
caso contrário                                 →  modelo @production
```

A consistência por hash garante que o mesmo colaborador seja sempre atendido pelo mesmo modelo durante o experimento, evitando oscilação de scores entre requests.

### Thresholds de rollback automático

| Métrica | Limite |
|---------|--------|
| Taxa de erro HTTP 5xx no canary | > 1% |
| Latência p95 do canary vs baseline | > 50% maior |
| PSI da distribuição de scores (canary vs baseline) | > 0.2 |

### Métricas de comparação

- **Distribuição de scores** — KS test, mediana e percentis
- **Latência** — p50, p95, p99
- **PSI das features recebidas** — sanity check de que canary e baseline recebem tráfego equivalente
- **Erro real** quando os labels de attrition chegarem — critério final para promoção ou descarte
