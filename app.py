import streamlit as st
import pandas as pd
import advertools as adv
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SEO Index Watcher", layout="wide")

st.title("🕵️‍♂️ Monitor de Indexación SEO")
st.markdown("Revisa qué URLs de tu sitemap llevan +3 días publicadas y Google ignora.")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("1. Configuración")
    # Opción para subir el archivo de claves de Google de forma segura
    uploaded_key = st.file_uploader("Sube tu archivo JSON de Google Cloud", type="json")
    
    st.header("2. Objetivo")
    sitemap_url = st.text_input("URL del Sitemap", value="https://tuweb.com/sitemap.xml")
    
    days_threshold = st.slider("Días de antigüedad para alertar", min_value=1, max_value=30, value=3)
    
    start_btn = st.button("🚀 Iniciar Auditoría")

# --- FUNCIONES ---

def get_gsc_service(key_file):
    """Autentica con la API de Google"""
    scopes = ['https://www.googleapis.com/auth/webmasters.readonly']
    # En Streamlit Cloud, esto se maneja diferente, pero para archivo local funciona así:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(key_file, scopes)
    service = build('searchconsole', 'v1', credentials=creds)
    return service

def inspect_url(service, site_url, page_url):
    """Consulta el estado de indexación de una URL"""
    try:
        request = service.urlInspection().index().inspect(
            body={'inspectionUrl': page_url, 'siteUrl': site_url, 'languageCode': 'es'}
        )
        response = request.execute()
        return response['inspectionResult']['indexStatusResult']['coverageState']
    except Exception as e:
        return f"Error: {str(e)}"

# --- LÓGICA PRINCIPAL ---

if start_btn:
    if not uploaded_key:
        st.error("⚠️ Por favor, sube primero el archivo JSON de credenciales.")
    elif not sitemap_url:
        st.error("⚠️ Introduce una URL de sitemap válida.")
    else:
        import json
        key_data = json.load(uploaded_key)
        
        with st.spinner('Descargando y analizando Sitemap...'):
            try:
                # 1. Descargar Sitemap
                sitemap_df = adv.sitemap_to_df(sitemap_url)
                
                # 2. Convertir fechas y filtrar por los 'días de antigüedad'
                sitemap_df['lastmod'] = pd.to_datetime(sitemap_df['lastmod']).dt.tz_localize(None)
                limit_date = datetime.datetime.now() - datetime.timedelta(days=days_threshold)
                
                # Filtramos: URLs antiguas (ya deberían estar indexadas)
                urls_to_check = sitemap_df[sitemap_df['lastmod'] < limit_date].copy()
                
                # Limpiamos para obtener solo las URLs (máximo 50 para la demo para no agotar cuota rápido)
                target_urls = urls_to_check['loc'].head(50).tolist()
                
                st.info(f"🔍 Se encontraron {len(target_urls)} URLs candidatas (con +{days_threshold} días). Analizando en GSC...")
                
                # 3. Conectar a API y Loop
                service = get_gsc_service(key_data)
                
                results = []
                progress_bar = st.progress(0)
                
                # Necesitamos saber la propiedad "raíz" para la API (ej: https://web.com/)
                # Un truco simple es usar la base del sitemap o pedirla al usuario. 
                # Aquí intentamos extraerla de la primera URL.
                from urllib.parse import urlparse
                parsed_uri = urlparse(sitemap_url)
                site_root = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri) # sc-domain:tudominio.com si es dominio

                for i, url in enumerate(target_urls):
                    status = inspect_url(service, site_root, url)
                    
                    # Guardamos resultados si NO está indexada (o si quieres ver todo)
                    if status != 'INDEXED': 
                        results.append({
                            'URL': url,
                            'Publicado': urls_to_check.iloc[i]['lastmod'],
                            'Estado GSC': status
                        })
                    
                    progress_bar.progress((i + 1) / len(target_urls))

                # 4. Mostrar Resultados
                if results:
                    st.error(f"🚨 Se detectaron {len(results)} URLs problemáticas.")
                    df_results = pd.DataFrame(results)
                    st.dataframe(df_results, use_container_width=True)
                    
                    # Botón de descarga
                    csv = df_results.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Descargar Reporte CSV", csv, "seo_audit.csv", "text/csv")
                else:
                    st.success("✅ ¡Felicidades! Todas las URLs revisadas están indexadas correctamente.")

            except Exception as e:
                st.error(f"Ocurrió un error: {e}")
                st.warning("Consejo: Asegúrate de que el email del JSON tenga permisos en GSC y que la URL del sitemap sea correcta.")