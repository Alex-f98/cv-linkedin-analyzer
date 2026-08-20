"""
cv_reader.py
Extrae el texto plano de un CV en formato PDF.
"""

import sys
import pdfplumber


def leer_cv(ruta_pdf: str) -> str:
    """
    Abre un PDF y devuelve todo su texto concatenado.

    Args:
        ruta_pdf: ruta al archivo PDF del CV.

    Returns:
        El texto extraído del PDF.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError: si no se pudo extraer texto (ej: PDF escaneado sin OCR).
    """
    texto_paginas = []

    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for pagina in pdf.pages:
                texto = pagina.extract_text()
                if texto:
                    texto_paginas.append(texto)
    except FileNotFoundError:
        raise FileNotFoundError(f"No se encontró el archivo de CV: {ruta_pdf}")

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
