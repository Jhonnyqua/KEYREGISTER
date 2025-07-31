# MIT License
# © 2025 Your Name
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software.

import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2.service_account import Credentials
from gspread.exceptions import SpreadsheetNotFound, APIError

# ── Configuration ───────────────────────────────────────────────
st.set_page_config(
    page_title="🔑 Key Register Scanner",
    layout="centered"
)

SPREADSHEET_ID = st.secrets["gcp_service_account"]["spreadsheet_id"]

# ── Google Sheets Client ───────────────────────────────────────
@st.cache_resource
def gs_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)

# ── Update Function ─────────────────────────────────────────────
def update_key(tag: str, assignee: str, return_date: str) -> str:
    """
    Updates the 'Observation' column for the given tag.
    - If assignee == "Returned": clears the cell.
    - Else: writes "Assignee @ YYYY-MM-DD HH:MM:SS" with optional " • Return: YYYY-MM-DD"
    """
    try:
        client = gs_client()
        ss = client.open_by_key(SPREADSHEET_ID)
        ws = ss.worksheet("Key Register")
    except (SpreadsheetNotFound, APIError) as e:
        return f"Error opening sheet: {e}"

    headers = ws.row_values(2)
    if "Tag" not in headers or "Observation" not in headers:
        return "Sheet missing required columns."

    tag_col = headers.index("Tag") + 1
    obs_col = headers.index("Observation") + 1

    records = ws.get_all_records(head=2)
    row = next((i + 3 for i, r in enumerate(records)
                if str(r.get("Tag", "")).strip() == tag), None)
    if row is None:
        return f"No key found for '{tag}'."

    if assignee == "Returned":
        new_obs = ""
    else:
        ts = datetime.now(ZoneInfo("Australia/Brisbane"))\
                .replace(microsecond=0).isoformat(sep=" ")
        new_obs = f"{assignee} @ {ts}"
        if return_date:
            new_obs += f" • Return: {return_date}"

    try:
        ws.update_cell(row, obs_col, new_obs)
        return f"✅ Record updated on row {row}."
    except Exception as e:
        return f"Error writing to sheet: {e}"

# ── UI ──────────────────────────────────────────────────────────
st.title("🔑 Key Register Scanner")
st.write("Scan or type your tag code, choose who has it, and hit Update.")

# 1) Tag input
tag = st.text_input("Tag code (e.g. M001)", placeholder="M001")

# 2) Assignee
assignee = st.selectbox(
    "Assign to:",
    ["Returned", "Owner", "Guest", "Contractor",
     "ALLIAHN","CAMILO","CATALINA","GONZALO",
     "JHONNY","LUIS","POL","STELLA"]
)

# 3) Dynamic fields
return_date = ""
if assignee in ("Owner", "Guest"):
    return_date = st.date_input("Return date").isoformat()

contractor_name = ""
if assignee == "Contractor":
    contractor_name = st.text_input("Contractor name").strip()

# … widgets Tag + Assignee + dinámicos …

if st.button("Update Record"):
    if not tag.strip():
        st.error("Please scan a valid tag first.")
    else:
        final_assignee = (
            contractor_name
            if assignee == "Contractor" and contractor_name
            else assignee
        )
        msg = update_key(tag.strip(), final_assignee, return_date)
        if msg.startswith("✅"):
            st.success(msg)
            # ← Aquí es donde forzamos el rerun para limpiar TODO
            st.experimental_rerun()
        else:
            st.error(msg)

# ── End-of-Day Notes ───────────────────────────────────────────
st.markdown("---")
if st.button("🔍 Show End-of-Day Notes"):
    try:
        ws = gs_client().open_by_key(SPREADSHEET_ID).worksheet("Key Register")
        df = pd.DataFrame(ws.get_all_records(head=2))
        notes = df[df["Observation"].astype(str).str.strip() != ""]
        if notes.empty:
            st.info("No keys currently with observations.")
        else:
            st.dataframe(notes[["Tag", "Observation"]], height=300)
    except Exception as e:
        st.error(f"Error fetching notes: {e}")
