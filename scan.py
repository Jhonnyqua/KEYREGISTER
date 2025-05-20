import streamlit as st
import gspread
import pandas as pd
import re
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
from google.oauth2.service_account import Credentials

# ————— Autorización a Google Sheets —————
def authorize_gspread():
    creds_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(credentials)

# ————— Actualización en hoja —————
def update_key_status(key_code: str, new_status: str) -> str:
    client = authorize_gspread()
    sheet_id = st.secrets["gcp_service_account"]["spreadsheet_id"]
    sheet = client.open_by_key(sheet_id).worksheet("Key Register")

    # recuperar encabezados y registros
    headers = sheet.row_values(2)
    records = sheet.get_all_records(head=2)

    # ubicar columnas
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"Encabezado faltante: {e}"

    # buscar fila
    row_to_update = next(
        (i + 3 for i, rec in enumerate(records) if rec.get("Tag","").strip() == key_code),
        None
    )
    if not row_to_update:
        return f"Código '{key_code}' no encontrado."

    # actualizar
    sheet.update_cell(row_to_update, obs_col, new_status)
    return f"Fila {row_to_update} actualizada: '{new_status}'."

# ————— Streamlit UI —————
st.set_page_config(page_title="Key Register with Camera", layout="wide")
st.title("🔑 Key Register Scanner")

st.markdown("""
1. **Escanea** el código con la cámara  
2. **Selecciona** a quién asignar  
3. **Actualiza** la hoja en Google Sheets  
""")

# — Cámara ➔ File
img_file = st.camera_input("📷 Escanea el código de barras o QR")

key_code = ""
if img_file:
    # decodificar
    pil_img = Image.open(img_file)
    barcodes = decode(pil_img)
    if barcodes:
        key_code = barcodes[0].data.decode("utf-8")
        st.success(f"Código detectado: **{key_code}**")
    else:
        st.warning("No encontré un código legible. Intenta de nuevo.")

# — Dropdown de asignación
names = ["ALLIAHN","CAMILO","CATALINA","CONTRACTOR","GONZALO","JHONNY","LUIS","POL","STELLA","Returned"]
assigned = st.selectbox("Asignar a:", sorted(names))

if assigned == "CONTRACTOR":
    contractor_name = st.text_input("Nombre del contratista:")
    final_assigned = contractor_name.strip() or "CONTRACTOR"
elif assigned == "Returned":
    final_assigned = ""
else:
    final_assigned = assigned

# — Botón de actualización
if st.button("📝 Actualizar hoja"):
    if not key_code:
        st.error("Primero escanea un código válido.")
    else:
        result = update_key_status(key_code, final_assigned)
        if result.startswith("Fila"):
            st.success(result)
        else:
            st.error(result)
