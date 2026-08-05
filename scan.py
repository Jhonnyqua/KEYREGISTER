import streamlit as st
import gspread
import pandas as pd
import re
import time
import random
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, WorksheetNotFound

# ── Configuración ─────────────────────────────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")

SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]
TZ = ZoneInfo("Australia/Brisbane")

SHEET_REGISTER = "Key Register"
SHEET_LOG = "Key Log"  # se crea automáticamente si no existe

HEADER_ROW = 2
DATA_START_ROW = 3

TAG_COL_NAME = "Tag"
OBS_COL_NAME = "Observation"

# Ajusta a tu formato real si hace falta (ej: M001 / G001 / M0001)
TAG_REGEX = re.compile(r"^[A-Z]\d{3,4}$")

DEBOUNCE_SECONDS = 1.2

# ✅ Parche A: throttle entre escrituras para evitar rate limit
MIN_SECONDS_BETWEEN_WRITES = 0.45


# ── Cliente Google Sheets ─────────────────────────────────────────
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


def open_ws(sheet_name: str):
    return gs_client().open_by_key(SPREADSHEET_ID).worksheet(sheet_name)


def get_or_create_ws(sheet_name: str, rows=2000, cols=20):
    sh = gs_client().open_by_key(SPREADSHEET_ID)
    try:
        return sh.worksheet(sheet_name)
    except WorksheetNotFound:
        return sh.add_worksheet(title=sheet_name, rows=str(rows), cols=str(cols))


# ── Utilidades ────────────────────────────────────────────────────
def now_ts() -> str:
    # Resta 7 horas al horario actual de la zona horaria configurada
    adjusted_time = datetime.now(TZ) - timedelta(hours=7)
    return adjusted_time.replace(microsecond=0).isoformat(sep=" ")


def normalize_tag(tag: str) -> str:
    return (tag or "").strip().upper()


def is_valid_tag(tag: str) -> bool:
    return bool(TAG_REGEX.match(tag))


# ✅ Parche A: reintentos con backoff para 429/503
def with_retries(fn, retries=6, base_sleep=0.8):
    last = None
    for i in range(retries):
        try:
            return fn()
        except APIError as e:
            last = e
            msg = str(e)
            # Rate limit / backend errors típicos
            if any(k in msg for k in ["429", "RESOURCE_EXHAUSTED", "503", "Service Unavailable"]):
                sleep = base_sleep * (2 ** i) + random.uniform(0, 0.4)
                time.sleep(sleep)
                continue
            raise
    if last:
        raise last


# ✅ Parche A: throttle global para no “disparar” requests
def throttle_write():
    last = st.session_state.get("_last_write_ts", 0.0)
    now = time.time()
    delta = now - last
    if delta < MIN_SECONDS_BETWEEN_WRITES:
        time.sleep(MIN_SECONDS_BETWEEN_WRITES - delta)
    st.session_state["_last_write_ts"] = time.time()


# ── Índice cacheado Tag -> fila ───────────────────────────────────
@st.cache_data(ttl=1800)  # ✅ subido a 30 min para evitar recalcular en medio de escaneos
def build_tag_index() -> dict:
    ws = open_ws(SHEET_REGISTER)
    headers = ws.row_values(HEADER_ROW)
    if TAG_COL_NAME not in headers:
        return {"__error__": f"Falta columna '{TAG_COL_NAME}' en fila {HEADER_ROW}."}

    tag_col = headers.index(TAG_COL_NAME) + 1

    last_row = ws.row_count
    start_a1 = gspread.utils.rowcol_to_a1(DATA_START_ROW, tag_col)
    end_a1 = gspread.utils.rowcol_to_a1(last_row, tag_col)
    rng = f"{start_a1}:{end_a1}"

    col_vals = ws.get(rng)

    idx = {}
    for i, row in enumerate(col_vals):
        t = normalize_tag(row[0] if row else "")
        if t:
            idx[t] = DATA_START_ROW + i
    return idx


def refresh_index():
    build_tag_index.clear()
    cached_cols.clear()


# ✅ Parche A: headers cacheados (evita ws.row_values en cada scan)
@st.cache_data(ttl=3600)  # 1 hora
def cached_cols():
    ws = open_ws(SHEET_REGISTER)
    headers = ws.row_values(HEADER_ROW)
    if TAG_COL_NAME not in headers or OBS_COL_NAME not in headers:
        raise ValueError("Faltan columnas Tag/Observation.")
    tag_col = headers.index(TAG_COL_NAME) + 1
    obs_col = headers.index(OBS_COL_NAME) + 1
    return tag_col, obs_col


# ── Log (append-only) ─────────────────────────────────────────────
def ensure_log_header(ws_log):
    desired = ["Timestamp", "Mode", "Action", "Tag", "Assignee", "ReturnDate", "Result", "Message"]
    existing = ws_log.row_values(1)
    if not any(existing):
        ws_log.update("A1", [desired])


