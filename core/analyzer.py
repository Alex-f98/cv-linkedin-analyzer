"""
analyzer.py
Usa la API de Groq para:
  1. Extraer un perfil resumido del CV (rol ideal, skills, seniority).
  2. Puntuar la compatibilidad de cada publicación contra el CV.
  3. Generar un resumen general agregado de toda la búsqueda.
"""

import json
import os
import re

from groq import Groq

MODEL = "openai/gpt-oss-120b"  # reemplazo oficial de llama-3.3-70b-versatile (deprecado 16 ago 2026)

# Override en memoria de la API key (lo usa la app de Streamlit para que cada
# usuario use la suya, sin depender de variables de entorno del servidor).
_api_key_override: str | None = None


def configurar_api_key(api_key: str | None) -> None:
    """
    Define una API key en memoria para esta sesión/proceso, con prioridad sobre
    la variable de entorno GROQ_API_KEY. Pensado para apps multiusuario (Streamlit)
    donde cada usuario pega su propia key en vez de compartir una del servidor.
    """
    global _api_key_override
    _api_key_override = api_key


def _cliente() -> Groq:
    api_key = _api_key_override or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No se encontró una API key de Groq. Creá un archivo .env con tu API key "
            "(mirá .env.example), exportala como variable de entorno, o configurala "
            "en memoria con analyzer.configurar_api_key(tu_key)."
        )
    return Groq(api_key=api_key)


def _extraer_json(texto: str) -> dict:
    """Limpia fences de markdown y parsea el JSON devuelto por el modelo."""
    limpio = re.sub(r"^```(json)?|```$", "", texto.strip(), flags=re.MULTILINE).strip()
    return json.loads(limpio)


def _llamar_groq(system_prompt: str, user_prompt: str) -> dict:
    cliente = _cliente()
    respuesta = cliente.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    contenido = respuesta.choices[0].message.content
    return _extraer_json(contenido)


def extraer_perfil(cv_texto: str) -> dict:
    """
    Analiza el CV y devuelve un perfil resumido para armar la búsqueda de empleo,
    con términos de búsqueda organizados en capas: uno general (amplio) y varios
    específicos (el diferencial del candidato).

    Returns dict con:
        rol_ideal, search_term_general, search_terms_especificos (list),
        seniority, skills_clave (list), resumen.
    """
    system_prompt = (
        "Sos un reclutador técnico experto. Analizás un CV y devolvés SOLO un JSON "
        "válido, sin texto adicional, con EXACTAMENTE estas 6 claves (ni una menos, "
        "ni una más, respetando estos nombres tal cual):\n"
        "- rol_ideal (string)\n"
        "- search_term_general (string)\n"
        "- search_terms_especificos (array de strings)\n"
        "- seniority (string)\n"
        "- skills_clave (array de strings)\n"
        "- resumen (string)\n\n"
        "Ejemplo de un JSON de respuesta válido y completo (con datos de otro CV, "
        "solo para que veas el formato exacto):\n"
        "{\n"
        '  "rol_ideal": "Data Scientist",\n'
        '  "search_term_general": "Data Scientist",\n'
        '  "search_terms_especificos": ["Conformal Prediction", "Signal Processing ML"],\n'
        '  "seniority": "Semi-Senior",\n'
        '  "skills_clave": ["Python", "PyTorch", "AWS", "Docker", "SQL", "Statistics"],\n'
        '  "resumen": "Ingeniero con foco en ML aplicado e investigación."\n'
        "}\n\n"
        "Reglas para completar los valores con el CV real que te paso:\n"
        "- search_term_general: título de rol MÁS AMPLIO y estándar posible "
        "(2-4 palabras), el que las empresas realmente usan, para maximizar volumen "
        "de resultados de búsqueda.\n"
        "- search_terms_especificos: 1-2 términos cortos (2-4 palabras cada uno) que "
        "representen el diferencial más distintivo del candidato (no genérico), que "
        "realmente aparecerían en publicaciones reales, no jerga inventada."
    )
    user_prompt = f"Este es el CV a analizar:\n\n{cv_texto}"
    perfil = _llamar_groq(system_prompt, user_prompt)
    return _validar_perfil(perfil)


def _validar_perfil(perfil: dict) -> dict:
    """
    Verifica que el perfil tenga las claves esperadas. Si el modelo se olvidó de
    alguna (puede pasar, no todos los modelos siguen el esquema al 100%), completa
    con un fallback razonable en vez de romper el programa, avisando por consola.
    """
    if "search_term_general" not in perfil:
        fallback = perfil.get("rol_ideal", "Data Scientist")
        print(f"⚠️  Aviso: Groq no devolvió 'search_term_general', uso '{fallback}' como fallback.")
        perfil["search_term_general"] = fallback

    if "search_terms_especificos" not in perfil:
        print("⚠️  Aviso: Groq no devolvió 'search_terms_especificos', se busca solo con el término general.")
        perfil["search_terms_especificos"] = []

    perfil.setdefault("rol_ideal", perfil["search_term_general"])
    perfil.setdefault("seniority", "No especificado")
    perfil.setdefault("skills_clave", [])
    perfil.setdefault("resumen", "")

    return perfil


