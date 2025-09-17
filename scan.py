# =============================================================================
#  🔑 Key Register Scanner (Streamlit + Google Sheets)
#  - Incluye MODO MANTENIMIENTO con animación y bloqueo total de la app.
#  - Código comentado (en español) para facilitar mantenimiento y cambios.
# =============================================================================

import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# -----------------------------------------------------------------------------
# ⚙️ CONFIGURACIÓN BÁSICA DE LA PÁGINA
# -----------------------------------------------------------------------------
# Título y layout de la app.
st.set_page_config("🔑 Key Register Scanner", layout="centered")

# -----------------------------------------------------------------------------
# 🧰 FLAG DE MANTENIMIENTO
# -----------------------------------------------------------------------------
# Si MAINTENANCE es True, la app mostrará un aviso con animación y se detendrá.
# Para reabrir el uso normal, pon MAINTENANCE = False.
MAINTENANCE = True

if MAINTENANCE:
    # Bloque visual con animación CSS sencilla (sin dependencias extra).
    st.markdown(
        """
        <style>
        .maint-wrapper {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 70vh;
            text-align: center;
            flex-direction: column;
            gap: 1rem;
        }
        .maint-emoji {
            font-size: 72px;
            animation: pulse 1.6s ease-in-out infinite;
        }
        .maint-title {
            font-size: 28px;
            font-weight: 800;
        }
        .maint-subtitle {
            opacity: 0.9;
            font-size: 16px;
        }
        .maint-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 999px;
            border: 1px solid rgba(255, 193, 7, 0.35);
            background: rgba(255, 193, 7, 0.12);
            font-weight: 600;
            font-size: 14px;
        }
        .dotting::after {
            content: '';
            animation: dots 1.5s steps(4, end) infinite;
        }
        @keyframes pulse {
            0%   { transform: scale(1);   opacity: 0.9; }
            50%  { transform: scale(1.08); opacity: 1;   }
            100% { transform: scale(1);   opacity: 0.9; }
        }
        @keyframes dots {
            0% { content: ''; }
            25% { content: '.'; }
            50% { content: '..'; }
            75% { content: '...'; }
            100% { content: ''; }
        }
        </style>

        <div class="maint-wrapper">
            <div class="maint-emoji">🛠️</div>
            <div class="maint-title">Página en actualización</div>
            <div class="maint-subtitle">
                Estamos realizando mejoras para un mejor desempeño y experiencia.
                <br>
                Por favor vuelve más tarde.
            </div>
            <div class="maint-chip">
                <span>Estado</span> <span>•</span> <span class="dotting">Actualizando</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # Mensaje adicional preventivo en Streamlit (opcional).
    st.warning("La aplicación se encuentra temporalmente deshabilitada por mantenimiento.")
    # Bloquea cualquier ejecución posterior para que nadie pueda usar los formularios.
    st.stop()

# -----------------------------------------------------------------------------
# 🗃️ CONFIGURACIÓN DE CONEXIÓN A GOOGLE SHEETS (solo se ejecuta si no hay mantenimiento)
# -----------------------------------------------------------------------------
# IMPORTANTE: Debe existir en st.secrets["gcp_service_account"] el campo "spreadsheet_id".
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

# Nombre de la hoja (worksheet) y columnas requeridas.
WORKSHEET_NAME = "Key Register"
REQUIRED_HEADERS = ("Tag", "Observation")

# -----------------------------------------------------------------------------
# 🔐 CLIENTE GSPREAD CACHEADO
# -----------------------------------------------------------------------------
@st.cache_resource
def gs_client():
    """
    Crea y cachea el cliente de gspread usando credenciales de servicio
    almacenadas en st.secrets.

    El caché evita re-autenticaciones innecesarias entre reruns de Streamlit.
    """
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# -----------------------------------------------------------------------------
# 🔁 UTILIDAD DE REINTENTOS CONTRA LA API DE GOOGLE
# -----------------------------------------------------------------------------
def _with_retry(fn, *args, **kwargs):
    """
    Ejecuta `fn(*args, **kwargs)` con reintentos exponenciales para manejar
    errores transitorios (429/5xx) de la API de Google.
    """
    import time
    max_attempts = 5       # número de intentos antes de fallar
    base_sleep = 0.5       # tiempo base (segundos) para backoff exponencial
    for i in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except APIError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (429, 500, 502, 503, 504):
                time.sleep((2 ** i) * base_sleep)
                continue
            # Si es otro tipo de error de API, re-lanzar de inmediato
            raise
        except Exception:
            # Errores de red genéricos: permitir 1-2 reintentos
            if i < max_attempts - 1:
                time.sleep((2 ** i) * base_sleep)
                continue
            raise

# -----------------------------------------------------------------------------
# 📄 APERTURA DE WORKSHEET + VALIDACIÓN DE HEADERS
# -----------------------------------------------------------------------------
def _open_ws():
    """
    Abre la hoja por clave (SPREADSHEET_ID) y worksheet (WORKSHEET_NAME),
    valida que existan los encabezados requeridos y devuelve:
      - ws: objeto Worksheet
      - idx: dict { nombre_columna: indice_columna_1_based }
    """
    ws = _with_retry(gs_client().open_by_key, SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    headers = _with_retry(ws.row_values, 2)  # Asumimos fila 2 = encabezados
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        raise RuntimeError(
            f"Faltan columnas: {', '.join(missing)}. Encabezados actuales: {headers}"
        )
    idx = {h: headers.index(h) + 1 for h in headers}  # 1-based
    return ws, idx

# -----------------------------------------------------------------------------
# 🔎 BÚSQUEDA DE FILA POR TAG
# -----------------------------------------------------------------------------
def _find_row_by_tag(ws, tag: str, tag_col_idx: int):
    """
    Busca la fila (1-based) donde el valor de la columna 'Tag' coincide con `tag`.
    - Se asume que los encabezados están en la fila 2, por lo que los datos reales
      comienzan en la fila 3.
    - Compara en mayúsculas y con espacios recortados para mayor robustez.
    """
    tag_col = _with_retry(ws.col_values, tag_col_idx)  # lee la columna completa
    for i, v in enumerate(tag_col[2:], start=3):       # ignora filas 1-2
        if str(v).strip().upper() == tag:
            return i
    return None

# -----------------------------------------------------------------------------
# 🧠 LÓGICA DE NEGOCIO: ACTUALIZAR Y LIMPIAR OBSERVACIÓN
# -----------------------------------------------------------------------------
def update_key(tag: str, assignee: str, return_date: str) -> str:
    """
    Actualiza la columna Observation de un registro por 'Tag'.
    - Si assignee == "Returned": vacía Observation.
    - Si no, escribe: "<ASSIGNEE> @ YYYY-MM-DD HH:MM:SS • Return: YYYY-MM-DD (opcional)"
    - Timestamp en zona horaria "Australia/Brisbane".
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
    """
    Borra el contenido de Observation para el registro cuyo 'Tag' coincide.
    """
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

# -----------------------------------------------------------------------------
# 🏁 CALLBACK PARA MODO END-OF-DAY
# -----------------------------------------------------------------------------
def eod_clear_callback():
    """
    Callback que se dispara al cambiar el input del modo EOD.
    - Toma 'eod_tag' del session_state.
    - Limpia Observation del Tag escaneado y resetea el campo para el próximo.
    """
    tag = st.session_state.get("eod_tag", "").strip()
    if not tag:
        st.session_state["eod_msg"] = ("error", "Escanea un tag válido.")
    else:
        msg = clear_observation(tag)
        st.session_state["eod_msg"] = ("success", msg) if msg.startswith("✅") else ("error", msg)
    st.session_state["eod_tag"] = ""  # limpia campo

# -----------------------------------------------------------------------------
# 🎛️ INTERFAZ DE USUARIO (solo si MAINTENANCE=False)
# -----------------------------------------------------------------------------
st.title("🔑 Key Register Scanner")

# Selector de modo de trabajo
mode = st.radio("Selecciona el modo:", ["Normal", "End-of-Day Auto-Clear"], horizontal=True)

# Pequeña utilidad para enfocar el input de Tag (mejor experiencia con escáner)
def autofocus_tag():
    """
    Intenta enfocar el input de 'Tag code' en el navegador tras cada rerun,
    para facilitar escaneo continuo sin usar mouse/teclado.
    """
    st.components.v1.html(
        """
        <script>
        const i = parent.document.querySelector('input[aria-label="Tag code (p.ej. M001)"]');
        if (i) { i.focus(); i.select && i.select(); }
        </script>
        """,
        height=0,
    )

if mode == "Normal":
    st.write("Modo Normal: escanea, asigna quién, opcional return date, luego **Actualizar**.")

    # clear_on_submit=False → mantenemos 'Assign to' y otros campos.
    with st.form("normal_form", clear_on_submit=False):
        # Campo de entrada para Tag (se limpia solo tras actualizar con éxito).
        tag = st.text_input("Tag code (p.ej. M001)", key="tag_input")

        # Selector del responsable (permanece para registrar múltiples llaves).
        assignee = st.selectbox(
            "Assign to:",
            ["Returned", "Owner", "Guest", "Contractor",
             "ALLIAHN","CAMILO","CATALINA","GONZALO",
             "JHONNY","LUIS","POL","STELLA"],
            key="assignee_input"
        )

        # Fecha de retorno opcional (solo para Owner/Guest).
        return_date = ""
        if assignee in ("Owner", "Guest"):
            # date_input retorna un objeto date -> isoformat() da "YYYY-MM-DD"
            return_date = st.date_input("Return date", key="return_date_input").isoformat()

        # Nombre de contratista (obligatorio si Assign to == Contractor).
        contractor_name = ""
        if assignee == "Contractor":
            contractor_name = st.text_input("Contractor name", key="contractor_input").strip()

        submitted = st.form_submit_button("Update Record")

    # Lógica al enviar el formulario:
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
                # Notificación breve (no rompe si el entorno no soporta toasts).
                try:
                    st.toast("Registro actualizado")
                except Exception:
                    pass
                # 🔑 Limpieza FIABLE del Tag para escaneo en cadena:
                # - Usamos pop() para eliminar el valor del estado interno del widget.
                # - Luego st.rerun() para que el input reaparezca vacío.
                st.session_state.pop("tag_input", None)
                st.rerun()
            else:
                st.error(msg)

    # Intenta enfocar el Tag tras cada render/rerun para acelerar el flujo de escaneo.
    autofocus_tag()

else:
    # Modo End-of-Day: al escanear, borra directamente la Observación del Tag.
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

# -----------------------------------------------------------------------------
# 📝 SECCIÓN: NOTAS DEL DÍA
# -----------------------------------------------------------------------------
# Permite ver solo los registros con 'Observation' no vacía sin descargar toda la hoja.
st.markdown("---")
if st.button("🔍 Mostrar Notas del Día"):
    try:
        ws, idx = _open_ws()

        # Traer únicamente las dos columnas necesarias para minimizar tráfico.
        tag_vals = _with_retry(ws.col_values, idx["Tag"])
        obs_vals = _with_retry(ws.col_values, idx["Observation"])

        # Saltar las filas 1 y 2 (título/encabezados). Datos reales desde 3.
        tag_vals_data = tag_vals[2:] if len(tag_vals) > 2 else []
        obs_vals_data = obs_vals[2:] if len(obs_vals) > 2 else []

        # Alinear longitudes por seguridad.
        max_len = max(len(tag_vals_data), len(obs_vals_data))
        tag_vals_data += [""] * (max_len - len(tag_vals_data))
        obs_vals_data += [""] * (max_len - len(obs_vals_data))

        # Construir filas y filtrar las que tengan Observation no vacía.
        rows = [{"Tag": t, "Observation": o} for t, o in zip(tag_vals_data, obs_vals_data)]
        notes = [r for r in rows if str(r["Observation"]).strip()]

        if not notes:
            st.info("No hay notas pendientes.")
        else:
            # Intento de ordenar por timestamp si el patrón " @ YYYY-MM-DD HH:MM:SS" está presente.
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
