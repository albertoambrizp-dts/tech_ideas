import os
import streamlit as st
import requests
import datetime
from dotenv import load_dotenv
from openai import OpenAI
# Importa stronger_prompt, asumiendo que contiene las instrucciones base para la IA
from prompts import stronger_prompt 

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN DE API ---

load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
#DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# URL del Webhook de n8n
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# Inicialización de clientes
#DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

client_openai = OpenAI(api_key=OPENAI_API_KEY)
#client_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

#model_deepseek = "deepseek-chat"
model_openai = "gpt-5-mini"

# --- 2. FUNCIONES DE LÓGICA ---

def send_to_n8n(data):
    """Envía los datos (metadatos o sesión completa) al Webhook de n8n."""
    if not N8N_WEBHOOK_URL:
        st.error("❌ La URL del Webhook de n8n no está configurada. Por favor, revisa tu archivo .env.")
        return False

    try:
        # Envía los datos como JSON
        response = requests.post(N8N_WEBHOOK_URL, json=data)

        if response.status_code >= 200 and response.status_code < 300:
            # st.success se muestra solo en la función de inicio, no aquí
            return True
        else:
            st.error(f"❌ Error al enviar datos a n8n. Código de estado: {response.status_code}")
            st.code(response.text)
            return False

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de conexión al Webhook: {e}. ¿Está n8n escuchando y la URL es correcta?")
        return False

def build_system_prompt():
    """Crea el System Prompt inyectando el rol y área del usuario para contextualizar la IA."""
    metadata = st.session_state['user_metadata']
    rol = metadata.get('rol_jerarquico', 'Usuario')
    area = metadata.get('area_proceso', 'General')
    
    # Asume que stronger_prompt es el prompt base
    base_prompt = stronger_prompt
    
    context_instruction = (
        f"CONTEXTO DE USUARIO: El usuario con el que estás interactuando es un {rol} "
        f"del área de {area}. Asegúrate de adaptar tu tono, terminología y nivel de "
        f"profundidad de las respuestas a su rol y enfoque de área. Tu objetivo es "
        f"generar ideas de tecnología para este perfil, siendo conciso y relevante."
    )
    
    return f"{base_prompt}\n\n{context_instruction}"

def finalize_session():
    """
    Recopila todos los datos de la sesión (metadatos + historial) 
    y los envía a n8n para el análisis final.
    """
    if 'messages' in st.session_state and 'user_metadata' in st.session_state:
        
        # 1. Calcular duración de la sesión
        start_time_str = st.session_state['user_metadata']['timestamp_inicio']
        start_time = datetime.datetime.fromisoformat(start_time_str)
        end_time = datetime.datetime.now()
        duration = str(end_time - start_time)

        # 2. Formatear historial para envío
        formatted_history = []
        for msg in st.session_state.messages:
            formatted_history.append(f"{msg['role'].upper()}: {msg['content']}")
        
        # 3. Ensamblar el paquete de datos final
        final_data = {
            "session_id": st.session_state['user_metadata']['nombre_id'] + "_" + start_time_str,
            "metadata_inicial": st.session_state['user_metadata'],
            "timestamp_fin": end_time.isoformat(),
            "duracion_sesion": duration,
            "historial_completo_texto": "\n---\n".join(formatted_history),
            "historial_completo_json": st.session_state.messages,
            "tipo_evento": "FIN_SESION" # Para n8n
        }
        
        # 4. Enviar a n8n (reutilizamos la misma función)
        if send_to_n8n(final_data):
            st.success("✅ Sesión finalizada y datos enviados a n8n para registro.")
            
            # Limpiar el estado y forzar el regreso al formulario de metadatos
            for key in ['metadata_submitted', 'messages', 'user_metadata']:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.rerun()
        else:
            st.error("❌ Ocurrió un error al intentar enviar los datos finales de la sesión a n8n.")
    else:
        st.warning("La sesión no se ha inicializado correctamente o faltan datos.")


def show_metadata_form():
    """Muestra el formulario inicial de recolección de metadatos."""
    # Título actualizado a "Tech Ideas"
    st.title("🚀 Tech Ideas - Consultora de Ideas de Tecnología")
    st.subheader("Paso 1: Identificate")
    
    with st.form(key='metadata_form', clear_on_submit=False):
        
        user_id = st.text_input("👤 Nombre / ID", key="form_user_id", help="Su nombre completo o ID único para seguimiento.")
        
        # Opciones de rol basadas en tu última entrada
        role_options = ["Director", "Gerente", "Coordinador", "Analista"]
        role = st.selectbox("🎯 Rol Jerárquico", options=role_options, key="form_role")
        
        # Opciones de área basadas en tu última entrada
        area_options = ["Finanzas", "IT", "Ventas", "Marketing", "General"]
        area = st.selectbox("📊 Área de Proceso", options=area_options, key="form_area")

        submit_button = st.form_submit_button(label='🚀 Comenzar la Sesión')

    if submit_button:
        if not user_id:
            st.warning("⚠️ Por favor, ingrese su Nombre/ID para continuar.")
        else:
            # 1. Metadatos iniciales con el tipo de evento
            metadata = {
                "nombre_id": user_id,
                "rol_jerarquico": role,
                "area_proceso": area,
                "timestamp_inicio": datetime.datetime.now().isoformat(),
                "tipo_evento": "INICIO_SESION" # Para que n8n sepa que es el primer evento
            }
            
            # 2. Enviar a n8n. show_metadata_form incluye un st.success en send_to_n8n
            if send_to_n8n(metadata):
                st.session_state['user_metadata'] = metadata
                st.session_state['metadata_submitted'] = True
                st.rerun()

def show_chat_interface():
    """Muestra la interfaz de chat principal."""
    metadata = st.session_state['user_metadata']
    
    st.title("📊 Tech Ideas")
    st.caption(f"Entregamos ideas de tecnología para mejorar tu empresa. Rol: {metadata['rol_jerarquico']} - Área: {metadata['area_proceso']}")

    # Botón para finalizar la sesión
    st.sidebar.button("👋 Finalizar Sesión y Enviar Datos", on_click=finalize_session, type="primary")

    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role": "assistant", "content": "¡Hola! Gracias por tu tiempo, a continuación iniciaremos la entrevista en cuanto me indiques iniciar la entrevista"}]

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input(placeholder="Escribe tu respuesta aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        
        # Obtiene el prompt contextualizado
        system_prompt = build_system_prompt()
        
        # Construye la conversación: System Prompt + Historial
        conversation = [{"role": "system", "content": system_prompt}] 
        conversation.extend({"role": m["role"], "content":m["content"]} for m in st.session_state.messages)

        with st.chat_message("assistant"):
            try:
                stream = client_openai.chat.completions.create(
                    model=model_openai, 
                    messages=conversation, 
                    stream=True
                )
                response = st.write_stream(stream)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.error(f"Error en la llamada a la API de OpenAI: {e}")
                # Eliminar el último mensaje del usuario para evitar un estado huérfano
                st.session_state.messages.pop() 


# --- 3. LÓGICA PRINCIPAL DE LA APLICACIÓN ---

if 'metadata_submitted' not in st.session_state:
    st.session_state['metadata_submitted'] = False

if st.session_state['metadata_submitted']:
    show_chat_interface()
else:
    show_metadata_form()