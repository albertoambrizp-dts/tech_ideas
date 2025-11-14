import os
import streamlit as st
import requests
import datetime
import json
from dotenv import load_dotenv
from openai import OpenAI 

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Webhooks de n8n - CRÍTICO: Necesitas estas dos URLs en tu .env
N8N_URL_FETCH_Q = os.getenv("N8N_URL_FETCH_Q") # Para obtener preguntas
N8N_URL_SAVE_A = os.getenv("N8N_URL_SAVE_A")   # Para guardar respuestas

# ID de usuario por defecto para pruebas
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "TEST_USER_A")

# Inicialización de clientes 
client_openai = OpenAI(api_key=OPENAI_API_KEY)
model_openai = "gpt-5-mini"

# Lista de Fallback (3 preguntas) - USADA si n8n falla o devuelve 1 pregunta.
FALLBACK_QUESTIONS = [
    {"ID_Pregunta": "FB01", "Texto_Pregunta": "¿Cuál es su principal desafío operativo actual que cree que la tecnología podría resolver?"},
    {"ID_Pregunta": "FB02", "Texto_Pregunta": "¿Qué tipo de datos considera usted que se pierden o no se aprovechan en su área?"},
    {"ID_Pregunta": "FB03", "Texto_Pregunta": "¿Qué métricas considera esenciales para medir el éxito de la transformación digital?"}
]

# --- 2. FUNCIONES DE COMUNICACIÓN Y NORMALIZACIÓN (N8N) ---

def send_to_n8n(url_variable_name, url, data):
    """Función unificada para enviar datos a n8n, incluyendo verificación de URL y manejo de errores."""
    
    response_data = None
    
    # === PUNTO DE DIAGNÓSTICO DE CONEXIÓN CRÍTICO ===
    print(f"\n--- DEBUG: INTENTANDO CONECTAR A {url_variable_name} ---")
    print(f"URL cargada: {url}")
    print("---------------------------------------------------\n")
    
    # 1. VERIFICACIÓN DE URL: Estricto control de URLs placeholder.
    if not url or "<Webhook URL" in url:
        error_message = f"La URL para la variable `{url_variable_name}` es inválida o aún contiene el placeholder."
        st.error(f"❌ CONFIGURACIÓN CRÍTICA FALLIDA: {error_message}")
        st.caption("Verifica el archivo `.env`. Asegúrate de que las URLs de n8n estén **CORRECTAS y en modo Production**.")
        return None

    try:
        response = requests.post(url, json=data, timeout=10) 

        if response.status_code >= 200 and response.status_code < 300:
            if response.content:
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {"status": "success"} 
            else:
                response_data = {"status": "success"}

        else:
            # Muestra el error de n8n (HTTP 4xx/5xx)
            st.error(f"❌ Error de n8n en `{url_variable_name}`. Código: {response.status_code}. Mensaje: {response.text[:200]}...")
            
    except requests.exceptions.RequestException as e:
        # Muestra el error de conexión (sin servicio, timeout, etc.)
        st.error(f"❌ Error de conexión al Webhook `{url_variable_name}`: {e}. Asegúrate de que el servidor de n8n esté activo y la URL sea accesible.")
    
    return response_data

def normalize_question_keys(question_data):
    """
    Normaliza las claves de las preguntas de snake_case (n8n) a PascalCase (app).
    """
    key_mapping = {
        'id_pregunta': 'ID_Pregunta',
        'pregunta_texto': 'Texto_Pregunta',
    }
    
    normalized = {}
    for old_key, new_key in key_mapping.items():
        if old_key in question_data:
            normalized[new_key] = question_data[old_key]
        elif new_key in question_data: 
            normalized[new_key] = question_data[new_key]
        else:
            normalized[new_key] = 'N/A' 
            
    return {**question_data, **normalized}