def append_log(mode: str, action: str, tag: str, assignee: str, return_date: str, ok: bool, message: str):
    # ✅ Parche A: SOLO loguear errores para no quemar cuota
    if ok:
        return

    def _do():
        ws_log = get_or_create_ws(SHEET_LOG, rows=5000, cols=12)
        ensure_log_header(ws_log)
        ws_log.append_row(
            [now_ts(), mode, action, tag, assignee or "", return_date or "", "OK" if ok else "ERROR", message],
            value_input_option="USER_ENTERED",
        )

    try:
        with_retries(_do, retries=3, base_sleep=0.8)
    except Exception:
        pass


# ── Debounce anti doble-scan ──────────────────────────────────────
def should_debounce(tag: str) -> bool:
    tag = normalize_tag(tag)
    last_tag = st.session_state.get("_last_scanned_tag")
    last_time = st.session_state.get("_last_scanned_time", 0.0)
    now = time.time()
    if last_tag == tag and (now - last_time) < DEBOUNCE_SECONDS:
        return True
    st.session_state["_last_scanned_tag"] = tag
    st.session_state["_last_scanned_time"] = now
    return False


# ── Acciones principales ──────────────────────────────────────────
def update_observation(tag: str, assignee: str, return_date: str, mode="Normal") -> str:
    tag = normalize_tag(tag)
    if not tag:
        append_log(mode, "Assign", tag, assignee, return_date, False, "Empty tag")
        return "Escanea un tag válido."

    if not is_valid_tag(tag):
        append_log(mode, "Assign", tag, assignee, return_date, False, "Invalid tag format")
        return f"Formato de tag inválido: '{tag}'."

    # ✅ usar cols cacheadas
    try:
        _, obs_col = cached_cols()
    except Exception as e:
        append_log(mode, "Assign", tag, assignee, return_date, False, f"Header error: {e}")
        return f"Error leyendo headers: {e}"

    idx = build_tag_index()
    if "__error__" in idx:
        append_log(mode, "Assign", tag, assignee, return_date, False, idx["__error__"])
        return idx["__error__"]

    row = idx.get(tag)
    if not row:
        append_log(mode, "Assign", tag, assignee, return_date, False, "Tag not found (index)")
        return f"Tag '{tag}' no encontrado."

    if assignee == "Returned":
        obs = ""
    else:
        obs = f"{assignee} @ {now_ts()}"
        if return_date:
            obs += f" • Return: {return_date}"

    def _do():
        ws = open_ws(SHEET_REGISTER)
        throttle_write()  # ✅ throttle antes de escribir
        ws.update_cell(row, obs_col, obs)

    try:
        with_retries(_do, retries=6, base_sleep=0.8)
        msg = f"✅ Actualizado: {tag} (fila {row})."
        append_log(mode, "Assign", tag, assignee, return_date, True, msg)
        return msg
    except Exception as e:
        msg = f"Error escribiendo en hoja: {e}"
        append_log(mode, "Assign", tag, assignee, return_date, False, msg)
        return msg


def clear_observation(tag: str, mode="EOD") -> str:
    tag = normalize_tag(tag)
    if not tag:
        append_log(mode, "Clear", tag, "", "", False, "Empty tag")
        return "Escanea un tag válido."

    if not is_valid_tag(tag):
        append_log(mode, "Clear", tag, "", "", False, "Invalid tag format")
        return f"Formato de tag inválido: '{tag}'."

    try:
        _, obs_col = cached_cols()
    except Exception as e:
        append_log(mode, "Clear", tag, "", "", False, f"Header error: {e}")
        return f"Error leyendo headers: {e}"

    idx = build_tag_index()
    if "__error__" in idx:
        append_log(mode, "Clear", tag, "", "", False, idx["__error__"])
        return idx["__error__"]

    row = idx.get(tag)
    if not row:
        append_log(mode, "Clear", tag, "", "", False, "Tag not found (index)")
        return f"Tag '{tag}' no encontrado."

    def _do():
        ws = open_ws(SHEET_REGISTER)
        throttle_write()  # ✅ throttle antes de escribir
        ws.update_cell(row, obs_col, "")

    try:
        with_retries(_do, retries=6, base_sleep=0.8)
        msg = f"✅ Observation borrada: {tag} (fila {row})."
        append_log(mode, "Clear", tag, "", "", True, msg)
        return msg
    except Exception as e:
        msg = f"Error escribiendo en hoja: {e}"
        append_log(mode, "Clear", tag, "", "", False, msg)
        return msg


