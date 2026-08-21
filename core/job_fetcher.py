"""
job_fetcher.py
Busca publicaciones de trabajo en LinkedIn usando JobSpy, combinando dos capas
de términos (uno general + varios específicos del diferencial del candidato),
con soporte de modalidad (local/remoto/ambos) y filtro de antigüedad.

Nota de diseño: convertimos cada resultado de JobSpy a una lista de dicts
(Python plano) INMEDIATAMENTE después de recibirlo, en vez de acumular varios
DataFrames y usar pd.concat/drop_duplicates sobre ellos. JobSpy puede devolver
columnas con dtypes especiales (ej. categóricos) que no siempre coinciden
entre una búsqueda y otra, y mezclarlos con pandas puede disparar errores de
bajo nivel (bug conocido de pandas/numpy al concatenar dtypes incompatibles).
Trabajando con dicts evitamos esa zona frágil por completo.
"""

import math

from jobspy import scrape_jobs


def _variantes_is_remote(mode: str) -> list[bool]:
    """Determina qué valores de is_remote usar según el modo elegido."""
    if mode == "local":
        return [False]
    elif mode == "remote":
        return [True]
    else:  # "both"
        return [False, True]


def _df_a_dicts(df) -> list[dict]:
    """Convierte un DataFrame de JobSpy a una lista de dicts planos, de forma segura."""
    if df is None or df.empty:
        return []
    # to_dict("records") ya devuelve tipos nativos de Python para la mayoría de
    # los casos; forzamos str en los campos que consumimos para blindarnos de
    # cualquier dtype exótico (categorical, Timestamp, etc.) que JobSpy devuelva.
    registros = df.to_dict(orient="records")
    return registros


def _buscar(search_term: str, location: str, is_remote: bool,
            results_wanted: int, hours_old: int) -> list[dict]:
    """Hace una búsqueda puntual en LinkedIn vía JobSpy y devuelve dicts planos."""
    try:
        df = scrape_jobs(
            site_name=["linkedin"],
            search_term=search_term,
            location=location,
            is_remote=is_remote,
            results_wanted=results_wanted,
            hours_old=hours_old,
            description_format="markdown",
            linkedin_fetch_description=True,  # trae la descripción completa de cada puesto
        )
        return _df_a_dicts(df)
    except Exception as e:
        etiqueta = "remoto" if is_remote else "local"
        print(f"⚠️  Aviso: falló la búsqueda de '{search_term}' ({etiqueta}): {e}")
        return []


def _buscar_termino_por_capas(search_term: str, location: str, mode: str,
                                hours_old: int, presupuesto: int) -> list[dict]:
    """
    Busca un término repartiendo el presupuesto de resultados entre las
    variantes de modalidad que correspondan según `mode`.
    """
    variantes = _variantes_is_remote(mode)
    por_variante = max(math.ceil(presupuesto / len(variantes)), 3)

    resultados = []
    for is_remote in variantes:
        etiqueta = "remoto" if is_remote else f"cerca de {location}"
        print(f"🔎 Buscando '{search_term}' en LinkedIn ({etiqueta})...")
        resultados.extend(_buscar(search_term, location, is_remote, por_variante, hours_old))

    return resultados


def buscar_publicaciones(
    search_term_general: str,
    search_terms_especificos: list[str],
    location: str,
    num_jobs: int = 12,
    mode: str = "both",
    hours_old: int = 336,
) -> list[dict]:
    """
    Busca publicaciones en LinkedIn combinando una capa general (volumen) y
    capas específicas (diferencial del candidato), deduplica y devuelve una
    lista de diccionarios lista para analizar.

    Args:
        search_term_general: término amplio del rol (ej: "Data Scientist").
        search_terms_especificos: términos del diferencial (ej: ["Conformal Prediction"]).
        location: ciudad/país para la búsqueda local.
        num_jobs: cantidad total aproximada de publicaciones a traer.
        mode: "both" (local+remoto), "local", o "remote".
        hours_old: antigüedad máxima de las publicaciones, en horas (default 336 = 2 semanas).

    Returns:
        Lista de dicts con los campos relevantes de cada publicación.
    """
    # Reparto 50/50 entre capa general y capas específicas.
    presupuesto_general = max(num_jobs // 2, 3)
    presupuesto_especificos_total = max(num_jobs - presupuesto_general, 3)
    n_especificos = max(len(search_terms_especificos), 1)
    presupuesto_por_especifico = max(presupuesto_especificos_total // n_especificos, 3)

    todos_los_registros = _buscar_termino_por_capas(
        search_term_general, location, mode, hours_old, presupuesto_general
    )
    for termino in search_terms_especificos:
        todos_los_registros.extend(
            _buscar_termino_por_capas(
                termino, location, mode, hours_old, presupuesto_por_especifico
            )
        )

    if not todos_los_registros:
        return []

    # Deduplicar por URL del posteo (o por título+empresa si no hay URL), en
    # Python plano, preservando el primer resultado encontrado para cada clave.
    vistos = set()
    publicaciones = []
    for registro in todos_los_registros:
        job_url = registro.get("job_url") or ""
        clave = job_url if job_url else (registro.get("title", ""), registro.get("company", ""))

        if clave in vistos:
            continue
        vistos.add(clave)

        publicaciones.append({
            "title": registro.get("title") or "Sin título",
            "company": registro.get("company") or "Empresa no especificada",
            "location": registro.get("location") or "No especificada",
            "job_url": job_url,
            "description": registro.get("description") or "",
            "date_posted": str(registro.get("date_posted") or ""),
            "job_type": str(registro.get("job_type") or ""),
            "is_remote": registro.get("is_remote", ""),
        })

        if len(publicaciones) >= num_jobs:
            break

    print(f"✅ Se encontraron {len(publicaciones)} publicaciones (tras deduplicar).")
    return publicaciones