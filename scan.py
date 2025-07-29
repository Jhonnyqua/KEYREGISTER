# scan.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURE YOUR SHEET NAME & SECRETS KEY ---
SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]
WORKSHEET_NAME = "Key Register"

def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    return gspread.authorize(creds)

def update_key_status(tag_code: str, assignee: str, return_date: str|None):
    """
    Finds the row where Tag == tag_code and writes in the Observation column:
      - blank if assignee == "Returned"
      - f"{assignee} @ {ISO timestamp}"   if Owner/Guest/Contractor/name
      - if return_date provided, append " – return by YYYY-MM-DD"
    """
    client = get_gspread_client()
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    headers = sheet.row_values(2)
    records = sheet.get_all_records(head=2)

    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"❌ Missing column in sheet: {e}"

    # find matching row
    row_num = None
    for idx, rec in enumerate(records, start=3):
        if str(rec.get("Tag","")).strip() == tag_code:
            row_num = idx
            break

    if not row_num:
        return f"❌ Tag “{tag_code}” not found."

    # build observation text
    if assignee == "Returned":
        obs_text = ""
    else:
        ts = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        obs_text = f"{assignee} @ {ts}"
        if return_date:
            obs_text += f" – return by {return_date}"

    # perform update
    sheet.update_cell(row_num, obs_col, obs_text)
    return f"✅ Record updated on row {row_num}."

# --- UI ---
st.set_page_config(page_title="Key Register", layout="centered")
st.title("🔑 Key Register Scanner")
st.markdown("""
Scan a tag with your scanner (or type manually), choose who holds it,
and click **Update Record**.  
""")

with st.form("key_form", clear_on_submit=False):
    tag_input = st.text_input(
        "Tag Code",
        placeholder="e.g. M001",
        key="tag_input"
    )

    options = [
        "Returned",       # always first
        "Owner",
        "Guest",
        "Contractor",
        "ALLIAHN",
        "CAMILO",
        "CATALINA",
        "GONZALO",
        "JHONNY",
        "LUIS",
        "POL",
        "STELLA"
    ]
    assignee = st.selectbox(
        "Assign to:",
        options,
        index=0,
        key="assignee_select"
    )

    # only show return-calendar for Owner/Guest
    return_date = None
    if assignee in ("Owner","Guest"):
        return_date = st.date_input(
            "Return Date",
            key="return_date"
        ).isoformat()

    submitted = st.form_submit_button("Update Record")
    if submitted:
        if not tag_input.strip():
            st.error("❗ Please scan or enter a Tag Code.")
        else:
            result = update_key_status(tag_input.strip(), assignee, return_date)
            if result.startswith("✅"):
                st.success(result)
                # reset form fields
                st.session_state["tag_input"] = ""
                st.session_state["assignee_select"] = "Returned"
                if "return_date" in st.session_state:
                    st.session_state["return_date"] = None
            else:
                st.error(result)