# ── Callbacks ─────────────────────────────────────────────────────
def eod_clear_callback():
    tag = normalize_tag(st.session_state.get("eod_tag", ""))
    if not tag:
        st.session_state["eod_msg"] = ("error", "Escanea un tag válido.")
    elif should_debounce(tag):
        st.session_state["eod_msg"] = ("error", "Tag repetido muy rápido (ignorado).")
    else:
        msg = clear_observation(tag, mode="EOD")
        st.session_state["eod_msg"] = ("success", msg) if msg.startswith("✅") else ("error", msg)
    st.session_state["eod_tag"] = ""


def normal_auto_update_callback():
    tag = normalize_tag(st.session_state.get("tag_input", ""))
    if not tag:
        st.session_state["normal_msg"] = ("error", "Escanea un tag válido.")
        return

    if should_debounce(tag):
        st.session_state["normal_msg"] = ("error", "Tag repetido muy rápido (ignorado).")
        st.session_state["tag_input"] = ""
        return

    assignee = st.session_state.get("assignee_input", "Returned")
    contractor_name = (st.session_state.get("contractor_input", "") or "").strip()
    return_date = st.session_state.get("return_date_str", "")

    final_assignee = (contractor_name or "Contractor") if assignee == "Contractor" else assignee

    msg = update_observation(tag, final_assignee, return_date, mode="Normal-Auto")
    st.session_state["normal_msg"] = ("success", msg) if msg.startswith("✅") else ("error", msg)

    # ✅ borrar solo Tag (contractor se mantiene)
    st.session_state["tag_input"] = ""


# ── UI ────────────────────────────────────────────────────────────
st.title("🔑 Key Register Scanner")

colA, colB = st.columns([1, 1])
with colA:
    if st.button("🔄 Refrescar índice"):
        refresh_index()
        st.success("Índice + headers refrescados.")
with colB:
    st.caption("Parche A: menos llamadas + throttle + backoff (contractor se mantiene)")

mode = st.radio("Selecciona el modo:", ["Normal", "End-of-Day Auto-Clear"], horizontal=True)

# ===== Normal =====
if mode == "Normal":
    st.write("Selecciona assignee y escanea. Auto-update acelera el flujo.")

    auto = st.toggle("⚡ Auto-Update al escanear", value=True)

    st.selectbox(
        "Assign to:",
        [
            "Returned", "Owner", "Guest", "Contractor",
            "ALLIAHN", "CAMILO", "CATALINA", "GONZALO", "JHONNY",
            "LUIS", "POL", "STELLA"
        ],
        key="assignee_input"
    )

    assignee_now = st.session_state.get("assignee_input", "Returned")

    if assignee_now in ("Owner", "Guest"):
        d = st.date_input("Return date", key="return_date_input", value=date.today())
        st.session_state["return_date_str"] = d.isoformat() if d else ""
    else:
        st.session_state["return_date_str"] = ""

    if assignee_now == "Contractor":
        st.text_input("Contractor name", key="contractor_input", help="Se mantiene para escaneos consecutivos.")
    else:
        st.session_state["contractor_input"] = ""

    if auto:
        st.text_input(
            "Tag code (p.ej. M001)",
            key="tag_input",
            on_change=normal_auto_update_callback,
            help="Escanea y se actualiza automáticamente."
        )
        if "normal_msg" in st.session_state:
            status, text = st.session_state["normal_msg"]
            (st.success if status == "success" else st.error)(text)
    else:
        st.text_input("Tag code (p.ej. M001)", key="tag_input")
        if st.button("Update Record", type="primary"):
            tag = normalize_tag(st.session_state.get("tag_input", ""))
            if not tag:
                st.error("Escanea un tag válido primero.")
            elif should_debounce(tag):
                st.error("Tag repetido muy rápido (ignorado).")
                st.session_state["tag_input"] = ""
            else:
                contractor_name = (st.session_state.get("contractor_input", "") or "").strip()
                return_date = st.session_state.get("return_date_str", "")
                final_assignee = (contractor_name or "Contractor") if assignee_now == "Contractor" else assignee_now

                with st.spinner("Actualizando registro..."):
                    msg = update_observation(tag, final_assignee, return_date, mode="Normal-Manual")

                if msg.startswith("✅"):
                    st.success(msg)
                    st.toast("Registro actualizado", icon="✅")
                    st.session_state["tag_input"] = ""
                else:
                    st.error(msg)

# ===== EOD =====
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

# ── Panel básico ──────────────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Mostrar Notas Pendientes"):
    try:
        ws = open_ws(SHEET_REGISTER)
        df = pd.DataFrame(ws.get_all_records(head=HEADER_ROW))
        if OBS_COL_NAME not in df.columns:
            st.error(f"Falta columna '{OBS_COL_NAME}'.")
        else:
            notes = df[df[OBS_COL_NAME].astype(str).str.strip() != ""]
            if notes.empty:
                st.info("No hay notas pendientes.")
            else:
                st.dataframe(notes[[TAG_COL_NAME, OBS_COL_NAME]], height=320, use_container_width=True)
    except Exception as e:
        st.error(f"No fue posible obtener las notas: {e}")
