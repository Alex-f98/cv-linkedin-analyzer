"""
report_builder.py
Genera el reporte final (Markdown, HTML y PDF) con el resumen general
y el ranking de publicaciones ordenado por puntaje de compatibilidad.
Sin iconografía decorativa: los estados se comunican con texto y color.
"""

import html
import os
import re
from datetime import datetime


def _bloque_resumen_md(perfil_cv: dict, resumen: dict) -> str:
    gaps = "\n".join(f"- {g}" for g in resumen.get("gaps_principales", []))
    skills = ", ".join(resumen.get("skills_mas_pedidas", []))
    conteo = resumen.get("conteo_recomendaciones", {})
    ats_promedio = resumen.get("ats_cobertura_promedio")
    ats_faltantes = ", ".join(resumen.get("ats_keywords_faltantes_frecuentes", []))

    bloque_ats = ""
    if ats_promedio is not None:
        bloque_ats = f"""
**Cobertura ATS promedio:** {ats_promedio}% (probabilidad estimada de pasar el primer filtro automático)
**Keywords ATS que más faltan en general:** {ats_faltantes if ats_faltantes else 'Ninguna recurrente'}
"""

    return f"""## Resumen general

**Rol ideal detectado:** {perfil_cv.get('rol_ideal', 'N/A')}
**Seniority:** {perfil_cv.get('seniority', 'N/A')}
**Encaje general con esta búsqueda:** {resumen.get('encaje_general', 'N/A')}
**Puntaje promedio:** {resumen.get('puntaje_promedio', 'N/A')}/100

**Distribución de recomendaciones:** Aplicar: {conteo.get('Aplicar', 0)} · Con reservas: {conteo.get('Aplicar con reservas', 0)} · No priorizar: {conteo.get('No priorizar', 0)}
{bloque_ats}
**Conclusión:** {resumen.get('conclusion', '')}

### Principales carencias detectadas
{gaps if gaps else '- No se detectaron carencias relevantes.'}

### Skills más pedidas en esta búsqueda
{skills if skills else 'No se detectaron skills recurrentes.'}

---
"""


def _bloque_posteo_md(resultado: dict, posicion: int) -> str:
    pub = resultado["publicacion"]
    an = resultado["analisis"]
    ats = resultado.get("riesgo_ats", {})

    match = "\n".join(f"  - {s}" for s in an.get("skills_match", []))
    parcial = "\n".join(f"  - {s}" for s in an.get("skills_parcial", []))
    faltantes = "\n".join(f"  - {s}" for s in an.get("skills_faltantes", []))
    sugerencias = "\n".join(f"  - {s}" for s in an.get("sugerencias", []))
    profile_fit = "\n".join(
        f"  - {dim}: {nivel}" for dim, nivel in an.get("profile_fit", {}).items()
    )

    recomendacion = an.get("recomendacion", "")

    ats_cobertura = ats.get("cobertura")
    ats_nivel = ats.get("nivel", "Sin datos")
    ats_encontradas = ", ".join(ats.get("encontradas", [])) or "Ninguna"
    ats_faltantes_pub = ", ".join(ats.get("faltantes", [])) or "Ninguna"
    ats_texto_cobertura = f"{ats_cobertura}%" if ats_cobertura is not None else "N/D"

    return f"""### {posicion}. {pub['title']} — {pub['company']}  `{an['puntaje']}/100`  · {recomendacion}

- **Ubicación:** {pub['location']}
- **Link:** [{pub['job_url']}]({pub['job_url']})
- **Motivo del puntaje:** {an.get('motivo', '')}

**Riesgo ATS:** {ats_nivel} ({ats_texto_cobertura} de keywords literales encontradas)
  - Encontradas: {ats_encontradas}
  - No encontradas (aunque tengas la experiencia, revisá si conviene agregarlas tal cual): {ats_faltantes_pub}

**Match:**
{match if match else '  - No se detectaron coincidencias claras'}

**Parcial / relacionado:**
{parcial if parcial else '  - Ninguno'}

**Faltante:**
{faltantes if faltantes else '  - Ninguna carencia relevante detectada'}

**Profile fit por dimensión:**
{profile_fit if profile_fit else '  - No disponible'}

**Sugerencias para este puesto:**
{sugerencias if sugerencias else '  - Sin sugerencias adicionales'}

**Carta de presentación sugerida:**
> {an.get('carta_presentacion', '')}

---
"""


def construir_markdown(perfil_cv: dict, resumen: dict, resultados: list[dict]) -> str:
    """Arma el reporte completo en Markdown."""
    resultados_ordenados = sorted(
        resultados, key=lambda r: r["analisis"]["puntaje"], reverse=True
    )

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = f"# Reporte de compatibilidad CV vs. LinkedIn\n\n_Generado el {fecha}_\n\n"
    md += _bloque_resumen_md(perfil_cv, resumen)
    md += f"## Ranking de publicaciones ({len(resultados_ordenados)})\n\n"

    for i, resultado in enumerate(resultados_ordenados, start=1):
        md += _bloque_posteo_md(resultado, i)

    return md


