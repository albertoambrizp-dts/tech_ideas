import json
import os
from unittest.mock import MagicMock

# --- Configuración Simulada de la API ---
# En un entorno real (como n8n), la clave API se cargaría desde un secreto o variable de entorno.
# La función 'fetch' se simula para mostrar la estructura de la llamada.
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent"
API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")

# 1. Definición del Agente Analista (System Instruction)
# Esta es la personalidad de consultor de alto nivel que guiará la respuesta del LLM.
SYSTEM_INSTRUCTION = """
Eres un consultor estratégico senior con experiencia en empresas Tier 1 (ej. Bain & Company, BCG). Tu tarea es tomar un conjunto de respuestas de una entrevista de alto nivel sobre un proceso de negocio e inmediatamente generar un Reporte de Análisis Estratégico en formato Markdown.

El reporte debe ser objetivo, analítico y conciso. La estructura de tu respuesta debe ser ESTRICTAMENTE la siguiente:

# Reporte de Análisis Estratégico
## 1. Resumen Ejecutivo (Executive Summary)
* Un párrafo que sintetiza el desafío, la situación actual y la principal recomendación.

## 2. Diagnóstico Situacional (Situational Diagnosis)
### 2.1 Fortalezas y Oportunidades (SWOT - Internas)
* Identifica las capacidades internas y los factores de éxito mencionados.
### 2.2 Debilidades y Amenazas (SWOT - Externas/Riesgos)
* Identifica los 'pain points', las ineficiencias o los riesgos explícitos.

## 3. Análisis de Brechas (Gap Analysis)
* Identifica la brecha principal entre la 'Visión Declarada' y la 'Realidad Operativa' descrita.

## 4. Recomendaciones Estratégicas (Strategic Recommendations)
* Tres (3) recomendaciones específicas y accionables, cada una justificada por los datos de la entrevista.

## 5. KPIs Sugeridos (Suggested KPIs)
* Tres (3) métricas clave para monitorear el éxito de las recomendaciones.
"""

# 2. Datos de Entrada (JSON de la entrevista, ya estructurado por Flow 2)
# En n8n, este sería el JSON que sale del nodo que recoge los datos de la entrevista.
MOCK_INTERVIEW_DATA = {
  "entrevistado": "Director de Operaciones",
  "rol": "Director",
  "fecha": "2025-11-15",
  "proceso": "Gestión del Ciclo de Pedido (Order-to-Cash)",
  "respuestas": [
    {
      "pregunta": "¿Cuál es la visión a 5 años para su principal proceso de negocio?",
      "respuesta": "La visión es reducir nuestro tiempo de ciclo de 30 días a solo 7, logrando una automatización del 90% y eliminando el 75% de los errores manuales."
    },
    {
      "pregunta": "¿Cuáles son los tres principales obstáculos o 'pain points' actuales?",
      "respuesta": "El obstáculo principal es la dependencia de una herramienta Legacy (ERP de 1998) que no tiene API para integraciones. El segundo es la falta de estandarización en los datos de entrada por parte de los equipos comerciales. El tercero es la alta rotación del personal que maneja los datos, obligando a constantes reentrenamientos."
    },
    {
      "pregunta": "¿Qué recursos o inversiones serían cruciales para alcanzar su visión?",
      "respuesta": "Necesitamos un presupuesto de $500k para migrar a un nuevo sistema de gestión de recursos y un equipo dedicado de 3 personas (Analista de Negocio, Desarrollador de Integración, y un QA) por al menos 12 meses."
    }
  ]
}

# 3. Construcción del Query (User Prompt)
# La instrucción final al LLM, incluyendo los datos de la entrevista.
USER_QUERY = f"""
Genera el Reporte de Análisis Estratégico basado en los siguientes datos de la entrevista.
Asegúrate de seguir estrictamente la estructura de Markdown y las secciones definidas en tu System Instruction.

--- DATOS DE LA ENTREVISTA ---
{json.dumps(MOCK_INTERVIEW_DATA, indent=2, ensure_ascii=False)}
--- FIN DE DATOS ---
"""

