import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1) Autenticación de Google Sheets vía st.secrets ---
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

# --- 2) Función para actualizar el registro en la hoja ---
def update_key_status(tag_code: str, assignee: str, return_date=None):
    try:
        client = get_gspread_client()
        ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        sheet = ss.worksheet("Key Register")

        # Leemos cabeceras y datos
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)

        # Encuentra índice de columna Tag y Observation
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1

        # Busca la fila que coincide con tag_code
        row_num = None
        for i, rec in enumerate(records, start=3):
            if rec.get("Tag", "").strip() == tag_code:
                row_num = i
                break
        if row_num is None:
            return f"Clave '{tag_code}' no encontrada."

        # Prepara el texto de Observación
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        obs = assignee
        if return_date:
            obs += f" hasta {return_date.strftime('%Y-%m-%d')}"
        obs += f" | {now}"

        # Actualiza la celda
        sheet.update_cell(row_num, obs_col, obs)
        return f"✅ Registro actualizado en fila {row_num}."
    except Exception as e:
        return f"❌ Error: {e}"

# --- 3) Inicializa state ANTES de crear widgets ---
if "tag_input" not in st.session_state:
    st.session_state["tag_input"] = ""
if "return_date" not in st.session_state:
    st.session_state["return_date"] = None

# --- 4) UI de Streamlit ---
st.title("🔑 Key Register")

# 4.1 Campo de escaneo / entrada de código
tag_code = st.text_input(
    "Escanea o ingresa el código de la llave:",
    key="tag_input"
)

# 4.2 Selector de a quién se asigna
options = ["Returned", "WITH_OWNER", "WITH_GUEST",
           "ALLIAHN", "CAMILO", "CATALINA", "GONZALO",
           "JHONNY", "LUIS", "POL", "STELLA"]
assigned = st.selectbox("Asignar a:", options)

# 4.3 Si es GUEST u OWNER, pide fecha de devolución
return_date = None
if assigned in ("WITH_GUEST", "WITH_OWNER"):
    return_date = st.date_input(
        "Fecha de devolución:",
        key="return_date"
    )

# 4.4 Botón de actualización
if st.button("🔄 Actualizar registro"):
    if not tag_code:
        st.error("Por favor, escanea o ingresa un código válido.")
    else:
        # Determina etiqueta final
        if assigned == "Returned":
            assignee = "Returned"
        elif assigned in ("WITH_GUEST", "WITH_OWNER"):
            assignee = assigned  # podrías transformar a texto amigable si quieres
        else:
            assignee = assigned

        # Llama a la función de update
        result = update_key_status(tag_code.strip(), assignee, return_date)
        if result.startswith("✅"):
            st.success(result)
            # Limpia inputs
            st.session_state["tag_input"] = ""
            st.session_state["return_date"] = None
        else:
            st.error(result)