def extraer_keywords_ats(publicacion: dict) -> list[str]:
    """
    Extrae del posteo SOLO los términos "duros" y literales que un ATS típico
    usaría como criterio de filtro automático: herramientas/tecnologías,
    certificaciones, título de grado requerido, años de experiencia, idiomas.
    No conceptos abstractos ni habilidades blandas.

    Returns lista de 8-15 keywords (strings cortos). Si el modelo falla en
    devolver el formato esperado, devuelve lista vacía (se avisa por consola).
    """
    system_prompt = (
        "Sos un motor de parsing de ATS (Applicant Tracking System). Tu única tarea "
        "es extraer, de una publicación de trabajo, los términos LITERALES y "
        "específicos que un sistema automático de filtrado buscaría como texto "
        "exacto en un CV: nombres de herramientas/tecnologías/lenguajes, "
        "certificaciones, título de grado requerido, años mínimos de experiencia, "
        "idiomas requeridos. NO incluyas habilidades blandas, adjetivos, ni "
        "conceptos generales sin nombre propio (ej: no incluyas 'buena comunicación' "
        "ni 'trabajo en equipo').\n\n"
        "Devolvés SOLO un JSON válido, sin texto adicional, con EXACTAMENTE esta "
        "única clave (ni una más, ni una menos, respetando el nombre tal cual):\n"
        "- keywords_ats (array de strings)\n\n"
        "Ejemplo de un JSON de respuesta válido (con datos de otro posteo, solo "
        "para que veas el formato exacto):\n"
        "{\n"
        '  "keywords_ats": ["Python", "AWS", "Docker", "Kubernetes", "SQL", '
        '"Ingeniería en Sistemas", "3 años de experiencia", "Inglés avanzado"]\n'
        "}"
    )
    user_prompt = (
        f"Puesto: {publicacion['title']}\n"
        f"Empresa: {publicacion['company']}\n"
        f"Descripción:\n{publicacion['description'][:6000]}"
    )
    resultado = _llamar_groq(system_prompt, user_prompt)
    keywords = resultado.get("keywords_ats", [])

    if not keywords:
        print(f"      ⚠️  Aviso: Groq no devolvió keywords ATS para '{publicacion['title']}', "
              f"se omite el chequeo de riesgo ATS para este posteo.")

    return keywords


def _calcular_recomendacion(puntaje: float) -> str:
    """Recomendación determinística en base al puntaje (mismo umbral siempre)."""
    if puntaje >= 75:
        return "Aplicar"
    elif puntaje >= 55:
        return "Aplicar con reservas"
    else:
        return "No priorizar"


def puntuar_publicacion(cv_texto: str, publicacion: dict) -> dict:
    """
    Compara una publicación de trabajo contra el CV y devuelve un análisis detallado.

    Returns dict con:
        puntaje (0-100), skills_match (list), skills_parcial (list),
        skills_faltantes (list), profile_fit (dict dimensión -> nivel),
        motivo (str), sugerencias (list), carta_presentacion (str),
        recomendacion (str, calculada por umbral de puntaje).
    """
    system_prompt = (
        "Sos un experto en reclutamiento técnico y en optimización de CVs. Comparás "
        "un CV contra una publicación de trabajo y devolvés SOLO un JSON válido, sin "
        "texto adicional, con este formato exacto:\n"
        "{\n"
        '  "puntaje": numero entre 0 y 100 indicando compatibilidad general,\n'
        '  "skills_match": ["requisitos del puesto que el candidato SÍ cumple '
        'claramente, según el CV"],\n'
        '  "skills_parcial": ["requisitos que el candidato cumple de forma parcial, '
        'indirecta, o con experiencia relacionada pero no exacta"],\n'
        '  "skills_faltantes": ["requisitos que el puesto pide y el candidato NO '
        'tiene ninguna evidencia de cumplir"],\n'
        '  "profile_fit": {\n'
        '    "<dimensión 1, ej: Data Science>": "Bajo | Medio | Medio-Alto | Alto",\n'
        '    "<dimensión 2, ej: MLOps>": "Bajo | Medio | Medio-Alto | Alto",\n'
        '    "...": "elegí entre 3 y 5 dimensiones relevantes para ESTE puesto '
        'específico (no siempre las mismas), como áreas de conocimiento o '
        'responsabilidad clave del rol"\n'
        "  },\n"
        '  "motivo": "1-2 oraciones explicando el puntaje otorgado y si los gaps '
        'son esenciales o secundarios para el rol",\n'
        '  "sugerencias": ["2-4 sugerencias concretas y accionables para mejorar '
        'el CV de cara a este puesto"],\n'
        '  "carta_presentacion": "carta de presentación breve (4-6 oraciones), '
        'profesional y personalizada para este puesto, en español"\n'
        "}"
    )
    user_prompt = (
        f"CV DEL CANDIDATO:\n{cv_texto}\n\n"
        f"---\n\n"
        f"PUBLICACIÓN DE TRABAJO:\n"
        f"Puesto: {publicacion['title']}\n"
        f"Empresa: {publicacion['company']}\n"
        f"Ubicación: {publicacion['location']}\n"
        f"Descripción:\n{publicacion['description'][:6000]}"
    )
    resultado = _llamar_groq(system_prompt, user_prompt)
    resultado["recomendacion"] = _calcular_recomendacion(resultado["puntaje"])
    return resultado


