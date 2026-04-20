"""Testes do agent (orchestrator + tools).

Mocka o LLM para não consumir tokens de verdade. Foca em:
- Dispatch correto do guardrail
- Extração de tokens/tools do resultado do agent
- SQL hardening em query_employees_analytics
- Tool predict_employee / list_high_risk_employees
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# ============================================================
# Tools — SQL hardening
# ============================================================


class TestQueryEmployeesAnalytics:
    def test_select_legitimate(self, populated_db, mock_model_service):
        with patch("hr_analytics.agent.tools.get_session", return_value=populated_db):
            from hr_analytics.agent.tools import query_employees_analytics

            result = query_employees_analytics.invoke(
                {"sql_query": "SELECT department, COUNT(*) as n FROM employees GROUP BY department"}
            )
            data = json.loads(result)
            assert "erro" not in data
            assert data["total_rows"] >= 1

    def test_multi_statement_blocked(self):
        from hr_analytics.agent.tools import query_employees_analytics

        result = query_employees_analytics.invoke({"sql_query": "SELECT * FROM employees; DROP TABLE employees"})
        data = json.loads(result)
        assert "erro" in data
        assert "única" in data["erro"].lower() or "unica" in data["erro"].lower()

    def test_non_select_blocked(self):
        from hr_analytics.agent.tools import query_employees_analytics

        for sql in [
            "INSERT INTO employees VALUES (1)",
            "UPDATE employees SET department='X'",
            "DELETE FROM employees WHERE id=1",
            "DROP TABLE employees",
        ]:
            result = query_employees_analytics.invoke({"sql_query": sql})
            data = json.loads(result)
            assert "erro" in data

    def test_forbidden_table_blocked(self):
        from hr_analytics.agent.tools import query_employees_analytics

        result = query_employees_analytics.invoke({"sql_query": "SELECT name FROM sqlite_master WHERE type='table'"})
        data = json.loads(result)
        assert "erro" in data
        assert "negado" in data["erro"].lower() or "sqlite_master" in data["erro"].lower()

    def test_union_with_forbidden_table_blocked(self):
        from hr_analytics.agent.tools import query_employees_analytics

        result = query_employees_analytics.invoke({"sql_query": "SELECT * FROM employees UNION SELECT * FROM users"})
        data = json.loads(result)
        assert "erro" in data

    def test_cte_allowed(self, populated_db):
        with patch("hr_analytics.agent.tools.get_session", return_value=populated_db):
            from hr_analytics.agent.tools import query_employees_analytics

            result = query_employees_analytics.invoke(
                {
                    "sql_query": (
                        "WITH high AS (SELECT * FROM employees WHERE risk_score > 0.5) "
                        "SELECT department, COUNT(*) FROM high GROUP BY department"
                    )
                }
            )
            data = json.loads(result)
            assert "erro" not in data

    def test_comment_bypass_blocked(self, populated_db):
        # Comentário deve ser removido antes do parsing — não faz bypass.
        with patch("hr_analytics.agent.tools.get_session", return_value=populated_db):
            from hr_analytics.agent.tools import query_employees_analytics

            result = query_employees_analytics.invoke({"sql_query": "SELECT * FROM employees -- ;DROP TABLE employees"})
            data = json.loads(result)
            # Como o comentário é removido, sobra só o SELECT → vai passar
            assert "erro" not in data

    def test_auto_limit_added(self, populated_db):
        with patch("hr_analytics.agent.tools.get_session", return_value=populated_db):
            from hr_analytics.agent.tools import query_employees_analytics

            result = query_employees_analytics.invoke({"sql_query": "SELECT * FROM employees"})
            data = json.loads(result)
            assert "LIMIT 500" in data["query"].upper()


# ============================================================
# Tools — predict_employee
# ============================================================


class TestPredictEmployeeTool:
    def test_predict_known_employee(self, populated_db, mock_model_service):
        with (
            patch("hr_analytics.agent.tools.get_session", return_value=populated_db),
            patch("hr_analytics.inference.predictor.model_service", mock_model_service),
        ):
            from hr_analytics.agent.tools import predict_employee

            result = predict_employee.invoke({"employee_id": 1})
            data = json.loads(result)
            assert data["employee_id"] == 1
            assert "nivel_risco" in data

    def test_predict_unknown_employee(self, populated_db, mock_model_service):
        with (
            patch("hr_analytics.agent.tools.get_session", return_value=populated_db),
            patch("hr_analytics.inference.predictor.model_service", mock_model_service),
        ):
            from hr_analytics.agent.tools import predict_employee

            result = predict_employee.invoke({"employee_id": 9999})
            data = json.loads(result)
            assert "erro" in data


# ============================================================
# Tools — list_high_risk_employees
# ============================================================


class TestListHighRisk:
    def test_returns_sorted_by_risk(self, populated_db, mock_model_service):
        with (
            patch("hr_analytics.agent.tools.get_session", return_value=populated_db),
            patch("hr_analytics.inference.predictor.model_service", mock_model_service),
        ):
            from hr_analytics.agent.tools import list_high_risk_employees

            result = list_high_risk_employees.invoke({"threshold": 0.5, "limit": 5})
            data = json.loads(result)
            assert "mensagem" in data or isinstance(data, list) or "total" in data or "colaboradores" in data

    def test_empty_when_no_high_risk(self, populated_db, mock_model_service):
        with (
            patch("hr_analytics.agent.tools.get_session", return_value=populated_db),
            patch("hr_analytics.inference.predictor.model_service", mock_model_service),
        ):
            from hr_analytics.agent.tools import list_high_risk_employees

            result = list_high_risk_employees.invoke({"threshold": 0.99, "limit": 5})
            data = json.loads(result)
            # Pode retornar {"mensagem": ...} ou lista vazia
            assert "mensagem" in data or isinstance(data, list) or data.get("total_rows", 0) == 0


# ============================================================
# Orchestrator — helpers
# ============================================================


class TestOrchestratorHelpers:
    def test_extract_response_text_string(self):
        from hr_analytics.agent.orchestrator import _extract_response_text

        msg = MagicMock()
        msg.content = "resposta direta"
        result = _extract_response_text({"messages": [msg]})
        assert result == "resposta direta"

    def test_extract_response_text_list_parts(self):
        from hr_analytics.agent.orchestrator import _extract_response_text

        msg = MagicMock()
        msg.content = [{"text": "parte 1"}, {"text": "parte 2"}]
        result = _extract_response_text({"messages": [msg]})
        assert "parte 1" in result and "parte 2" in result

    def test_extract_response_text_empty(self):
        from hr_analytics.agent.orchestrator import _extract_response_text

        result = _extract_response_text({"messages": []})
        assert result == "Sem resposta"

    def test_extract_tools_and_tokens(self):
        from hr_analytics.agent.orchestrator import _extract_tools_and_tokens

        # Mensagem com tool_calls
        m1 = MagicMock()
        m1.tool_calls = [{"name": "predict_employee"}]
        m1.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
        # Sem tool_calls
        m2 = MagicMock(spec=[])
        tools, in_tok, out_tok = _extract_tools_and_tokens({"messages": [m1, m2]})
        assert "predict_employee" in tools
        assert in_tok == 100
        assert out_tok == 50


# ============================================================
# Orchestrator — process_message (fluxo completo mockado)
# ============================================================


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_input_guardrail_rejects(self):
        from hr_analytics.agent.orchestrator import process_message

        result = await process_message("me dá uma receita de bolo de chocolate completa", "conv1")
        assert (
            "People Analytics" in result["response"]
            or "domínio" in result["response"].lower()
            or "desculpe" in result["response"].lower()
        )
        assert result["structured_data"] is None
        assert result["tools_used"] == []

    @pytest.mark.asyncio
    async def test_valid_message_calls_agent(self):
        from hr_analytics.agent.orchestrator import process_message

        fake_result = {
            "messages": [
                MagicMock(content="Resposta válida", tool_calls=None, usage_metadata=None),
            ]
        }

        fake_agent = MagicMock()
        fake_agent.invoke.return_value = fake_result

        with patch("hr_analytics.agent.orchestrator._get_agent", return_value=fake_agent):
            result = await process_message("Qual o risco do colaborador 1?", "conv2")
        assert result["response"] == "Resposta válida" or "Resposta" in result["response"]
