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

# Inicialización de clientes (mantener la inicialización si planeas usar IA en el futuro)
client_openai = OpenAI(api_key=OPENAI_API_KEY)
model_openai = "gpt-5-mini"

# --- 2. FUNCIONES DE COMUNICACIÓN CON N8N ---

def send_to_n8n(url, data):
    """Función unificada para enviar datos a n8n."""
    if not url:
        st.error(f"❌ La URL de n8n ({url}) no está configurada. Revisa tu archivo .env.")
        return None

    try:
        response = requests.post(url, json=data)

        if response.status_code >= 200 and response.status_code < 300:
            # Devuelve el cuerpo JSON de la respuesta (necesario para fetch_questions)
            if response.content:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # Retorna éxito si no hay cuerpo JSON (ej. para la función save_answer)
                    return {"status": "success"} 
            return {"status": "success"}

        else:
            st.error(f"❌ Error al enviar datos a n8n. Código: {response.status_code}. Mensaje: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de conexión al Webhook {url}: {e}")
        return None

def fetch_questions(metadata):
    """Llama al Flujo 1 de n8n para obtener la lista de preguntas filtradas."""
    st.info("Buscando preguntas adaptadas a su Rol y Área...")
    
    # Se utiliza la URL específica para la obtención de preguntas
    questions_response = send_to_n8n(N8N_URL_FETCH_Q, metadata)
    
    if questions_response and isinstance(questions_response, list):
        # El Webhook Response de n8n debe devolver una lista de objetos como:
        # [{"ID_Pregunta": "P01", "Texto_Pregunta": "..."}, ...]
        return questions_response
    
    st.error("No se pudo obtener la lista de preguntas de n8n o la respuesta tiene un formato inesperado.")
    # Lista de fallback para pruebas si n8n falla
    return [
        {"ID_Pregunta": "FB01", "Texto_Pregunta": "¿Cuál es su principal desafío operativo actual que cree que la tecnología podría resolver?"},
        {"ID_Pregunta": "FB02", "Texto_Pregunta": "¿Qué tipo de datos considera usted que se pierden o no se aprovechan en su área?"}
    ]

def save_answer(question_id, answer_text):
    """Llama al Flujo 2 de n8n para guardar una respuesta individual."""
    metadata = st.session_state['user_metadata']
    
    answer_data = {
        "nombre_id": metadata['nombre_id'],
        "rol_jerarquico": metadata['rol_jerarquico'],
        "area_proceso": metadata['area_proceso'],
        "id_pregunta": question_id,
        "respuesta_texto": answer_text,
        "timestamp_respuesta": datetime.datetime.now().isoformat()
    }
    
    # Se utiliza la URL específica para el guardado de respuestas
    if send_to_n8n(N8N_URL_SAVE_A, answer_data):
        st.toast(f"✅ Respuesta de {question_id} guardada.", icon="💾")
        return True
    return False

# --- 3. FUNCIONES DE INTERFAZ DE USUARIO ---

def handle_next_question(answer_key):
    """Maneja el click del botón: Guarda la respuesta y avanza al siguiente índice."""
    
    # Obtener la respuesta del input de Streamlit
    user_answer = st.session_state.get(answer_key, "") # Usar .get para evitar KeyError
    current_index = st.session_state['current_question_index']
    
    # Extraer la ID de la pregunta actual
    current_question = st.session_state.questions_list[current_index]
    
    if not user_answer or len(user_answer.strip()) < 5:
        st.warning("Debe proporcionar una respuesta significativa (mínimo 5 caracteres) para continuar.")
        return # No avanzar ni guardar
        
    # 1. GUARDAR LA RESPUESTA CON N8N
    if save_answer(current_question["ID_Pregunta"], user_answer):
        
        # 2. AVANZAR AL SIGUIENTE ÍNDICE
        st.session_state['current_question_index'] += 1
        
        # 3. Limpiar el estado del input para la siguiente pregunta
        st.session_state[answer_key] = ""
        st.rerun() # Recargar la interfaz para mostrar la siguiente pregunta

def finalize_interview():
    """Finaliza el proceso y limpia el estado de la sesión."""
    st.success("✅ ¡Entrevista completada! Gracias por su participación. Los datos han sido registrados.")
    
    # Limpiar estado y volver al formulario inicial
    for key in ['metadata_submitted', 'user_metadata', 'questions_list', 'current_question_index', 'current_answer_input']:
        if key in st.session_state:
            del st.session_state[key]
    
    st.rerun()

def show_interview_interface():
    """Muestra la interfaz de entrevista paso a paso."""
    
    # Inicializar el índice de la pregunta si es la primera vez
    if 'current_question_index' not in st.session_state:
        st.session_state['current_question_index'] = 0
        
    questions = st.session_state.questions_list
    current_index = st.session_state['current_question_index']
    total_questions = len(questions)
    
    metadata = st.session_state['user_metadata']
    
    st.title("💡 Entrevista de Innovación Tecnológica")
    st.caption(f"Pregunta {current_index + 1} de {total_questions} | Rol: {metadata['rol_jerarquico']} | Área: {metadata['area_proceso']}")
    
    # Verificar si hemos llegado al final de las preguntas
    if current_index >= total_questions:
        finalize_interview()
        return

    # Mostrar la pregunta actual
    current_q_data = questions[current_index]
    st.subheader(f"Pregunta: {current_q_data['ID_Pregunta']}")
    # Asume que la columna en Google Sheets se llama 'Texto_Pregunta'
    st.markdown(f"#### {current_q_data['Texto_Pregunta']}") 

    # Input del usuario
    answer_key = "current_answer_input"
    st.text_area(
        "Su Respuesta:", 
        key=answer_key, 
        height=150, 
        help="Proporcione una respuesta detallada que refleje su perspectiva."
    )

    # Botón de Navegación
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
