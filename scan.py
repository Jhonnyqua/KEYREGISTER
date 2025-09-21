import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

<<<<<<< HEAD
# ── Configuración de página y credenciales ─────────────────────────
=======
# ── Configuración de página y constantes ───────────────────────────
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)
st.set_page_config("🔑 Key Register Scanner", layout="centered")

# Debe existir en st.secrets["gcp_service_account"] el campo spreadsheet_id
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

<<<<<<< HEAD
@st.cache_resource
def gs_client():
    """Crea y cachea el cliente de Google Sheets."""
=======
# Nombre de la hoja y columnas requeridas
WORKSHEET_NAME = "Key Register"
REQUIRED_HEADERS = ("Tag", "Observation")

# ── Cliente GSpread cacheado ───────────────────────────────────────
@st.cache_resource
def gs_client():
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

<<<<<<< HEAD
# ── Funciones de negocio ───────────────────────────────────────────
def update_key(tag: str, assignee: str, return_date: str) -> str:
    """Actualiza la columna Observation según Tag."""
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error abriendo hoja: {e}"
=======
# ── Utilidades de robustez ─────────────────────────────────────────
def _with_retry(fn, *args, **kwargs):
    """Reintentos exponenciales para 429/5xx de la API de Google."""
    import time
    max_attempts = 5
    base_sleep = 0.5
    for i in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except APIError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (429, 500, 502, 503, 504):
                time.sleep((2 ** i) * base_sleep)
                continue
            raise
        except Exception:
            # Errores de red intermitentes pueden intentar reintento 1 vez
            if i < max_attempts - 1:
                time.sleep((2 ** i) * base_sleep)
                continue
            raise

def _open_ws():
    """Abre worksheet, valida headers y retorna (ws, idx_dict)."""
    ws = _with_retry(gs_client().open_by_key, SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    headers = _with_retry(ws.row_values, 2)  # Fila 2: encabezados
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise RuntimeError(
            f"Faltan columnas: {', '.join(missing)}. Encabezados actuales: {headers}"
        )
    # Mapa de header -> índice 1-based
    idx = {h: headers.index(h) + 1 for h in headers}
    return ws, idx

def _find_row_by_tag(ws, tag: str, tag_col_idx: int):
    """Busca la fila (1-based) del Tag; datos arrancan en fila 3."""
    tag_col = _with_retry(ws.col_values, tag_col_idx)  # Incluye filas 1..n
    # Headers en fila 2 → datos desde fila 3
    for i, v in enumerate(tag_col[2:], start=3):
        if str(v).strip().upper() == tag:
            return i
    return None

# ── Lógica de negocio ──────────────────────────────────────────────
def update_key(tag: str, assignee: str, return_date: str) -> str:
    """
    Actualiza Observation:
      - "Returned" -> Observation vacía
      - Otro -> "<ASSIGNEE> @ YYYY-MM-DD HH:MM:SS • Return: YYYY-MM-DD (opcional)"
    """
    try:
        ws, idx = _open_ws()
    except (SpreadsheetNotFound, APIError) as e:
        return "❌ No se pudo abrir la hoja. Verifica permisos/ID."
    except Exception as e:
        return f"❌ No se pudo abrir la hoja: {e}"
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)

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
<<<<<<< HEAD
    """Borra la Observation del Tag dado."""
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error abriendo hoja: {e}"
=======
    """Borra Observation para un Tag dado."""
    try:
        ws, idx = _open_ws()
    except (SpreadsheetNotFound, APIError) as e:
        return "❌ No se pudo abrir la hoja. Verifica permisos/ID."
    except Exception as e:
        return f"❌ No se pudo abrir la hoja: {e}"
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)

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

<<<<<<< HEAD
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
=======
# ── Callback End-of-Day ────────────────────────────────────────────
def eod_clear_callback():
    tag = st.session_state.get("eod_tag", "").strip()
    if not tag:
        st.session_state["eod_msg"] = ("error", "Escanea un tag válido.")
    else:
        msg = clear_observation(tag)
        st.session_state["eod_msg"] = ("success", msg) if msg.startswith("✅") else ("error", msg)
    # Limpia campo para siguiente escaneo
    st.session_state["eod_tag"] = ""

