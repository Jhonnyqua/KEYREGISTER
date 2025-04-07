import streamlit as st
import gspread
import pandas as pd
import re
from google.oauth2.service_account import Credentials

# ===========================================
# 1. Authorization using st.secrets (no local file)
# ===========================================
def authorize_gspread():
    """
    Authorizes gspread using credentials stored in st.secrets.
    Make sure your Streamlit Cloud secrets contain a section [gcp_service_account].
    """
    creds_dict = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(credentials)
    return client

# ===========================================
# 2. Functions for Data Processing
# ===========================================
def simplify_address_15chars(address):
    """
    Returns 15 characters starting from the first digit, after cleaning the text.
    (Removes special characters, lowercases, and trims spaces.)
    """
    address = address.strip()
    match = re.search(r'\d', address)
    if match:
        start_index = match.start()
        substring = address[start_index:start_index+15]
    else:
        substring = address[:15]
    simplified = re.sub(r'[^0-9a-zA-Z\s]', '', substring).lower().strip()
    return simplified

def simplify_address_basic(address):
    """
    Basic cleaning: removes extra spaces and special characters, lowercases.
    """
    address = address.strip()
    simplified = re.sub(r'[^0-9a-zA-Z\s]', '', address).lower().strip()
    return simplified

def process_files(igms_csv_file, apply_15chars, order_by_cleaner):
    """
    Processes the IGMS CSV file and merges it with available keys from Google Sheets.
    Assumes:
      - Row 1: Title (e.g., "Key Register")
      - Row 2: Headers (including "Tag" and "Observation")
      - Row 3+: Data
    The CSV report is sorted by extracting the first alphabetical character of "Property Nickname"
    (ignoring any numbers).
    Returns:
      * df_result_sorted: The sorted DataFrame with columns renamed in English.
      * csv_bytes: The CSV report in bytes.
      * result_str: The string representation of the CSV report.
      * a status message.
    """
    try:
        client = authorize_gspread()
        spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "YOUR_SPREADSHEET_ID")
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
        data = sheet.get_all_values()
    except Exception as e:
        return None, None, "", f"Error accessing the sheet: {e}"
    
    try:
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return None, None, "", f"Error retrieving data from the sheet: {e}"
    
    # Create DataFrame from keys (rows 3+)
    df_keys = pd.DataFrame(data[2:], columns=headers)
    df_keys = df_keys.drop(columns='', errors='ignore')
    df_keys_available = df_keys[(df_keys["Observation"].isna()) | (df_keys["Observation"].str.strip() == "")]
    
    try:
        df_igms = pd.read_csv(igms_csv_file)
    except Exception as e:
        return None, None, "", f"Error reading the CSV: {e}"
    
    # Create "Simplified Address" column in both DataFrames using selected method
    if apply_15chars:
        df_igms["Simplified Address"] = df_igms["Property Nickname"].apply(lambda x: simplify_address_15chars(x.split('-')[0]))
        df_keys_available["Simplified Address"] = df_keys_available["Property Address"].apply(lambda x: simplify_address_15chars(x))
    else:
        df_igms["Simplified Address"] = df_igms["Property Nickname"].apply(lambda x: simplify_address_basic(x.split('-')[0]))
        df_keys_available["Simplified Address"] = df_keys_available["Property Address"].apply(lambda x: simplify_address_basic(x))
    
    # Merge the IGMS CSV with available keys on "Simplified Address"
    df_merged = pd.merge(
        df_igms,
        df_keys_available,
        on="Simplified Address",
        how="left",
        suffixes=('_IGMS', '_Key')
    )
    
    # Create "M_Key": assign the key (from column "Tag") if it starts with "M"
    df_merged["M_Key"] = df_merged.apply(lambda row: row["Tag"] if pd.notna(row["Tag"]) and row["Tag"].strip().startswith("M") else "", axis=1)
    
    # Select columns of interest
    df_result = df_merged[[ "Property Nickname", "Cleaner", "M_Key", "Simplified Address" ]]
    df_result["Cleaner"] = df_result["Cleaner"].fillna("")
    
    # For the CSV report: sort by the first alphabetical character of "Property Nickname"
    df_result_sorted = df_result.copy()
    df_result_sorted["SortKey"] = df_result_sorted["Property Nickname"].str.extract(r'([A-Za-z])', expand=False).fillna('')
    df_result_sorted = df_result_sorted.sort_values(by="SortKey", na_position="first")
    df_result_sorted = df_result_sorted.drop(columns=["SortKey"])
    
    # Rename columns to English
    df_result_sorted = df_result_sorted.rename(columns={
        "Property Nickname": "Property",
        "Cleaner": "Assigned To",
        "M_Key": "Key Code",
        "Simplified Address": "Simplified Address"
    })
    
    csv_bytes = df_result_sorted.to_csv(index=False).encode('utf-8')
    result_str = df_result_sorted.to_string(index=False, max_rows=None)
    return df_result_sorted, csv_bytes, result_str, "Process completed."