# 4. Simulación de la Llamada a la API (Ejecución del Agente)
def run_analysis_agent():
    """Simula la ejecución del agente, enviando el System Prompt y el User Query."""

    print("--- 1. SYSTEM INSTRUCTION DEL AGENTE ANALISTA ---")
    print(SYSTEM_INSTRUCTION)
    print("\n--- 2. USER QUERY (Instrucción + Datos) ---")
    print(USER_QUERY)
    
    # Payload que se enviaría a la API de Gemini
    payload = {
        "contents": [{"parts": [{"text": USER_QUERY}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
    }
    
    # En un entorno real, aquí se haría la llamada 'fetch'
    # response = fetch(API_URL, method='POST', headers={'Content-Type': 'application/json'}, body=json.dumps(payload))
    
    print("\n--- 3. RESULTADO SIMULADO (Output del LLM) ---\n")
    
    # Resultado simulado para mostrar el formato esperado
    mock_response_text = """
# Reporte de Análisis Estratégico

## 1. Resumen Ejecutivo (Executive Summary)
La Dirección de Operaciones se enfrenta a una brecha crítica entre su visión de eficiencia de 7 días y su dependencia actual de un sistema ERP obsoleto y procesos de entrada de datos no estandarizados. La recomendación clave es priorizar la inversión de $500k en la migración del ERP y la formación de un equipo de integración dedicado para desbloquear una automatización del 90% y mitigar los riesgos de errores manuales y alta rotación.

## 2. Diagnóstico Situacional (Situational Diagnosis)
### 2.1 Fortalezas y Oportunidades (SWOT - Internas)
* **Visión Clara y Medible:** El director tiene una meta muy específica de reducción de ciclo (de 30 a 7 días) y automatización (90%), lo que facilita la planificación del proyecto.
* **Conciencia de Recursos:** Existe claridad sobre la necesidad de inversión ($500k) y el equipo técnico requerido (3 roles especializados).

### 2.2 Debilidades y Amenazas (SWOT - Externas/Riesgos)
* **Debilidad Crítica (ERP Legacy):** La dependencia del ERP de 1998 sin API es el principal cuello de botella que impide cualquier integración moderna o automatización avanzada.
* **Amenaza Operativa (Datos):** La falta de estandarización en los datos de entrada por parte de los equipos comerciales introduce errores que deben corregirse manualmente.
* **Riesgo de Talento:** La alta rotación de personal aumenta los costos de reentrenamiento y compromete la calidad de los datos.

## 3. Análisis de Brechas (Gap Analysis)
La brecha principal reside en la **Capacidad Tecnológica vs. Ambición de Automatización**. La visión del 90% de automatización es inalcanzable con el actual sistema ERP sin API. El 100% de la inversión y el esfuerzo debe dirigirse primero a modernizar la infraestructura tecnológica antes de poder abordar la estandarización de datos y la automatización de procesos.

## 4. Recomendaciones Estratégicas (Strategic Recommendations)
1.  **Migración Prioritaria del Core:** Asignar el presupuesto de $500k para la migración del ERP en los próximos 12 meses. Esta acción eliminará el principal riesgo tecnológico y permitirá las integraciones necesarias.
2.  **Creación de un Data Gatekeeper:** Implementar un proceso (y potencialmente una herramienta simple) de validación de datos de entrada obligatoria para los equipos comerciales, estandarizando los campos y formatos antes de que el pedido entre en el sistema principal.
3.  **Programa de Especialización Interna:** Desarrollar un programa de retención y especialización para el personal operativo, ofreciendo certificaciones y mejoras salariales para mitigar la alta rotación y proteger la inversión en entrenamiento.

## 5. KPIs Sugeridos (Suggested KPIs)
1.  **KPI de Progreso (Recomendación 1):** Porcentaje de Avance en la Migración del ERP (Meta: 100% en 12 meses).
2.  **KPI de Calidad (Recomendación 2):** Tasa de Error de Datos de Entrada (Meta: Reducción del 75% en 6 meses).
3.  **KPI de Eficiencia (General):** Tiempo Promedio del Ciclo de Pedido (Meta: 7 días al finalizar el proyecto).
    """
    
    print(mock_response_text)
    print("--------------------------------------------------")

if __name__ == "__main__":
    run_analysis_agent()