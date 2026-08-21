"""
main.py
Programa principal: sube tu CV, busca publicaciones en LinkedIn que encajen
con tu perfil (por capas: general + tu diferencial), las puntúa con Groq,
chequea riesgo ATS y genera un reporte final.

Uso:
    python main.py --cv mi_cv.pdf --location "Buenos Aires, Argentina"
    python main.py --cv mi_cv.pdf --location "Madrid, España" --num-jobs 15 --mode remote
    python main.py --cv mi_cv.pdf --location "CABA" --hours-old 72
"""

import argparse
import sys

from dotenv import load_dotenv

from core import analyzer
from core import ats_checker
from core import cv_reader
from core import job_fetcher
from core import report_builder


def parsear_argumentos():
    parser = argparse.ArgumentParser(
        description="Busca publicaciones en LinkedIn que encajen con tu CV y las puntúa con IA."
    )
    parser.add_argument("--cv", required=True, help="Ruta al archivo PDF de tu CV.")
    parser.add_argument(
        "--location", required=True,
        help='Ciudad/país para la búsqueda local, ej: "Buenos Aires, Argentina".'
    )
    parser.add_argument(
        "--num-jobs", type=int, default=12,
        help="Cantidad aproximada de publicaciones a traer (default: 12)."
    )
    parser.add_argument(
        "--mode", choices=["both", "local", "remote"], default="both",
        help="Modalidad de búsqueda: local+remoto (default), solo local, o solo remoto."
    )
    parser.add_argument(
        "--hours-old", type=int, default=336,
        help="Antigüedad máxima de las publicaciones, en horas (default: 336 = 2 semanas)."
    )
    parser.add_argument(
        "--search-term", default=None,
        help="Forzar un único término de búsqueda en vez de que Groq infiera las capas."
    )
    parser.add_argument(
        "--output", default="output",
        help="Carpeta donde guardar el reporte (default: ./output)."
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parsear_argumentos()

    # 1. Leer el CV
    print(f" Leyendo CV desde {args.cv}...")
    try:
        cv_texto = cv_reader.leer_cv(args.cv)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Error leyendo el CV: {e}")
        sys.exit(1)
    print(f"   Texto extraído: {len(cv_texto)} caracteres.\n")

    # 2. Extraer perfil resumido con Groq (incluye términos de búsqueda por capas)
    print(" Analizando tu perfil con Groq...")
    perfil_cv = analyzer.extraer_perfil(cv_texto)

    if args.search_term:
        search_term_general = args.search_term
        search_terms_especificos = []
    else:
        search_term_general = perfil_cv.get("search_term_general", perfil_cv.get("rol_ideal", "Data Scientist"))
        search_terms_especificos = perfil_cv.get("search_terms_especificos", [])

    print(f"   Rol ideal detectado: {perfil_cv['rol_ideal']}")
    print(f"   Término general: {search_term_general}")
    if search_terms_especificos:
        print(f"   Términos específicos (diferencial): {', '.join(search_terms_especificos)}")
    print()

    # 3. Buscar publicaciones en LinkedIn (por capas)
    publicaciones = job_fetcher.buscar_publicaciones(
        search_term_general=search_term_general,
        search_terms_especificos=search_terms_especificos,
        location=args.location,
        num_jobs=args.num_jobs,
        mode=args.mode,
        hours_old=args.hours_old,
    )

    if not publicaciones:
        print(" No se encontraron publicaciones. Probá con otro --search-term, "
              "--location, --mode, o ampliá --hours-old.")
        sys.exit(1)

    # 4. Puntuar cada publicación + chequear riesgo ATS
    print(f"\n Analizando compatibilidad de {len(publicaciones)} publicaciones con Groq...")
    resultados = []
    for i, pub in enumerate(publicaciones, start=1):
        print(f"   [{i}/{len(publicaciones)}] {pub['title']} — {pub['company']}")
        try:
            analisis = analyzer.puntuar_publicacion(cv_texto, pub)
            keywords_ats = analyzer.extraer_keywords_ats(pub)
            riesgo_ats = ats_checker.analizar_riesgo_ats(cv_texto, keywords_ats)
            resultados.append({
                "publicacion": pub,
                "analisis": analisis,
                "riesgo_ats": riesgo_ats,
            })
        except Exception as e:
            print(f"        Se saltó esta publicación por un error: {e}")

    if not resultados:
        print(" Ninguna publicación pudo ser analizada.")
        sys.exit(1)

    # 5. Generar resumen general agregado
    print("\n Generando resumen general de la búsqueda...")
    resumen = analyzer.generar_resumen_general(perfil_cv, resultados)

    # 6. Guardar reporte
    ruta_md, ruta_html = report_builder.guardar_reporte(
        perfil_cv, resumen, resultados, args.output
    )

    print(f"\n Reporte generado:")
    print(f"   Markdown: {ruta_md}")
    print(f"   HTML:     {ruta_html}")
    print(f"\n Encaje general: {resumen.get('encaje_general')} "
          f"(promedio {resumen.get('puntaje_promedio')}/100)")
    if resumen.get("ats_cobertura_promedio") is not None:
        print(f" Cobertura ATS promedio: {resumen.get('ats_cobertura_promedio')}%")


if __name__ == "__main__":
    main()