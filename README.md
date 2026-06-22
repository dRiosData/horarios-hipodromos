# Automatización de Horarios de Hipódromos

Automatización end-to-end que scrapea semanalmente los horarios de carreras de tres hipódromos argentinos (La Plata, Palermo y San Isidro), consolida los datos en una tabla y los envía por mail — sin intervención manual.

## Problema

Cada hipódromo publica sus horarios en un sitio web distinto, con formatos de fecha y estructura HTML/PDF diferentes. Revisar manualmente las tres páginas todas las semanas para saber a qué hora arranca y termina la cartelera es repetitivo y propenso a olvidos.

## Solución

Un scraper en Python unifica los tres orígenes en una sola tabla, y un workflow de **n8n** lo ejecuta automáticamente todas las semanas y distribuye el resultado por email.

```
┌────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│ Schedule Trigger│ →   │ Ejecutar Scraper  │ →   │ Leer CSV Horarios   │
│ (jueves 12:00hs)│     │ (Execute Command) │     │ (Read/Write File)   │
└────────────────┘     └──────────────────┘     └────────────────────┘
                                                           │
                                                           ▼
┌────────────────────┐     ┌────────────────────┐     ┌─────────────────┐
│ Enviar Mail Horarios│ ←   │ Generar Tabla HTML  │ ←   │ Extraer Datos CSV│
│ (SMTP / Gmail)      │     │ (Code Node)         │     │ (Extract from File)│
└────────────────────┘     └────────────────────┘     └─────────────────┘
```

## Qué hace el scraper (`scraper_laplata.py`)

| Hipódromo | Fuente | Técnica de extracción |
|---|---|---|
| La Plata | `hipodromolaplata.gba.gov.ar` | HTML parsing (BeautifulSoup), filtra reuniones de los próximos 7 días |
| Palermo | `old.palermo.com.ar` | HTML parsing + descarga y lectura de PDF del programa oficial (pdfplumber), toma las próximas 2 reuniones publicadas |
| San Isidro | `hipodromosanisidro.com` | Consumo de endpoint JSON de calendario + scraping de la página de programa, filtra próximos 7 días |

Para cada reunión, extrae el horario de la primera y la última carrera con expresiones regulares, normaliza las fechas a formato `DD/MM/YYYY` y genera:

- `horarios_laplata.xlsx` (con autoajuste de ancho de columnas)
- `horarios_laplata.csv`

### Ejemplo de salida

| Hipódromo | Reunión | Primera carrera | Última carrera |
|---|---|---|---|
| LP | 18/06/2026 | 15:00 | 19:00 |
| PL | 20/06/2026 | 12:25 | 20:55 |
| SI | 19/06/2026 | 13:00 | 20:00 |

## El workflow de n8n

| Nodo | Función |
|---|---|
| **Schedule Trigger** | Dispara el flujo todos los jueves a las 12:00hs |
| **Ejecutar Scraper** | Corre `scraper_laplata.py` en la máquina local (nodo Execute Command) |
| **Leer CSV Horarios** | Lee el CSV recién generado desde disco |
| **Extraer Datos CSV** | Convierte el CSV en filas de datos estructurados (JSON) |
| **Generar Tabla HTML** | Code Node que transforma los datos en una tabla HTML lista para email |
| **Enviar Mail Horarios** | Envía la tabla por mail vía SMTP (Gmail) |

## Stack técnico

- **Python**: `requests`, `BeautifulSoup4`, `pdfplumber`, `pandas`, `openpyxl`
- **n8n** (self-hosted): orquestación, scheduling y envío de email vía SMTP
- Formatos de salida: `.xlsx`, `.csv`, tabla HTML embebida en el cuerpo del mail

## Resultado

Un mail automático cada semana con los horarios actualizados de los tres hipódromos, sin tener que entrar a ningún sitio manualmente.
