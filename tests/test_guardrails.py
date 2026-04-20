"""Testes dos guardrails do agente."""

from hr_analytics.agent.guardrails import validate_input, validate_output


class TestInputGuardrail:
    """Testes de validação de entrada."""

    def test_valid_risk_question(self):
        is_valid, _ = validate_input("Qual colaborador tem maior risco?")
        assert is_valid

    def test_valid_attrition_question(self):
        is_valid, _ = validate_input("Por que esse funcionário está em risco de saída?")
        assert is_valid

    def test_valid_model_question(self):
        is_valid, _ = validate_input("Qual a métrica ROC AUC do modelo?")
        assert is_valid

    def test_blocked_recipe_request(self):
        is_valid, msg = validate_input("Me dá uma receita de bolo de chocolate")
        assert not is_valid
        assert "People Analytics" in msg

    def test_blocked_joke_request(self):
        is_valid, msg = validate_input("Conte uma piada engraçada")
        assert not is_valid

    def test_blocked_code_request(self):
        is_valid, msg = validate_input("Escreva um código em Python para ordenar uma lista")
        assert not is_valid

    def test_short_messages_accepted(self):
        """Mensagens curtas são aceitas (podem ser IDs ou saudações)."""
        is_valid, _ = validate_input("oi")
        assert is_valid

    def test_off_topic_no_keywords(self):
        is_valid, msg = validate_input("A capital da França fica na Europa e tem uma torre famosa de metal")
        assert not is_valid


class TestOutputGuardrail:
    """Testes de validação de saída."""

    def test_valid_analytics_response(self):
        response = "O colaborador 42 tem risco alto de saída. Os principais fatores são..."
        is_valid, text = validate_output(response)
        assert is_valid
        assert text == response

    def test_blocks_recipe_in_output(self):
        response = "Aqui está: Ingredientes: 2 xícaras de farinha, 1 xícara de açúcar..."
        is_valid, text = validate_output(response)
        assert not is_valid
        assert "People Analytics" in text

    def test_blocks_code_in_output(self):
        response = "Claro! def main():\n    print('hello')"
        is_valid, text = validate_output(response)
        assert not is_valid
