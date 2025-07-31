import streamlit as st
import gspread
import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config("Key Register", layout="centered")
st.title("🔑 Key Register Scanner")

# ──────────────────────────────────────────────────────────────────────────────
# GSPREAD CLIENT
# ──────────────────────────────────────────────────────────────────────────────
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# ──────────────────────────────────────────────────────────────────────────────
# UPDATE FUNCTION
# ──────────────────────────────────────────────────────────────────────────────
def update_key(tag_code: str, assignee: str, return_date: str="") -> str:
    try:
        client = get_gspread_client()
        ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening Google Sheet: {e}"

    headers = ws.row_values(2)
    records = ws.get_all_records(head=2)
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"Missing column: {e}"

    # find row
    row = next(
        (i+3 for i,r in enumerate(records) if str(r.get("Tag","")).strip()==tag_code),
        None
    )
    if not row:
        return f"No key found with code '{tag_code}'."

    # build observation
    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane"))\
                  .replace(microsecond=0)\
                  .isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ──────────────────────────────────────────────────────────────────────────────
# THE FORM
# ──────────────────────────────────────────────────────────────────────────────
with st.form("update_form"):
    tag = st.text_input("Tag code (e.g. M001)", key="tag_input")
    people = [
        "Returned", "Owner", "Guest", "Contractor",
        "ALLIAHN","CAMILO","CATALINA","GONZALO",
        "JHONNY","LUIS","POL","STELLA"
    ]
    assignee = st.selectbox("Assign to:", people, key="assignee_input")

    contractor_name = ""
    if assignee == "Contractor":
        contractor_name = st.text_input("Contractor name", key="contractor_input")

    return_date = ""
    if assignee in ("Owner","Guest"):
        return_date = st.date_input("Return date", key="return_date_input").isoformat()

    submitted = st.form_submit_button("Update Record")
    if submitted:
        if not tag.strip():
            st.error("Please scan a valid tag first.")
        else:
            final_assignee = (contractor_name.strip() or "Contractor") \
                              if assignee=="Contractor" else assignee
            msg = update_key(tag.strip(), final_assignee, return_date)
            if msg.startswith("✅"):
                st.success(msg)
                # clear fields
                for key in ["tag_input","assignee_input","contractor_input","return_date_input"]:
                    if key in st.session_state:
                        st.session_state[key] = "" if "input" in key else None
                # no need to call rerun manually — form_submit_button will re-render
            else:
                st.error(msg)

# ──────────────────────────────────────────────────────────────────────────────
# END-OF-DAY NOTES BUTTON
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
if st.button("Show End-of-Day Notes"):
    client = get_gspread_client()
    ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
    ws = ss.worksheet("Key Register")
    df = pd.DataFrame(ws.get_all_records(head=2))
    notes = df[df["Observation"].astype(str).str.strip() != ""]
    if notes.empty:
        st.info("No outstanding notes.")
    else:
        st.dataframe(notes[["Tag","Observation"]], height=300)
