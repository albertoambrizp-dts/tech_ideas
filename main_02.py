import os
import streamlit as st
import requests
import datetime
from dotenv import load_dotenv
from openai import OpenAI
from prompts import stronger_prompt # Asume que 'stronger_prompt' está correctamente definido

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN DE API ---

# Carga las variables de entorno (API Keys)
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# URL del Webhook de n8n - ¡IMPORTANTE! REEMPLAZA ESTA URL
# Asegúrate de que este es el punto final de tu nodo Webhook en n8n
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# Inicialización de clientes
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# NOTA: client_openai se mantiene aunque solo usemos client_deepseek para el chat por ahora.
# Esto previene errores si tu código usa la clave de OpenAI en otras partes.
client_openai = OpenAI(api_key=OPENAI_API_KEY)
client_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

# Modelos a usar
model_deepseek = "deepseek-chat"


# --- 2. FUNCIONES DE LÓGICA ---

def send_to_n8n(data):
    """Envía los metadatos al Webhook de n8n."""
    if not N8N_WEBHOOK_URL:
        st.error("❌ La URL del Webhook de n8n no está configurada. Por favor, revisa tu archivo .env.")
        return False

    try:
        # Envía los datos como JSON
        response = requests.post(N8N_WEBHOOK_URL, json=data)

        if response.status_code >= 200 and response.status_code < 300:
            st.session_state['metadata_submitted'] = True
            st.success("✅ Metadatos enviados a n8n con éxito. ¡Iniciando el asistente!")
            return True
        else:
            st.error(f"❌ Error al enviar datos a n8n. Código de estado: {response.status_code}")
            st.code(response.text)
            return False

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error de conexión al Webhook: {e}. ¿Está n8n escuchando y la URL es correcta?")
        return False

def show_metadata_form():
    """Muestra el formulario inicial de recolección de metadatos."""
    st.title("🚀 Tech Ideas - Consultora de Ideas de Tecnología")
    st.subheader("Paso 1: Identificación y Metadatos")
    
    # Se crea un formulario para asegurar que la acción solo ocurre al presionar el botón
    with st.form(key='metadata_form', clear_on_submit=False):
        
        # 1. Nombre/ID
        user_id = st.text_input("👤 Nombre / ID", help="Su nombre completo o ID único para seguimiento.")
        
        # 2. Rol Jerárquico
        role_options = ["Director", "Gerente", "Coordinador", "Analista"]
        role = st.selectbox("🎯 Rol Jerárquico", options=role_options)
        
        # 3. Área de Proceso
        area_options = ["Finanzas", "IT", "Ventas", "Marketing", "General"]
        area = st.selectbox("📊 Área de Proceso", options=area_options)

        # Botón de inicio
        submit_button = st.form_submit_button(label='🚀 Comenzar la Sesión')

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
            
            # 2. Enviar a n8n y si es exitoso, reiniciar la aplicación para mostrar el chat
            if send_to_n8n(metadata):
                # Guarda los metadatos en la sesión por si son necesarios más tarde
                st.session_state['user_metadata'] = metadata
                st.session_state['metadata_submitted'] = True
                st.rerun() # Forzar el cambio de estado a la interfaz de chat

def show_chat_interface():
    """Muestra la interfaz de chat principal."""
    st.title("📊 Tech Ideas")
    st.caption(f"Entregamos ideas de tecnología para tu empresa. Rol: {st.session_state['user_metadata']['rol_jerarquico']} - Área: {st.session_state['user_metadata']['area_proceso']}")

    if "messages" not in st.session_state:
        st.session_state["messages"] = [{"role": "assistant", "content": "¿En qué empresa o concepto fundamental te gustaría enfocarte hoy?"}]

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input(placeholder="Escribe tu mensaje aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)
        
        # El primer mensaje es siempre el System Prompt (stronger_prompt) para establecer el rol
        conversation = [{"role": "system", "content": stronger_prompt}] 
        conversation.extend({"role": m["role"], "content":m["content"]} for m in st.session_state.messages)

        with st.chat_message("assistant"):
            stream = client_deepseek.chat.completions.create(
                model=model_deepseek, 
                messages=conversation, 
                stream=True
            )
            response = st.write_stream(stream)

        st.session_state.messages.append({"role": "assistant", "content": response})


# --- 3. LÓGICA PRINCIPAL DE LA APLICACIÓN ---

# Inicializa el estado 'metadata_submitted' si no existe
if 'metadata_submitted' not in st.session_state:
    st.session_state['metadata_submitted'] = False

# Muestra el formulario o el chat, basado en el estado
if st.session_state['metadata_submitted']:
    show_chat_interface()
else:
    show_metadata_form()