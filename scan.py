import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pandas as pd

# ─── IMPORT & ADJUST RERUN EXCEPTION ────────────────────────────────────
from streamlit.runtime.scriptrunner import RerunException
def rerun():
    """Trigger a full Streamlit rerun."""
    raise RerunException(rerun_data={})

# ─── PAGE CONFIG ────────────────────────────────────────────────────────
st.set_page_config(page_title="Key Register Scanner", layout="centered")

SPREADSHEET_ID   = st.secrets["gcp_service_account"]["spreadsheet_id"]
WORKSHEET_NAME   = "Key Register"
ALL_USERS        = ["ALLIAHN","CAMILO","CATALINA","GONZALO","JHONNY","LUIS","POL","STELLA"]
ASSIGNEE_OPTIONS = ["Returned","Owner","Guest","Contractor"] + ALL_USERS

# ─── CACHED GOOGLE SHEETS CLIENT ─────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_gsheet_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ],
    )
    return gspread.authorize(creds)

# ─── CORE FUNCTIONS ──────────────────────────────────────────────────────
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
    row_num = next(
        (i+3 for i,r in enumerate(records)
         if str(r.get("Tag","")).strip()==tag_code),
        None
    )
    if row_num is None:
        return f"❌ Tag “{tag_code}” not found."

    # Build the observation string
    if assignee == "Returned":
        obs = ""
    else:
        ts  = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        obs = f"{assignee} @ {ts}"
        if return_date:
            obs += f"  (return by {return_date})"

    sheet.update_cell(row_num, obs_col, obs)
    return f"✅ Record updated on row {row_num}."

def fetch_notes_dataframe() -> pd.DataFrame:
    client = get_gsheet_client()
    sheet  = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    df     = pd.DataFrame(sheet.get_all_records(head=2))
    return df[df["Observation"].astype(str).str.strip() != ""]

# ─── UI LAYOUT ───────────────────────────────────────────────────────────
st.title("🔑 Key Register Scanner")
st.markdown("Scan or type a Tag Code, choose assignment, optionally pick a return date, then click **Update Record**.")

# 1) Tag code input
tag_code = st.text_input("Tag Code", placeholder="e.g. M001", key="tag_input")

# 2) Assignee selection
assignee = st.selectbox("Assign to:", ASSIGNEE_OPTIONS, key="assignee_select")

# 3) If Contractor → show a text field
contractor_name = None
if assignee == "Contractor":
    contractor_name = st.text_input("Contractor Name", key="contractor_name")
    final_assignee = contractor_name.strip() or "Contractor"
else:
    final_assignee = assignee

# 4) If Owner or Guest → show return-date picker
return_date = None
if final_assignee in ("Owner", "Guest"):
    return_date = st.date_input("Return Date", key="return_date").isoformat()

# 5) Update button
if st.button("Update Record"):
    if not tag_code.strip():
        st.error("❗ Please enter a Tag Code.")
    else:
        msg = update_key_status(tag_code.strip(), final_assignee, return_date)
        if msg.startswith("✅"):
            st.success(msg)
            rerun()                # clear all inputs immediately
        else:
            st.error(msg)

# ─── END-OF-DAY NOTES ─────────────────────────────────────────────────────
st.markdown("---")
st.header("🔍 End-of-Day Notes")
notes_df = fetch_notes_dataframe()
if notes_df.empty:
    st.info("All tags returned—no outstanding notes.")
else:
    st.dataframe(
        notes_df[["Tag","Observation"]],
        use_container_width=True
    )
