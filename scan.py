# scan.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ── CONFIG ─────────────────────────────────────────────────────────────────────
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]
WORKSHEET_NAME = "Key Register"

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    return gspread.authorize(creds)

def update_key_status(tag_code: str, assignee: str, return_date: str|None) -> str:
    """
    Updates the 'Observation' cell for the row whose 'Tag' equals tag_code.
    - If assignee == "Returned", leaves Observation blank.
    - Otherwise writes "ASSIGNEE @ UTC_ISO_TIMESTAMP" plus optional "– return by YYYY‑MM‑DD".
    """
    client = get_gspread_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

    headers = sheet.row_values(2)
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"❌ Missing column: {e}"

    records = sheet.get_all_records(head=2)
    row_num = next((i+3 for i, r in enumerate(records) if str(r.get("Tag","")).strip() == tag_code), None)
    if row_num is None:
        return f"❌ Tag “{tag_code}” not found."

    if assignee == "Returned":
        obs_text = ""
    else:
        ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        obs_text = f"{assignee} @ {ts}"
        if return_date:
            obs_text += f" – return by {return_date}"

    sheet.update_cell(row_num, obs_col, obs_text)
    return f"✅ Record updated on row {row_num}."

# ── UI ───────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Key Register", layout="centered")
st.title("🔑 Key Register Scanner")
st.markdown(
    "Scan a tag with your scanner (or type), pick who holds it, optionally select a return date, "
    "and click **Update Record**."
)

with st.form("key_form", clear_on_submit=True):
    tag_code = st.text_input("Tag Code", placeholder="e.g. M001")

    assignee = st.selectbox(
        "Assign to:",
        ["Returned", "Owner", "Guest", "Contractor",
         "ALLIAHN","CAMILO","CATALINA","GONZALO","JHONNY","LUIS","POL","STELLA"]
    )

    return_date = None
    if assignee in ("Owner", "Guest"):
        return_date = st.date_input("Return Date").isoformat()

    submitted = st.form_submit_button("Update Record")
    if submitted:
        if not tag_code.strip():
            st.error("❗ Please enter or scan a Tag Code.")
        else:
            msg = update_key_status(tag_code.strip(), assignee, return_date)
            if msg.startswith("✅"):
                st.success(msg)
            else:
                st.error(msg)