def _markdown_a_html_basico(md_texto: str) -> str:
    """Conversión simple de Markdown a HTML (sin dependencias externas)."""
    lineas = md_texto.split("\n")
    html_lineas = []
    en_lista = False

    for linea in lineas:
        l = linea.rstrip()

        if l.startswith("### "):
            if en_lista:
                html_lineas.append("</ul>")
                en_lista = False
            html_lineas.append(f"<h3>{html.escape(l[4:])}</h3>")
        elif l.startswith("## "):
            if en_lista:
                html_lineas.append("</ul>")
                en_lista = False
            html_lineas.append(f"<h2>{html.escape(l[3:])}</h2>")
        elif l.startswith("# "):
            html_lineas.append(f"<h1>{html.escape(l[2:])}</h1>")
        elif l.startswith("---"):
            html_lineas.append("<hr>")
        elif l.startswith("  - ") or l.startswith("- "):
            if not en_lista:
                html_lineas.append("<ul>")
                en_lista = True
            contenido = l.strip("- ").strip()
            html_lineas.append(f"<li>{_inline_md(contenido)}</li>")
        elif l.startswith("> "):
            html_lineas.append(f"<blockquote>{_inline_md(l[2:])}</blockquote>")
        elif l.strip() == "":
            if en_lista:
                html_lineas.append("</ul>")
                en_lista = False
            html_lineas.append("<br>")
        else:
            html_lineas.append(f"<p>{_inline_md(l)}</p>")

    if en_lista:
        html_lineas.append("</ul>")

    return "\n".join(html_lineas)


def _inline_md(texto: str) -> str:
    """Maneja negritas, links, y code inline dentro de una línea, escapando el resto."""
    partes = []
    resto = texto
    patron = re.compile(r"(\*\*(.+?)\*\*|`(.+?)`|\[(.+?)\]\((.+?)\))")

    ultimo = 0
    for m in patron.finditer(resto):
        partes.append(html.escape(resto[ultimo:m.start()]))
        if m.group(2) is not None:
            partes.append(f"<strong>{html.escape(m.group(2))}</strong>")
        elif m.group(3) is not None:
            partes.append(f"<code>{html.escape(m.group(3))}</code>")
        elif m.group(4) is not None:
            texto_link, url = m.group(4), m.group(5)
            partes.append(f'<a href="{html.escape(url)}">{html.escape(texto_link)}</a>')
        ultimo = m.end()
    partes.append(html.escape(resto[ultimo:]))

    return "".join(partes)


# Paleta y tipografía consistentes con la app de Streamlit (ver app/streamlit_app.py).
_ESTILOS_REPORTE = """
  body { font-family: 'Inter', -apple-system, Segoe UI, Roboto, sans-serif; max-width: 850px;
          margin: 40px auto; padding: 0 24px; line-height: 1.65; color: #18181B;
          background: #FAFAFA; }
  h1, h2, h3 { font-family: 'Space Grotesk', 'Inter', sans-serif; font-weight: 600; }
  h1 { border-bottom: 2px solid #4F46E5; padding-bottom: 12px; letter-spacing: -0.02em; }
  h2 { color: #4F46E5; margin-top: 40px; font-size: 1.3rem; }
  h3 { margin-top: 32px; background: #FFFFFF; border: 1px solid #E5E5EA;
       padding: 12px 16px; border-radius: 8px; }
  a { color: #4F46E5; text-decoration: none; font-weight: 500; }
  a:hover { text-decoration: underline; }
  blockquote { background: #FFFFFF; border-left: 3px solid #4F46E5; margin: 12px 0;
               padding: 12px 16px; color: #3F3F46; border-radius: 0 6px 6px 0; }
  hr { border: none; border-top: 1px solid #E5E5EA; margin: 32px 0; }
  code { font-family: 'JetBrains Mono', 'Courier New', monospace; background: #F4F4F5;
         padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #4F46E5; }
  ul { margin: 8px 0; padding-left: 20px; }
  li { margin: 4px 0; }
  strong { color: #18181B; }
"""


def construir_html(perfil_cv: dict, resumen: dict, resultados: list[dict]) -> str:
    """Arma el reporte completo en HTML con estilos propios, a partir del Markdown."""
    cuerpo_md = construir_markdown(perfil_cv, resumen, resultados)
    cuerpo_html = _markdown_a_html_basico(cuerpo_md)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Reporte de compatibilidad CV vs. LinkedIn</title>
<style>
{_ESTILOS_REPORTE}
</style>
</head>
<body>
{cuerpo_html}
</body>
</html>
"""


def construir_pdf(perfil_cv: dict, resumen: dict, resultados: list[dict]) -> bytes:
    """
    Convierte el reporte HTML a PDF usando xhtml2pdf (pura Python, sin binarios
    del sistema, apto para Streamlit Community Cloud).

    Returns:
        Contenido del PDF como bytes, listo para st.download_button.
    """
    from io import BytesIO
    from xhtml2pdf import pisa

    html_contenido = construir_html(perfil_cv, resumen, resultados)
    buffer = BytesIO()
    resultado = pisa.CreatePDF(src=html_contenido, dest=buffer, encoding="utf-8")

    if resultado.err:
        raise RuntimeError("No se pudo generar el PDF a partir del reporte HTML.")

    return buffer.getvalue()


def guardar_reporte(perfil_cv: dict, resumen: dict, resultados: list[dict], carpeta_salida: str) -> tuple[str, str]:
    """
    Genera y guarda el reporte en Markdown y HTML (uso desde CLI).

    Returns:
        Tupla (ruta_md, ruta_html) con las rutas de los archivos generados.
    """
    os.makedirs(carpeta_salida, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")

    ruta_md = os.path.join(carpeta_salida, f"reporte_{timestamp}.md")
    ruta_html = os.path.join(carpeta_salida, f"reporte_{timestamp}.html")

    md_contenido = construir_markdown(perfil_cv, resumen, resultados)
    html_contenido = construir_html(perfil_cv, resumen, resultados)

    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(md_contenido)

    with open(ruta_html, "w", encoding="utf-8") as f:
        f.write(html_contenido)

    return ruta_md, ruta_html