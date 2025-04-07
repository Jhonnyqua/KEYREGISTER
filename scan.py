import streamlit as st
import gspread
import pandas as pd
import re
from google.oauth2.service_account import Credentials

# ===========================================
# Authorization using st.secrets (no file local)
# ===========================================
def authorize_gspread():
    """
    Authorizes gspread using credentials stored in st.secrets.
    Ensure your Streamlit Cloud secrets have a section [gcp_service_account].
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
# Functions for processing the data
# ===========================================
def simplify_address_15chars(address):
    """ Returns 15 characters starting from the first digit, after cleaning the text """
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
    """ Basic cleaning: remove extra spaces and special characters, lower-case """
    address = address.strip()
    simplified = re.sub(r'[^0-9a-zA-Z\s]', '', address).lower().strip()
    return simplified

def process_files(igms_csv_file, apply_15chars, order_by_cleaner):
    """
    Processes the IGMS CSV file and merges it with the available keys in Google Sheets.
    Returns a sorted DataFrame (with columns renamed in English) and a CSV in bytes.
    """
    try:
        client = authorize_gspread()
        spreadsheet_id = st.secrets["gcp_service_account"].get("spreadsheet_id", "YOUR_SPREADSHEET_ID")
        sheet = client.open_by_key(spreadsheet_id).worksheet("Key Register")
        data = sheet.get_all_values()
    except Exception as e:
        return None, None, "", f"Error accessing the sheet: {e}"

    try:
        # Row 1: Title, Row 2: Headers, Data starts at row 3.
        headers = sheet.row_values(2)
        records = sheet.get_all_records(head=2)
    except Exception as e:
        return None, None, "", f"Error retrieving data from the sheet: {e}"
    
    # Create DataFrame from keys and filter for available keys (Observation empty)
    df_keys = pd.DataFrame(data[2:], columns=headers)
    df_keys = df_keys.drop(columns='', errors='ignore')
    df_keys_available = df_keys[(df_keys["Observation"].isna()) | (df_keys["Observation"].str.strip() == "")]
    
    try:
        df_igms = pd.read_csv(igms_csv_file)
    except Exception as e:
        return None, None, "", f"Error reading the CSV: {e}"
    
    # Create "Simplified Address" column
    if apply_15chars:
        df_igms["Simplified Address"] = df_igms["Property Nickname"].apply(
            lambda x: simplify_address_15chars(x.split('-')[0])
        )
        df_keys_available["Simplified Address"] = df_keys_available["Property Address"].apply(
            lambda x: simplify_address_15chars(x)
        )
    else:
        df_igms["Simplified Address"] = df_igms["Property Nickname"].apply(
            lambda x: simplify_address_basic(x.split('-')[0])
        )
        df_keys_available["Simplified Address"] = df_keys_available["Property Address"].apply(
            lambda x: simplify_address_basic(x)
        )
    
    # Merge IGMS CSV and available keys
    df_merged = pd.merge(
        df_igms,
        df_keys_available,
        on="Simplified Address",
        how="left",
        suffixes=('_IGMS', '_Key')
    )
    
    # Create column "M_Key": assign the key (from column "Tag") if it starts with "M"
    df_merged["M_Key"] = df_merged.apply(
        lambda row: row["Tag"] if pd.notna(row["Tag"]) and row["Tag"].strip().startswith("M") else "",
        axis=1
    )
    
    # Select columns of interest
    df_result = df_merged[[ 
        "Property Nickname",  # From IGMS
        "Cleaner",            # From IGMS (could be empty)
        "M_Key",              # Key code
        "Simplified Address"  # Reference
    ]]
    df_result["Cleaner"] = df_result["Cleaner"].fillna("")
    
    sort_column = "Cleaner" if order_by_cleaner else "Property Nickname"
    df_result_sorted = df_result.sort_values(by=sort_column, na_position="first")
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
    Returns the record as a dictionary if found.
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
        obs_index = headers.index("Observation") + 1
    except ValueError:
        return "Column 'Observation' not found.", None
    try:
        # Read the entire row and create a dictionary
        row_values = sheet.row_values(row_number)
        record_dict = dict(zip(headers, row_values))
        return None, record_dict
    except Exception as e:
        return f"Error reading record: {e}", None

def generate_grouped_report(df_result_sorted):
    """
    Groups the final DataFrame by Property and concatenates all available Key Codes
    in a single cell, ordered by Assigned To and Property. Generates an attractive Excel report.
    """
    df_grouped = df_result_sorted.groupby("Property", as_index=False).agg({
        "Assigned To": "first",
        "Simplified Address": "first",
        "Key Code": lambda x: ", ".join(sorted(set(x.dropna().astype(str).str.strip()).difference({''})))
    })
    df_grouped = df_grouped.sort_values(by=["Assigned To", "Property"], na_position="first")
    
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

# Create three tabs: Update Key, Search Key, Grouped Report
tabs = st.tabs(["Update Key Status", "Search Key", "Grouped Report"])

# -------------------------------------------
# Tab 1: Update Key Status
# -------------------------------------------
with tabs[0]:
    st.header("Update Key Status")
    key_code_input = st.text_input("Key Code (e.g., M001):", key="update_key")
    
    # Assignment options with 'Returned' as the first option
    names = ["Returned", "ALLIAHN", "CAMILO", "CATALINA", "CONTRACTOR", "GONZALO", "JHONNY", "LUIS", "POL", "STELLA"]
    # The list is sorted alphabetically except "Returned" remains first.
    others = sorted([name for name in names if name not in ["Returned"]])
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

# -------------------------------------------
# Tab 2: Search Key
# -------------------------------------------
with tabs[1]:
    st.header("Search Key")
    search_code = st.text_input("Enter key code to search (e.g., M001):", key="search_key")
    if st.button("Search", key="search_button"):
        if not search_code:
            st.error("Please enter the key code to search.")
        else:
            error_msg, record = search_key_status(search_code.strip())
            if error_msg:
                st.error(error_msg)
            else:
                st.success("Record found:")
                st.write(record)

# -------------------------------------------
# Tab 3: Grouped Report
# -------------------------------------------
with tabs[2]:
    st.header("Grouped Report")
    # Aquí se asume que ya has procesado los datos mediante process_files
    # y que el DataFrame final está disponible. Por ejemplo, podemos permitir al usuario
    # cargar el CSV IGMS para generar el reporte.
    csv_file = st.file_uploader("Upload IGMS CSV file for report generation", type=["csv"], key="report_csv")
    apply_15chars = st.checkbox("Apply 15 characters from the first digit", value=True, key="report_apply")
    order_option = st.radio("Order by:", ("Cleaner", "Property Nickname"), key="report_order")
    order_by_cleaner = True if order_option == "Cleaner" else False

    if st.button("Generate Report", key="generate_report"):
        if csv_file is None:
            st.error("Please upload the IGMS CSV file.")
        else:
            df_result_sorted, csv_bytes, result_str, msg = process_files(csv_file, apply_15chars, order_by_cleaner)
            if df_result_sorted is None:
                st.error(msg)
            else:
                st.success(msg)
                st.text_area("Plain Report", result_str, height=300)
                st.download_button(label="Download Plain CSV", data=csv_bytes, file_name="resultado_llaves_m_sorted.csv", mime="text/csv")
                output_xlsx, xlsx_bytes, grouped_str = generate_grouped_report(df_result_sorted)
                st.text_area("Grouped Report", grouped_str, height=300)
                st.download_button(label="Download Grouped Excel", data=xlsx_bytes, file_name="resultado_llaves_m_grouped.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
