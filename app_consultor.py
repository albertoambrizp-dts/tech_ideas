import streamlit as st
import pandas as pd
import openai # <-- ¡NUEVA LIBRERÍA!
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import json
import os
from fpdf import FPDF
import numpy as np
from dotenv import load_dotenv
import requests # Necesario para la conexión con N8N

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(layout="wide", page_title="Tablero de Control - Consultor", page_icon="📊")
load_dotenv() # Necesario solo si corres en local

# Carga de variables (buscadas en os.environ, que incluye Streamlit Secrets)
# CAMBIAMOS A OPENAI_API_KEY
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') 
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

# URLs de los Webhooks (permanecen igual)
N8N_URL_FETCH_RESPONSES = os.getenv("N8N_URL_FETCH_RESPONSES")
N8N_URL_FETCH_CONTEXT = os.getenv("N8N_URL_FETCH_CONTEXT")

# Inicialización del cliente OpenAI
if OPENAI_API_KEY:
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# --- 2. FUNCIONES DE CARGA DE DATOS (N8N) ---

def fetch_data_from_n8n(url, key_name):
    """Función genérica para obtener datos de un Webhook de N8N."""
    if not url:
        st.error(f"❌ ERROR: La URL de {key_name} no está configurada en los Secrets.")
        return []

    try:
        response = requests.get(url, timeout=20) 
        if response.status_code != 200:
            st.error(f"❌ Error N8N ({response.status_code}) en {key_name}: Falló al devolver datos.")
            return []
        
        # N8N devuelve la lista de filas directamente
        return response.json()

    except Exception as e:
        st.error(f"❌ Error de conexión o JSON en {key_name}: {e}")
        return []

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
        # Asumimos que la hoja Contexto devuelve una lista con un solo objeto (la primera fila)
        contexto_data = data_contexto[0] 
        contexto_global = {
            "Industria": contexto_data.get('Industria', 'N/A'),
            "Mision": contexto_data.get('Mision', 'N/A'),
            "Vision": contexto_data.get('Vision', 'N/A'),
            "KPIs": contexto_data.get('KPIs_Actuales', 'N/A')
        }
    
    return df_respuestas, contexto_global

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

# --- 4. ANÁLISIS COMPLETO (Embeddings y LLM) ---
def run_full_analysis(df_respuestas, contexto_global):
    llm_similitud_context = "Análisis no ejecutado."
    metrica_silueta = "N/A"
    
    if not df_respuestas.empty:
        try:
            model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            roles = df_respuestas['rol_jerarquico'].unique()
            rol_embeddings = {}
            all_embeddings_list = []
            cluster_labels_list = []

            for rol in roles:
                texts = df_respuestas[df_respuestas['rol_jerarquico'] == rol]['respuesta_texto'].tolist()
                valid_texts = [t for t in texts if t.strip()]
                if valid_texts:
                    rol_embeddings[rol] = model.encode(" ".join(valid_texts))
                    batch = model.encode(valid_texts)
                    all_embeddings_list.extend(batch)
                    cluster_labels_list.extend([rol] * len(batch))

            # Silueta
            if len(set(cluster_labels_list)) >= 2 and len(all_embeddings_list) > len(set(cluster_labels_list)):
                mapper = {l: i for i, l in enumerate(set(cluster_labels_list))}
                num_labels = [mapper[l] for l in cluster_labels_list]
                silueta = f"{silhouette_score(np.array(all_embeddings_list), num_labels):.2f}"
            
            # Similitud
            pairs = [('Director','Analista'), ('Gerente','Analista'), ('Director','Gerente')]
            sims = []
            for r1, r2 in pairs:
                if r1 in rol_embeddings and r2 in rol_embeddings:
                    val = util.cos_sim(rol_embeddings[r1], rol_embeddings[r2])[0][0].item()
                    sims.append(f"- {r1} vs {r2}: {val:.2f}")
            
            llm_similitud_context = f"Coeficiente de Silueta: {silueta}\n\nSimilitud de Roles:\n" + "\n".join(sims)
            metrica_silueta = silueta

        except Exception as e:
            llm_similitud_context = f"Error en embeddings: {e}"

    # --- LLAMADA A OPENAI (GPT-4o mini) ---
    reporte = "Error: Reporte no generado."
    if OPENAI_API_KEY:
        try:
            raw = "\n".join([f"- {row.get('rol_jerarquico', 'N/A')}: {row.get('respuesta_texto', 'N/A')}" for _, row in df_respuestas.iterrows()])
            
            # El prompt de Gemini se convierte en la system instruction y el user message
            SYSTEM_INSTRUCTION = f"""
            Eres un Auditor Senior Big Four. Genera reporte Markdown CMMI (Nivel 1-5).
            Justifica el nivel usando la métrica de Silueta ({metrica_silueta}) y Similitud de Coseno.
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

            # Llamada a la API de OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini", # Modelo más rápido y económico
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": prompt}
                ]
            )
            reporte = response.choices[0].message.content
        except Exception as e: 
            reporte = f"Error al generar con OpenAI: {e}"
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
        with st.spinner("Ejecutando análisis profundo (Embeddings + OpenAI)..."):
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