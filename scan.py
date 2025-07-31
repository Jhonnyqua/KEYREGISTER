import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Page & Secrets ─────────────────────────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

# ── Google Sheets Client ───────────────────────────────────────
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

# ── Update Function ─────────────────────────────────────────────
def update_key(tag, assignee, return_date):
    """
    Finds the row in 'Key Register' where Tag == tag,
    writes Observation = "" for Returned, or
    f"{assignee} @ <Brisbane ISO ts>" [+ " • Return: YYYY-MM-DD"]
    """
    try:
        client = gs_client()
        ss = client.open_by_key(SPREADSHEET_ID)
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    # read headers & data
    headers = ws.row_values(2)
    if "Tag" not in headers or "Observation" not in headers:
        return "Sheet missing Tag/Observation columns"
    tag_col = headers.index("Tag") + 1
    obs_col = headers.index("Observation") + 1

    records = ws.get_all_records(head=2)
    # find row
    row = next((i+3 for i,r in enumerate(records)
                if str(r.get("Tag","")).strip() == tag), None)
    if row is None:
        return f"No key found for '{tag}'."

    # build observation
    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane"))\
                .replace(microsecond=0).isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ── Initialize Session State ──────────────────────────────────
if 'form_submitted' not in st.session_state:
    st.session_state.form_submitted = False
if 'reset_form' not in st.session_state:
    st.session_state.reset_form = False

# ── The Form ───────────────────────────────────────────────────
with st.form("key_form"):
    st.info("Scan or type your Tag code, then choose who has it.")
    
    # Use a unique key for the text input
    tag = st.text_input("Tag code (e.g. M001)", key="tag_input")
    
    # Assignee selection
    assignee = st.selectbox(
        "Assign to:",
        ["Returned", "Owner", "Guest", "Contractor",
         "ALLIAHN","CAMILO","CATALINA","GONZALO",
         "JHONNY","LUIS","POL","STELLA"],
        key="who",
    )

    # Dynamic fields based on selection
    return_date = ""
    contractor_name = ""
    final_assignee = assignee
    
    # Show date picker for Owner/Guest
    if assignee in ("Owner", "Guest"):
        return_date = st.date_input(
            "Return date", key="ret"
        ).isoformat()
    
    # Show text input for Contractor
    if assignee == "Contractor":
        contractor_name = st.text_input(
            "Contractor name", key="cont"
        ).strip()
        final_assignee = contractor_name or "Contractor"

    submitted = st.form_submit_button("Update Record")
    
    if submitted:
        if not tag.strip():
            st.error("Please scan a valid tag first.")
        else:
            msg = update_key(tag.strip(), final_assignee, return_date)
            if msg.startswith("✅"):
                st.success(msg)
                # Trigger form reset
                st.session_state.reset_form = True
            else:
                st.error(msg)

# Reset form after successful submission
if st.session_state.reset_form:
    st.session_state.reset_form = False
    st.session_state.form_submitted = True
    st.rerun()

# ── End-of-Day Notes ───────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Show End-of-Day Notes"):
    client = gs_client()
    ws = client.open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    df = pd.DataFrame(ws.get_all_records(head=2))
    notes = df[df["Observation"].astype(str).str.strip() != ""]
    if notes.empty:
        st.info("No keys currently with observations.")
    else:
        st.dataframe(notes[["Tag", "Observation"]], height=300)