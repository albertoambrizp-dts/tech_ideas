notebook_ok
# %%
# --- REPORTE DE ANÁLISIS ESTRATÉGICO Y MADUREZ DIGITAL ---
# Este es el Notebook FINAL, depurado y listo para ejecución.

# --- 1. Instalación de Dependencias ---
# Ejecutar esta celda una sola vez en la terminal/notebook:
# !pip install pandas gspread oauth2client google-generativeai sentence-transformers scikit-learn fpdf2 google-search-results python-dotenv

import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import google.generativeai as genai
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity
import json
import os
from fpdf import FPDF
import numpy as np
import http.client
from dotenv import load_dotenv

print("--- Dependencias Cargadas ---")

# %%
# %%
# --- 2. CONFIGURACIÓN DE APIS Y CONEXIONES ---
load_dotenv()

# Carga de variables del .env (corregido para usar el nombre de la variable APP_ID)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
APP_ID = os.getenv('APP_ID') # ¡ID PURO de tu Google Sheet!
SERPER_API_KEY = os.getenv('SERPER_API_KEY')
GOOGLE_SHEETS_JSON_PATH = "credenciales_gsheets.json" 

# Asignamos un ID de respaldo por si el .env falla (usando el ID que ya verificamos)
if not APP_ID:
    APP_ID = "1Pq_qWcIACNw3A5j1Ptjopez3TYkWtLevEd69tSoLIh8"

genai.configure(api_key=GEMINI_API_KEY)
print("--- Claves y APIs configuradas ---")

# %%


# %%
# --- 3. (Agente de Carga de Datos) Cargar Respuestas de la Entrevista ---
print("Cargando respuestas de Google Sheets...")
try:
    # --- FIX CRÍTICO: AUTENTICACIÓN ROBUSTA CON CONTENIDO JSON ---
    # Esto soluciona los errores 404 y de NameError de ServiceAccountCredentials
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    credentials_path = os.path.join(current_dir, GOOGLE_SHEETS_JSON_PATH)

    with open(credentials_path, 'r') as f:
        creds_json_content = json.load(f)

    client = gspread.service_account_from_dict(creds_json_content)
    # --- FIN DEL FIX DE AUTENTICACIÓN ---
    
    # Intenta abrir el archivo con el ID
    spreadsheet = client.open_by_key(APP_ID)
    
    # Verifica que la hoja se llama "Respuestas", si falla, usa la primera hoja
    try:
        sheet = spreadsheet.worksheet('Respuestas')
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.get_worksheet(0) 

    data = sheet.get_all_records()
    df_respuestas = pd.DataFrame(data)

    if len(df_respuestas) == 0:
        raise ValueError("No se encontraron respuestas en Google Sheets. Hoja vacía o cabeceras incorrectas.")
    print(f"✅ Se cargaron {len(df_respuestas)} respuestas.")

except Exception as e:
    if "No such file or directory" in str(e) or "FileNotFoundError" in str(e):
        print(f"¡ERROR CRÍTICO! ARCHIVO DE CREDENCIALES FALTANTE: {e}")
    elif "Spreadsheet not found" in str(e) or "Insufficient Permission" in str(e) or "404" in str(e):
        print(f"¡ERROR CRÍTICO! PERMISOS (404) O APP_ID INCORRECTO: {e}")
    else:
        print(f"¡ERROR CRÍTICO AL CARGAR GOOGLE SHEETS! {e}")
    df_respuestas = pd.DataFrame(columns=['rol_jerarquico', 'respuesta_texto', 'area', 'id_pregunta', 'recomendaciones'])

# %%
df_respuestas

