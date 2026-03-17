import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Project Ligand Draft", layout="wide")

# --- GLOBAL VARIABLES ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"
ROUNDS = ['RD 1', 'RD 2', 'Sweet 16', 'Elite 8', 'Final 4', 'Final']
DB_COLUMNS = ["Owner", "Player", "Team", "Seed", "PPG"] + ROUNDS + ["Total", "Predicted", "Last Sync"]

# --- 1. AUTHENTICATION (The Bulletproof Method) ---
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

# --- 2. LOAD SCOUTING CSV ---
@st.cache_data
def load_csv_data():
    try:
        df = pd.read_csv('ncaa_2026_top_scorers.csv')
        df = df[['Player', 'Team', 'Seed', 'PPG']]
        df['Seed'] = df['Seed'].astype(str).str.extract(r'(\d+)')
        df = df.dropna(subset=['Seed'])
        df['Seed'] = df['Seed'].astype(int)
        df['PPG'] = df['PPG'].round(1)
        return df
    except Exception:
        # Fallback empty dataframe if CSV is missing
        return pd.DataFrame(columns=['Player', 'Team', 'Seed', 'PPG'])

available_players_df = load_csv_data()

# --- 3. FETCH LIVE GOOGLE SHEET DATA ---
client = get_gspread_client()
sheet = client.open_by_url(SHEET_URL).sheet1
data = sheet.get_all_records()

if not data:
    db_df = pd.DataFrame(columns=DB_COLUMNS)
else:
    db_df = pd.DataFrame(data)
    # Clean up empty rows
    db_df = db_df[db_df['Player'].astype(str).str.strip() != '']

# --- 4. THE DRAFTING ROOM (< 10 Players) ---
if len(db_df) < 10:
    st.title("🏀 NCAA Tournament Player Draft")
    
    # Alternating turns logic
    current_turn = "Greg" if len(db_df) % 2 == 0 else "Brad"
    st.header(f"👉 Currently Picking: **{current_turn}**")
    st.progress(len(db_df) / 10, text=f"{len(db_df)} out of 10 players drafted")
    st.divider()
    
    # Filter out players already drafted
    drafted_names = db_df['Player'].tolist()
    filtered_df = available_players_df[~available_players_df['Player'].isin(drafted_names)]
    
    # The 5th Pick Constraint
    current_user_picks = len(db_df[db_df['Owner'] == current_turn])
    if current_user_picks == 4:
        filtered_df = filtered_df[filtered_df['Seed'] >= 7]
        st.warning("🚨 **5th Pick Constraint Active:** The pool has been filtered. You may only select a 7-seed or lower!")
    
    # Draft Selection UI
    selected_player_name = st.selectbox("Search & Select a Player to Draft:", filtered_df['Player'].tolist())
    
    if st.button(f"Draft {selected_player_name} for {current_turn}", type="primary"):
        player_data = filtered_df[filtered_df['Player'] == selected_player_name].iloc[0]
        
        # Build the new row exactly matching your Google Sheet columns
        new_row = [
            current_turn,           # Owner
            player_data['Player'],  # Player
            player_data['Team'],    # Team
            int(player_data['Seed']),# Seed
            float(player_data['PPG']),# PPG
            "", "", "", "", "", "", # The 6 Rounds
            0,                      # Total
            0,                      # Predicted
            ""                      # Last Sync
        ]
        
        # Append directly to Google Sheet
        sheet.append_row(new_row)
        
        # Force a refresh to update the UI
        st.toast(f"✅ Successfully drafted {selected_player_name}!")
        st.rerun()

    st.divider()
    
    # Show current rosters
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Greg's Team")
        greg_view = db_df[db_df['Owner'] == 'Greg']
        st.dataframe(greg_view[['Player', 'Team', 'Seed', 'PPG']], hide_index=True, width='stretch')
    with col2:
        st.subheader("Brad's Team")
        brad_view = db_df[db_df['Owner'] == 'Brad']
        st.dataframe(brad_view[['Player', 'Team', 'Seed', 'PPG']], hide_index=True, width='stretch')

# --- 5. THE DASHBOARD (Draft Complete) ---
else:
    st.title("🏆 Tournament Dashboard")
    st.success("The Draft is Complete! The system is now waiting for Melvin to sync live scores.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Greg's Roster")
        greg_df = db_df[db_df['Owner'] == 'Greg']
        st.dataframe(greg_df[['Player', 'Team', 'Seed', 'Total']], hide_index=True, width='stretch')
    with col2:
        st.subheader("Brad's Roster")
        brad_df = db_df[db_df['Owner'] == 'Brad']
        st.dataframe(brad_df[['Player', 'Team', 'Seed', 'Total']], hide_index=True, width='stretch')