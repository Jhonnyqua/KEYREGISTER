# scan.py
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# ─── CONFIG ──────────────────────────────────────────────────────────────────────
st.set_page_config("Key Register", layout="centered")
SPREADSHEET_ID   = st.secrets["gcp_service_account"]["spreadsheet_id"]
WORKSHEET_NAME   = "Key Register"
ALL_USERS        = ["ALLIAHN","CAMILO","CATALINA","GONZALO","JHONNY","LUIS","POL","STELLA"]
ASSIGNEE_OPTIONS = ["Returned","Owner","Guest","Contractor"] + ALL_USERS

# ─── HELPERS ─────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_gsheet_client():
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
    client = get_gsheet_client()
    sheet  = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

    headers = sheet.row_values(2)
    try:
        tag_col = headers.index("Tag") + 1
        obs_col = headers.index("Observation") + 1
    except ValueError as e:
        return f"❌ Missing column: {e}"

    records = sheet.get_all_records(head=2)
    row_num = next((i+3 for i,r in enumerate(records)
                    if str(r.get("Tag","")).strip()==tag_code), None)
    if row_num is None:
        return f"❌ Tag “{tag_code}” not found."

    # Build the new Observation cell:
    if assignee=="Returned":
        obs = ""
    else:
        ts  = datetime.utcnow().replace(microsecond=0).isoformat()+"Z"
        obs  = f"{assignee} @ {ts}"
        if return_date:
            obs += f"  (return by {return_date})"

    sheet.update_cell(row_num, obs_col, obs)
    return f"✅ Record updated on row {row_num}."

def fetch_notes_dataframe() -> pd.DataFrame:
    client = get_gsheet_client()
    sheet  = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    data   = sheet.get_all_records(head=2)
    df     = pd.DataFrame(data)
    # Keep only rows with a non-empty Observation:
    return df[df["Observation"].astype(str).str.strip() != ""]

# ─── UI ──────────────────────────────────────────────────────────────────────────
st.title("🔑 Key Register Scanner")
st.markdown("Scan or type a Tag Code, pick who holds it, optionally set a return date, then click **Update**.")

# Controlled inputs outside of a form so that any change immediately reruns the script:
tag_code = st.text_input("Tag Code", placeholder="e.g. M001", key="tag_input")
assignee = st.selectbox("Assign to:", ASSIGNEE_OPTIONS, key="assignee_select")

# Show Return Date picker immediately if Owner or Guest:
return_date = None
if assignee in ("Owner","Guest"):
    return_date = st.date_input("Return Date", key="return_date").isoformat()

# Update button
if st.button("Update Record"):
    if not tag_code.strip():
        st.error("❗ Please enter or scan a Tag Code.")
    else:
        msg = update_key_status(tag_code.strip(), assignee, return_date)
        if msg.startswith("✅"):
            st.success(msg)
            # reset fields:
            st.session_state.tag_input    = ""
            st.session_state.assignee_select = "Returned"
            if "return_date" in st.session_state:
                st.session_state.return_date = None
        else:
            st.error(msg)

# ─── NOTES DASHBOARD ──────────────────────────────────────────────────────────────
st.markdown("---")
st.header("🔍 End-of-Day Notes")
notes_df = fetch_notes_dataframe()
if notes_df.empty:
    st.info("All tags returned—no outstanding notes.")
else:
    # Only show Tag / Observation columns
    st.dataframe(notes_df[["Tag","Observation"]])