# %%
# --- 4. (Agente de Contexto) Cargar Misión, Visión, KPIs e Industria ---
print("Cargando contexto (Misión/Visión/KPIs/Industria)...")
try:
    # 1. Abrimos el Spreadsheet
    spreadsheet = client.open_by_key(APP_ID)
    
    context_sheet = None
    
    # 2. BÚSQUEDA POR NOMBRE (La forma más robusta)
    try:
        # Intenta 'contexto' (minúsculas)
        context_sheet = spreadsheet.worksheet('contexto') 
        print("Hoja encontrada por nombre: 'contexto'.")
    except gspread.WorksheetNotFound:
        try:
            # Intenta 'Contexto' (capitalizado)
            context_sheet = spreadsheet.worksheet('Contexto') 
            print("Hoja encontrada por nombre: 'Contexto'.")
        except gspread.WorksheetNotFound:
            
            # 3. BÚSQUEDA POR ÍNDICE (Como sugirió el usuario, índice 1)
            try:
                # Intenta la segunda hoja (índice 1)
                context_sheet = spreadsheet.get_worksheet(1)
                print(f"Advertencia: No se encontró por nombre. Usando la hoja en índice 1: '{context_sheet.title}'.")
            except gspread.WorksheetNotFound:
                # Intenta la primera hoja (índice 0) como fallback final
                try:
                    context_sheet = spreadsheet.get_worksheet(0)
                    print(f"Advertencia: No se encontró por nombre. Usando la hoja en índice 0: '{context_sheet.title}'.")
                except Exception as index_e:
                    # Si falla obtener la hoja por índice, levanta la excepción original
                    raise gspread.WorksheetNotFound(f"No se encontró la pestaña 'contexto', 'Contexto' ni en los índices 0 o 1. Error: {index_e}")
            
    
    # 4. PROCESAR LA HOJA ENCONTRADA
    if context_sheet is None:
        raise Exception("Fallo interno al asignar la hoja de contexto.")
            
    context_data = context_sheet.get_all_records()
    
    if not context_data:
        raise ValueError(f"La pestaña '{context_sheet.title}' está vacía o no tiene cabeceras.")

    mision_vision_kpis = context_data[0] # Asume que el contexto está en la primera fila
    
    # Extracción de variables 
    mision = mision_vision_kpis.get('Mision')
    vision = mision_vision_kpis.get('Vision')
    kpis = mision_vision_kpis.get('KPIs_Actuales')
    industria = mision_vision_kpis.get('Industria')
    
    if not mision or not vision or not kpis or not industria:
         # Si falta una columna, levantamos el KeyError para que lo imprima el except principal
         raise KeyError("Falta una de las columnas clave: Mision, Vision, KPIs_Actuales o Industria.")

    # Si todo es exitoso, asignamos los valores finales
    contexto_global = {
        "Mision": mision,
        "Vision": vision,
        "KPIs_Actuales": kpis,
        "Industria": industria
    }
    INDUSTRIA_CLIENTE = contexto_global['Industria']
    
    print("✅ Contexto cargado con éxito.")
         
except Exception as e:
    # ¡ESTE ES EL BLOQUE QUE QUERÍAS! Imprime el error exacto y usa N/A
    print(f"❌ ERROR AL CARGAR CONTEXTO: {e}")
    contexto_global = {
        "Mision": "N/A (Error de Carga)",
        "Vision": "N/A (Error de Carga)",
        "KPIs_Actuales": "N/A (Error de Carga)",
        "Industria": "N/A (Error de Carga)"
    }
    INDUSTRIA_CLIENTE = contexto_global['Industria']

# %%
contexto_global

# %%
# %%
# --- 5. (Diagnóstico de Contexto) Verificar Carga de Variables ---
# Este bloque es la verificación que solicitaste.
print("--- VERIFICACIÓN DE CONTEXTO CARGADO ---")
if not df_respuestas.empty:
    print(f"Columnas de Respuestas: {df_respuestas.columns.tolist()}")
    print(f"Primer Rol Cargado: {df_respuestas.head(1).get('rol_jerarquico', 'N/A').iloc[0]}")
    print("------------------------------------------")

print(f"✅ Industria del Cliente: {contexto_global.get('Industria')}")
print(f"✅ Misión: {contexto_global.get('Mision')}")
print(f"✅ Visión: {contexto_global.get('Vision')}")
print(f"✅ KPIs Actuales: {contexto_global.get('KPIs_Actuales')}")
print("------------------------------------------")

# %%
# %%
# --- 6. (Agente de Contexto) API Externa - Google Search (Serper) ---
print(f"Buscando contexto externo para: {INDUSTRIA_CLIENTE}...")

try:
    # Usamos la conexión HTTP de Python directamente
    conn = http.client.HTTPSConnection("google.serper.dev")
    payload = json.dumps({"q": f"Tendencias y desafíos de {INDUSTRIA_CLIENTE} 2025"})
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    conn.request("POST", "/search", payload, headers)
    res = conn.getresponse()
    data = res.read()
    search_results = json.loads(data.decode("utf-8"))

    contexto_externo = "Tendencias de la Industria:\n"
    if 'organic' in search_results:
        for s in search_results.get('organic', [])[:3]:
            contexto_externo += f"- {s.get('title', 'N/A')}: {s.get('snippet', 'N/A')}\n"
    else:
        contexto_externo = "No se encontró contexto externo relevante."
