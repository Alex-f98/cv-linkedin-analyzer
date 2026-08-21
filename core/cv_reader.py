"""
cv_reader.py
Extrae el texto plano de un CV en formato PDF. Acepta tanto una ruta de archivo
(uso desde CLI) como un objeto de archivo en memoria (uso desde Streamlit,
sin necesidad de guardar el PDF en disco).
"""

import sys
import pdfplumber


def leer_cv(fuente) -> str:
    """
    Abre un PDF y devuelve todo su texto concatenado.

    Args:
        fuente: ruta (str) al archivo PDF, o un objeto tipo archivo en memoria
                 (ej: el resultado de st.file_uploader en Streamlit).

    Returns:
        El texto extraído del PDF.

    Raises:
        FileNotFoundError: si la ruta no existe (solo aplica si `fuente` es un str).
        ValueError: si no se pudo extraer texto (ej: PDF escaneado sin OCR).
    """
    texto_paginas = []

    try:
        with pdfplumber.open(fuente) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    texto_paginas.append(texto)
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo de CV: {fuente}")

    texto_completo = "\n".join(texto_paginas).strip()

    if not texto_completo:
        raise ValueError(
            "No se pudo extraer texto del PDF. "
            "Puede que sea un PDF escaneado (imagen) sin capa de texto/OCR."
        )

    return texto_completo


if __name__ == "__main__":
    # Permite probar el módulo solo: python cv_reader.py mi_cv.pdf
    if len(sys.argv) != 2:
        print("Uso: python cv_reader.py <ruta_al_cv.pdf>")
        sys.exit(1)

    contenido = leer_cv(sys.argv[1])
    print(f"--- Texto extraído ({len(contenido)} caracteres) ---\n")
    print(contenido[:1000] + ("..." if len(contenido) > 1000 else ""))