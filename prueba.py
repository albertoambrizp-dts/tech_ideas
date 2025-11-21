import streamlit as st
import requests

# --- CONFIGURACIÓN MANUAL (Sin .env) ---
# Pega aquí tu URL de PRODUCCIÓN de N8N (la que termina en /respuestas)
# Asegúrate de que sea la correcta y esté entre comillas.
URL_N8N_SAVE = "https://albertampa07.app.n8n.cloud/webhook/respuestas" 

st.title("🛠️ Prueba de Fuego: Conexión Directa")
st.write(f"Intentando conectar a: `{URL_N8N_SAVE}`")

# Formulario simple
texto = st.text_input("Escribe algo para guardar:", "Prueba desde Streamlit Directo")

if st.button("🔥 ENVIAR A N8N AHORA"):
    if "PEGA_AQUI" in URL_N8N_SAVE:
        st.error("¡No pegaste la URL en el código! Edita el archivo prueba_directa.py")
    else:
        try:
            st.info("Enviando...")
            payload = {
                "id_pregunta": "TEST_DIRECTO",
                "respuesta_texto": texto,
                "origen": "Streamlit sin .env"
            }
            
            # Hacemos el POST
            response = requests.post(URL_N8N_SAVE, json=payload, timeout=10)
            
            st.write(f"**Status Code:** {response.status_code}")
            
            if 200 <= response.status_code < 300:
                st.success("✅ ¡ÉXITO! Se envió correctamente.")
                st.balloons()
                st.write("Respuesta del servidor:", response.text)
            else:
                st.error(f"❌ Error del servidor: {response.text}")
                
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")