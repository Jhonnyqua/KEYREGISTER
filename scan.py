import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

def authorize_gspread():
    """
    Autoriza a gspread utilizando las credenciales almacenadas en st.secrets.
    Asegúrate de haber configurado los secrets en Streamlit Cloud (o localmente en .streamlit/secrets.toml).
    """
    creds_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)
    return client

def update_key_status(key_code, new_status):
    """
    Busca en la hoja "Key Register" la fila en la que el valor de la columna "Tag" coincide con key_code,
    y actualiza la celda de la columna "Observation" con new_status.
    Se asume que:
      - La fila 2 contiene los encabezados.
      - Los datos comienzan en la fila 3.
    """
    try:
        client = authorize_gspread()
    except Exception as e:
        return f"Error al autorizar gspread: {e}"
    
    # Obtener el ID del spreadsheet desde st.secrets o usar uno por defecto
    spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "TU_SPREADSHEET_ID")
    
    try:
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
    except Exception as e:
        return f"Error al abrir la hoja 'Key Register': {e}"
    
    try:
        # La fila 2 es la de encabezados
        headers = sheet.row_values(2)
        # Obtén todos los registros, interpretando la fila 2 como encabezados
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return f"Error al obtener los datos de la hoja: {e}"
    
    # Buscar la columna "Tag"
    try:
        tag_index = headers.index("Tag") + 1  # Conversión a índice 1-based
    except ValueError:
        return "No se encontró la columna 'Tag' en la hoja."
    
    # Buscar la fila cuyo valor en "Tag" coincida con key_code
    row_number = None
    for i, record in enumerate(records, start=3):  # Los datos empiezan en la fila 3
        if record.get("Tag", "").strip() == key_code:
            row_number = i
            break

    if row_number is None:
        return f"No se encontró la llave con código '{key_code}'."
    
    # Buscar la columna "Observation"
    try:
        obs_index = headers.index("Observation") + 1
    except ValueError:
        return "No se encontró la columna 'Observation' en la hoja."
    
    try:
        # Actualiza la celda con el nuevo valor (si new_status es vacío, la celda se dejará en blanco)
        sheet.update_cell(row_number, obs_index, new_status)
        return f"Registro actualizado correctamente en la fila {row_number}."
    except Exception as e:
        return f"Error al actualizar la celda: {e}"

# INTERFAZ CON STREAMLIT
st.title("Actualización de Llaves M")
st.markdown("Ingresa el código de la llave y el nuevo valor para la columna **Observation** (deja en blanco si se devuelve la llave).")

# Campo para el código de la llave (por ejemplo, M001)
key_code = st.text_input("Código de la llave (ej. M001):")
# Campo para el nuevo estado (nombre de quien toma la llave o vacío si se devuelve)
new_status = st.text_input("Nuevo valor para 'Observation':")

if st.button("Actualizar Registro"):
    if not key_code:
        st.error("Debe ingresar el código de la llave.")
    else:
        result = update_key_status(key_code, new_status)
        if "Error" in result or "No se encontró" in result:
            st.error(result)
        else:
            st.success(result)
