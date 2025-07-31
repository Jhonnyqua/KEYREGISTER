import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Page config & secrets ────────────────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

# ── Cached Google Sheets client ───────────────────────────────
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

# ── Function to write back to the sheet ───────────────────────
def update_key(tag, assignee, return_date_iso):
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    headers = ws.row_values(2)
    if "Tag" not in headers or "Observation" not in headers:
        return "Missing Tag/Observation columns"
    obs_col = headers.index("Observation") + 1

    records = ws.get_all_records(head=2)
    row = next((i+3 for i,r in enumerate(records) if str(r.get("Tag","")).strip()==tag), None)
    if not row:
        return f"No key found for '{tag}'."

    # build the Observation
    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane"))\
                 .replace(microsecond=0).isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date_iso:
            obs += f" • Return: {return_date_iso}"

    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ── The form (auto-clears when submitted) ─────────────────────
with st.form("key_form", clear_on_submit=True):
    st.text_input("Tag code (e.g. M001)", key="tag_input")

    assignee = st.selectbox(
        "Assign to:",
        [
            "Returned",
            "Owner",
            "Guest",
            "Contractor",
            "ALLIAHN","CAMILO","CATALINA","GONZALO",
            "JHONNY","LUIS","POL","STELLA",
        ],
        key="who",
    )

    # dynamic fields:
    return_date_iso = ""
    if assignee in ("Owner", "Guest"):
        return_date_iso = st.date_input("Return date", key="ret").isoformat()
    contractor_name = ""
    if assignee == "Contractor":
        contractor_name = st.text_input("Contractor name", key="cont").strip()

    submitted = st.form_submit_button("Update Record")
    if submitted:
        tag = st.session_state.tag_input.strip()
        if not tag:
            st.error("Please scan a valid tag first.")
        else:
            final_assignee = (
                contractor_name or "Contractor"
                if assignee == "Contractor"
                else assignee
            )
            msg = update_key(tag, final_assignee, return_date_iso)
            st.success(msg) if msg.startswith("✅") else st.error(msg)

# ── End-of-Day Notes ────────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Show End-of-Day Notes"):
    ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    df = pd.DataFrame(ws.get_all_records(head=2))
    notes = df[df["Observation"].astype(str).str.strip() != ""]
    if notes.empty:
        st.info("No keys currently with observations.")
    else:
        st.dataframe(notes[["Tag", "Observation"]], height=300)
