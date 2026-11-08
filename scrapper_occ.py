from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
import os
import math
from concurrent.futures import ThreadPoolExecutor

# ==========================================
#  CONFIGURACION DEL SCRAPER
# ==========================================
CONFIG = {
    "MAPA_RUTA": "data/mapa_estados_occ.csv",
    "NUM_BOTS": 2,
    
    # Tiempos de espera
    "ESPERA_CARGA_PAGINA": 3.0,
    "ESPERA_CLIC_TARJETA": 2.0,
    "ESPERA_PANEL_CARGA": 2.0, 
    "ESPERA_ENTRE_TARJETAS": 1.5 
}

CARPETA_TEMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "temp")
os.makedirs(CARPETA_TEMP, exist_ok=True)

# ==========================================
#  FUNCIONES
# ==========================================
def limpiar_texto_sucio(texto):
    if not isinstance(texto, str): return texto
    texto = texto.replace('\t', ' ').replace('\n', ' ')
    texto = re.sub(r'[\-\*]\s*', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'^(Requerimientos|Descripcion|Funciones principales|Descripcion del Puesto)\s*:?', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'Recuerda que ningun reclutador.*', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'ID:\s*\d+', '', texto)
    return texto

def extraer_detalle_tarjeta(page, tarjeta, num_pagina, estado):
    try:
        ubicacion_raw = tarjeta.locator(".vacancy-card__location span").first.text_content()
        ubicacion = ubicacion_raw.strip() if ubicacion_raw else "Desconocido"
        titulo_tarjeta = tarjeta.locator(".vacancy-card__title").first.text_content().strip()
        id_oferta = tarjeta.get_attribute("data-id") or titulo_tarjeta[:10]

        tarjeta.click()
        
        try:
            page.wait_for_function(
                f"document.querySelector('#job-detail-container') && document.querySelector('#job-detail-container').innerText.includes('ID: {id_oferta}')",
                timeout=CONFIG["ESPERA_PANEL_CARGA"] * 1000
            )
            time.sleep(0.5) 
        except Exception:
            pass

        contenedor = page.locator(".px-8.py-6").first
        texto_completo = contenedor.inner_text()

        salario = "No mostrado"
        match_salario = re.search(r'\$[\d,]+', texto_completo)
        if match_salario: salario = match_salario.group(0)
        
        perfil = ""
        match_perfil = re.search(r'Perfil requerido:(.*?)(?=Funciones principales:|Oferta y Condiciones:|$)', texto_completo, re.DOTALL | re.IGNORECASE)
        if match_perfil: perfil = match_perfil.group(1).strip()
        
        funciones = ""
        match_funciones = re.search(r'Funciones principales:(.*?)(?=Oferta y Condiciones:|Perfil requerido:|$)', texto_completo, re.DOTALL | re.IGNORECASE)
        if match_funciones: funciones = match_funciones.group(1).strip()

        if not perfil and not funciones:
            match_desc = re.search(r'Descripcion(.*?)(?=Recuerda que ningun|ID:)', texto_completo, re.DOTALL | re.IGNORECASE)
            if match_desc: perfil = match_desc.group(1).strip()

        return {
            "id": id_oferta, "titulo": titulo_tarjeta, "ubicacion": ubicacion, 
            "salario": salario, "requerimientos": perfil, "funciones": funciones, 
            "pagina": num_pagina, "estado_busqueda": estado
        }
    except Exception as e:
        return None

def scrapear_estado(page, num_bot, estado, slug, total_paginas):
    """Recibe la pagina ya abierta y extrae los datos de un estado."""
    tiempo_inicio = time.time()
    print(f" [Bot {num_bot}] Iniciando: {estado} ({total_paginas} paginas).")
    datos_bot = []
    
    url_base = f"https://www.occ.com.mx/empleos/de-analista-de-datos/en-{slug}/"
    
    for num_pagina in range(1, total_paginas + 1):
        url = f"{url_base}?page={num_pagina}" if num_pagina > 1 else url_base
        print(f"  [Bot {num_bot}] {estado}: pagina {num_pagina}/{total_paginas}...")
        
        try:
            page.goto(url)
            time.sleep(CONFIG["ESPERA_CARGA_PAGINA"])
            
            tarjetas = page.locator(".vacancy-card").all()
            
            for tarjeta in tarjetas:
                datos = extraer_detalle_tarjeta(page, tarjeta, num_pagina, estado)
                if datos:
                    datos_bot.append(datos)
                time.sleep(CONFIG["ESPERA_ENTRE_TARJETAS"])
        except Exception as e:
            print(f"  [Bot {num_bot}] Error en pagina {num_pagina} de {estado}: {e}")
            
    if datos_bot:
        nombre_archivo = f"bot_{num_bot}_{slug}.csv"
        ruta_temp = os.path.join(CARPETA_TEMP, nombre_archivo)
        pd.DataFrame(datos_bot).to_csv(ruta_temp, index=False, encoding="utf-8-sig", quoting=1)
        
    duracion = time.time() - tiempo_inicio
    print(f" [Bot {num_bot}] Termino {estado} en {duracion:.2f} segs. Extrajo {len(datos_bot)} registros.")
    return duracion

