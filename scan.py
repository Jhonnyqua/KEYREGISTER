import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ------------------------
# Authorize using credentials from st.secrets
# ------------------------
def authorize_gspread():
    """
    Authorizes gspread using credentials stored in st.secrets.
    Make sure you have configured the secrets in Streamlit Cloud.
    """
    creds_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)
    return client

# ------------------------
# Update the key status in the Google Sheet ("Observation" column)
# ------------------------
def update_key_status(key_code, new_status):
    """
    Searches in the "Key Register" sheet for the row where the "Tag" column
    matches key_code, and updates the "Observation" column with new_status.
    Assumes:
      - Row 1: Title (e.g., "Key Register")
      - Row 2: Headers (including "Tag" and "Observation")
      - Row 3+: Data
    """
    try:
        client = authorize_gspread()
    except Exception as e:
        return f"Error authorizing gspread: {e}"
    
    spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "YOUR_SPREADSHEET_ID")
    
    try:
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
    except Exception as e:
        return f"Error opening the 'Key Register' sheet: {e}"
    
    try:
        # Row 2 contains the headers; data starts at row 3
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return f"Error retrieving data from the sheet: {e}"
    
    try:
        tag_index = headers.index("Tag") + 1  # 1-based
    except ValueError:
        return "Column 'Tag' not found in the sheet."
    
    row_number = None
    for i, record in enumerate(records, start=3):
        if record.get("Tag", "").strip() == key_code:
            row_number = i
            break

    if row_number is None:
        return f"No key found with code '{key_code}'."
    
    try:
        obs_index = headers.index("Observation") + 1
    except ValueError:
        return "Column 'Observation' not found in the sheet."
    
    try:
        # If new_status is empty, the cell is cleared (indicating the key is returned)
        sheet.update_cell(row_number, obs_index, new_status)
        return f"Record updated successfully at row {row_number}."
    except Exception as e:
        return f"Error updating the cell: {e}"

# ------------------------
# Streamlit Interface
# ------------------------
st.title("Key Update System")
st.markdown("This application updates the key assignment in your Google Sheet.")

# Create tabs for different functionalities
tabs = st.tabs(["Update Key Status", "Search Key", "View Records"])

# ------------------------
# Tab 1: Update Key Status
# ------------------------
with tabs[0]:
    st.header("Update Key Status")
    key_code = st.text_input("Key Code (e.g., M001):", key="update_key")
    
    # List of assignment options, ensuring "Returned" is the first option
    names = ["Returned", "ALLIAHN", "CAMILO", "CATALINA", "CONTRACTOR", "GONZALO", "JHONNY", "LUIS", "POL", "STELLA"]
    # Sort the names (except "Returned") alphabetically:
    others = sorted([name for name in names if name != "Returned"])
    options = ["Returned"] + others
    
    assigned_option = st.selectbox("Assigned To:", options, index=0, key="assigned_option")
    
    if assigned_option == "CONTRACTOR":
        contractor_name = st.text_input("Enter contractor's name:", key="contractor")
        final_assigned = contractor_name.strip() if contractor_name.strip() else "CONTRACTOR"
    elif assigned_option == "Returned":
        final_assigned = ""
    else:
        final_assigned = assigned_option
    
    if st.button("Update Record", key="update_button"):
        if not key_code:
            st.error("Please enter the key code.")
        else:
            result = update_key_status(key_code.strip(), final_assigned)
            if "Error" in result or "No key found" in result:
                st.error(result)
            else:
                st.success(result)

# ------------------------
# Tab 2: Search Key (placeholder)
# ------------------------
with tabs[1]:
    st.header("Search Key")
    search_code = st.text_input("Enter key code to search:", key="search_key")
    if st.button("Search", key="search_button"):
        st.info("Search functionality not implemented yet.")

# ------------------------
# Tab 3: View Records
# ------------------------
with tabs[2]:
    st.header("View Records")
    try:
        client = authorize_gspread()
        spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "YOUR_SPREADSHEET_ID")
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
        records = sheet.get_all_records(head=2)
        st.dataframe(records)
    except Exception as e:
        st.error(f"Error loading records: {e}")
