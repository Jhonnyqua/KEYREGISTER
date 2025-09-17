import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Configuración de página y credenciales ─────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")

# Lee el ID desde secrets → debe estar en [gcp_service_account].spreadsheet_id
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

@st.cache_resource
def gs_client():
    """Crea y cachea el cliente de Google Sheets."""
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# ── Funciones de negocio ───────────────────────────────────────────
def update_key(tag: str, assignee: str, return_date: str) -> str:
    """Actualiza la columna Observation según Tag."""
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error abriendo hoja: {e}"

    headers = ws.row_values(2)
    if "Tag" not in headers or "Observation" not in headers:
        return "Faltan columnas Tag/Observation"

    obs_col = headers.index("Observation") + 1
    records = ws.get_all_records(head=2)

    # Busca fila del Tag (los datos empiezan en fila 3)
    row = next(
        (i + 3 for i, r in enumerate(records)
         if str(r.get("Tag", "")).strip() == tag),
        None
    )
    if row is None:
        return f"Tag '{tag}' no encontrado."

    # Construye observación
    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane")) \
               .replace(microsecond=0).isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Registro actualizado en fila {row}."
    except Exception as e:
        return f"Error escribiendo en hoja: {e}"

def clear_observation(tag: str) -> str:
    """Borra la Observation del Tag dado."""
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error abriendo hoja: {e}"

    headers = ws.row_values(2)
    if "Observation" not in headers or "Tag" not in headers:
        return "Faltan columnas Tag/Observation"

    obs_col = headers.index("Observation") + 1
    records = ws.get_all_records(head=2)

    row = next(
        (i + 3 for i, r in enumerate(records)
         if str(r.get("Tag", "")).strip() == tag),
        None
    )
    if row is None:
        return f"Tag '{tag}' no encontrado."

    try:
        ws.update_cell(row, obs_col, "")
        return f"✅ Observation borrada para '{tag}' (fila {row})."
    except Exception as e:
        return f"Error escribiendo en hoja: {e}"

# ── Callback End-of-Day ────────────────────────────────────────────
def eod_clear_callback():
    """Borra la nota al escanear en modo End-of-Day y limpia el input."""
    tag = st.session_state.get("eod_tag", "").strip()
    if not tag:
        st.session_state["eod_msg"] = ("error", "Escanea un tag válido.")
    else:
        msg = clear_observation(tag)
        st.session_state["eod_msg"] = ("success", msg) if msg.startswith("✅") else ("error", msg)
    st.session_state["eod_tag"] = ""

# ── Interfaz de usuario ────────────────────────────────────────────
st.title("🔑 Key Register Scanner")

# 1) Selector de modo
mode = st.radio("Selecciona el modo:", ["Normal", "End-of-Day Auto-Clear"])

if mode == "Normal":
    st.write("Modo Normal: escanea, asigna quién, opcional return date, luego **Actualizar**.")

    # Campos
    tag = st.text_input("Tag code (p.ej. M001)", key="tag_input")
    assignee = st.selectbox(
        "Assign to:",
        ["Returned", "Owner", "Guest", "Contractor",
         "ALLIAHN","CAMILO","CATALINA","GONZALO",
         "JHONNY","LUIS","POL","STELLA"],
        key="assignee_input"
    )

    return_date = ""
    if assignee in ("Owner", "Guest"):
        return_date = st.date_input("Return date", key="return_date_input").isoformat()

    contractor_name = ""
    if assignee == "Contractor":
        contractor_name = st.text_input("Contractor name", key="contractor_input").strip()

    # Acción
    if st.button("Update Record"):
        if not tag.strip():
            st.error("Escanea un tag válido primero.")
        elif assignee == "Contractor" and not contractor_name:
            st.error("Ingresa el nombre del contratista.")
        else:
            final = (contractor_name or "Contractor") if assignee == "Contractor" else assignee
            msg = update_key(tag.strip(), final, return_date)
            if msg.startswith("✅"):
                st.success(msg)

                # 🔹 Limpia SOLO el Tag y deja el Assign to como está
                st.session_state["tag_input"] = ""

                # Si quieres limpieza total, descomenta:
                # st.session_state["assignee_input"] = "Returned"
                # st.session_state.pop("return_date_input", None)
                # st.session_state["contractor_input"] = ""

                # Re-render para dejar el cursor en Tag y seguir escaneando
                st.rerun()
            else:
                st.error(msg)

else:
    st.write("Modo End-of-Day: escanea y se borra la nota automáticamente.")
    st.text_input(
        "Escanea Tag para borrar nota:",
        key="eod_tag",
        on_change=eod_clear_callback
    )
    if "eod_msg" in st.session_state:
        status, text = st.session_state["eod_msg"]
        (st.success if status == "success" else st.error)(text)

# 2) Notas del día
st.markdown("---")
if st.button("🔍 Mostrar Notas del Día"):
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
        df = pd.DataFrame(ws.get_all_records(head=2))
        notes = df[df["Observation"].astype(str).str.strip() != ""]
        if notes.empty:
            st.info("No hay notas pendientes.")
        else:
            st.dataframe(notes[["Tag", "Observation"]], height=300)
    except Exception as e:
        st.error(f"No se pudieron cargar las notas: {e}")

# 🔸 Autofocus al campo de Tag para facilitar escaneo continuo
st.components.v1.html(
    """
    <script>
    const el = parent.document.querySelector('input[aria-label="Tag code (p.ej. M001)"]');
    if (el) { el.focus(); el.select && el.select(); }
    </script>
    """,
    height=0,
)
