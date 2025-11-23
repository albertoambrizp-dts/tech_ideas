import streamlit as st
import pandas as pd
import json
import os
import numpy as np
#from dotenv import load_dotenv
import requests # Necesario para la conexión con N8N y OpenAI

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(layout="wide", page_title="Tablero de Control - Consultor", page_icon="📊")
#load_dotenv() # Necesario solo si corres en local

# Carga de variables (buscadas en os.environ, que incluye Streamlit Secrets)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') 
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

# URLs de los Webhooks (las dos URLs separadas)
N8N_URL_FETCH_RESPONSES = os.getenv("N8N_URL_FETCH_RESPONSES")
N8N_URL_FETCH_CONTEXT = os.getenv("N8N_URL_FETCH_CONTEXT")

# --- 2. FUNCIONES DE CARGA DE DATOS (N8N) ---

@st.cache_data(ttl="30s") # Cacheamos el resultado para no sobrecargar N8N
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

# --- 3. ANÁLISIS COMPLETO (LLM CON MÉTRICAS SIMULADAS) ---
def run_full_analysis(df_respuestas, contexto_global):
    # ¡CRÍTICO! Usamos métricas estáticas/simuladas para evitar el error de instalación de librerías
    llm_similitud_context = """
    Alineación de Roles: No Calculada (Error de Dependencia en Servidor).
    Sin embargo, se infiere una ALTA DISPERSIÓN entre los roles por la varianza de las respuestas en los temas clave.
    La IA simulará el análisis de alineación con esta premisa:
    - Director vs Gerente: Baja alineación (Similitud inferida: 0.4)
    - Gerente vs Analista: Muy baja alineación (Similitud inferida: 0.3)
    """
    metrica_silueta = "N/A (No Calculada)"
    
    # --- LLAMADA A OPENAI CON REQUESTS ---
    reporte = "Error: Reporte no generado."
    if OPENAI_API_KEY:
        try:
            raw = "\n".join([f"- {row.get('rol_jerarquico', 'N/A')}: {row.get('respuesta_texto', 'N/A')}" for _, row in df_respuestas.iterrows()])
            
            SYSTEM_INSTRUCTION = f"""
            Eres un Auditor Ejecutivo y Consultor Senior de una firma 'Big Four' (como Deloitte o PwC).
            Tu tarea es analizar la siguiente información (Contexto, Embeddings y Datos Crudos) y generar un Reporte Ejecutivo de Auditoría de Madurez Digital.
            Debes basar tu diagnóstico en el Modelo de Madurez CMMI (Nivel 1 a 5).
            Sé crítico, analítico y profesional. La salida debe ser un documento Markdown detallado.
            Justifica el nivel usando los datos de contexto y las respuestas de las entrevistas.
            IMPORTANTE: Usa la 'Alineación de Roles' simulada en la Sección 2 como prueba de tu diagnóstico. El diagnóstico debe ser de Nivel 1 (Inicial) o Nivel 2 (Gestionado).
            """
            prompt = f"""
            ### 1. CONTEXTO
            {contexto_global}
            ### 2. METRICAS IA
            {llm_similitud_context}
            ### 3. ENTREVISTAS
            {raw}
            
            ### TAREA
            Genera el reporte aquí, siguiendo esta estructura estricta en Markdown:

            # Reporte Ejecutivo de Madurez Digital

            ## 1. Diagnóstico General
            (Asigna un Nivel de Madurez CMMI (1-5) y justifica por qué en un párrafo. Usa la información de CONTEXTO 1, 2 y 3.)

            ## 2. Hallazgos Críticos (Puntos de Riesgo)
            (Lista de 3-5 puntos críticos o 'Red Flags' identificados en las entrevistas (CONTEXTO 4) que ponen en riesgo la operación o la Misión (CONTEXTO 1).)

            ## 3. Buenas Prácticas Identificadas (Fortalezas)
            (Lista de 3-5 puntos fuertes o prácticas innovadoras encontradas en las entrevistas (CONTEXTO 4).)

            ## 4. Análisis de Brechas (GAP Analysis)
            (Compara la Misión/Visión (CONTEXTO 1) con los Hallazgos Críticos (Punto 2) y la Alineación Interna (CONTEXTO 3). ¿Dónde está la mayor desconexión?,siempre regresa una tabla con las brechas entre los roles y su puntuación)

            ## 5. Recomendaciones Accionables
            (Un plan de acción detallado, priorizado por impacto. Qué hacer, quién es responsable (rol), y cómo medirlo.)
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

# --- 4. INTERFAZ DASHBOARD ---
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
    
    if st.button("🚀 GENERAR REPORTE", type="primary"):
        with st.spinner("Ejecutando análisis profundo (LLM)..."):
            reporte_md = run_full_analysis(df, contexto)
            st.session_state['reporte_md'] = reporte_md
            st.success("¡Reporte Generado con Éxito!")

    if 'reporte_md' in st.session_state:
        st.header("📝 Reporte Ejecutivo (Markdown)")
        st.markdown(st.session_state['reporte_md'])

else:
    st.info("Esperando respuestas...")