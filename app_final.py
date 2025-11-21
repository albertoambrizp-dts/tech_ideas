import os
import streamlit as st
import requests
import datetime
import json
from dotenv import load_dotenv

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Entrevista CMMI", page_icon="🚀", layout="centered")
load_dotenv()

# --- CARGA UNIVERSAL DE VARIABLES (.env O SECRETS DE CLOUD) ---
N8N_URL_FETCH_Q = os.getenv("N8N_URL_FETCH_Q")
N8N_URL_SAVE_A = os.getenv("N8N_URL_SAVE_A")
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID") or "Usuario_Test"

# --- 2. FUNCIÓN DE CONEXIÓN ---
def send_to_n8n(url, data, tipo):
    """Envía datos a n8n con manejo de errores robusto."""
    if not url:
        st.error(f"❌ Error: La URL de {tipo} no está configurada.")
        return None
        
    try:
        response = requests.post(url, json=data, timeout=15)
        if 200 <= response.status_code < 300:
            if response.content:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": "ok"}
            return {"status": "ok"}
        else:
            st.error(f"⚠️ Error del servidor n8n ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión ({tipo}): {e}")
        return None

# --- 3. LÓGICA DE NEGOCIO ---
def normalize_question_keys(question_data):
    normalized = {}
    normalized['ID_Pregunta'] = question_data.get('ID_Pregunta') or question_data.get('id_pregunta') or 'N/A'
    normalized['Texto_Pregunta'] = question_data.get('Texto_Pregunta') or question_data.get('pregunta_texto') or 'Error cargando texto'
    return normalized

def fetch_questions(metadata):
    with st.spinner("🔄 Consultando al Consultor IA (n8n)..."):
        response = send_to_n8n(N8N_URL_FETCH_Q, metadata, "FETCH")
    
    final_list = None
    if response:
        if isinstance(response, list):
            final_list = response
        elif isinstance(response, dict):
            if 'questions' in response:
                final_list = response['questions']
            elif 'id_pregunta' in response or 'ID_Pregunta' in response:
                final_list = [response]
    
    if final_list:
        return [normalize_question_keys(q) for q in final_list]
    
    st.warning("⚠️ No se pudo conectar con n8n. Cargando preguntas de respaldo.")
    return [
        {'ID_Pregunta': 'OFF01', 'Texto_Pregunta': 'Describa el desafío operativo más crítico.'},
        {'ID_Pregunta': 'OFF02', 'Texto_Pregunta': '¿Qué herramientas tecnológicas utiliza?'}
    ]

def save_answer(q_id, answer_text):
    meta = st.session_state.get('user_metadata', {})
    payload = {
        "nombre_id": meta.get('nombre_id', 'Anon'),
        "rol_jerarquico": meta.get('rol_jerarquico', 'N/A'),
        "area_proceso": meta.get('area_proceso', 'N/A'),
        "id_pregunta": q_id,
        "respuesta_texto": answer_text,
        "timestamp_respuesta": datetime.datetime.now().isoformat()
    }
    result = send_to_n8n(N8N_URL_SAVE_A, payload, "SAVE")
    return result is not None

def handle_next_question():
    """Maneja el avance de preguntas."""
    answer = st.session_state.current_answer.strip()
    if len(answer) < 3:
        # Usamos una bandera simple para mostrar el error sin reiniciar
        st.session_state['show_warning'] = True
        return

    idx = st.session_state.current_index
    questions = st.session_state.questions_list
    current_q = questions[idx]
    
    if save_answer(current_q['ID_Pregunta'], answer):
        st.toast("✅ Respuesta guardada correctamente")
        
        # 1. Marcar el avance
        if idx + 1 < len(questions):
            st.session_state.current_index += 1
            st.session_state.current_answer = "" 
        else:
            st.session_state.interview_finished = True
        
        # 2. Forzar un reinicio si el estado cambió
        st.session_state['state_changed'] = True

# --- 4. INTERFAZ ---
def show_metadata_form():
    st.title("🚀 Consultoría Tech Ideas")
    st.subheader("Fase 1: Diagnóstico de Madurez")
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("👤 Su Nombre / ID", value=DEFAULT_USER_ID)
            area = st.selectbox("📊 Área", ["Operaciones", "Tecnología", "Finanzas", "Marketing", "RRHH"])
        with col2:
            role = st.selectbox("🎯 Rol", ["Analista", "Coordinador", "Gerente", "Director"])
        
        if st.form_submit_button("Comenzar Entrevista ➡️", type="primary"):
            if not user_id:
                st.error("Ingrese nombre.")
            else:
                metadata = {"nombre_id": user_id, "rol_jerarquico": role, "area_proceso": area}
                questions = fetch_questions(metadata)
                st.session_state.user_metadata = metadata
                st.session_state.questions_list = questions
                st.session_state.current_index = 0
                st.session_state.interview_started = True
                st.session_state.interview_finished = False
                st.session_state['show_warning'] = False
                st.rerun()

def show_interview_interface():
    questions = st.session_state.questions_list
    idx = st.session_state.current_index
    current_q = questions[idx]
    meta = st.session_state.user_metadata
    
    # Mostrar advertencia si el botón la activó
    if st.session_state.get('show_warning'):
        st.warning("⚠️ Por favor escribe una respuesta más completa.")
        st.session_state['show_warning'] = False # Limpiar la bandera
    
    st.progress((idx + 1) / len(questions), text=f"Pregunta {idx + 1} de {len(questions)}")
    st.caption(f"👤 {meta['nombre_id']} | 🎯 {meta['rol_jerarquico']}")
    st.markdown(f"### 📝 {current_q['Texto_Pregunta']}")
    st.text_area("Su respuesta:", key="current_answer", height=150)
    
    st.button("Guardar y Siguiente ➡️", on_click=handle_next_question, type="primary")

def show_finish_screen():
    st.title("🎉 ¡Entrevista Completada!")
    st.success("Información almacenada exitosamente.")
    if st.button("🔄 Nueva Entrevista"):
        st.session_state.clear()
        st.rerun()

# --- 5. EJECUCIÓN PRINCIPAL Y LÓGICA DE ESTADO ---
if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False
if 'state_changed' not in st.session_state:
    st.session_state['state_changed'] = False
    
# Disparador de reinicio forzado si el estado interno cambió
if st.session_state.state_changed:
    st.session_state.state_changed = False # Limpiar bandera
    st.rerun()

# Lógica de flujo
if st.session_state.get('interview_finished'):
    show_finish_screen()
elif st.session_state.interview_started:
    show_interview_interface()
else:
    show_metadata_form()