# app.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ------------ CONFIGURACIÓN DE SECRETS  ------------
# En tu .streamlit/secrets.toml deberías tener:
#
# [gcp_service_account]
# type = "service_account"
# project_id = "..."
# private_key_id = "..."
# private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
# client_email = "..."
# client_id = "..."
# auth_uri = "..."
# token_uri = "..."
# auth_provider_x509_cert_url = "..."
# client_x509_cert_url = "..."
# spreadsheet_id = "TU_SPREADSHEET_ID"
#
# ----------------------------------------------------

@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

def update_key_status(tag_code: str, new_observation: str) -> str:
    client = get_gspread_client()
    ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
    try:
        sheet = ss.worksheet("Key Register")
    except Exception as e:
        return f"❌ No pude abrir la hoja 'Key Register': {e}"

    # lee encabezados en fila 2
    headers = sheet.row_values(2)
    try:
        idx_tag = headers.index("Tag") + 1
        idx_obs = headers.index("Observation") + 1
    except ValueError as ve:
        return f"❌ No encuentro columna {ve}"

    # busca fila donde Tag == tag_code
    records = sheet.get_all_records(head=2)  # retorna dicts de fila 3 en adelante
    target_row = None
    for i, rec in enumerate(records, start=3):
        if str(rec.get("Tag","")).strip() == tag_code:
            target_row = i
            break

    if target_row is None:
        return f"❌ Tag '{tag_code}' no encontrado."

    # actualiza
    try:
        sheet.update_cell(target_row, idx_obs, new_observation)
        return f"✅ Registro actualizado en fila {target_row}."
    except Exception as e:
        return f"❌ Error al actualizar: {e}"

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Key Register", layout="centered")
st.title("🔑 Key Register Automático")
st.markdown(
    """
Escanea un código con tu lector **HID** directamente en el campo, selecciona a quién asignar  
ó marca **Returned** para liberar la llave.
""")

with st.form("form_update"):
    tag = st.text_input(
        "Escanea aquí tu Tag",
        placeholder="Ej: M001",
        key="tag_input",
        help="El lector tecleará el código y enviará el ENTER automáticamente."
    )
    # selecciona asignación
    choice = st.selectbox(
        "Asignar a:",
        ["ALLIAHN","CAMILO","CATALINA","GONZALO","JHONNY","LUIS","POL","STELLA","CONTRACTOR","Returned"],
        help="Elige 'Returned' para liberar (limpia Observation)"
    )
    # si es contractor pide nombre
    if choice == "CONTRACTOR":
        contractor = st.text_input("Nombre del contractor:")
        final_assignee = contractor.strip() or "CONTRACTOR"
    elif choice == "Returned":
        final_assignee = ""
    else:
        final_assignee = choice

    submitted = st.form_submit_button("Actualizar registro")
    if submitted:
        if not tag.strip():
            st.error("🔴 Por favor escanea un Tag válido.")
        else:
            result = update_key_status(tag.strip(), final_assignee)
            if result.startswith("✅"):
                st.success(result)
                # Después de un éxito, limpio campo
                st.session_state["tag_input"] = ""
            else:
                st.error(result)
