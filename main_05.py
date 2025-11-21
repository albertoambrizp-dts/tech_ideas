import os
import streamlit as st
import requests
import datetime
import json
from dotenv import load_dotenv

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Entrevista CMMI", page_icon="🚀", layout="centered")
load_dotenv(override=True)

# Carga de variables (Asegúrate de que en tu .env sean las de PRODUCCIÓN)
N8N_URL_FETCH_Q = os.getenv("N8N_URL_FETCH_Q") 
N8N_URL_SAVE_A = os.getenv("N8N_URL_SAVE_A") 
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "Usuario_Test")

# --- 2. FUNCIÓN DE CONEXIÓN (LA QUE SÍ FUNCIONA) ---
def send_to_n8n(url, data, tipo):
    """Envía datos a n8n con manejo de errores robusto."""
    print(f"\n[{tipo}] Conectando a: {url}") # Debug en terminal
    
    if not url:
        st.error(f"❌ Error: La URL de {tipo} no está configurada en el .env")
        return None
        
    try:
        # Timeout de 15s para dar tiempo a n8n
        response = requests.post(url, json=data, timeout=15)
        print(f"[{tipo}] Respuesta: {response.status_code}")
        
        if 200 <= response.status_code < 300:
            if response.content:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {"status": "ok", "message": "JSON vacío pero exitoso"}
            return {"status": "ok"}
        else:
            st.error(f"⚠️ Error del servidor n8n ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        st.error(f"❌ Error de conexión ({tipo}): {e}")
        print(f"[{tipo}] Excepción: {e}")
        return None

# --- 3. LÓGICA DE NEGOCIO ---

def normalize_question_keys(question_data):
    """Asegura que las preguntas tengan las llaves correctas pase lo que pase en n8n."""
    normalized = {}
    # Mapeo de posibles nombres de columnas en Excel/n8n
    normalized['ID_Pregunta'] = question_data.get('ID_Pregunta') or question_data.get('id_pregunta') or 'N/A'
    normalized['Texto_Pregunta'] = question_data.get('Texto_Pregunta') or question_data.get('pregunta_texto') or 'Error cargando texto'
    return normalized

def fetch_questions(metadata):
    """Obtiene preguntas filtradas por rol/área desde n8n."""
    with st.spinner("🔄 Consultando al Consultor IA (n8n)..."):
        response = send_to_n8n(N8N_URL_FETCH_Q, metadata, "FETCH")
    
    final_list = None
    if response:
        # N8N puede devolver una lista directa o un objeto con "questions"
        if isinstance(response, list):
            final_list = response
        elif isinstance(response, dict):
            if 'questions' in response:
                final_list = response['questions']
            elif 'id_pregunta' in response or 'ID_Pregunta' in response:
                final_list = [response] # Caso de una sola pregunta
    
    if final_list:
        return [normalize_question_keys(q) for q in final_list]
    
    # Fallback solo si falla la red, para no bloquear la demo
    st.warning("⚠️ No se pudo conectar con n8n. Cargando preguntas de respaldo offline.")
    return [
        {'ID_Pregunta': 'OFF01', 'Texto_Pregunta': 'Describa el desafío operativo más crítico de su día a día.'},
        {'ID_Pregunta': 'OFF02', 'Texto_Pregunta': '¿Qué herramientas tecnológicas utiliza actualmente y qué limitaciones tienen?'},
        {'ID_Pregunta': 'OFF03', 'Texto_Pregunta': 'Si pudiera automatizar un proceso mañana, ¿cuál sería?'}
    ]

def save_answer(q_id, answer_text):
    """Guarda la respuesta en Google Sheets vía n8n."""
    meta = st.session_state.get('user_metadata', {})
    
    payload = {
        "nombre_id": meta.get('nombre_id', 'Anon'),
        "rol_jerarquico": meta.get('rol_jerarquico', 'N/A'),
        "area_proceso": meta.get('area_proceso', 'N/A'),
        "id_pregunta": q_id,
        "respuesta_texto": answer_text,
        "timestamp_respuesta": datetime.datetime.now().isoformat()
    }
    
    # No mostramos spinner aquí para hacerlo sentir más fluido, usamos toast al final
    result = send_to_n8n(N8N_URL_SAVE_A, payload, "SAVE")
    return result is not None

def handle_next_question():
    """Maneja el avance de preguntas."""
    answer = st.session_state.current_answer.strip()
    
    if len(answer) < 3:
        st.warning("⚠️ Por favor escribe una respuesta más completa.")
        return

    idx = st.session_state.current_index
    questions = st.session_state.questions_list
    current_q = questions[idx]
    
    # 1. Guardar
    if save_answer(current_q['ID_Pregunta'], answer):
        st.toast("✅ Respuesta guardada correctamente")
        
        # 2. Avanzar
        if idx + 1 < len(questions):
            st.session_state.current_index += 1
            st.session_state.current_answer = "" # Limpiar input
            st.rerun()
        else:
            st.session_state.interview_finished = True
            st.rerun()

# --- 4. INTERFAZ DE USUARIO (UI) ---

def show_metadata_form():
    """Pantalla 1: Registro."""
    st.title("🚀 Consultoría Tech Ideas")
    st.subheader("Fase 1: Diagnóstico de Madurez")
    st.markdown("---")
    
    with st.form("login_form"):
        col1, col2 = st.columns(2)
        with col1:
            user_id = st.text_input("👤 Su Nombre / ID", value=DEFAULT_USER_ID)
            area = st.selectbox("📊 Área", ["Operaciones", "Tecnología", "Finanzas", "Marketing", "RRHH"])
        with col2:
            role = st.selectbox("🎯 Rol", ["Analista", "Coordinador", "Gerente", "Director"])
            
        st.info("ℹ️ Las preguntas se adaptarán según su Rol y Área.")
        
        submitted = st.form_submit_button("Comenzar Entrevista ➡️", type="primary")
        
        if submitted:
            if not user_id:
                st.error("Por favor ingrese su nombre.")
            else:
                metadata = {"nombre_id": user_id, "rol_jerarquico": role, "area_proceso": area}
                questions = fetch_questions(metadata)
                
                # Inicializar sesión
                st.session_state.user_metadata = metadata
                st.session_state.questions_list = questions
                st.session_state.current_index = 0
                st.session_state.interview_started = True
                st.session_state.interview_finished = False
                st.rerun()

def show_interview_interface():
    """Pantalla 2: Preguntas."""
    questions = st.session_state.questions_list
    idx = st.session_state.current_index
    total = len(questions)
    current_q = questions[idx]
    meta = st.session_state.user_metadata
    
    # Barra de progreso
    progress = (idx + 1) / total
    st.progress(progress, text=f"Pregunta {idx + 1} de {total}")
    
    st.caption(f"👤 {meta['nombre_id']} | 🎯 {meta['rol_jerarquico']} | 📊 {meta['area_proceso']}")
    
    st.markdown(f"### 📝 {current_q['Texto_Pregunta']}")
    st.caption(f"ID: {current_q['ID_Pregunta']}")
    
    st.text_area("Su respuesta:", key="current_answer", height=150, placeholder="Escriba su respuesta aquí...")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        btn_text = "Guardar y Finalizar 🏁" if idx + 1 == total else "Guardar y Siguiente ➡️"
        st.button(btn_text, on_click=handle_next_question, type="primary", use_container_width=True)

def show_finish_screen():
    """Pantalla 3: Final."""
    st.title("🎉 ¡Entrevista Completada!")
    st.success("Todas sus respuestas han sido almacenadas exitosamente en nuestra base de conocimiento.")
    st.markdown("### ¿Qué sigue?")
    st.info("El sistema procesará esta información para generar el **Reporte de Madurez Digital**.")
    
    if st.button("🔄 Iniciar Nueva Entrevista"):
        st.session_state.clear()
        st.rerun()

# --- 5. EJECUCIÓN PRINCIPAL ---

if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False

if st.session_state.get('interview_finished'):
    show_finish_screen()
elif st.session_state.interview_started:
    show_interview_interface()
else:
    show_metadata_form()