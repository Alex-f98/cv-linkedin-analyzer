# Job Fit — LinkedIn Job Matcher (con Groq)

Sube tu CV, busca automáticamente publicaciones de trabajo en LinkedIn que
encajen con tu perfil, las analiza con IA (Groq) y genera un reporte con:

- Resumen general de qué tan bien encaja tu perfil en la búsqueda.
- Principales carencias/gaps y skills más pedidas.
- Ranking de publicaciones por puntaje de compatibilidad, con recomendación
  de aplicar o no.
- Riesgo ATS por publicación: si tu CV, en texto plano, pasaría el primer
  filtro automático de un sistema de reclutamiento.
- Carta de presentación sugerida por puesto.

Disponible en dos formas: **línea de comandos** (`main.py`) y **app web**
(`app/streamlit_app.py`).

## Estructura del proyecto

```
linkedin-job-matcher/
├── core/                    # Lógica de negocio (agnóstica de CLI o web)
│   ├── cv_reader.py          # Extrae texto del CV en PDF
│   ├── job_fetcher.py         # Busca publicaciones en LinkedIn (JobSpy)
│   ├── analyzer.py             # Prompts y llamadas a la API de Groq
│   ├── ats_checker.py           # Riesgo ATS (matching literal, sin IA)
│   └── report_builder.py        # Genera el reporte en Markdown/HTML/PDF
├── app/
│   └── streamlit_app.py     # App web
├── .streamlit/
│   └── config.toml           # Tema visual de Streamlit
├── main.py                   # Punto de entrada de la CLI
├── requirements.txt
├── .env.example               # Solo para uso por CLI
└── output/                    # Reportes generados por la CLI
```

## Importante sobre LinkedIn

Este programa usa [JobSpy](https://github.com/speedyapply/JobSpy) para buscar
publicaciones públicas en LinkedIn. LinkedIn es agresivo bloqueando scraping:
usalo con moderación, no lo automatices en loop.

## Instalación

```bash
git clone <tu-repo>
cd linkedin-job-matcher
python -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Uso por línea de comandos

```bash
cp .env.example .env
# Editá .env y pegá tu API key de Groq (gratis en console.groq.com/keys)

python main.py --cv mi_cv.pdf --location "Buenos Aires, Argentina"
```

### Opciones de la CLI

| Argumento        | Obligatorio | Descripción                                                        |
|-------------------|:-----------:|---------------------------------------------------------------------|
| `--cv`            | Sí          | Ruta al PDF de tu CV.                                               |
| `--location`      | Sí          | Ciudad/país para la búsqueda local.                                 |
| `--num-jobs`      | No          | Cantidad aproximada de publicaciones a traer (default: 12).         |
| `--mode`          | No          | `both` (local+remoto, default), `local`, o `remote`.                |
| `--hours-old`     | No          | Antigüedad máxima de las publicaciones, en horas (default: 336).    |
| `--search-term`   | No          | Forzar un único término de búsqueda.                                |
| `--output`        | No          | Carpeta de salida del reporte (default: `./output`).                |

## Uso como app web (Streamlit)

```bash
streamlit run app/streamlit_app.py
```

A diferencia de la CLI, **la app web no usa `.env`**: cada usuario pega su
propia API key de Groq en la barra lateral. Esto es intencional — si varios
usuarios comparten una sola API key, se agotaría rápido el límite gratuito
de tokens por minuto de Groq. Cada persona usa su propia cuota.

### Desplegar en Streamlit Community Cloud

1. Subí este repo a GitHub (asegurate de que `.env` esté en `.gitignore`,
   nunca subas tu API key).
2. Andá a [share.streamlit.io](https://share.streamlit.io) y conectá el repo.
3. Como archivo principal, indicá `app/streamlit_app.py`.
4. Listo — no hace falta configurar ningún secret del lado del servidor,
   ya que la API key la pone cada usuario en su sesión.

**Nota:** con múltiples usuarios simultáneos, el scraping de LinkedIn puede
verse afectado si todos corren búsquedas al mismo tiempo (comparten la
misma infraestructura de salida a internet). Es un límite conocido, no algo
que se pueda evitar del todo con este approach.

## Cómo busca las publicaciones (capas)

Groq genera dos capas de términos a partir de tu CV:
- **Capa general:** 1 término amplio y estándar (ej: "Data Scientist").
- **Capa específica:** 1-2 términos de tu diferencial real (ej: "Conformal Prediction").

El total de publicaciones se reparte 50/50 entre ambas capas. Cada término
se busca según el modo elegido (local, remoto, o ambos), y los resultados
se deduplican por URL al final.

## Riesgo ATS

Además del puntaje de compatibilidad (criterio "humano" de Groq), cada
publicación incluye un chequeo de riesgo ATS: busca de forma literal (texto
exacto + variantes de plural/singular y abreviaciones comunes) si las
keywords "duras" del posteo aparecen tal cual en tu CV. Esto simula el
primer filtro automático real de un ATS, que es mucho más rígido que un
reclutador humano.