import streamlit as st
import gspread
import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ─── Page config ─────────────────────────────────────────────
st.set_page_config("Key Register Scanner", layout="centered")
st.title("🔑 Key Register Scanner")

# ─── Auth ────────────────────────────────────────────────────
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# ─── Update function ─────────────────────────────────────────
def update_key(tag, assignee, return_date=""):
    try:
        client = get_client()
        ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    headers = ws.row_values(2)
    if "Tag" not in headers or "Observation" not in headers:
        return "Sheet missing required columns"
    tag_col = headers.index("Tag") + 1
    obs_col = headers.index("Observation") + 1

    records = ws.get_all_records(head=2)
    row = next((i+3 for i,r in enumerate(records)
                if str(r.get("Tag","")).strip()==tag), None)
    if row is None:
        return f"No key found for '{tag}'."

    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane")) \
                   .replace(microsecond=0) \
                   .isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ─── The form ────────────────────────────────────────────────
with st.form("form"):
    tag = st.text_input("Tag code (e.g. M001)", key="tag")
    assignee = st.selectbox(
        "Assign to:",
        ["Returned","Owner","Guest","Contractor",
         "ALLIAHN","CAMILO","CATALINA","GONZALO",
         "JHONNY","LUIS","POL","STELLA"],
        key="who",
    )

    # conditional widgets appear immediately next run
    if assignee in ("Owner","Guest"):
        return_date = st.date_input("Return date", key="ret")
        return_date = return_date.isoformat()
    else:
        return_date = ""

    if assignee == "Contractor":
        contractor_name = st.text_input("Contractor name", key="cont")
        final_assignee = contractor_name.strip() or "Contractor"
    else:
        final_assignee = assignee

    submitted = st.form_submit_button("Update Record")
    if submitted:
        if not tag.strip():
            st.error("Please scan a tag first.")
        else:
            msg = update_key(tag.strip(), final_assignee, return_date)
            if msg.startswith("✅"):
                st.success(msg)
                # clear for next entry
                st.session_state["tag"] = ""
                st.session_state["who"] = "Returned"
                st.session_state["ret"] = None
                st.session_state["cont"] = ""
            else:
                st.error(msg)

# ─── End-of-day notes ────────────────────────────────────────
st.markdown("---")
if st.button("Show End-of-Day Notes"):
    client = get_client()
    ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
    df = pd.DataFrame(ss.worksheet("Key Register").get_all_records(head=2))
    notes = df[df["Observation"].astype(str).str.strip() != ""]
    if notes.empty:
        st.info("No outstanding notes.")
    else:
        st.dataframe(notes[["Tag","Observation"]], height=300)
