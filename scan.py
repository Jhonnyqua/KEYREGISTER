import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ========================
# Función para autorizar gspread usando credenciales desde un archivo (ruta absoluta)
# ========================
def authorize_gspread():
    # Reemplaza esta ruta con la ubicación completa de tu archivo de credenciales JSON
    credenciales_path = r"C:\Users\jhonn\OneDrive\Documents\bedspoke\key register\credenciales.json"
    credentials = Credentials.from_service_account_file(
        credenciales_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    client = gspread.authorize(credentials)
    return client

# ========================
# Función para actualizar el registro de una llave en Google Sheets
# ========================
def update_key_status(key_code, new_status):
    try:
        client = authorize_gspread()
    except Exception as e:
        return f"Error al autorizar gspread: {e}"
    
    # Reemplaza con el ID de tu Google Sheet (extraído de la URL)
    spreadsheet_id = "1AEX3jKwAdO5cROqTe6k4uNv7BCy7lPOKHrGQjZA3om0"
    
    try:
        # Abre la hoja "Key Register"
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
    except Exception as e:
        return f"Error al abrir la hoja 'Key Register': {e}"
    
    try:
        # Asumimos que la fila 2 tiene los encabezados
        headers = sheet.row_values(2)
        # Se obtienen los registros, indicando que la fila 2 son los encabezados
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return f"Error al obtener los datos de la hoja: {e}"
    
    # Buscamos la columna "Tag" (índice 1-based)
    try:
        tag_index = headers.index("Tag") + 1
    except ValueError:
        return "No se encontró la columna 'Tag' en la hoja."
    
    # Buscamos la fila cuyo valor en "Tag" coincide con el código ingresado.
    # Dado que la fila 1 es el título y la 2 son los encabezados, los datos comienzan en la fila 3.
    row_number = None
    for i, record in enumerate(records, start=3):
        if record.get("Tag", "").strip() == key_code:
            row_number = i
            break

    if row_number is None:
        return f"No se encontró la llave con código '{key_code}'."
    
    # Buscamos la columna "Observation"
    try:
        obs_index = headers.index("Observation") + 1
    except ValueError:
        return "No se encontró la columna 'Observation' en la hoja."
    
    try:
        sheet.update_cell(row_number, obs_index, new_status)
        return f"Registro actualizado correctamente en la fila {row_number}."
    except Exception as e:
        return f"Error al actualizar la celda: {e}"

# ========================
# Interfaz visual con Streamlit
# ========================
st.title("Actualización de Llaves M")
st.markdown("Ingrese el código de la llave y el nombre de la persona que la toma (déjelo en blanco para devolverla).")

# Campo para ingresar o escanear el código de la llave
key_code = st.text_input("Código de la llave (ej. M001):")
# Campo para ingresar el nombre del usuario
new_status = st.text_input("Nombre del usuario (déjelo en blanco si se devuelve):")

if st.button("Actualizar registro"):
    if not key_code:
        st.error("Debe ingresar el código de la llave.")
    else:
        result = update_key_status(key_code, new_status)
        if "Error" in result or "No se encontró" in result:
            st.error(result)
        else:
            st.success(result)