def fetch_questions(metadata):
    """Llama al Flujo 1 de n8n para obtener la lista de preguntas filtradas."""
    st.info("Buscando preguntas adaptadas a su Rol y Área...")
    
    questions_response = send_to_n8n("N8N_URL_FETCH_Q", N8N_URL_FETCH_Q, metadata)
    
    # ================================================
    # === DIAGNÓSTICO 1: JSON recibido sin procesar (se imprime en la terminal) ===
    print("\n--- DIAGNÓSTICO 1: JSON RECIBIDO DE N8N (Raw) ---")
    print(questions_response) 
    print("----------------------------------------------------------\n")
    # ====================================================================
    
    final_list = None

    if questions_response:
        # Lógica de extracción de la lista de preguntas
        if isinstance(questions_response, list) and questions_response and isinstance(questions_response[0], dict):
            final_list = questions_response
        elif isinstance(questions_response, dict):
            if 'questions' in questions_response and isinstance(questions_response['questions'], list):
                final_list = questions_response['questions']
            elif 'id_pregunta' in questions_response or 'ID_Pregunta' in questions_response:
                final_list = [questions_response] 

    if final_list:
        normalized_list = [normalize_question_keys(q) for q in final_list]
        
        # ====================================================================
        # === DIAGNÓSTICO 2: Lista después de la normalización (se imprime en la terminal) ===
        print("--- DIAGNÓSTICO 2: LISTA NORMALIZADA Y FINAL ---")
        print(normalized_list)
        print("------------------------------------------------\n")
        # ====================================================================

        if normalized_list and all(q.get('ID_Pregunta') != 'N/A' for q in normalized_list):
            
            if len(normalized_list) < 2:
                st.warning("⚠️ n8n devolvió solo 1 pregunta. Usando lista de Fallback para pruebas de navegación.")
                return FALLBACK_QUESTIONS
            
            st.success(f"✅ Se cargaron {len(normalized_list)} preguntas exitosamente.")
            return normalized_list
        else:
            st.error("⚠️ Error de Normalización: Claves faltantes en la respuesta de n8n. Usando Fallback.")
            return FALLBACK_QUESTIONS
    
    st.error("❌ No se pudo obtener la lista de preguntas de n8n. Usando la lista de Fallback (3 preguntas).")
    return FALLBACK_QUESTIONS 

def save_answer(question_id, answer_text):
    """Llama al Flujo 2 de n8n para guardar una respuesta individual."""
    metadata = st.session_state.get('user_metadata', {})
    
    answer_data = {
        "nombre_id": metadata.get('nombre_id', 'N/A'),
        "rol_jerarquico": metadata.get('rol_jerarquico', 'N/A'),
        "area_proceso": metadata.get('area_proceso', 'N/A'),
        "id_pregunta": question_id,
        "respuesta_texto": answer_text,
        "timestamp_respuesta": datetime.datetime.now().isoformat()
    }
    
    # Guarda la respuesta. Retorna True solo si send_to_n8n no devuelve None.
    if send_to_n8n("N8N_URL_SAVE_A", N8N_URL_SAVE_A, answer_data):
        st.toast(f"✅ Respuesta de {question_id} guardada.", icon="💾")
        return True
    
    st.warning("⚠️ Error al guardar la respuesta. La aplicación NO avanzará. Revise su consola y el historial de ejecución de n8n.")
    return False

# --- 3. FUNCIONES DE INTERFAZ DE USUARIO ---

def handle_next_question(answer_key):
    """Maneja el click del botón: Guarda la respuesta y avanza al siguiente índice."""
    
    user_answer = st.session_state.get(answer_key, "")
    
    if not user_answer or len(user_answer.strip()) < 5:
        st.warning("Debe proporcionar una respuesta significativa (mínimo 5 caracteres) para continuar.")
        return 
        
    current_index = st.session_state['current_question_index']
    current_question = st.session_state.questions_list[current_index]
    question_id_to_save = current_question.get("ID_Pregunta") 
    
    # 1. INTENTAR GUARDAR LA RESPUESTA CON N8N
    if question_id_to_save and save_answer(question_id_to_save, user_answer):
        
        # 2. AVANZAR AL SIGUIENTE ÍNDICE O FINALIZAR
        if (current_index + 1) < len(st.session_state.questions_list):
            st.session_state['current_question_index'] += 1
            st.session_state[answer_key] = "" 
            st.rerun()
        else:
            finalize_interview() 

