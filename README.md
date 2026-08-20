# LinkedIn Job Matcher (con Groq)

Sube tu CV, busca automáticamente publicaciones de trabajo en LinkedIn que
encajen con tu perfil, las analiza con IA (Groq) y te arma un reporte con:

- Resumen general de qué tan bien encaja tu perfil en la búsqueda.
- Principales carencias/gaps detectados y skills más pedidas.
- Ranking de publicaciones ordenado por puntaje de compatibilidad.
- Por cada publicación: skills faltantes, sugerencias de mejora, link directo
  y una carta de presentación sugerida.

## Importante sobre LinkedIn

Este programa usa [JobSpy](https://github.com/speedyapply/JobSpy) para buscar
publicaciones públicas en LinkedIn. LinkedIn es agresivo bloqueando scraping:
si buscás con mucha frecuencia o pedís muchos resultados, puede que te
rate-limitee temporalmente. Usalo con moderación (no lo corras en loop ni
lo dejes automatizado 24/7).

## Instalación

```bash
# 1. Cloná o descargá esta carpeta, y entrá en ella
cd linkedin-job-matcher

# 2. Creá un entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate

# 3. Instalá las dependencias
pip install -r requirements.txt

# 4. Configurá tu API key de Groq
cp .env.example .env
# Editá .env y pegá tu API key (gratis en https://console.groq.com/keys)
```

## Uso

```bash
python main.py --cv mi_cv.pdf --location "Buenos Aires, Argentina"
```

### Opciones disponibles

| Argumento        | Obligatorio | Descripción                                                        |
|-------------------|:-----------:|---------------------------------------------------------------------|
| `--cv`            | Sí          | Ruta al PDF de tu CV.                                               |
| `--location`      | Sí          | Ciudad/país para la búsqueda local.                                 |
| `--num-jobs`      | No          | Cantidad aproximada de publicaciones a traer (default: 12).         |
| `--mode`          | No          | `both` (local+remoto, default), `local`, o `remote`.                |
| `--hours-old`     | No          | Antigüedad máxima de las publicaciones, en horas (default: 336 = 2 semanas). |
| `--search-term`   | No          | Forzar un único término de búsqueda en vez de las capas automáticas.|
| `--output`        | No          | Carpeta de salida del reporte (default: `./output`).                |

### Ejemplos

```bash
# Básico (busca local + remoto, últimas 2 semanas)
python main.py --cv mi_cv.pdf --location "Córdoba, Argentina"

# Solo remoto, últimos 3 días
python main.py --cv mi_cv.pdf --location "Madrid, España" --mode remote --hours-old 72

# Ampliar la ventana de antigüedad a un mes
python main.py --cv mi_cv.pdf --location "CABA" --hours-old 720

# Forzar un solo término en vez de las capas que infiere Groq
python main.py --cv mi_cv.pdf --location "CABA" --search-term "Data Analyst"
```

## Cómo busca las publicaciones (capas)

En vez de un único término rígido, Groq genera dos capas a partir de tu CV:
- **Capa general:** 1 término amplio y estándar (ej: "Data Scientist") — trae volumen.
- **Capa específica:** 1-2 términos de tu diferencial real (ej: "Conformal Prediction") — trae mejor matcheo con tu perfil único.

El `--num-jobs` total se reparte 50/50 entre la capa general y las específicas. Cada término se busca según `--mode` (local, remoto, o ambos), y todos los resultados se deduplican por URL al final.

## Riesgo ATS

Además del puntaje de compatibilidad (que evalúa con criterio "humano" qué tan bueno sos para el rol), cada publicación incluye un chequeo de **riesgo ATS**: busca de forma literal (texto exacto + variantes obvias como plural/singular y abreviaciones comunes) si las keywords "duras" del posteo (herramientas, certificaciones, años de experiencia) aparecen tal cual en tu CV. Esto simula el primer filtro automático real de un ATS, que es mucho más rígido que un reclutador humano — por eso puede darte un puntaje alto de Groq y a la vez un riesgo ATS alto, si tenés la experiencia pero tu CV no usa las palabras exactas que buscan.


## Salida

El programa genera dos archivos en la carpeta `output/`:
- `reporte_<fecha>.md` — versión Markdown.
- `reporte_<fecha>.html` — versión HTML lista para abrir en el navegador.

## Estructura del proyecto

```
linkedin-job-matcher/
├── main.py              # Orquesta todo el flujo
├── cv_reader.py          # Extrae texto del CV en PDF
├── job_fetcher.py         # Busca publicaciones en LinkedIn (JobSpy)
├── analyzer.py             # Prompts y llamadas a la API de Groq
├── report_builder.py      # Genera el reporte en Markdown/HTML
├── requirements.txt
├── .env.example
└── output/                # Acá se guardan los reportes generados
```