"""Componentes de sidebar e filtros compartilhados."""

import streamlit as st

API_BASE_URL = "http://localhost:8000/api/v1"


def get_api_url(path: str) -> str:
    """Retorna a URL completa da API."""
    return f"{API_BASE_URL}{path}"
