"""
streamlit_app.py
Interfaz web del LinkedIn Job Matcher: subís tu CV, ponés tu propia API key
de Groq, y la app busca publicaciones en LinkedIn, las puntúa, chequea riesgo
ATS, y muestra un reporte navegable con descarga en Markdown, HTML o PDF.
"""

import sys
from io import BytesIO
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core import analyzer, ats_checker, cv_reader, job_fetcher, report_builder

st.set_page_config(
    page_title="LinkedIn Job Matcher (con Groq)",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sistema de diseño: paleta, tipografía y componentes propios (sin el tema
# default de Streamlit ni iconografía decorativa).
# ---------------------------------------------------------------------------
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg: #FAFAFA;
  --surface: #FFFFFF;
  --border: #E5E5EA;
  --text: #18181B;
  --text-muted: #6B7280;
  --accent: #4F46E5;
  --accent-soft: #EEF2FF;
  --success: #059669;
  --success-soft: #ECFDF5;
  --warning: #D97706;
  --warning-soft: #FFFBEB;
  --danger: #DC2626;
  --danger-soft: #FEF2F2;
}

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }

.stApp { background: var(--bg); }

h1, h2, h3, h4 { font-family: 'Space Grotesk', 'Inter', sans-serif !important;
                 font-weight: 600 !important; letter-spacing: -0.02em; color: var(--text); }

/* Hero */
.job-hero { padding: 8px 0 28px 0; border-bottom: 1px solid var(--border); margin-bottom: 32px; }
.job-hero__eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
                      color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em;
                      margin-bottom: 8px; }
.job-hero__title { font-size: 2.1rem; margin: 0 0 8px 0; }
.job-hero__subtitle { color: var(--text-muted); font-size: 1rem; max-width: 640px; }

/* Tarjetas KPI */
.kpi-row { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
.kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
            padding: 18px 20px; flex: 1; min-width: 160px; }
.kpi-card__label { font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase;
                    letter-spacing: 0.05em; margin-bottom: 6px; }
.kpi-card__value { font-family: 'JetBrains Mono', monospace; font-size: 1.6rem;
                    font-weight: 500; color: var(--text); }

/* Medidor de señal (elemento de firma): barra segmentada de puntaje */
.signal-meter { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.signal-meter__track { display: flex; gap: 3px; flex: 1; max-width: 220px; }
.signal-meter__segment { height: 8px; flex: 1; border-radius: 2px; background: var(--border); }
.signal-meter__segment.is-filled.level-high { background: var(--success); }
.signal-meter__segment.is-filled.level-mid { background: var(--warning); }
.signal-meter__segment.is-filled.level-low { background: var(--danger); }
.signal-meter__value { font-family: 'JetBrains Mono', monospace; font-weight: 500;
                        font-size: 0.95rem; color: var(--text); min-width: 48px; }

/* Badges de estado (texto + color, sin iconos) */
.badge { display: inline-block; padding: 3px 10px; border-radius: 6px; font-size: 0.78rem;
         font-weight: 500; font-family: 'JetBrains Mono', monospace; }
.badge-success { background: var(--success-soft); color: var(--success); }
.badge-warning { background: var(--warning-soft); color: var(--warning); }
.badge-danger  { background: var(--danger-soft); color: var(--danger); }
.badge-neutral { background: var(--accent-soft); color: var(--accent); }

/* Tarjeta de publicación */
.job-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
            padding: 20px 22px; margin-bottom: 16px; }
.job-card__header { display: flex; justify-content: space-between; align-items: flex-start;
                     gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
.job-card__title { font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 1.05rem;
                    color: var(--text); margin: 0; }
.job-card__company { color: var(--text-muted); font-size: 0.9rem; margin-top: 2px; }
.job-card__section-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
                            color: var(--text-muted); margin-top: 14px; margin-bottom: 6px; }
