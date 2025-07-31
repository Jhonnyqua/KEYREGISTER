import streamlit as st
import gspread
import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

#  ─── GSPREAD AUTH ─────────────────────────────────────────────────────────────

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

#  ─── UPDATE FUNCTION ──────────────────────────────────────────────────────────

def update_key_status(tag_code: str, assignee: str, return_date: str = "") -> str:
    """
    Finds the row with Tag==tag_code in 'Key Register' sheet,
    updates Observation to either '' (Returned) or
    'Assignee @ TIMESTAMP' (+ optional ' • Return: YYYY-MM-DD' for guest/owner)
    """
    try:
        client = get_gspread_client()
        ss_id = st.secrets["gcp_service_account"]["spreadsheet_id"]
        sheet = client.open_by_key(ss_id).worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    # load headers & records
    headers = sheet.row_values(2)
    records = sheet.get_all_records(head=2)

    # column indices
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"Missing column: {e}"

    # find row
    row_num = next((i+3 for i, r in enumerate(records) if str(r.get("Tag","")).strip()==tag_code), None)
    if not row_num:
        return f"No key found with code '{tag_code}'."

    # build new observation
    if assignee == "Returned":
        new_obs = ""
    else:
        # Brisbane time stamp
        ts = datetime.now(ZoneInfo("Australia/Brisbane")) \
                  .replace(microsecond=0) \
                  .isoformat(sep=" ")
        new_obs = f"{assignee} @ {ts}"
        if return_date:
            new_obs += f" • Return: {return_date}"

    # write
    try:
        sheet.update_cell(row_num, obs_col, new_obs)
        return f"✅ Record updated on row {row_num}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

#  ─── STREAMLIT UI ──────────────────────────────────────────────────────────────

st.set_page_config("Key Register", layout="centered")
st.title("🔑 Key Register Scanner")
st.markdown("Scan a tag, assign it, optionally pick a return date, and click Update.")

# --- Tag input (auto-focused on scan)
tag = st.text_input("Tag code (e.g. M001)", key="tag_input")

# --- Assignee select
people = ["Returned","Owner","Guest","Contractor",
          "ALLIAHN","CAMILO","CATALINA","GONZALO",
          "JHONNY","LUIS","POL","STELLA"]
assignee = st.selectbox("Assign to:", people, key="assignee_select")

# --- Contractor free-text
if assignee == "Contractor":
    contractor_name = st.text_input("Contractor name", key="contractor_input")
    final_assignee = contractor_name.strip() or "Contractor"
else:
    final_assignee = assignee

# --- Return date for Owner/Guest
return_date = ""
if assignee in ("Owner","Guest"):
    return_date = st.date_input("Return date", key="return_date").isoformat()

# --- Update button
if st.button("Update Record"):
    if not tag.strip():
        st.error("Please scan a valid tag.")
    else:
        msg = update_key_status(tag.strip(), final_assignee, return_date)
        if msg.startswith("✅"):
            st.success(msg)
            # reset form fields
            st.session_state["tag_input"] = ""
            st.session_state["assignee_select"] = "Returned"
            if "contractor_input" in st.session_state:
                st.session_state["contractor_input"] = ""
            if "return_date" in st.session_state:
                st.session_state["return_date"] = None
        else:
            st.error(msg)
