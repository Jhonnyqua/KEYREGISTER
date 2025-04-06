import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ========================
# Function to authorize gspread using a local credentials JSON file
# ========================
def authorize_gspread():
    # Replace with the full path to your credentials JSON file.
    cred_path = r"C:\Users\jhonn\OneDrive\Documents\bedspoke\key register\credenciales.json"
    credentials = Credentials.from_service_account_file(
        cred_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )
    client = gspread.authorize(credentials)
    return client

# ========================
# Function to update the key status in Google Sheets
# ========================
def update_key_status(key_code, new_status):
    try:
        client = authorize_gspread()
    except Exception as e:
        return f"Error authorizing gspread: {e}"
    
    # Replace with your actual spreadsheet ID (from the URL of your Google Sheet)
    spreadsheet_id = "1AEX3jKwAdO5cROqTe6k4uNv7BCy7lPOKHrGQjZA3om0"
    
    try:
        # Open the "Key Register" worksheet
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
    except Exception as e:
        return f"Error opening the 'Key Register' sheet: {e}"
    
    try:
        # Assume row 2 contains headers, and data starts at row 3
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return f"Error retrieving data from the sheet: {e}"
    
    # Find the column "Tag" (1-based index)
    try:
        tag_index = headers.index("Tag") + 1
    except ValueError:
        return "Column 'Tag' not found."
    
    # Search for the row where the "Tag" value matches key_code (data starts on row 3)
    row_number = None
    for i, record in enumerate(records, start=3):
        if record.get("Tag", "").strip() == key_code:
            row_number = i
            break

    if row_number is None:
        return f"No key found with code '{key_code}'."
    
    # Find the column "Observation"
    try:
        obs_index = headers.index("Observation") + 1
    except ValueError:
        return "Column 'Observation' not found."
    
    try:
        # Update the cell: if new_status is empty, the cell will be set to blank (indicating a returned key)
        sheet.update_cell(row_number, obs_index, new_status)
        return f"Record updated successfully at row {row_number}."
    except Exception as e:
        return f"Error updating the cell: {e}"

# ========================
# Streamlit User Interface
# ========================
st.title("Key Update System")
st.markdown("Enter the key code and select who is assigned to it. If the key is returned, choose 'Returned' to clear the assignment.")

# Input for the key code (e.g., M001)
key_code = st.text_input("Key Code (e.g., M001):")

# Define the list of names and options
names = ["ALLIAHN", "CAMILO", "CATALINA", "CONTRACTOR", "GONZALO", "JHONNY", "LUIS", "POL", "STELLA", "Returned"]
sorted_names = sorted(names)  # Sorted alphabetically

# Create a select box for assignment
assigned_option = st.selectbox("Assigned To:", sorted_names)

# If CONTRACTOR is selected, provide an additional text input for the contractor's name
if assigned_option == "CONTRACTOR":
    contractor_name = st.text_input("Enter contractor's name:")
    final_assigned = contractor_name.strip() if contractor_name.strip() else "CONTRACTOR"
elif assigned_option == "Returned":
    final_assigned = ""  # Empty string indicates the key is returned
else:
    final_assigned = assigned_option

if st.button("Update Key Record"):
    if not key_code:
        st.error("Please enter the key code.")
    else:
        result = update_key_status(key_code, final_assigned)
        if "Error" in result or "No key found" in result:
            st.error(result)
        else:
            st.success(result)
