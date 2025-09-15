import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Configuración de página y constantes ───────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")

# Debe existir en st.secrets["gcp_service_account"] el campo spreadsheet_id
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

# Nombre de la hoja y columnas requeridas
WORKSHEET_NAME = "Key Register"
REQUIRED_HEADERS = ("Tag", "Observation")

# ── Cliente GSpread cacheado ───────────────────────────────────────
@st.cache_resource
def gs_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

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
    idx = {h: headers.index(h) + 1 for h in headers}  # header -> índice 1-based
    return ws, idx

def _find_row_by_tag(ws, tag: str, tag_col_idx: int):
    """Busca la fila (1-based) del Tag; datos arrancan en fila 3."""
    tag_col = _with_retry(ws.col_values, tag_col_idx)  # Incluye filas 1..n
    for i, v in enumerate(tag_col[2:], start=3):  # salta filas 1 y 2 (título/headers)
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
    except (SpreadsheetNotFound, APIError):
        return "❌ No se pudo abrir la hoja. Verifica permisos/ID."
    except Exception as e:
        return f"❌ No se pudo abrir la hoja: {e}"

    tag_norm = tag.strip().upper()
    row = _find_row_by_tag(ws, tag_norm, idx["Tag"])
    if row is None:
        return f"❌ Tag '{tag_norm}' no encontrado."

    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane")).replace(microsecond=0).isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    try:
        _with_retry(ws.update_cell, row, idx["Observation"], obs)
        return f"✅ Registro actualizado (fila {row})."
    except Exception:
        return "❌ Error escribiendo en la hoja. Intenta de nuevo."

def clear_observation(tag: str) -> str:
    """Borra Observation para un Tag dado."""
    try:
        ws, idx = _open_ws()
    except (SpreadsheetNotFound, APIError):
        return "❌ No se pudo abrir la hoja. Verifica permisos/ID."
    except Exception as e:
        return f"❌ No se pudo abrir la hoja: {e}"

    row = _find_row_by_tag(ws, tag.strip().upper(), idx["Tag"])
    if row is None:
        return f"❌ Tag '{tag}' no encontrado."
    try:
        _with_retry(ws.update_cell, row, idx["Observation"], "")
        return f"✅ Observation borrada para '{tag}' (fila {row})."
    except Exception:
        return "❌ Error escribiendo en la hoja. Intenta de nuevo."

# ── Callback End-of-Day ────────────────────────────────────────────
def eod_clear_callback():
    tag = st.session_state.get("eod_tag", "").strip()
    if not tag:
        st.session_state["eod_msg"] = ("error", "Escanea un tag válido.")
    else:
        msg = clear_observation(tag)
        st.session_state["eod_msg"] = ("success", msg) if msg.startswith("✅") else ("error", msg)
    st.session_state["eod_tag"] = ""  # limpia campo

# ── Interfaz de usuario ────────────────────────────────────────────
st.title("🔑 Key Register Scanner")

# 1) Selector de modo
mode = st.radio("Selecciona el modo:", ["Normal", "End-of-Day Auto-Clear"], horizontal=True)

if mode == "Normal":
    st.write("Modo Normal: escanea, asigna quién, opcional return date, luego **Actualizar**.")

    # ⬇️ Cambiado a clear_on_submit=True para auto-limpiar el form
    with st.form("normal_form", clear_on_submit=True):
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
                # ⬇️ Reset explícito del estado + rerun para garantizar limpieza total
                st.session_state["assignee_input"] = "Returned"
                if "tag_input" in st.session_state:
                    st.session_state["tag_input"] = ""
                if "return_date_input" in st.session_state:
                    st.session_state.pop("return_date_input")
                if "contractor_input" in st.session_state:
                    st.session_state["contractor_input"] = ""
                st.rerun()
            else:
                st.error(msg)

else:
    st.write("Modo End-of-Day: escanea y se borra la nota automáticamente.")
    st.text_input(
        "Escanea Tag para borrar nota:",
        key="eod_tag",
        on_change=eod_clear_callback,
        placeholder="Ej: M001"
    )
    if "eod_msg" in st.session_state:
        status, text = st.session_state["eod_msg"]
        (st.success if status == "success" else st.error)(text)

# ── Notas del día ─────────────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Mostrar Notas del Día"):
    try:
        ws, idx = _open_ws()
        tag_vals = _with_retry(ws.col_values, idx["Tag"])
        obs_vals = _with_retry(ws.col_values, idx["Observation"])

        tag_vals_data = tag_vals[2:] if len(tag_vals) > 2 else []
        obs_vals_data = obs_vals[2:] if len(obs_vals) > 2 else []

        max_len = max(len(tag_vals_data), len(obs_vals_data))
        tag_vals_data += [""] * (max_len - len(tag_vals_data))
        obs_vals_data += [""] * (max_len - len(obs_vals_data))

        rows = [{"Tag": t, "Observation": o} for t, o in zip(tag_vals_data, obs_vals_data)]
        notes = [r for r in rows if str(r["Observation"]).strip()]

        if not notes:
            st.info("No hay notas pendientes.")
        else:
            def _extract_ts(obs_text: str):
                try:
                    if " @ " in obs_text:
                        part = obs_text.split(" @ ", 1)[1].split("•", 1)[0].strip()
                        return datetime.fromisoformat(part)
                except Exception:
                    pass
                return datetime.min

            notes_sorted = sorted(notes, key=lambda r: _extract_ts(str(r["Observation"])), reverse=True)
            df_notes = pd.DataFrame(notes_sorted, columns=["Tag", "Observation"])
            st.dataframe(df_notes, height=320)
    except Exception as e:
        st.error(f"No se pudieron cargar las notas: {e}")
