import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

st.set_page_config(page_title="Project Ligand: NCAA Draft", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"
CSV_FILE = 'ncaa_2026_top_scorers.csv'

def get_sheet_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url(SHEET_URL).sheet1
    return pd.DataFrame(sheet.get_all_records()), sheet.acell('N1').value

# TABS FOR ORGANIZATION
tab1, tab2 = st.tabs(["🏆 Leaderboard", "📊 Research Lab"])

with tab1:
    st.title("🏀 Live Leaderboard")
    try:
        df, last_sync = get_sheet_data()
        st.metric("Last Heartbeat Sync", last_sync if last_sync else "N/A")
        if 'Total' in df.columns:
            st.dataframe(df.sort_values(by='Total', ascending=False), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Connection Error: {e}")

with tab2:
    st.title("🧪 Scouting & Research")
    if os.path.exists(CSV_FILE):
        research_df = pd.read_csv(CSV_FILE)
        st.write("### 2026 Top Scoring Prospects")
        st.dataframe(research_df, use_container_width=True, hide_index=True)
    else:
        st.info("Scouting report (CSV) not found in the cloud yet. See terminal instructions to push it.")

st.caption(f"Project Ligand Architecture • {datetime.now().strftime('%H:%M:%S')}")