.job-card__tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 0.8rem; padding: 2px 9px; border-radius: 5px; background: #F4F4F5;
       color: var(--text); border: 1px solid var(--border); }
.tag-missing { background: var(--danger-soft); color: var(--danger); border-color: transparent; }

/* Botones y widgets nativos de Streamlit, re-tematizados */
.stButton>button { background: var(--accent); color: white; border-radius: 8px; border: none;
                    font-weight: 500; padding: 0.5rem 1.2rem; }
.stButton>button:hover { background: #4338CA; color: white; }
section[data-testid="stSidebar"] { background: var(--surface); border-right: 1px solid var(--border); }
</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Componentes de UI reutilizables
# ---------------------------------------------------------------------------

def _nivel_de_puntaje(puntaje: float) -> str:
    if puntaje >= 75:
        return "high"
    elif puntaje >= 50:
        return "mid"
    return "low"


def signal_meter(puntaje: float, segmentos: int = 10) -> str:
    """Genera el HTML del medidor de señal (elemento de firma del diseño)."""
    nivel = _nivel_de_puntaje(puntaje)
    llenos = round((puntaje / 100) * segmentos)
    piezas = []
    for i in range(segmentos):
        clases = "signal-meter__segment"
        if i < llenos:
            clases += f" is-filled level-{nivel}"
        piezas.append(f'<div class="{clases}"></div>')
    return (
        '<div class="signal-meter">'
        f'<div class="signal-meter__track">{"".join(piezas)}</div>'
        f'<span class="signal-meter__value">{puntaje:.0f}/100</span>'
        '</div>'
    )


_BADGE_RECOMENDACION = {
    "Aplicar": "badge-success",
    "Aplicar con reservas": "badge-warning",
    "No priorizar": "badge-danger",
}

_BADGE_ATS = {
    "Bajo riesgo": "badge-success",
    "Riesgo medio": "badge-warning",
    "Alto riesgo": "badge-danger",
    "Sin datos": "badge-neutral",
}


def badge(texto: str, clase: str) -> str:
    return f'<span class="badge {clase}">{texto}</span>'


def render_job_card(resultado: dict, posicion: int) -> None:
    pub = resultado["publicacion"]
    an = resultado["analisis"]
    ats = resultado.get("riesgo_ats", {})

    recomendacion = an.get("recomendacion", "")
    badge_recomendacion = badge(recomendacion, _BADGE_RECOMENDACION.get(recomendacion, "badge-neutral"))

    ats_nivel = ats.get("nivel", "Sin datos")
    ats_cobertura = ats.get("cobertura")
    ats_texto = f"ATS: {ats_nivel}" + (f" ({ats_cobertura:.0f}%)" if ats_cobertura is not None else "")
    badge_ats = badge(ats_texto, _BADGE_ATS.get(ats_nivel, "badge-neutral"))

    st.markdown(
        f"""
        <div class="job-card">
          <div class="job-card__header">
            <div>
              <p class="job-card__title">{posicion}. {pub['title']}</p>
              <p class="job-card__company">{pub['company']} · {pub['location']}</p>
            </div>
            <div>{badge_recomendacion} {badge_ats}</div>
          </div>
          {signal_meter(an['puntaje'])}
          <p style="color:var(--text-muted); font-size:0.92rem; margin-top:8px;">{an.get('motivo', '')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Ver análisis completo"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('<div class="job-card__section-label">Coincide</div>', unsafe_allow_html=True)
            st.markdown(
                "".join(f'<span class="tag">{s}</span> ' for s in an.get("skills_match", [])) or "—",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown('<div class="job-card__section-label">Parcial</div>', unsafe_allow_html=True)
            st.markdown(
                "".join(f'<span class="tag">{s}</span> ' for s in an.get("skills_parcial", [])) or "—",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown('<div class="job-card__section-label">Falta</div>', unsafe_allow_html=True)
            st.markdown(
                "".join(f'<span class="tag tag-missing">{s}</span> ' for s in an.get("skills_faltantes", [])) or "—",
                unsafe_allow_html=True,
            )

        if an.get("profile_fit"):
            st.markdown('<div class="job-card__section-label">Encaje por dimensión</div>', unsafe_allow_html=True)
            for dim, nivel in an["profile_fit"].items():
                st.markdown(f"**{dim}:** {nivel}")

        if an.get("sugerencias"):
            st.markdown('<div class="job-card__section-label">Sugerencias</div>', unsafe_allow_html=True)
            for s in an["sugerencias"]:
                st.markdown(f"- {s}")

        st.markdown('<div class="job-card__section-label">Carta de presentación sugerida</div>', unsafe_allow_html=True)
        st.markdown(f"> {an.get('carta_presentacion', '')}")

        st.markdown(f"[Ver publicación en LinkedIn]({pub['job_url']})")


# ---------------------------------------------------------------------------
# Sidebar: configuración de la búsqueda
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Configuración")

    api_key = st.text_input(
        "API key de Groq",
        type="password",
        help="Se usa solo en esta sesión, nunca se guarda. Conseguila gratis en console.groq.com/keys",
    )

    cv_file = st.file_uploader("Tu CV (PDF)", type=["pdf"])

    location = st.text_input("Ubicación", placeholder="Buenos Aires, Argentina")

    num_jobs = st.slider("Cantidad de publicaciones", min_value=1, max_value=30, value=10, step=1)

    mode = st.radio("Modalidad", options=["both", "local", "remote"], index=0,
                     format_func=lambda m: {"both": "Local + remoto", "local": "Solo local", "remote": "Solo remoto"}[m])

    hours_old = st.selectbox(
        "Antigüedad máxima",
        options=[72, 168, 336, 720],
        index=2,
        format_func=lambda h: {72: "3 días", 168: "1 semana", 336: "2 semanas", 720: "1 mes"}[h],
    )

    ejecutar = st.button("Generar reporte", use_container_width=True, disabled=not (api_key and cv_file and location))

    if not (api_key and cv_file and location):
        st.caption("Completá API key, CV y ubicación para habilitar el botón.")


# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="job-hero">
      <div class="job-hero__eyebrow">LinkedIn Job Matcher</div>
      <h1 class="job-hero__title">Cuánto encaja tu perfil, en cifras</h1>
      <p class="job-hero__subtitle">
        Subí tu CV y dejá que el análisis separe la señal del ruido entre las
        publicaciones de LinkedIn: qué tan bien encajás, qué te falta, y si
        tu CV pasaría el primer filtro automático.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------
if "reporte" not in st.session_state:
    st.session_state.reporte = None


# ---------------------------------------------------------------------------
# Ejecución del pipeline
# ---------------------------------------------------------------------------
if ejecutar:
    analyzer.configurar_api_key(api_key)

    with st.status("Procesando...", expanded=True) as status:
        try:
            status.write("Leyendo CV...")
            cv_texto = cv_reader.leer_cv(BytesIO(cv_file.getvalue()))

            status.write("Analizando tu perfil...")
            perfil_cv = analyzer.extraer_perfil(cv_texto)
            search_term_general = perfil_cv.get("search_term_general", perfil_cv.get("rol_ideal", "Data Scientist"))
            search_terms_especificos = perfil_cv.get("search_terms_especificos", [])

            status.write(f"Buscando publicaciones ({search_term_general})...")
            publicaciones = job_fetcher.buscar_publicaciones(
                search_term_general=search_term_general,
                search_terms_especificos=search_terms_especificos,
                location=location,
                num_jobs=num_jobs,
                mode=mode,
                hours_old=hours_old,
            )

            if not publicaciones:
                status.update(label="No se encontraron publicaciones.", state="error")
                st.stop()

            resultados = []
            for i, pub in enumerate(publicaciones, start=1):
                status.write(f"Analizando publicación {i}/{len(publicaciones)}: {pub['title']}...")
                try:
                    analisis = analyzer.puntuar_publicacion(cv_texto, pub)
                    keywords_ats = analyzer.extraer_keywords_ats(pub)
                    riesgo_ats = ats_checker.analizar_riesgo_ats(cv_texto, keywords_ats)
                    resultados.append({"publicacion": pub, "analisis": analisis, "riesgo_ats": riesgo_ats})
                except Exception as e:
                    status.write(f"Se saltó esta publicación por un error: {e}")

            if not resultados:
                status.update(label="Ninguna publicación pudo ser analizada.", state="error")
                st.stop()

            status.write("Generando resumen general...")
            resumen = analyzer.generar_resumen_general(perfil_cv, resultados)

            st.session_state.reporte = {
                "perfil_cv": perfil_cv,
                "resumen": resumen,
                "resultados": resultados,
            }
            status.update(label="Reporte generado.", state="complete")

        except Exception as e:
            status.update(label=f"Ocurrió un error: {e}", state="error")
            st.exception(e)
            st.stop()


# ---------------------------------------------------------------------------
# Reporte
# ---------------------------------------------------------------------------
if st.session_state.reporte:
    perfil_cv = st.session_state.reporte["perfil_cv"]
    resumen = st.session_state.reporte["resumen"]
    resultados = st.session_state.reporte["resultados"]

    conteo = resumen.get("conteo_recomendaciones", {})
    ats_promedio = resumen.get("ats_cobertura_promedio")

    st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
    cols = st.columns(4)
    kpis = [
        ("Puntaje promedio", f"{resumen.get('puntaje_promedio', 'N/D')}/100"),
        ("Encaje general", resumen.get("encaje_general", "N/D")),
        ("Cobertura ATS", f"{ats_promedio:.0f}%" if ats_promedio is not None else "N/D"),
        ("Para aplicar", str(conteo.get("Aplicar", 0))),
    ]
    for col, (label, value) in zip(cols, kpis):
        with col:
            st.markdown(
                f"""<div class="kpi-card"><div class="kpi-card__label">{label}</div>
                <div class="kpi-card__value">{value}</div></div>""",
                unsafe_allow_html=True,
            )
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"**Rol ideal detectado:** {perfil_cv.get('rol_ideal', 'N/D')} · **Seniority:** {perfil_cv.get('seniority', 'N/D')}")
    st.markdown(resumen.get("conclusion", ""))

    gaps = resumen.get("gaps_principales", [])
    if gaps:
        st.markdown('<div class="job-card__section-label">Principales carencias detectadas</div>', unsafe_allow_html=True)
        st.markdown("".join(f'<span class="tag tag-missing">{g}</span> ' for g in gaps), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Ranking de publicaciones")

    resultados_ordenados = sorted(resultados, key=lambda r: r["analisis"]["puntaje"], reverse=True)
    for i, resultado in enumerate(resultados_ordenados, start=1):
        render_job_card(resultado, i)

    st.markdown("---")
    st.markdown("### Descargar reporte")

    md_contenido = report_builder.construir_markdown(perfil_cv, resumen, resultados)
    html_contenido = report_builder.construir_html(perfil_cv, resumen, resultados)

    col_md, col_html, col_pdf = st.columns(3)
    with col_md:
        st.download_button("Descargar Markdown", md_contenido, file_name="reporte.md", use_container_width=True)
    with col_html:
        st.download_button("Descargar HTML", html_contenido, file_name="reporte.html", use_container_width=True)
    with col_pdf:
        try:
            pdf_bytes = report_builder.construir_pdf(perfil_cv, resumen, resultados)
            st.download_button("Descargar PDF", pdf_bytes, file_name="reporte.pdf", use_container_width=True)
        except Exception as e:
            st.caption(f"No se pudo generar el PDF: {e}")