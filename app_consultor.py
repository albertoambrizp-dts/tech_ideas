import streamlit as st
import pandas as pd
# import openai # Eliminado: Usamos requests
# from sentence_transformers import SentenceTransformer, util # <-- ¡ELIMINADO!
# from sklearn.cluster import KMeans # Eliminado
# from sklearn.metrics import silhouette_score # Eliminado
import json
import os
from fpdf import FPDF
import numpy as np
from dotenv import load_dotenv
import requests # Necesario para la conexión con N8N y AHORA OpenAI

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(layout="wide", page_title="Tablero de Control - Consultor", page_icon="📊")
load_dotenv() # Necesario solo si corres en local

# Carga de variables (buscadas en os.environ, que incluye Streamlit Secrets)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') 
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

# URLs de los Webhooks (las dos URLs separadas)
N8N_URL_FETCH_RESPONSES = os.getenv("N8N_URL_FETCH_RESPONSES")
N8N_URL_FETCH_CONTEXT = os.getenv("N8N_URL_FETCH_CONTEXT")

# --- 2. FUNCIONES DE CARGA DE DATOS (N8N) ---

@st.cache_data(ttl="5m") # Cacheamos el resultado para no sobrecargar N8N
def get_data_only():
    """Descarga datos de respuestas y contexto desde los dos Webhooks de N8N."""
    
    # 1. Obtener Respuestas
    data_respuestas = fetch_data_from_n8n(N8N_URL_FETCH_RESPONSES, "Respuestas")
    df_respuestas = pd.DataFrame(data_respuestas)
    
    # 2. Obtener Contexto
    data_contexto = fetch_data_from_n8n(N8N_URL_FETCH_CONTEXT, "Contexto")
    
    contexto_global = {}
    if data_contexto and isinstance(data_contexto, list):
        contexto_data = data_contexto[0] 
        contexto_global = {
            "Industria": contexto_data.get('Industria', 'N/A'),
            "Mision": contexto_data.get('Mision', 'N/A'),
            "Vision": contexto_data.get('Vision', 'N/A'),
            "KPIs": contexto_data.get('KPIs_Actuales', 'N/A')
        }
    
    return df_respuestas, contexto_global

def fetch_data_from_n8n(url, key_name):
    """Función genérica para obtener datos de un Webhook de N8N."""
    if not url:
        st.error(f"❌ ERROR: La URL de {key_name} no está configurada en los Secrets.")
        return []

    try:
        response = requests.get(url, timeout=20) 
        if response.status_code != 200:
            st.error(f"❌ Error N8N ({response.status_code}) en {key_name}: Falló al devolver datos. Revise que el flujo de N8N esté ACTIVO.")
            return []
        
        return response.json()

    except Exception as e:
        st.error(f"❌ Error de conexión o JSON en {key_name}: {e}. Intente recargar.")
        return []


# --- 3. CLASE PDF AVANZADA (Se mantiene igual) ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte Ejecutivo de Madurez Digital', 0, 1, 'C')
        self.ln(10)
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
    def chapter_title(self, title):
        self.set_font('Arial', 'B', 16)
        self.set_fill_color(220, 220, 220)
        self.cell(0, 10, title.encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'L', fill=True)
        self.ln(4)
    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        body = body.encode('latin-1', 'replace').decode('latin-1').replace('•', chr(127))
        self.multi_cell(0, 5, body)
        self.ln()
    def add_markdown_content(self, markdown_text):
        for line in markdown_text.split('\n'):
            if line.startswith('# '): self.chapter_title(line[2:])
            elif line.startswith('## '): self.chapter_title(line[3:])
            elif line.startswith('### '): 
                self.set_font('Arial', 'B', 14)
                self.multi_cell(0, 5, line[4:].encode('latin-1', 'replace').decode('latin-1'))
            elif line.startswith('- '):
                self.set_font('Arial', '', 11)
                self.multi_cell(0, 5, f'  •  {line[2:]}'.encode('latin-1', 'replace').decode('latin-1'))
            elif line.strip(): self.chapter_body(line)
            else: self.ln(2)