except Exception as e:
    contexto_externo = f"Error al acceder a Google Search API: {e}. Usando contexto general."

print("Contexto externo cargado.")

# %%
# %%
# --- 7. (Agente de Pre-Análisis) Similitud de Coseno (Word Embeddings) ---
print("Ejecutando Agente de Pre-Análisis (Similitud de Coseno)...")

if not df_respuestas.empty:
    # FIX CRÍTICO: Usamos el modelo más pequeño y estable para evitar el error 401 de Hugging Face
    model_name = 'sentence-transformers/all-MiniLM-L6-v2' 
    model = SentenceTransformer(model_name)
    
    # FIX CRÍTICO: Usamos el nombre de columna correcto: 'rol_jerarquico'
    roles = df_respuestas['rol_jerarquico'].unique() 
    rol_embeddings = {}

    # 7.1 Generar un embedding promedio por ROL
    for rol in roles:
        # FIX CRÍTICO: Usamos las columnas correctas: 'rol_jerarquico' y 'respuesta_texto'
        respuestas_rol = " ".join(df_respuestas[df_respuestas['rol_jerarquico'] == rol]['respuesta_texto'].tolist())
        if respuestas_rol:
            rol_embeddings[rol] = model.encode(respuestas_rol)

    # 7.2 Calcular similitud entre roles
    similitud_context = "Análisis de Alineación (Similitud de Coseno):\n"

    # Pares clave para la alineación estratégica (basado en tus 5 respuestas de valor)
    pairs = [('Director', 'Analista'), ('Gerente', 'Analista'), ('Director', 'Gerente')]

    for rol1, rol2 in pairs:
        if rol1 in rol_embeddings and rol2 in rol_embeddings:
            sim = util.cos_sim(rol_embeddings[rol1], rol_embeddings[rol2])[0][0].item()
            similitud_context += f"- Alineación {rol1} vs. {rol2}: {sim:.2f} (1.0 es alineación perfecta)\n"
            if sim < 0.5:
                similitud_context += f"  - ALERTA: Baja alineación, indica desconexión entre la visión ({rol1}) y la operación ({rol2}).\n"
        else:
            similitud_context += f"- Alineación {rol1} vs. {rol2}: Insuficiente data para calcular.\n"
else:
    similitud_context = "Análisis de Similitud no ejecutado: No hay respuestas de entrevista."

print("Análisis de similitud completado.")
llm_similitud_context = similitud_context

# %%
# %%
# --- 8. (Agente de Reporte LLM) Construcción del Mega-Prompt ---
print("Construyendo Mega-Prompt para el Agente de Reporte...")

respuestas_texto = ""
if not df_respuestas.empty:
    for index, row in df_respuestas.iterrows():
        # Usamos los nombres de columnas verificados
        respuestas_texto += f"- Rol: {row.get('rol_jerarquico', 'N/A')}, Área: {row.get('area', 'N/A')}\n  Pregunta: {row.get('id_pregunta', 'N/A')}\n  Respuesta: {row.get('respuesta_texto', 'N/A')}\n\n"
else:
    respuestas_texto = "No se cargaron datos de entrevista para el análisis."

MODELO_MADUREZ = """
Basado en el CMMI (Capability Maturity Model Integration):
- Nivel 1 (Inicial): Procesos caóticos, reactivos.
- Nivel 2 (Gestionado): Proyectos gestionados, pero aún reactivos.
- Nivel 3 (Definido): Procesos estandarizados y proactivos en toda la organización.
- Nivel 4 (Cuantitativo): Se usan métricas y datos para gestionar procesos.
- Nivel 5 (Optimizado): Mejora continua e innovación (ej. uso de IA).
"""

SYSTEM_INSTRUCTION = f"""
Eres un Auditor Ejecutivo y Consultor Senior de una firma 'Big Four' (como Deloitte o PwC).
Tu tarea es analizar la siguiente información (Contexto, Embeddings y Datos Crudos) y generar un Reporte Ejecutivo de Auditoría de Madurez Digital.
Debes basar tu diagnóstico en el Modelo de Madurez CMMI (Nivel 1 a 5).
Sé crítico, analítico y profesional. La salida debe ser un documento Markdown detallado.
"""

