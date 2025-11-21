import os
import streamlit as st
import requests
import datetime
import json
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv(override=True)

# URLs de N8N (Asegúrate de que sean las de PRODUCCIÓN en tu .env)
N8N_URL_FETCH_Q = os.getenv("N8N_URL_FETCH_Q") 
N8N_URL_SAVE_A = os.getenv("N8N_URL_SAVE_A") 
DEFAULT_USER_ID = os.getenv("DEFAULT_USER_ID", "Usuario_Test")

# --- FUNCIÓN DE CONEXIÓN (CON DEBUG) ---
def send_to_n8n(url, data, tipo):
    print(f"\n[{tipo}] Conectando a: {url}")
    if not url:
        st.error(f"❌ URL de {tipo} no configurada en .env")
        return None
        
    try:
        # Timeout de 10 segundos para que no se quede "pensando" eternamente
        response = requests.post(url, json=data, timeout=10)
        print(f"[{tipo}] Status: {response.status_code}")
        
        if 200 <= response.status_code < 300:
            if response.content:
                return response.json()
            return {"status": "ok"}
        else:
            st.error(f"Error N8N ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"[{tipo}] Error: {e}")
        st.error(f"Error de conexión con N8N: {e}")
        return None

# --- LÓGICA ---
def fetch_questions(metadata):
    st.info("⏳ Obteniendo preguntas de n8n...")
    data = send_to_n8n(N8N_URL_FETCH_Q, metadata, "FETCH")
    
    if data:
        # Manejo flexible de la respuesta de n8n
        questions = []
        if isinstance(data, list): questions = data
        elif isinstance(data, dict) and 'questions' in data: questions = data['questions']
        elif isinstance(data, dict): questions = [data]
        
        # Normalizar claves (ID_Pregunta vs id_pregunta)
        norm_questions = []
        for q in questions:
            new_q = {}
            new_q['ID_Pregunta'] = q.get('ID_Pregunta') or q.get('id_pregunta') or 'N/A'
            new_q['Texto_Pregunta'] = q.get('Texto_Pregunta') or q.get('pregunta_texto') or 'Pregunta sin texto'
            norm_questions.append(new_q)
            
        if norm_questions:
            return norm_questions

    # Fallback solo si falla n8n
    st.warning("⚠️ Usando preguntas de respaldo (Fallo de conexión)")
    return [
        {'ID_Pregunta': 'F1', 'Texto_Pregunta': 'Describa su mayor desafío operativo.'},
        {'ID_Pregunta': 'F2', 'Texto_Pregunta': '¿Qué métricas usa actualmente?'}
    ]

def save_answer(q_id, text):
    meta = st.session_state.get('meta', {})
    payload = {
        "nombre_id": meta.get('id', 'Anon'),
        "rol_jerarquico": meta.get('rol', 'N/A'),
        "area_proceso": meta.get('area', 'N/A'),
        "id_pregunta": q_id,
        "respuesta_texto": text,
        "timestamp": datetime.datetime.now().isoformat()
    }
    
    res = send_to_n8n(N8N_URL_SAVE_A, payload, "SAVE")
    return res is not None

# --- INTERFAZ ---
st.title("🚀 Entrevista Final (Solo N8N)")

if 'questions' not in st.session_state:
    with st.form("inicio"):
        uid = st.text_input("Tu ID/Nombre", value=DEFAULT_USER_ID)
        rol = st.selectbox("Rol", ["Director", "Gerente", "Analista"])
        area = st.selectbox("Área", ["Operaciones", "TI", "Finanzas"])
        if st.form_submit_button("Iniciar Entrevista"):
            meta = {'id': uid, 'rol': rol, 'area': area}
            qs = fetch_questions(meta)
            st.session_state.meta = meta
            st.session_state.questions = qs
            st.session_state.idx = 0
            st.rerun()

else:
    # Mostrar preguntas
    idx = st.session_state.idx
    if idx < len(st.session_state.questions):
        q = st.session_state.questions[idx]
        st.subheader(f"Pregunta {idx+1}: {q['ID_Pregunta']}")
        st.write(q['Texto_Pregunta'])
        
        ans = st.text_area("Respuesta", key=f"ans_{idx}")
        
        if st.button("Guardar y Siguiente ➡️"):
            if save_answer(q['ID_Pregunta'], ans):
                st.toast("Guardado en n8n ✅")
                st.session_state.idx += 1
                st.rerun()
    else:
        st.success("¡Entrevista Finalizada! Gracias.")
        if st.button("Reiniciar"):
            st.session_state.clear()
            st.rerun()