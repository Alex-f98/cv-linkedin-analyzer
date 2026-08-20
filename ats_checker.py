"""
ats_checker.py
Simula el primer filtro automático (ATS) de forma determinística: busca coincidencias
LITERALES de keywords en el texto del CV, sin usar IA. Esto es intencional: un ATS
real es "ciego" al contexto, busca texto exacto (con algunas variantes obvias como
plural/singular y abreviaciones comunes), no entiende sinónimos conceptuales.
"""

import re
import unicodedata

# Equivalencias comunes y no ambiguas (abreviación <-> forma completa).
# Curada a mano a propósito: si esto lo decidiera una IA dejaría de ser determinístico.
_EQUIVALENCIAS = {
    "ml": "machine learning",
    "ia": "inteligencia artificial",
    "ai": "artificial intelligence",
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "db": "database",
    "sql": "structured query language",
    "oop": "object oriented programming",
    "poo": "programacion orientada a objetos",
    "ci/cd": "continuous integration continuous deployment",
    "llm": "large language model",
}
# Agrega también el mapeo inverso (forma completa -> abreviación).
_EQUIVALENCIAS.update({v: k for k, v in list(_EQUIVALENCIAS.items())})


def _normalizar(texto: str) -> str:
    """Minúsculas y sin acentos."""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _variantes(keyword_norm: str) -> set[str]:
    """Genera variantes de una keyword."""
    variantes = {keyword_norm}

    if keyword_norm in _EQUIVALENCIAS:
        variantes.add(_EQUIVALENCIAS[keyword_norm])

    # Plural/singular básico (español e inglés: sufijo "s").
    if keyword_norm.endswith("s") and len(keyword_norm) > 3:
        variantes.add(keyword_norm[:-1])
    else:
        variantes.add(keyword_norm + "s")

    return variantes


def analizar_riesgo_ats(cv_texto: str, keywords: list[str]) -> dict:
    """
    Compara las keywords "duras" de un posteo contra el texto crudo del CV,
    usando matching literal + variantes (no similitud semántica).

    Args:
        cv_texto: texto plano extraído del CV.
        keywords: lista de términos extraídos del posteo (analyzer.extraer_keywords_ats).

    Returns dict con:
        cobertura (0-100), nivel (str), encontradas (list), faltantes (list).
    """
    if not keywords:
        return {"cobertura": None, "nivel": "Sin datos", "encontradas": [], "faltantes": []}

    cv_norm = _normalizar(cv_texto)

    encontradas, faltantes = [], []
    for kw in keywords:
        kw_norm = _normalizar(kw)
        variantes = _variantes(kw_norm)
        if any(v in cv_norm for v in variantes if v):
            encontradas.append(kw)
        else:
            faltantes.append(kw)

    total = len(keywords)
    cobertura = round(len(encontradas) / total * 100, 1)

    if cobertura >= 80:
        nivel = "Bajo riesgo"
    elif cobertura >= 50:
        nivel = "Riesgo medio"
    else:
        nivel = "Alto riesgo"

    return {
        "cobertura": cobertura,
        "nivel": nivel,
        "encontradas": encontradas,
        "faltantes": faltantes,
    }