USER_PROMPT = f"""
Por favor, genera el Reporte Ejecutivo de Auditoría de Madurez Digital.

---
### 1. CONTEXTO DE LA EMPRESA
**Industria:** {contexto_global.get('Industria')}
**Misión:** {contexto_global.get('Mision')}
**Visión:** {contexto_global.get('Vision')}
**KPIs Actuales:** {contexto_global.get('KPIs_Actuales')}

---
### 2. CONTEXTO EXTERNO (Google Search)
{contexto_externo}

---
### 3. ANÁLISIS DE ALINEACIÓN INTERNA (Word Embeddings)
{llm_similitud_context}

---
### 4. TRANSCRIPCIÓN DE ENTREVISTAS (Datos Crudos)
{respuestas_texto}

---
### 5. REPORTE EJECUTIVO DE AUDITORÍA (Tu Tarea)
Genera el reporte aquí, siguiendo esta estructura estricta en Markdown:

# Reporte Ejecutivo de Madurez Digital

## 1. Diagnóstico General
(Asigna un Nivel de Madurez CMMI (1-5) y justifica por qué en un párrafo. Usa la información de CONTEXTO 1, 2 y 3.)

## 2. Hallazgos Críticos (Puntos de Riesgo)
(Lista de 3-5 puntos críticos o 'Red Flags' identificados en las entrevistas (CONTEXTO 4) que ponen en riesgo la operación o la Misión (CONTEXTO 1).)

## 3. Buenas Prácticas Identificadas (Fortalezas)
(Lista de 3-5 puntos fuertes o prácticas innovadoras encontradas en las entrevistas (CONTEXTO 4).)

## 4. Análisis de Brechas (GAP Analysis)
(Compara la Misión/Visión (CONTEXTO 1) con los Hallazgos Críticos (Punto 2) y la Alineación Interna (CONTEXTO 3). ¿Dónde está la mayor desconexión?)

## 5. Recomendaciones Accionables
(Un plan de acción detallado, priorizado por impacto. Qué hacer, quién es responsable (rol), y cómo medirlo.)
"""

# %%
# %%
# --- 9. (Agente de Reporte LLM) Ejecución de la Generación ---
print("Llamando al Agente de Reporte LLM (Gemini)... Esto puede tardar.")

if not GEMINI_API_KEY:
    reporte_markdown = "ERROR: La clave GEMINI_API_KEY no está configurada. No se pudo generar el reporte LLM. Por favor, revisa tu archivo .env."
else:
    try:
        model = genai.GenerativeModel(model_name='gemini-2.5-flash',
                                      system_instruction=SYSTEM_INSTRUCTION)
        response = model.generate_content(USER_PROMPT)
        reporte_markdown = response.text
    except Exception as e:
        reporte_markdown = f"ERROR AL LLAMAR A GEMINI: {e}"

print("Reporte en Markdown generado.")

# %%
# %%
# --- 10. (Agente de PDF) Generación del PDF Ejecutivo ---
print("Generando PDF ejecutivo...")

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte Ejecutivo de Madurez Digital', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 16)
        self.set_fill_color(220, 220, 220)
        title_encoded = title.encode('latin-1', 'replace').decode('latin-1')
        self.cell(0, 10, title_encoded, 0, 1, 'L', fill=True)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 11)
        body = body.encode('latin-1', 'replace').decode('latin-1')
        body = body.replace('•', chr(127))
        self.multi_cell(0, 5, body)
        self.ln()

    def add_markdown_content(self, markdown_text):
        lines = markdown_text.split('\n')
        for line in lines:
            if line.startswith('# '):
                if "Reporte Ejecutivo" not in line:
                    self.chapter_title(line[2:])
            elif line.startswith('## '):
                self.chapter_title(line[3:])
            elif line.startswith('### '):
                self.set_font('Arial', 'B', 14)
                self.multi_cell(0, 5, line[4:].encode('latin-1', 'replace').decode('latin-1'))
                self.ln(1)
            elif line.startswith('* ') or line.startswith('- '):
                self.set_font('Arial', '', 11)
                self.multi_cell(0, 5, f'  •  {line[2:]}'.encode('latin-1', 'replace').decode('latin-1'))
                self.ln(1)
            elif line.strip():
                self.chapter_body(line)
            else:
                self.ln(3)

pdf = PDF()
pdf.add_page()
pdf.add_markdown_content(reporte_markdown)

pdf_output_path = "Reporte_Ejecutivo_Madurez.pdf"
try:
    pdf.output(pdf_output_path)
    print(f"\n--- ¡PROCESO COMPLETO! ---")
    print(f"Reporte en PDF guardado como: {pdf_output_path}")
except Exception as e:
    print(f"ERROR AL GUARDAR PDF: {e}")