# ── Interfaz de usuario ────────────────────────────────────────────
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)
st.title("🔑 Key Register Scanner")
show_flash()

<<<<<<< HEAD
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
=======
# 1) Selector de modo
mode = st.radio("Selecciona el modo:", ["Normal", "End-of-Day Auto-Clear"], horizontal=True)

if mode == "Normal":
    st.write("Modo Normal: escanea, asigna quién, opcional return date, luego **Actualizar**.")

    with st.form("normal_form", clear_on_submit=False):
        tag = st.text_input("Tag code (p.ej. M001)", key="tag_input")

        assignee = st.selectbox(
            "Assign to:",
            ["Returned", "Owner", "Guest", "Contractor",
             "ALLIAHN","CAMILO","CATALINA","GONZALO",
             "JHONNY","LUIS","POL","STELLA"],
            key="assignee_input"
        )

        return_date = ""
        if assignee in ("Owner","Guest"):
            # date_input retorna date; isoformat() → YYYY-MM-DD
            return_date = st.date_input("Return date", key="return_date_input").isoformat()

        contractor_name = ""
        if assignee == "Contractor":
            contractor_name = st.text_input("Contractor name", key="contractor_input").strip()

        submitted = st.form_submit_button("Update Record")

    if submitted:
        if not tag.strip():
            st.error("Escanea un tag válido primero.")
        elif assignee == "Contractor" and not contractor_name:
            st.error("Ingresa el nombre del contratista.")
        else:
            final_assignee = (contractor_name or "Contractor") if assignee == "Contractor" else assignee
            msg = update_key(tag.strip(), final_assignee, return_date)
            if msg.startswith("✅"):
                st.success(msg)
                try:
                    st.toast("Registro actualizado")
                except Exception:
                    pass
                # Limpieza de estado y rerun
                st.session_state["tag_input"] = ""
                st.session_state["assignee_input"] = "Returned"
                if "return_date_input" in st.session_state:
                    st.session_state.pop("return_date_input")
                if "contractor_input" in st.session_state:
                    st.session_state["contractor_input"] = ""
                st.rerun()
            else:
                st.error(msg)
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)

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

<<<<<<< HEAD
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
=======
# ── Notas del día ─────────────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Mostrar Notas del Día"):
    try:
        ws, idx = _open_ws()

        # Traer solo columnas necesarias (Tag y Observation) usando col_values
        tag_vals = _with_retry(ws.col_values, idx["Tag"])
        obs_vals = _with_retry(ws.col_values, idx["Observation"])

        # Quitar filas de encabezado (1 y 2). Datos arrancan en 3.
        tag_vals_data = tag_vals[2:] if len(tag_vals) > 2 else []
        obs_vals_data = obs_vals[2:] if len(obs_vals) > 2 else []

        # Alinear longitudes
        max_len = max(len(tag_vals_data), len(obs_vals_data))
        tag_vals_data += [""] * (max_len - len(tag_vals_data))
        obs_vals_data += [""] * (max_len - len(obs_vals_data))

        rows = [{"Tag": t, "Observation": o} for t, o in zip(tag_vals_data, obs_vals_data)]
        notes = [r for r in rows if str(r["Observation"]).strip()]

        if not notes:
            st.info("No hay notas pendientes.")
        else:
            # Ordenar por timestamp si está en el texto como " @ YYYY-MM-DD HH:MM:SS"
            def _extract_ts(obs_text: str):
                try:
                    # Buscar el segmento después de " @ "
                    if " @ " in obs_text:
                        part = obs_text.split(" @ ", 1)[1].split("•", 1)[0].strip()
                        return datetime.fromisoformat(part)
                except Exception:
                    pass
                # Fallback: ordenar al final
                return datetime.min

            notes_sorted = sorted(notes, key=lambda r: _extract_ts(str(r["Observation"])), reverse=True)
            df_notes = pd.DataFrame(notes_sorted, columns=["Tag", "Observation"])
            st.dataframe(df_notes, height=320)
>>>>>>> bff8d13 (nueva version add TAIMESTAMP AND DATE OWNER AND GUEST)
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
