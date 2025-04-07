import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

def authorize_gspread():
    """
    Authorize gspread using credentials from st.secrets.
    Make sure you have configured the secrets in Streamlit Cloud as explained.
    """
    creds_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)
    return client

def update_key_status(key_code, new_status):
    """
    Searches in the 'Key Register' sheet for the row where the 'Tag' column matches key_code,
    and updates the 'Observation' column with new_status.
    
    Assumes:
      - Row 1: Title (e.g., "Key Register")
      - Row 2: Headers (including "Tag" and "Observation")
      - Row 3+: Data
    """
    try:
        client = authorize_gspread()
    except Exception as e:
        return f"Error authorizing gspread: {e}"
    
    # Read the spreadsheet ID from secrets
    spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "YOUR_SPREADSHEET_ID")

    try:
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
    except Exception as e:
        return f"Error opening 'Key Register' sheet: {e}"
    
    try:
        # Row 2 has headers
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return f"Error retrieving data from the sheet: {e}"
    
    # Find column 'Tag'
    try:
        tag_index = headers.index("Tag") + 1  # 1-based index
    except ValueError:
        return "Column 'Tag' not found in the sheet."
    
    # Find the row where 'Tag' == key_code
    row_number = None
    for i, record in enumerate(records, start=3):  # data starts at row 3
        if record.get("Tag", "").strip() == key_code:
            row_number = i
            break

    if row_number is None:
        return f"No key found with code '{key_code}'."
    
    # Find column 'Observation'
    try:
        obs_index = headers.index("Observation") + 1
    except ValueError:
        return "Column 'Observation' not found in the sheet."
    
    # Update the cell (if new_status is empty, the cell is cleared)
    try:
        sheet.update_cell(row_number, obs_index, new_status)
        return f"Record updated successfully at row {row_number}."
    except Exception as e:
        return f"Error updating the cell: {e}"

# --- STREAMLIT UI ---
st.title("Key Update System")
st.markdown("Enter the key code and select who is assigned. If the key is returned, choose 'Returned' to clear the assignment.")

# Input for the key code
key_code = st.text_input("Key Code (e.g., M001):")

# Create a sorted list of names, plus "CONTRACTOR" and "Returned"
names = [
    "ALLIAHN", "CAMILO", "CATALINA", "CONTRACTOR", "GONZALO",
    "JHONNY", "LUIS", "POL", "STELLA", "Returned"
]
sorted_names = sorted(names)

assigned_option = st.selectbox("Assigned To:", sorted_names)

# If user chooses CONTRACTOR, show an extra input for contractor name
if assigned_option == "CONTRACTOR":
    contractor_name = st.text_input("Enter contractor's name:")
    final_assigned = contractor_name.strip() if contractor_name.strip() else "CONTRACTOR"
elif assigned_option == "Returned":
    # If returned, we set final_assigned to an empty string
    final_assigned = ""
else:
    final_assigned = assigned_option

if st.button("Update Key Record"):
    if not key_code:
        st.error("Please enter the key code.")
    else:
        result = update_key_status(key_code.strip(), final_assigned)
        if "Error" in result or "No key found" in result:
            st.error(result)
        else:
            st.success(result)