def finalize_interview():
    """Finaliza el proceso y limpia el estado de la sesión."""
    st.success("✅ ¡Entrevista completada! Gracias por su participación.")
    
    # Limpiar estado y volver al formulario inicial
    for key in ['metadata_submitted', 'user_metadata', 'questions_list', 'current_question_index', 'current_answer_input']:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

def show_interview_interface():
    """Muestra la interfaz de entrevista paso a paso."""
    
    if 'current_question_index' not in st.session_state:
        st.session_state['current_question_index'] = 0
        
    questions = st.session_state.questions_list
    current_index = st.session_state['current_question_index']
    total_questions = len(questions)
    
    metadata = st.session_state.get('user_metadata', {'rol_jerarquico': 'N/A', 'area_proceso': 'N/A'})
    
    st.title("💡 Entrevista de Innovación Tecnológica")
    st.caption(f"Pregunta {current_index + 1} de {total_questions} | Rol: {metadata['rol_jerarquico']} | Área: {metadata['area_proceso']}")
    
    if current_index >= total_questions:
        finalize_interview()
        return

    current_q_data = questions[current_index]
    
    st.subheader(f"Pregunta: {current_q_data.get('ID_Pregunta', 'N/A')}")
    st.markdown(f"#### {current_q_data.get('Texto_Pregunta', 'Error al cargar el texto de la pregunta.')}") 

    answer_key = "current_answer_input"
    st.text_area(
        "Su Respuesta:", 
        key=answer_key, 
        height=150, 
        value=st.session_state.get(answer_key, ""), 
        help="Proporcione una respuesta detallada que refleje su perspectiva."
    )

    if current_index < total_questions - 1:
        st.button(
            "Guardar Respuesta y Siguiente ➡️", 
            on_click=handle_next_question, 
            args=(answer_key,),
            type="primary"
        )
    else:
        st.button(
            "Finalizar Entrevista y Guardar Última Respuesta ✅", 
            on_click=handle_next_question, 
            args=(answer_key,),
            type="secondary"
        )
        st.button(
            "Terminar sin Guardar Última Respuesta ❌",
            on_click=finalize_interview,
            help="Solo presione si desea salir sin guardar la respuesta actual."
        )


def show_metadata_form():
    """Muestra el formulario inicial de recolección de metadatos."""
    st.title("🚀 Tech Ideas - Consultora de Ideas de Tecnología")
    st.subheader("Paso 1: Identificate")
    
    with st.form(key='metadata_form', clear_on_submit=False):
        
        user_id = st.text_input("👤 Nombre / ID", key="form_user_id", value=DEFAULT_USER_ID, help="Su nombre completo o ID único para seguimiento.")
        
        role_options = ["Director", "Gerente", "Coordinador", "Analista"]
        role = st.selectbox("🎯 Rol Jerárquico", options=role_options, key="form_role")
        
        area_options = ["Finanzas", "IT", "Ventas", "Marketing", "General"]
        area = st.selectbox("📊 Área de Proceso", options=area_options, key="form_area")

        submit_button = st.form_submit_button(label='🚀 Comenzar la Entrevista')

    if submit_button:
        if not user_id:
            st.warning("⚠️ Por favor, ingrese su Nombre/ID para continuar.")
        else:
            metadata = {
                "nombre_id": user_id,
                "rol_jerarquico": role,
                "area_proceso": area,
                "timestamp_inicio": datetime.datetime.now().isoformat()
            }
            
            # 1. OBTENER LAS PREGUNTAS FILTRADAS DE N8N
            questions_list = fetch_questions(metadata)
            
            if questions_list:
                # 2. Guardar estado y cambiar de interfaz
                st.session_state['user_metadata'] = metadata
                st.session_state['questions_list'] = questions_list
                st.session_state['metadata_submitted'] = True
                st.session_state['current_question_index'] = 0
                st.rerun()


# --- 4. LÓGICA PRINCIPAL DE LA APLICACIÓN ---

if 'metadata_submitted' not in st.session_state:
    st.session_state['metadata_submitted'] = False

if st.session_state['metadata_submitted']:
    show_interview_interface()
else:
    show_metadata_form()
