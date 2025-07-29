import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1) Authenticate with Google Sheets via st.secrets ---
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ],
    )
    return gspread.authorize(creds)

# --- 2) Update a key record in the sheet ---
def update_key_record(key_code: str, assignee: str, return_date=None):
    try:
        client = get_gspread_client()
        ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        sheet = ss.worksheet("Key Register")

        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)

        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1

        # find the row matching key_code
        row_to_update = None
        for i, rec in enumerate(records, start=3):
            if rec.get("Tag", "").strip() == key_code:
                row_to_update = i
                break

        if row_to_update is None:
            return f"❌ Key '{key_code}' not found."

        # build the observation text
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if assignee == "Returned":
            obs = ""  # clear the observation
        else:
            obs = assignee
            if assignee in ("Guest", "Owner") and return_date:
                obs += f" until {return_date.strftime('%Y-%m-%d')}"
        obs += f" | {now}"

        sheet.update_cell(row_to_update, obs_col, obs)
        return f"✅ Record updated in row {row_to_update}."

    except Exception as e:
        return f"❌ Error updating record: {e}"

# --- 3) Build the Streamlit UI ---
st.set_page_config(page_title="🔑 Key Register", layout="centered")
st.title("🔑 Key Register")

with st.form("key_form"):
    key_code = st.text_input("Scan or enter the key code:")
    assignee = st.selectbox(
        "Assign to:",
        ["Returned", "Guest", "Owner", "ALLIAHN", "CAMILO", "CATALINA",
         "GONZALO", "JHONNY", "LUIS", "POL", "STELLA"]
    )

    return_date = None
    if assignee in ("Guest", "Owner"):
        return_date = st.date_input("Return date:")

    submit = st.form_submit_button("Update record")

if submit:
    if not key_code.strip():
        st.error("Please enter a valid key code.")
    else:
        msg = update_key_record(key_code.strip(), assignee, return_date)
        if msg.startswith("✅"):
            st.success(msg)
        else:
            st.error(msg)