def generar_resumen_general(perfil_cv: dict, resultados: list[dict]) -> dict:
    """
    Genera un resumen ejecutivo agregado de toda la búsqueda, sin volver a mandar
    los CVs/descripciones completas (usa solo los datos ya extraídos por posteo,
    para ahorrar tokens).

    Returns dict con: encaje_general (str), puntaje_promedio (number),
    gaps_principales (list), skills_mas_pedidas (list), conclusion (str),
    conteo_recomendaciones (dict), ats_cobertura_promedio (number),
    ats_keywords_faltantes_frecuentes (list).
    """
    resumen_por_posteo = [
        {
            "titulo": r["publicacion"]["title"],
            "empresa": r["publicacion"]["company"],
            "puntaje": r["analisis"]["puntaje"],
            "recomendacion": r["analisis"]["recomendacion"],
            "skills_match": r["analisis"].get("skills_match", []),
            "skills_faltantes": r["analisis"].get("skills_faltantes", []),
        }
        for r in resultados
    ]
    puntaje_promedio = round(
        sum(r["analisis"]["puntaje"] for r in resultados) / len(resultados), 1
    ) if resultados else 0

    conteo_recomendaciones = {"Aplicar": 0, "Aplicar con reservas": 0, "No priorizar": 0}
    for r in resultados:
        conteo_recomendaciones[r["analisis"]["recomendacion"]] += 1

    # Agregado de riesgo ATS: se calcula en código (determinístico), no con Groq,
    # para que sea 100% consistente y no gaste tokens extra.
    coberturas_ats = [
        r["riesgo_ats"]["cobertura"]
        for r in resultados
        if r.get("riesgo_ats", {}).get("cobertura") is not None
    ]
    ats_cobertura_promedio = round(sum(coberturas_ats) / len(coberturas_ats), 1) if coberturas_ats else None

    conteo_faltantes = {}
    for r in resultados:
        for kw in r.get("riesgo_ats", {}).get("faltantes", []):
            clave = kw.strip().lower()
            conteo_faltantes[clave] = conteo_faltantes.get(clave, (0, kw))[0] + 1, kw
    ats_keywords_faltantes_frecuentes = [
        original for _, (_, original) in sorted(
            conteo_faltantes.items(), key=lambda item: item[1][0], reverse=True
        )
    ][:8]

    system_prompt = (
        "Sos un analista de carrera y reclutamiento. Recibís el perfil resumido de "
        "un candidato y los resultados de comparar su CV contra varias publicaciones "
        "de LinkedIn. Devolvés SOLO un JSON válido, sin texto adicional, con este "
        "formato exacto:\n"
        "{\n"
        '  "encaje_general": "Bajo | Parcial | Bueno | Muy bueno",\n'
        '  "gaps_principales": ["3-6 carencias o skills que se repiten como faltantes '
        'entre varios posteos, ordenadas por frecuencia/impacto"],\n'
        '  "skills_mas_pedidas": ["top 8-10 skills o requisitos que más aparecen '
        'pedidos en el conjunto de publicaciones analizadas"],\n'
        '  "conclusion": "3-4 oraciones con una conclusión honesta y accionable sobre '
        'qué tan bien encaja el perfil en esta búsqueda y qué priorizar para mejorar"\n'
        "}"
    )
    user_prompt = (
        f"PERFIL DEL CANDIDATO:\n{json.dumps(perfil_cv, ensure_ascii=False, indent=2)}\n\n"
        f"PUNTAJE PROMEDIO OBTENIDO: {puntaje_promedio}/100\n\n"
        f"RESULTADOS POR PUBLICACIÓN:\n"
        f"{json.dumps(resumen_por_posteo, ensure_ascii=False, indent=2)}"
    )
    resumen = _llamar_groq(system_prompt, user_prompt)
    resumen["puntaje_promedio"] = puntaje_promedio
    resumen["conteo_recomendaciones"] = conteo_recomendaciones
    resumen["ats_cobertura_promedio"] = ats_cobertura_promedio
    resumen["ats_keywords_faltantes_frecuentes"] = ats_keywords_faltantes_frecuentes
    return resumen