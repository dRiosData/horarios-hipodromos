import io
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import pdfplumber
from datetime import datetime, timedelta
from openpyxl import load_workbook

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

URL_PRINCIPAL = "https://www.hipodromolaplata.gba.gov.ar/ns2012/ih_Infohipica/ih_000InfoHipica.php"
BASE_URL = "https://www.hipodromolaplata.gba.gov.ar/ns2012/wsAdmin/programaOficial/"

URL_PALERMO = "https://old.palermo.com.ar/es/turf/programa-oficial"
BASE_URL_PALERMO = "https://old.palermo.com.ar"

URL_CALENDARIO_SAN_ISIDRO = "https://hipodromosanisidro.com/wacP/public/calendario"
URL_PROGRAMA_SAN_ISIDRO = "https://hipodromosanisidro.com/wacP/public/programa-oficial/{}"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

def formatear_fecha_laplata(texto):
    match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
    return match.group(1) if match else texto

def formatear_fecha_palermo(texto):
    match = re.search(r'(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+(\d{4})', texto)
    if not match:
        return texto
    dia, mes_nombre, anio = match.groups()
    mes = MESES.get(mes_nombre.lower())
    if not mes:
        return texto
    return f"{int(dia):02d}/{mes:02d}/{anio}"

def formatear_fecha_san_isidro(fecha_iso):
    fecha = datetime.strptime(fecha_iso, "%Y-%m-%d")
    return fecha.strftime("%d/%m/%Y")

def fecha_en_rango(fecha_str, inicio, fin):
    try:
        fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except ValueError:
        return False
    return inicio <= fecha <= fin

def obtener_links_programa():
    response = requests.get(URL_PRINCIPAL)
    soup = BeautifulSoup(response.content, "html.parser")
    
    links = []
    for a in soup.find_all("a", href=True):
        if "verPrograma.php" in a["href"]:
            href = a["href"]
            if href.startswith("../"):
                href = href.replace("../", "https://www.hipodromolaplata.gba.gov.ar/ns2012/")
            elif not href.startswith("http"):
                href = BASE_URL + href
            links.append({
                "texto": a.text.strip(),
                "url": href
            })
    return links

def obtener_horarios(url):
    url_telas = url.replace("verPrograma.php", "verTelas.php").split("&numeroPremio")[0]
    response = requests.get(url_telas)
    soup = BeautifulSoup(response.content, "html.parser")
    
    horarios = []
    for td in soup.find_all("td"):
        texto = td.get_text(" ", strip=True)
        match = re.search(r'\d+[°º]\s+(\d{2}:\d{2})\s*Hs', texto)
        if match:
            horarios.append(match.group(1))
    
    if horarios:
        return horarios[0], horarios[-1]
    return None, None

def obtener_reuniones_palermo():
    response = requests.get(URL_PALERMO, headers=HEADERS)
    soup = BeautifulSoup(response.content, "html.parser")

    reuniones = []
    tabla = soup.find("table", class_="tabla_ver_dia")
    if not tabla:
        return reuniones

    for fila in tabla.find_all("tr")[1:]:
        celdas = fila.find_all("td")
        if len(celdas) < 2:
            continue
        link = celdas[1].find("a", href=True)
        if not link:
            continue
        href = link["href"]
        if not href.startswith("http"):
            href = BASE_URL_PALERMO + href
        reuniones.append({
            "texto": celdas[0].get_text(strip=True),
            "url": href
        })
    return reuniones

def obtener_pdf_reunion_palermo(url_reunion):
    response = requests.get(url_reunion, headers=HEADERS)
    soup = BeautifulSoup(response.content, "html.parser")
    link = soup.find("a", href=re.compile(r"app_programa_oficial.*\.pdf", re.IGNORECASE))
    if not link:
        return None
    href = link["href"]
    if not href.startswith("http"):
        href = BASE_URL_PALERMO + href
    return href

def obtener_horarios_palermo(url_reunion):
    pdf_url = obtener_pdf_reunion_palermo(url_reunion)
    if not pdf_url:
        return None, None

    response = requests.get(pdf_url, headers=HEADERS)
    texto_completo = ""
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for pagina in pdf.pages:
            texto_completo += (pagina.extract_text() or "") + "\n"

    carreras = re.findall(r'\d+\D{0,3}Carrera\s+(\d{2}:\d{2})\s*Hs', texto_completo)
    if carreras:
        return carreras[0], carreras[-1]
    return None, None

def obtener_reuniones_san_isidro(inicio, fin):
    params = {
        "start": inicio.strftime("%Y-%m-%d"),
        "end": fin.strftime("%Y-%m-%d")
    }
    response = requests.get(URL_CALENDARIO_SAN_ISIDRO, headers=HEADERS, params=params)
    eventos = response.json()

    reuniones = []
    for evento in eventos:
        if evento.get("className") != "programa-oficial-color":
            continue
        match = re.search(r'calendario_id=(\d+)', evento["url"])
        if not match:
            continue
        reuniones.append({
            "fecha": evento["start"],
            "id": match.group(1)
        })
    return reuniones

def obtener_horarios_san_isidro(calendario_id):
    response = requests.get(URL_PROGRAMA_SAN_ISIDRO.format(calendario_id), headers=HEADERS)
    horarios = re.findall(r'(\d{1,2}:\d{2})\s*hs\.', response.text, re.IGNORECASE)
    if horarios:
        return horarios[0], horarios[-1]
    return None, None

HOY = datetime.now().date()
FIN_RANGO = HOY + timedelta(days=7)

links = obtener_links_programa()
resultados = []

for link in links:
    fecha = formatear_fecha_laplata(link["texto"])
    if not fecha_en_rango(fecha, HOY, FIN_RANGO):
        continue
    primera, ultima = obtener_horarios(link["url"])
    resultados.append({
        "Hipódromo": "LP",
        "Reunión": fecha,
        "Primera carrera": primera,
        "Última carrera": ultima
    })

reuniones_palermo = obtener_reuniones_palermo()

for reunion in reuniones_palermo:
    primera, ultima = obtener_horarios_palermo(reunion["url"])
    resultados.append({
        "Hipódromo": "PL",
        "Reunión": formatear_fecha_palermo(reunion["texto"]),
        "Primera carrera": primera,
        "Última carrera": ultima
    })

reuniones_san_isidro = obtener_reuniones_san_isidro(HOY, FIN_RANGO)

for reunion in reuniones_san_isidro:
    primera, ultima = obtener_horarios_san_isidro(reunion["id"])
    resultados.append({
        "Hipódromo": "SI",
        "Reunión": formatear_fecha_san_isidro(reunion["fecha"]),
        "Primera carrera": primera,
        "Última carrera": ultima
    })

df = pd.DataFrame(resultados, columns=["Hipódromo", "Reunión", "Primera carrera", "Última carrera"])
print(df)

ruta = r"C:\Users\dpatr\.n8n-files\horarios_laplata.xlsx"

df.to_excel(ruta, index=False)
df.to_csv(r"C:\Users\dpatr\.n8n-files\horarios_laplata.csv", index=False)

wb = load_workbook(ruta)
ws = wb.active
for col in ws.columns:
    max_length = max(len(str(cell.value)) for cell in col if cell.value)
    ws.column_dimensions[col[0].column_letter].width = max_length + 4
wb.save(ruta)

print("Archivo Excel generado correctamente")