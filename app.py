import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# PAGE CONFIG
st.set_page_config(page_title="Project Ligand: Draft Board", layout="wide")

# THE FIX: Hardcoding the Sheet URL directly
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"

# AUTH & DATA FETCH
def get_data():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    # Using the hardcoded URL instead of secrets
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    sync_time = sheet.acell('N1').value
    return pd.DataFrame(data), sync_time

# UI TABS
tab1, tab2 = st.tabs(["🏆 Leaderboard", "📝 Draft Assistant"])

with tab1:
    st.title("🏀 Live Leaderboard")
    try:
        df, last_sync = get_data()
        st.metric("Last Heartbeat Sync", last_sync if last_sync else "N/A")
        
        # Display Totals by Owner (Greg vs Brad)
        if 'Owner' in df.columns and 'Total' in df.columns:
            standings = df.groupby('Owner')['Total'].sum().sort_values(ascending=False)
            st.subheader("Current Standings")
            st.table(standings)
        
        st.subheader("Full Roster")
        st.dataframe(df, width='stretch', hide_index=True)
    except Exception as e:
        st.error(f"Waiting for Draft Data: {e}")

with tab2:
    st.title("🧪 Scouting & Draft Search")
    try:
        research_df = pd.read_csv('ncaa_2026_top_scorers.csv')
        search_query = st.text_input("Search for a player to draft:")
        
        if search_query:
            results = research_df[research_df['Player'].str.contains(search_query, case=False, na=False)]
            st.write(f"Showing results for: **{search_query}**")
            st.dataframe(results, width='stretch', hide_index=True)
        else:
            st.write("Enter a name (e.g., 'Boozer' or 'Smith') to see stats.")
            st.dataframe(research_df.head(10), width='stretch', hide_index=True)
            
        st.info("💡 **Drafting Instructions:** Find your player here, then type their name and your Owner name ('Greg' or 'Brad') directly into the Google Sheet.")
    except Exception as e:
        st.warning(f"Research CSV not found: {e}")

st.caption(f"Project Ligand • Version 2.2 • {datetime.now().strftime('%H:%M:%S')}")