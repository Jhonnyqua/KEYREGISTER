# scan.py

import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Page config ───────────────────────────────────────────────
st.set_page_config("🔑 Key Register Scanner", layout="centered")

# ── Secrets ───────────────────────────────────────────────────
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

# ── Google Sheets Client (cached) ────────────────────────────
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

# ── Update Function ───────────────────────────────────────────
def update_key(tag, assignee, return_date_iso):
    try:
        ss = gs_client().open_by_key(SPREADSHEET_ID)
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    headers = ws.row_values(2)
    if "Tag" not in headers or "Observation" not in headers:
        return "Sheet missing Tag/Observation columns"
    tag_col = headers.index("Tag") + 1
    obs_col = headers.index("Observation") + 1

    records = ws.get_all_records(head=2)
    row_idx = next((i+3 for i,r in enumerate(records)
                    if str(r.get("Tag","")).strip()==tag), None)
    if row_idx is None:
        return f"No key found for '{tag}'."

    # build Observation
    if assignee=="Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane"))\
                 .replace(microsecond=0).isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date_iso:
            obs += f" • Return: {return_date_iso}"

    try:
        ws.update_cell(row_idx, obs_col, obs)
        return f"✅ Record updated on row {row_idx}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ── The form ──────────────────────────────────────────────────
with st.form("key_form", clear_on_submit=True):
    tag = st.text_input("Tag code (e.g. M001)", key="tag")

    assignee = st.selectbox(
        "Assign to:",
        ["Returned", "Owner", "Guest", "Contractor",
         "ALLIAHN","CAMILO","CATALINA","GONZALO",
         "JHONNY","LUIS","POL","STELLA"],
        key="who",
    )

    # conditional inputs
    return_date_iso = ""
    if assignee in ("Owner","Guest"):
        return_date_iso = st.date_input("Return date", key="return_date").isoformat()
    if assignee=="Contractor":
        contractor_name = st.text_input("Contractor name", key="contractor")
        final_assignee = contractor_name.strip() or "Contractor"
    else:
        final_assignee = assignee

    submitted = st.form_submit_button("Update Record")
    if submitted:
        if not tag.strip():
            st.error("Please scan a valid tag first.")
        else:
            msg = update_key(tag.strip(), final_assignee, return_date_iso)
            if msg.startswith("✅"):
                st.success(msg)
            else:
                st.error(msg)

# ── End-of-Day Notes ───────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Show End-of-Day Notes"):
    ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
    df = pd.DataFrame(ws.get_all_records(head=2))
    notes = df[df["Observation"].astype(str).str.strip()!=""]
    if notes.empty:
        st.info("No keys currently with observations.")
    else:
        st.dataframe(notes[["Tag","Observation"]], height=300)
