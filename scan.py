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
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

# ──────────────────────────────────────────────────────────────────────────────
# UPDATE LOGIC
# ──────────────────────────────────────────────────────────────────────────────
def update_key_status(tag_code: str, assignee: str, return_date: str="") -> str:
    try:
        gc = get_client()
        ss = gc.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    headers = ws.row_values(2)
    records = ws.get_all_records(head=2)
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"Missing column: {e}"

    # Find row
    row = next(
        (i+3 for i,r in enumerate(records)
         if str(r.get("Tag","")).strip() == tag_code),
        None
    )
    if not row:
        return f"No key found with code '{tag_code}'."

    # Build observation
    if assignee == "Returned":
        obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane")) \
                     .replace(microsecond=0) \
                     .isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    # Write it
    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ──────────────────────────────────────────────────────────────────────────────
# WIDGETS
# ──────────────────────────────────────────────────────────────────────────────
# 1) Tag input
tag = st.text_input("Tag code (e.g. M001)", key="tag_input")

# 2) Who?
people = [
    "Returned", "Owner", "Guest", "Contractor",
    "ALLIAHN","CAMILO","CATALINA","GONZALO",
    "JHONNY","LUIS","POL","STELLA"
]
assignee = st.selectbox("Assign to:", people, key="assignee_input")

# 3) If contractor, capture name
contractor_name = ""
if assignee == "Contractor":
    contractor_name = st.text_input("Contractor name", key="contractor_input")

# 4) If Owner or Guest, show return-date picker
return_date = ""
if assignee in ("Owner","Guest"):
    return_date = st.date_input("Return date", key="return_date_input").isoformat()

# 5) Update button
if st.button("Update Record"):
    if not tag.strip():
        st.error("Please scan a valid tag first.")
    else:
        final_assignee = (contractor_name.strip() or "Contractor") \
                          if assignee=="Contractor" else assignee
        msg = update_key_status(tag.strip(), final_assignee, return_date)
        if msg.startswith("✅"):
            st.success(msg)
            # Clear all inputs
            for k in ["tag_input","assignee_input","contractor_input","return_date_input"]:
                if k in st.session_state:
                    st.session_state[k] = ""
            st.experimental_rerun()
        else:
            st.error(msg)

# ──────────────────────────────────────────────────────────────────────────────
# END-OF-DAY NOTES
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.header("🔍 End-of-Day Notes")
def fetch_notes_df():
    gc = get_client()
    ss = gc.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
    ws = ss.worksheet("Key Register")
    df = pd.DataFrame(ws.get_all_records(head=2))
    return df[df["Observation"].astype(str).str.strip() != ""]

notes = fetch_notes_df()
if notes.empty:
    st.write("No outstanding notes.")
else:
    st.dataframe(notes[["Tag","Observation"]], height=300)
