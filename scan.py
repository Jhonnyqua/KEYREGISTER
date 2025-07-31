import streamlit as st
import gspread
import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ────────────────────────────────────────────────────────────────────────────────
# GSPREAD AUTH
# ────────────────────────────────────────────────────────────────────────────────

def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

# ────────────────────────────────────────────────────────────────────────────────
# UPDATE FUNCTION
# ────────────────────────────────────────────────────────────────────────────────

def update_key_status(tag_code: str, assignee: str, return_date: str = "") -> str:
    """
    Updates the 'Observation' cell for the given Tag in the 'Key Register' sheet.
    """
    try:
        gc = get_gspread_client()
        ss = gc.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    # headers & records
    headers = ws.row_values(2)
    records = ws.get_all_records(head=2)

    # find columns
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"Missing column: {e}"

    # locate row
    row = next(
        (idx + 3 for idx, r in enumerate(records)
         if str(r.get("Tag", "")).strip() == tag_code),
        None
    )
    if not row:
        return f"No key found with code '{tag_code}'."

    # build observation
    if assignee == "Returned":
        obs = ""
    else:
        # Brisbane timestamp
        ts = datetime.now(ZoneInfo("Australia/Brisbane")) \
                   .replace(microsecond=0) \
                   .isoformat(sep=" ")
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f" • Return: {return_date}"

    # write it
    try:
        ws.update_cell(row, obs_col, obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ────────────────────────────────────────────────────────────────────────────────
# STREAMLIT UI
# ────────────────────────────────────────────────────────────────────────────────

st.set_page_config("Key Register", layout="centered")
st.title("🔑 Key Register Scanner")
st.markdown("Scan a tag, assign it (Returned/Owner/Guest/Contractor), and press Update.")

with st.form("scan_form", clear_on_submit=True):
    # 1) Tag
    tag = st.text_input("Tag code (e.g. M001)")

    # 2) Assignee dropdown
    options = ["Returned", "Owner", "Guest", "Contractor",
               "ALLIAHN", "CAMILO", "CATALINA",
               "GONZALO", "JHONNY", "LUIS", "POL", "STELLA"]
    assignee = st.selectbox("Assign to:", options)

    # 3) Contractor name if needed
    if assignee == "Contractor":
        contractor_name = st.text_input("Contractor name")
        final_assignee = contractor_name.strip() or "Contractor"
    else:
        final_assignee = assignee

    # 4) Return date picker if Owner/Guest
    return_date = ""
    if assignee in ("Owner", "Guest"):
        return_date = st.date_input("Return date").isoformat()

    submitted = st.form_submit_button("Update Record")
    if submitted:
        if not tag.strip():
            st.error("Please scan a valid tag.")
        else:
            msg = update_key_status(tag.strip(), final_assignee, return_date)
            if msg.startswith("✅"):
                st.success(msg)
            else:
                st.error(msg)

# ────────────────────────────────────────────────────────────────────────────────
# END-OF-DAY NOTES (always visible below the form)
# ────────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.header("🔍 End-of-Day Notes")
def fetch_notes_dataframe():
    """Pulls all non-empty Observation rows for quick review."""
    gc = get_gspread_client()
    ss = gc.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
    ws = ss.worksheet("Key Register")
    df = pd.DataFrame(ws.get_all_records(head=2))
    # keep only those with Observation filled
    return df[df["Observation"].astype(str).str.strip() != ""]

notes_df = fetch_notes_dataframe()
if notes_df.empty:
    st.write("No outstanding notes.")
else:
    st.dataframe(notes_df[["Tag", "Observation"]], height=300)
