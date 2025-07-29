# scan.py

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# -----------------------
# 1) Authenticate with Google Sheets via st.secrets
# -----------------------
@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# -----------------------
# 2) Update a single key’s Observation cell
# -----------------------
def update_key_record(key_code: str, assignee: str, return_date=None) -> str:
    """
    key_code: the tag (e.g. "M001")
    assignee: one of "Owner", "Guest", "Contractor", or "Returned"
    return_date: a datetime.date if assignee is Guest or Owner, else None
    """
    try:
        client = get_gspread_client()
        ss = client.open_by_key(st.secrets["gcp_service_account"]["spreadsheet_id"])
        sheet = ss.worksheet("Key Register")

        # Read headers & records
        headers = sheet.row_values(2)             # row 2 = headers
        records = sheet.get_all_records(head=2)   # data from row 3 onward

        # Find column indexes (1‑based)
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1

        # Locate the correct row
        row_to_update = None
        for idx, rec in enumerate(records, start=3):
            if rec.get("Tag", "").strip() == key_code:
                row_to_update = idx
                break

        if row_to_update is None:
            return f"❌ Key '{key_code}' not found."

        # Build the new Observation text
        if assignee == "Returned":
            obs_text = ""  # clear the cell completely
        else:
            obs_text = assignee
            if assignee in ("Guest", "Owner") and return_date:
                obs_text += f" until {return_date.strftime('%Y-%m-%d')}"
            # Append timestamp for non‑returned
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            obs_text += f" | {timestamp}"

        # Write back to the sheet
        sheet.update_cell(row_to_update, obs_col, obs_text)
        return f"✅ Record updated in row {row_to_update}."

    except Exception as e:
        return f"❌ Error updating record: {e}"

# -----------------------
# 3) Streamlit UI
# -----------------------
st.set_page_config(page_title="Key Register", layout="centered")
st.title("🔑 Key Register")

# Form for input and automatic reset
with st.form("key_form"):
    tag_input = st.text_input("Tag Code", key="tag_input", placeholder="e.g. M001")
    assignee = st.selectbox(
        "Assign to:",
        ["Owner", "Guest", "Contractor", "Returned"],
        key="assignee_select",
    )

    return_date = None
    if assignee in ("Guest", "Owner"):
        return_date = st.date_input("Return Date", key="return_date")

    submitted = st.form_submit_button("Update Record")

if submitted:
    if not tag_input.strip():
        st.error("❗ Please enter or scan a Tag Code first.")
    else:
        result = update_key_record(
            key_code=tag_input.strip(),
            assignee=assignee,
            return_date=return_date if assignee in ("Guest", "Owner") else None,
        )
        if result.startswith("✅"):
            st.success(result)
            # Clear fields after success
            st.session_state["tag_input"] = ""
            if "return_date" in st.session_state:
                st.session_state["return_date"] = None
        else:
            st.error(result)