def main():
    print("="*50)
    print(" SCRAPER DE EXTRACCION MASIVA")
    print("="*50)
    
    # Leer el mapa de ruta
    ruta_mapa = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG["MAPA_RUTA"])
    if not os.path.exists(ruta_mapa):
        print(f" Error: No se encontro el mapa en {ruta_mapa}.")
        return
        
    df_mapa = pd.read_csv(ruta_mapa)
    df_mapa = df_mapa[df_mapa["total_paginas"] > 0]
    
    print(f"Mapa cargado. Estados con vacantes: {len(df_mapa)}")
    
    # Menu de bots
    try:
        num_bots = int(input(f"Cuantos bots quieres usar? (Default {CONFIG['NUM_BOTS']}): ") or CONFIG["NUM_BOTS"])
        if num_bots < 1: num_bots = 1
    except ValueError:
        num_bots = CONFIG["NUM_BOTS"]
        
    print(f"\nDividiendo el trabajo entre {num_bots} bots...\n")
    
    # Asignar estados a los bots
    tareas = []
    for i, fila in df_mapa.iterrows():
        bot_asignado = (i % num_bots) + 1
        tareas.append((bot_asignado, fila["estado"], fila["slug"], fila["total_paginas"]))
        
    # Ejecutar: Un solo navegador por bot
    def ejecutar_bot(num_bot, tareas_bot):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--window-size=1280,720"])
            context = browser.new_context()
            page = context.new_page()
            
            for tarea in tareas_bot:
                scrapear_estado(page, num_bot, tarea[1], tarea[2], tarea[3])
                
            context.close()
            browser.close()

    # Agrupar tareas 
    tareas_por_bot = {i: [] for i in range(1, num_bots + 1)}
    for tarea in tareas:
        tareas_por_bot[tarea[0]].append(tarea)

    with ThreadPoolExecutor(max_workers=num_bots) as executor:
        futuros = [executor.submit(ejecutar_bot, bot, tareas_por_bot[bot]) for bot in tareas_por_bot]
        for futuro in futuros:
            futuro.result()

    # Consolidar
    print("\n" + "="*50)
    print(" CONSOLIDANDO RESULTADOS...")
    print("="*50)
    
    dfs = []
    for archivo in os.listdir(CARPETA_TEMP):
        if archivo.endswith(".csv") and archivo.startswith("bot_"):
            dfs.append(pd.read_csv(os.path.join(CARPETA_TEMP, archivo)))

    if dfs:
        df_final = pd.concat(dfs, ignore_index=True)
        df_final = df_final.drop_duplicates(subset=['id'])
        
        print("Limpiando textos...")
        df_final['requerimientos'] = df_final['requerimientos'].apply(limpiar_texto_sucio)
        df_final['funciones'] = df_final['funciones'].apply(limpiar_texto_sucio)
        df_final['titulo'] = df_final['titulo'].apply(limpiar_texto_sucio)
        
        ruta_final = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "occ_empleos_todos_estados.csv")
        df_final.to_csv(ruta_final, index=False, encoding="utf-8-sig", quoting=1)
        
        print(f"\n Exito! Total de empleos unicos: {len(df_final)}")
        print(f"Archivo guardado en: '{ruta_final}'")
        
        borrar = input("\nDeseas borrar los archivos temporales? (s/n): ").strip().lower()
        if borrar == 's':
            for archivo in os.listdir(CARPETA_TEMP):
                if archivo.endswith(".csv"):
                    os.remove(os.path.join(CARPETA_TEMP, archivo))
            print("Archivos temporales eliminados.")
    else:
        print("\n No se generaron datos.")

if __name__ == "__main__":
    main()