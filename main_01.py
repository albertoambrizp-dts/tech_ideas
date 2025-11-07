import os
import streamlit as st

st.title("📊 FinguIA")
st.caption("💰 Inversiones simplificadas.")

prompt = st.chat_input("En qué te puedo ayudar?")
if prompt:
    st.write(f"El usuario ha enviado el siguiente prompt: '{prompt}'")