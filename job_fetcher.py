"""
job_fetcher.py
Busca publicaciones de trabajo en LinkedIn usando JobSpy, combinando dos capas
de términos (uno general + varios específicos del diferencial del candidato),
con soporte de modalidad (local/remoto/ambos) y filtro de antigüedad.
"""

import math

import pandas as pd
from jobspy import scrape_jobs


def _variantes_is_remote(mode: str) -> list[bool]:
    """Valores de is_remote según el modo."""
    if mode == "local":
        return [False]
    elif mode == "remote":
        return [True]
    else:  # "both"
        return [False, True]


def _buscar(search_term: str, location: str, is_remote: bool,
            results_wanted: int, hours_old: int) -> pd.DataFrame:
    """Búsqueda puntual en LinkedIn vía JobSpy."""
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
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        etiqueta = "remoto" if is_remote else "local"
        print(f"Aviso: falló la búsqueda de '{search_term}' ({etiqueta}): {e}")
        return pd.DataFrame()


def _buscar_termino_por_capas(search_term: str, location: str, mode: str,
                                hours_old: int, presupuesto: int) -> pd.DataFrame:
    """Busca un término repartiendo resultados entre variantes de modalidad."""
    variantes = _variantes_is_remote(mode)
    por_variante = max(math.ceil(presupuesto / len(variantes)), 3)

    dfs = []
    for is_remote in variantes:
        etiqueta = "remoto" if is_remote else f"cerca de {location}"
        print(f"Buscando '{search_term}' en LinkedIn ({etiqueta})...")
        dfs.append(_buscar(search_term, location, is_remote, por_variante, hours_old))

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


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

    dfs = [
        _buscar_termino_por_capas(
            search_term_general, location, mode, hours_old, presupuesto_general
        )
    ]
    for termino in search_terms_especificos:
        dfs.append(
            _buscar_termino_por_capas(
                termino, location, mode, hours_old, presupuesto_por_especifico
            )
        )

    df = pd.concat(dfs, ignore_index=True)

    if df.empty:
        return []

    # Deduplicar por URL del posteo (o por título+empresa si no hay URL)
    columna_dedupe = "job_url" if "job_url" in df.columns else None
    if columna_dedupe:
        df = df.drop_duplicates(subset=[columna_dedupe])
    else:
        df = df.drop_duplicates(subset=["title", "company"])

    df = df.head(num_jobs)

    publicaciones = []
    for _, fila in df.iterrows():
        publicaciones.append({
            "title": fila.get("title", "Sin título"),
            "company": fila.get("company", "Empresa no especificada"),
            "location": fila.get("location", "No especificada"),
            "job_url": fila.get("job_url", ""),
            "description": fila.get("description", "") or "",
            "date_posted": str(fila.get("date_posted", "")),
            "job_type": fila.get("job_type", ""),
            "is_remote": fila.get("is_remote", ""),
        })

    print(f"Se encontraron {len(publicaciones)} publicaciones (tras deduplicar).")
    return publicaciones