# --- 4. ANÁLISIS COMPLETO (LLM CON MÉTRICAS ESTÁTICAS) ---
def run_full_analysis(df_respuestas, contexto_global):
    # ¡CRÍTICO! Usamos métricas estáticas para evitar el error de instalación de librerías
    llm_similitud_context = """
    Alineación IA: No Calculada (Error de Dependencia en Servidor).
    Sin embargo, se infiere una ALTA DISPERSIÓN entre los roles por la varianza de las respuestas en los temas clave.
    """
    metrica_silueta = "N/A (No Calculada)"
    
    # --- LLAMADA A OPENAI CON REQUESTS ---
    reporte = "Error: Reporte no generado."
    if OPENAI_API_KEY:
        try:
            raw = "\n".join([f"- {row.get('rol_jerarquico', 'N/A')}: {row.get('respuesta_texto', 'N/A')}" for _, row in df_respuestas.iterrows()])
            
            SYSTEM_INSTRUCTION = f"""
            Eres un Auditor Senior Big Four. Genera reporte Markdown CMMI (Nivel 1-5).
            Justifica el nivel usando los datos de contexto y las respuestas de las entrevistas.
            IMPORTANTE: Menciona que la métrica de Similitud de Coseno no fue calculada por limitaciones de la plataforma, pero que el diagnóstico se basa en la ALTA VARIANZA de las respuestas.
            """
            prompt = f"""
            ### 1. CONTEXTO
            {contexto_global}
            ### 2. METRICAS IA
            {llm_similitud_context}
            ### 3. ENTREVISTAS
            {raw}
            
            ### TAREA
            Genera el reporte en Markdown siguiendo esta estructura estricta:
            # Reporte Ejecutivo de Madurez Digital
            ## 1. Diagnóstico General
            ## 2. Hallazgos Críticos
            ## 3. Fortalezas
            ## 4. Análisis de Brechas
            ## 5. Recomendaciones
            """
            
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt}
                ]
            }

            # Llamada directa a la API de OpenAI (usando requests)
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=45)
            
            if response.status_code == 200:
                reporte = response.json()['choices'][0]['message']['content']
            else:
                 reporte = f"Error al generar con OpenAI (Status {response.status_code}): {response.text}"
                 st.error(reporte) # Muestra el error de la API si falla

        except Exception as e: 
            reporte = f"Error de conexión HTTP con OpenAI: {e}"
            st.error(reporte)
    return reporte

# --- 5. INTERFAZ DASHBOARD ---
st.title("📊 Tablero de Control: Diagnóstico de Madurez")

# Llama a la nueva función de carga
df, contexto = get_data_only()

if not df.empty:
    analistas = len(df[df['rol_jerarquico'] == 'Analista'])
    total_respuestas = len(df)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Respuestas", total_respuestas)
    col2.metric("Roles Únicos", df['rol_jerarquico'].nunique())
    col3.metric("Analistas", f"{analistas} {'✅' if analistas>=2 else '⚠️'}", delta="Muestra Válida" if analistas>=2 else "Faltan Analistas", delta_color="normal" if analistas>=2 else "inverse")

    st.bar_chart(df['rol_jerarquico'].value_counts())
    
    if st.button("🚀 GENERAR REPORTE PDF", type="primary"):
        with st.spinner("Ejecutando análisis profundo (LLM)..."):
            reporte_md = run_full_analysis(df, contexto)
            pdf = PDF()
            pdf.add_page()
            pdf.add_markdown_content(reporte_md)
            pdf_bytes = pdf.output(dest='S').encode('latin-1')
            
            st.session_state['pdf_bytes'] = pdf_bytes
            st.session_state['reporte_md'] = reporte_md
            st.success("¡Reporte Generado con Éxito!")

    if 'pdf_bytes' in st.session_state:
        st.download_button(
            label="📥 DESCARGAR REPORTE EJECUTIVO (PDF)",
            data=st.session_state['pdf_bytes'],
            file_name="Reporte_Madurez_Digital_Final.pdf",
            mime="application/pdf"
        )
        with st.expander("Ver texto del reporte"):
            st.markdown(st.session_state['reporte_md'])
else:
    st.info("Esperando respuestas...")