from playwright.sync_api import sync_playwright
import pandas as pd
import time
import re
import os

CONFIG = {
    # Diccionario con el nombre exacto y el slug (texto para la URL)
    "ESTADOS": [
        {"nombre": "Aguascalientes", "slug": "aguascalientes"},
        {"nombre": "Baja California", "slug": "baja-california"},
        {"nombre": "Baja California Sur", "slug": "baja-california-sur"},
        {"nombre": "Campeche", "slug": "campeche"},
        {"nombre": "Chiapas", "slug": "chiapas"},
        {"nombre": "Chihuahua", "slug": "chihuahua"},
        {"nombre": "Ciudad de Mexico", "slug": "ciudad-de-mexico"},
        {"nombre": "Coahuila", "slug": "coahuila"},
        {"nombre": "Colima", "slug": "colima"},
        {"nombre": "Durango", "slug": "durango"},
        {"nombre": "Estado de Mexico", "slug": "estado-de-mexico"},
        {"nombre": "Guanajuato", "slug": "guanajuato"},
        {"nombre": "Guerrero", "slug": "guerrero"},
        {"nombre": "Hidalgo", "slug": "hidalgo"},
        {"nombre": "Jalisco", "slug": "jalisco"},
        {"nombre": "Michoacan", "slug": "michoacan"},
        {"nombre": "Morelos", "slug": "morelos"},
        {"nombre": "Nayarit", "slug": "nayarit"},
        {"nombre": "Nuevo Leon", "slug": "nuevo-leon"},
        {"nombre": "Oaxaca", "slug": "oaxaca"},
        {"nombre": "Puebla", "slug": "puebla"},
        {"nombre": "Queretaro", "slug": "queretaro"},
        {"nombre": "Quintana Roo", "slug": "quintana-roo"},
        {"nombre": "San Luis Potosi", "slug": "san-luis-potosi"},
        {"nombre": "Sinaloa", "slug": "sinaloa"},
        {"nombre": "Sonora", "slug": "sonora"},
        {"nombre": "Tabasco", "slug": "tabasco"},
        {"nombre": "Tamaulipas", "slug": "tamaulipas"},
        {"nombre": "Tlaxcala", "slug": "tlaxcala"},
        {"nombre": "Veracruz", "slug": "veracruz"},
        {"nombre": "Yucatan", "slug": "yucatan"},
        {"nombre": "Zacatecas", "slug": "zacatecas"}
    ],
    "URL_BASE": "https://www.occ.com.mx/empleos/de-analista-de-datos/en-"#modificable
}

def main():
    print("="*50)
    print(" SCRAPER EXPLORADOR OCC (Modo URL Directa)")
    print("="*50)
    
    mapa_rutas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for i, estado in enumerate(CONFIG["ESTADOS"]):
            nombre = estado["nombre"]
            slug = estado["slug"]
            url = f"{CONFIG['URL_BASE']}{slug}/"
            
            print(f"[{i+1}/{len(CONFIG['ESTADOS'])}] Entrando a: {url}")
            
            try:
                page.goto(url)
                time.sleep(3) # Esperar a que cargue la pagina
                
                # Buscar el total de ofertas
                try:
                    page.wait_for_selector("p[data-total-offers]", timeout=10000)
                    total_texto = page.locator("p[data-total-offers]").first.text_content()
                    total_vacantes = int(re.search(r'\d+', total_texto).group())
                except:
                    # Si no encuentra el selector, puede ser que la URL no exista o este vacia
                    total_vacantes = 0
                
                if total_vacantes > 0:
                    total_paginas = (total_vacantes // 20) + 1
                    print(f"   {nombre}: {total_vacantes} vacantes, {total_paginas} paginas.")
                    mapa_rutas.append({
                        "estado": nombre, 
                        "slug": slug,
                        "total_vacantes": total_vacantes, 
                        "total_paginas": total_paginas
                    })
                else:
                    print(f"   {nombre}: 0 vacantes encontradas (pagina vacia).")
                    mapa_rutas.append({
                        "estado": nombre, 
                        "slug": slug,
                        "total_vacantes": 0, 
                        "total_paginas": 0
                    })
                    
            except Exception as e:
                print(f"   Error con {nombre}: {e}")
                mapa_rutas.append({
                    "estado": nombre, 
                    "slug": slug,
                    "total_vacantes": 0, 
                    "total_paginas": 0
                })

        context.close()
        browser.close()

    # --- RESUMEN FINAL ---
    print("\n" + "="*50)
    print(" RESUMEN DE EXPLORACION")
    print("="*50)
    
    df = pd.DataFrame(mapa_rutas)
    exitosos = df[df["total_vacantes"] > 0]
    vacios = df[df["total_vacantes"] == 0]
    
    print(f"Estados explorados: {len(df)}")
    print(f"Estados con datos: {len(exitosos)}")
    print(f"Estados sin datos: {len(vacios)}")
    
    if len(vacios) > 0:
        print("\nEstados sin datos (0 vacantes):")
        print(vacios["estado"].tolist())
    
    # Guardar el mapa completo
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "mapa_estados_occ.csv")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    
    print(f"\n Mapa guardado en: {ruta}")
    print("\nVista previa:")
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()