import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Configuración de página y credenciales ─────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")

# Debe existir en st.secrets["gcp_service_account"] el campo spreadsheet_id
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
        ts = datetime.now(ZoneInfo("Australia/Brisbane")).replace(microsecond=0).isoformat(sep=" ")
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

# ── Flash message persistente tras rerun ───────────────────────────
def show_flash():
    flash = st.session_state.pop("flash", None)
    if not flash:
        return
    level, text = flash
    if level == "success":
        st.success(text)
    elif level == "error":
        st.error(text)
    else:
        st.info(text)

# ── Callback de “scan-to-commit” ───────────────────────────────────
def scan_commit():
    """
    Se dispara cuando el usuario (o escáner) presiona Enter en el campo Tag.
    Lee el estado actual de Assign to, Return date y Contractor name,
    actualiza, muestra mensaje y limpia SOLO el Tag.
    """
    tag = st.session_state.get("tag_input", "").strip()
    assignee = st.session_state.get("assignee_input", "Returned")
    return_date = ""
    if assignee in ("Owner", "Guest"):
        # date_input guarda date en session_state; si no existe, queda None
        d = st.session_state.get("return_date_input", None)
        if d:
            return_date = d.isoformat()

    contractor_name = st.session_state.get("contractor_input", "").strip()

    if not tag:
        st.session_state["flash"] = ("error", "Escanea un tag válido primero.")
        return

    if assignee == "Contractor" and not contractor_name:
        st.session_state["flash"] = ("error", "Ingresa el nombre del contratista.")
        # NO limpiamos el tag para que puedas corregir de una
        return

    final_assignee = (contractor_name or "Contractor") if assignee == "Contractor" else assignee

    msg = update_key(tag, final_assignee, return_date)
    if msg.startswith("✅"):
        st.session_state["flash"] = ("success", msg)
        # Limpia SOLO Tag y rerun para volver a enfocar y seguir escaneando
        st.session_state.pop("tag_input", None)
    else:
        st.session_state["flash"] = ("error", msg)
    st.rerun()

# ── UI ─────────────────────────────────────────────────────────────
st.title("🔑 Key Register Scanner")
show_flash()

mode = st.radio("Selecciona el modo:", ["Normal", "End-of-Day Auto-Clear"], horizontal=True)

if mode == "Normal":
    st.write("Modo Normal: **escanea y presiona Enter** para actualizar. También puedes usar el botón.")

    # Tag con on_change → modo scan-to-commit
    st.text_input(
        "Tag code (p.ej. M001)",
        key="tag_input",
        on_change=scan_commit,   # ⬅️ Aquí está la magia
        placeholder="Escanea aquí y presiona Enter",
    )

    # Assign to (se mantiene para procesar varias llaves seguidas)
    st.selectbox(
        "Assign to:",
        ["Returned", "Owner", "Guest", "Contractor",
         "ALLIAHN","CAMILO","CATALINA","GONZALO",
         "JHONNY","LUIS","POL","STELLA"],
        key="assignee_input"
    )

    # Campos condicionales (aparecen en vivo)
    if st.session_state.get("assignee_input") in ("Owner", "Guest"):
        st.date_input("Return date", key="return_date_input")

    if st.session_state.get("assignee_input") == "Contractor":
        st.text_input("Contractor name", key="contractor_input")

    # Botón de respaldo (opcional) por si no usas Enter
    if st.button("Update Record", type="primary"):
        scan_commit()

else:
    st.write("Modo End-of-Day: escanea y se borra la nota automáticamente.")
    st.text_input(
        "Escanea Tag para borrar nota:",
        key="eod_tag",
        on_change=lambda: (
            st.session_state.update(
                {"eod_msg": (("success", clear_observation(st.session_state.get("eod_tag", "").strip()))
                             if st.session_state.get("eod_tag", "").strip()
                             else ("error", "Escanea un tag válido."))}
            ),
            st.session_state.update({"eod_tag": ""}),
            st.rerun()
        ),
        placeholder="Ej: M001"
    )
    if "eod_msg" in st.session_state:
        status, text = st.session_state["eod_msg"]
        (st.success if status == "success" else st.error)(text)

# Notas del día
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

# Autofocus para que siempre puedas escanear de una
st.components.v1.html(
    """
    <script>
    const el = parent.document.querySelector('input[aria-label="Tag code (p.ej. M001)"]');
    if (el) { el.focus(); el.select && el.select(); }
    </script>
    """,
    height=0,
)