def search_key_status(key_code):
    """
    Searches for a key in the "Key Register" sheet by matching the "Tag" column.
    Returns an error message (if any) and the record as a dictionary.
    """
    try:
        client = authorize_gspread()
        spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "YOUR_SPREADSHEET_ID")
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return f"Error accessing the sheet: {e}", None
    
    try:
        tag_index = headers.index("Tag") + 1
    except ValueError:
        return "Column 'Tag' not found.", None
    
    row_number = None
    for i, record in enumerate(records, start=3):
        if record.get("Tag", "").strip() == key_code:
            row_number = i
            break
    if row_number is None:
        return f"No key found with code '{key_code}'.", None
    try:
        row_values = sheet.row_values(row_number)
        record_dict = dict(zip(headers, row_values))
        return None, record_dict
    except Exception as e:
        return f"Error reading record: {e}", None

def generate_grouped_report(df_result_sorted, grouping_option):
    """
    Groups the final DataFrame by Property and concatenates all Key Codes in one cell.
    If grouping_option is "Cleaner", the report is ordered by 'Assigned To' then 'Property'.
    If grouping_option is "Property", the report is ordered by 'Simplified Address' then 'Property'.
    Generates an Excel report (using xlsxwriter) for download.
    """
    df_grouped = df_result_sorted.groupby("Property", as_index=False).agg({
        "Assigned To": "first",
        "Simplified Address": "first",
        "Key Code": lambda x: ", ".join(sorted(set(x.dropna().astype(str).str.strip()).difference({''})))
    })
    
    if grouping_option == "Cleaner":
        df_grouped = df_grouped.sort_values(by=["Assigned To", "Property"], na_position="first")
    elif grouping_option == "Property":
        df_grouped = df_grouped.sort_values(by=["Simplified Address", "Property"], na_position="first")
    
    output_xlsx = "resultado_llaves_m_grouped.xlsx"
    with pd.ExcelWriter(output_xlsx, engine="xlsxwriter") as writer:
        df_grouped.to_excel(writer, sheet_name="Report", index=False)
        workbook = writer.book
        worksheet = writer.sheets["Report"]
        
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        for col_num, value in enumerate(df_grouped.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        worksheet.set_column(0, 0, 30, cell_format)  # Property
        worksheet.set_column(1, 1, 20, cell_format)  # Assigned To
        worksheet.set_column(2, 2, 40, cell_format)  # Simplified Address
        worksheet.set_column(3, 3, 30, cell_format)  # Key Code
    with open(output_xlsx, "rb") as f:
        xlsx_data = f.read()
    grouped_str = df_grouped.to_string(index=False, max_rows=None)
    return output_xlsx, xlsx_data, grouped_str

# ===========================================
# Streamlit Interface with Tabs
# ===========================================
st.title("Key Management System")

tabs = st.tabs(["Update Key Status", "Search Key", "Grouped Report"])

# ---------------------------
# Tab 1: Update Key Status
# ---------------------------
with tabs[0]:
    st.header("Update Key Status")
    key_code_input = st.text_input("Key Code (e.g., M001):", key="update_key")
    
    names = ["Returned", "ALLIAHN", "CAMILO", "CATALINA", "CONTRACTOR", "GONZALO", "JHONNY", "LUIS", "POL", "STELLA"]
    others = sorted([name for name in names if name != "Returned"])
    options = ["Returned"] + others
    assigned_option = st.selectbox("Assigned To:", options, index=0, key="update_assigned")
    
    if assigned_option == "CONTRACTOR":
        contractor_name = st.text_input("Enter contractor's name:", key="contractor")
        final_assigned = contractor_name.strip() if contractor_name.strip() else "CONTRACTOR"
    elif assigned_option == "Returned":
        final_assigned = ""
    else:
        final_assigned = assigned_option
    
    if st.button("Update Record", key="update_button"):
        if not key_code_input:
            st.error("Please enter the key code.")
        else:
            result = update_key_status(key_code_input.strip(), final_assigned)
            if "Error" in result or "No key found" in result:
                st.error(result)
            else:
                st.success(result)

# ---------------------------
# Tab 2: Search Key
# ---------------------------
with tabs[1]:
    st.header("Search Key")
    search_code = st.text_input("Enter key code to search (e.g., M001):", key="search_key")
    if st.button("Search", key="search_button"):
        if not search_code:
            st.error("Please enter a key code to search.")
        else:
            error_msg, record = search_key_status(search_code.strip())
            if error_msg:
                st.error(error_msg)
            else:
                st.success("Record found:")
                st.json(record)

# ---------------------------
# Tab 3: Grouped Report
# ---------------------------
with tabs[2]:
    st.header("Grouped Report")
    st.markdown("Upload the IGMS CSV file for report generation.")
    csv_file = st.file_uploader("Upload IGMS CSV", type=["csv"], key="report_csv")
    apply_15chars = st.checkbox("Apply 15 characters from the first digit", value=True, key="report_apply")
    grouping_option = st.radio("Group by:", ("Cleaner", "Property"), key="grouping_option")
    
    if st.button("Generate Grouped Report", key="generate_report"):
        if csv_file is None:
            st.error("Please upload the IGMS CSV file.")
        else:
            df_result_sorted, _, result_str, msg = process_files(csv_file, apply_15chars, order_by_cleaner=True)
            if df_result_sorted is None:
                st.error(msg)
            else:
                st.success(msg)
                # We only offer one download: the grouped Excel file.
                output_xlsx, xlsx_bytes, grouped_str = generate_grouped_report(df_result_sorted, grouping_option)
                st.text_area("Grouped Report", grouped_str, height=300)
                st.download_button(label="Download Grouped Excel", data=xlsx_bytes,
                                   file_name="resultado_llaves_m_grouped.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
