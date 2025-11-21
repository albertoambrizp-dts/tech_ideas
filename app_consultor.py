import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
from sentence_transformers import SentenceTransformer, util
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import json
import os
from fpdf import FPDF
import numpy as np
from dotenv import load_dotenv

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(layout="wide", page_title="Tablero de Control - Consultor", page_icon="📊")
load_dotenv()

# Carga de variables
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
APP_ID = os.getenv('APP_ID') 
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
GOOGLE_SHEETS_JSON_PATH = "credenciales_gsheets.json" 

if not APP_ID:
    APP_ID = "1Pq_qWcIACNw3A5j1Ptjopez3TYkWtLevEd69tSoLIh8"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 2. FUNCIONES DE CARGA DE DATOS ---
def get_google_sheet_client():
    """Función auxiliar para autenticación robusta."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(current_dir, GOOGLE_SHEETS_JSON_PATH)
    with open(credentials_path, 'r') as f:
        creds_json_content = json.load(f)
    return gspread.service_account_from_dict(creds_json_content)

def get_data_only():
    """Descarga datos para el Dashboard."""
    try:
        client = get_google_sheet_client()
        spreadsheet = client.open_by_key(APP_ID)
        try: sheet = spreadsheet.worksheet('Respuestas')
        except: sheet = spreadsheet.get_worksheet(0)
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        st.error(f"Error conexión Sheets: {e}")
        return pd.DataFrame()

# --- 3. CLASE PDF AVANZADA ---
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
        title_encoded = title.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, title_encoded, 0, 1, 'L', fill=True)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        body = body.encode('latin-1', 'replace').decode('latin-1')
        body = body.replace('•', chr(127))
        self.multi_cell(0, 5, body)
        self.ln()

    def add_markdown_content(self, markdown_text):
        lines = markdown_text.split('\n')
        for line in lines:
            if line.startswith('# '):
                if "Reporte Ejecutivo" not in line:
                    self.chapter_title(line[2:])
            elif line.startswith('## '):
                self.chapter_title(line[3:])
            elif line.startswith('### '):
                self.set_font('Arial', 'B', 14)
                self.multi_cell(0, 5, line[4:].encode('latin-1', 'replace').decode('latin-1'))
                self.ln(1)
            elif line.startswith('* ') or line.startswith('- '):
                self.set_font('Arial', '', 11)
                self.multi_cell(0, 5, f'  •  {line[2:]}'.encode('latin-1', 'replace').decode('latin-1'))
                self.ln(1)
            elif line.strip():
                self.chapter_body(line)
            else:
                self.ln(3)

# --- 4. ANÁLISIS COMPLETO ---
def run_full_analysis(df_respuestas):
    # 4.1 Cargar Contexto
    try:
        client = get_google_sheet_client()
        spreadsheet = client.open_by_key(APP_ID)
        context_sheet = None
        for name in ['contexto', 'Contexto']:
            try: context_sheet = spreadsheet.worksheet(name); break
            except: pass
        if not context_sheet: context_sheet = spreadsheet.get_worksheet(1)
        ctx_data = context_sheet.get_all_records()[0]
        contexto_global = {
            "Industria": ctx_data.get('Industria', 'N/A'),
            "Mision": ctx_data.get('Mision', 'N/A'),
            "Vision": ctx_data.get('Vision', 'N/A'),
            "KPIs": ctx_data.get('KPIs_Actuales', 'N/A')
        }
    except:
        contexto_global = {"Industria": "N/A", "Mision": "N/A", "Vision": "N/A", "KPIs": "N/A"}

    # 4.2 Embeddings y Métricas
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
                valid_texts = [t for t in texts if t and len(t.strip()) > 0]
                
                if valid_texts:
                    rol_embeddings[rol] = model.encode(" ".join(valid_texts))
                    individual_embeddings = model.encode(valid_texts)
                    all_embeddings_list.extend(individual_embeddings)
                    cluster_labels_list.extend([rol] * len(individual_embeddings))

            try:
                all_embeddings = np.array(all_embeddings_list)
                n_labels = len(np.unique(cluster_labels_list))
                if n_labels >= 2 and all_embeddings.shape[0] > n_labels:
                    label_map = {label: i for i, label in enumerate(np.unique(cluster_labels_list))}
                    numeric_labels = [label_map[label] for label in cluster_labels_list]
                    silueta = silhouette_score(all_embeddings, numeric_labels)
                    metrica_silueta = f"{silueta:.2f}"
            except Exception as e:
                metrica_silueta = f"Error silueta: {e}"

            similitudes = []
            pairs = [('Director', 'Analista'), ('Gerente', 'Analista'), ('Director', 'Gerente')]
            for r1, r2 in pairs:
                if r1 in rol_embeddings and r2 in rol_embeddings:
                    sim = util.cos_sim(rol_embeddings[r1], rol_embeddings[r2])[0][0].item()
                    similitudes.append(f"- {r1} vs {r2}: {sim:.2f}")
            
            llm_similitud_context = f"Coeficiente de Silueta: {metrica_silueta}\n\nSimilitud de Roles:\n" + "\n".join(similitudes)

        except Exception as e:
            llm_similitud_context = f"Error en embeddings: {e}"

    # 4.3 Generación LLM
    reporte_markdown = "Error generación reporte."
    if GEMINI_API_KEY:
        try:
            raw_text = ""
            for _, row in df_respuestas.iterrows():
                raw_text += f"- Rol: {row.get('rol_jerarquico')}, Área: {row.get('area')}\n  Respuesta: {row.get('respuesta_texto')}\n\n"

            SYSTEM_INSTRUCTION = f"""
            Eres un Auditor Ejecutivo y Consultor Senior de una firma 'Big Four'.
            Genera un Reporte Ejecutivo de Madurez Digital (CMMI Nivel 1-5).
            Justifica el nivel usando la métrica de Silueta ({metrica_silueta}) y Similitud de Coseno.
            """
            
            USER_PROMPT = f"""
            ### 1. CONTEXTO
            {contexto_global}
            ### 2. METRICAS IA
            {llm_similitud_context}
            ### 3. ENTREVISTAS
            {raw_text}
            
            ### TAREA
            Genera el reporte en Markdown estricto:
            # Reporte Ejecutivo de Madurez Digital
            ## 1. Diagnóstico General
            ## 2. Hallazgos Críticos
            ## 3. Fortalezas
            ## 4. Análisis de Brechas
            ## 5. Recomendaciones
            """
            
            model = genai.GenerativeModel(model_name='gemini-2.5-flash', system_instruction=SYSTEM_INSTRUCTION)
            response = model.generate_content(USER_PROMPT)
            reporte_markdown = response.text
        except Exception as e:
            reporte_markdown = f"Error Gemini: {e}"

    return reporte_markdown

# --- 5. INTERFAZ DASHBOARD ---
st.title("📊 Tablero de Control: Diagnóstico de Madurez") # FIX: Forzar Reconstruccion

df = get_data_only()

if not df.empty:
    # --- NUEVO: Validación de Analistas y Lista de Participantes ---
    
    # Contar analistas
    analistas_count = len(df[df['rol_jerarquico'] == 'Analista'])
    total_respuestas = len(df)
    roles_unicos = df['rol_jerarquico'].nunique()

    # Métricas Superiores
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Total Respuestas", total_respuestas)
    col2.metric("Roles Únicos", roles_unicos)
    
    # Validación Visual
    if analistas_count >= 2:
        col3.metric("Analistas (Mín. 2)", f"{analistas_count} ✅", delta="Muestra Válida")
    else:
        col3.metric("Analistas (Mín. 2)", f"{analistas_count} ⚠️", delta="Faltan Analistas", delta_color="inverse")

    st.markdown("---")

    # Tablas y Gráficas
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.subheader("👥 Participantes Registrados")
        # Seleccionamos solo columnas relevantes para privacidad/claridad
        cols_to_show = ['nombre_id', 'rol_jerarquico', 'area_proceso']
        # Verificar si existen las columnas (por si n8n guardó con otros nombres)
        valid_cols = [c for c in cols_to_show if c in df.columns]
        
        if valid_cols:
            st.dataframe(df[valid_cols], hide_index=True, use_container_width=True)
        else:
            st.dataframe(df, use_container_width=True) # Fallback: mostrar todo
            
    with c2:
        st.subheader("Distribución por Rol")
        st.bar_chart(df['rol_jerarquico'].value_counts())
    
    st.markdown("---")
    st.header("🧠 Generación de Análisis")
    
    # Botón condicional: Sugerimos esperar si no hay suficientes datos, pero permitimos generar
    if analistas_count < 2:
        st.warning("⚠️ Advertencia: Tienes menos de 2 Analistas. El análisis de comparación (Director vs Analista) podría no ser estadísticamente significativo.")
    
    if st.button("🚀 GENERAR REPORTE PDF", type="primary"):
        with st.spinner("Ejecutando análisis profundo (Embeddings + Gemini)..."):
            reporte_md = run_full_analysis(df)
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
    if st.button("Recargar"): st.rerun()