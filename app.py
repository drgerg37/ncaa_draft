import pandas as pd
import streamlit as st
import altair as alt
import base64
import os
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="NCAA Player Draft", layout="wide")

# --- GLOBAL VARIABLES ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit?gid=0#gid=0"
ROUNDS = ['RD 1', 'RD 2', 'Sweet 16', 'Elite 8', 'Final 4', 'Final']
DB_COLUMNS = ["Owner", "Player", "Team", "Seed", "PPG"] + ROUNDS + ["Total", "Predicted"]

# --- HELPER: LOAD LOCAL IMAGE FOR BACKGROUND ---
@st.cache_data
def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

# --- 1. POTENTIAL ENERGY IMPORT (Top Scorers CSV) ---
@st.cache_data
def load_csv_data():
    df = pd.read_csv('ncaa_2026_top_scorers.csv')
    df = df[['Player', 'Team', 'Seed', 'PPG']]
    df['Seed'] = df['Seed'].astype(str).str.extract(r'(\d+)')
    df = df.dropna(subset=['Seed'])
    df['Seed'] = df['Seed'].astype(int)
    df['PPG'] = df['PPG'].round(1)
    return df

available_players_df = load_csv_data()

# --- 2. THE RESERVOIR CONNECTION (Google Sheets) ---
conn = st.connection("gsheets", type=GSheetsConnection)

# BUFFER FIX: ttl=10 stops the app from spamming Google on every keystroke
try:
    db_df = conn.read(spreadsheet=SHEET_URL, ttl=10)
    db_df = db_df.dropna(subset=['Player'])
    
    if db_df.empty or "Player" not in db_df.columns:
        db_df = pd.DataFrame(columns=DB_COLUMNS)
except Exception:
    db_df = pd.DataFrame(columns=DB_COLUMNS)

for r in ROUNDS:
    db_df[r] = db_df[r].fillna("").astype(str)

# --- 3. DRAFTING ROOM (Triggers if < 10 players in DB) ---
if len(db_df) < 10:
    st.title("🏀 NCAA Tournament Player Draft")
    
    current_turn = "Greg" if len(db_df) % 2 == 0 else "Brad"
    st.header(f"👉 Currently Picking: {current_turn}")
    st.divider()
    
    drafted_names = db_df['Player'].tolist()
    filtered_df = available_players_df[~available_players_df['Player'].isin(drafted_names)]
    
    current_user_picks = len(db_df[db_df['Owner'] == current_turn])
    if current_user_picks == 4:
        filtered_df = filtered_df[filtered_df['Seed'] >= 7]
        st.info("⚠️ **5th Pick Constraint Active:** The pool has been filtered. You may only select a 7-seed or lower!")
    
    selected_player_name = st.selectbox("Search & Select a Player to Draft:", filtered_df['Player'])
    
    if st.button(f"Draft Player for {current_turn}"):
        player_data = filtered_df[filtered_df['Player'] == selected_player_name].iloc[0]
        
        new_row = pd.DataFrame([{
            "Owner": current_turn,
            "Player": player_data['Player'],
            "Team": player_data['Team'],
            "Seed": player_data['Seed'],
            "PPG": player_data['PPG'],
            "RD 1": "", "RD 2": "", "Sweet 16": "", "Elite 8": "", "Final 4": "", "Final": "",
            "Total": 0.0,
            "Predicted": 0.0
        }])
        
        updated_db = pd.concat([db_df, new_row], ignore_index=True)
        conn.update(spreadsheet=SHEET_URL, data=updated_db)
        
        # CACHE CLEAR: Forces the app to fetch the new player from Google instantly
        st.cache_data.clear()
        st.rerun()

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Greg's Current Team")
        greg_view = db_df[db_df['Owner'] == 'Greg']
        if not greg_view.empty:
            st.dataframe(greg_view[['Player', 'Team', 'Seed', 'PPG']], hide_index=True)
    with col2:
        st.subheader("Brad's Current Team")
        brad_view = db_df[db_df['Owner'] == 'Brad']
        if not brad_view.empty:
            st.dataframe(brad_view[['Player', 'Team', 'Seed', 'PPG']], hide_index=True)

# --- 4. THE DASHBOARD (Triggers when DB has 10 players) ---
else:
    st.title("🏆 Tournament Dashboard")
    st.markdown("Enter points below. Enter **X** if a player's team is eliminated. Edits save to the cloud automatically.")
    
    def process_scores(df_input):
        df_proc = df_input.copy()
        for index, row in df_proc.iterrows():
            total = 0
            blanks = 0
            hit_x = False
            for r in ROUNDS:
                val = str(row[r]).strip().upper()
                if val.endswith(".0"): val = val[:-2] 
                
                if hit_x:
                    df_proc.at[index, r] = 'X'
                elif val == 'X':
                    hit_x = True
                    df_proc.at[index, r] = 'X'
                else:
                    if val != "" and val != "NAN":
                        try:
                            total += float(val)
                            df_proc.at[index, r] = val
                        except ValueError:
                            df_proc.at[index, r] = ""
                            blanks += 1
                    else:
                        df_proc.at[index, r] = ""
                        blanks += 1
            
            df_proc.at[index, 'Total'] = total
            df_proc.at[index, 'Predicted'] = total + (float(row['PPG']) * blanks)
        return df_proc

    db_df = process_scores(db_df)

    greg_df = db_df[db_df['Owner'] == 'Greg'].reset_index(drop=True)
    brad_df = db_df[db_df['Owner'] == 'Brad'].reset_index(drop=True)

    def style_dataframe(df_styled):
        def row_style(row):
            if 'X' in row.values:
                return ['background-color: #4a0000; text-decoration: line-through; color: #ff9999'] * len(row)
            return [''] * len(row)
        return df_styled.style.apply(row_style, axis=1)

    def sync_edits_to_cloud(owner, session_key, original_df):
        edits = st.session_state[session_key]["edited_rows"]
        if edits:
            for row_idx, row_edits in edits.items():
                for col, val in row_edits.items():
                    original_df.at[int(row_idx), col] = val
            
            processed_df = process_scores(original_df)
            other_owner = "Brad" if owner == "Greg" else "Greg"
            other_df = db_df[db_df['Owner'] == other_owner]
            
            final_db = pd.concat([processed_df, other_df], ignore_index=True)
            conn.update(spreadsheet=SHEET_URL, data=final_db)
            
            # CACHE CLEAR: Ensures both players see the new scores
            st.cache_data.clear()

    col1, col2 = st.columns(2)
    display_cols = ['Player', 'Team', 'Seed', 'PPG', 'RD 1', 'RD 2', 'Sweet 16', 'Elite 8', 'Final 4', 'Final', 'Total']
    col_config = {"PPG": st.column_config.NumberColumn("PPG", format="%.1f")}

    with col1:
        st.subheader("Greg's Players")
        st.data_editor(
            style_dataframe(greg_df), 
            hide_index=True,
            column_order=display_cols,
            column_config=col_config,
            disabled=['Player', 'Team', 'Seed', 'PPG', 'Total'],
            key="greg_editor",
            on_change=sync_edits_to_cloud,
            args=("Greg", "greg_editor", greg_df)
        )
        
        greg_total = greg_df['Total'].sum()
        greg_predicted = greg_df['Predicted'].sum()
        
        m1, m2 = st.columns(2)
        m1.metric("Current Score", f"{greg_total:g}")
        m2.metric("Predicted Potential", f"{greg_predicted:.1f}")

    with col2:
        st.subheader("Brad's Players")
        st.data_editor(
            style_dataframe(brad_df), 
            hide_index=True,
            column_order=display_cols,
            column_config=col_config,
            disabled=['Player', 'Team', 'Seed', 'PPG', 'Total'],
            key="brad_editor",
            on_change=sync_edits_to_cloud,
            args=("Brad", "brad_editor", brad_df)
        )
        
        brad_total = brad_df['Total'].sum()
        brad_predicted = brad_df['Predicted'].sum()
        
        m3, m4 = st.columns(2)
        m3.metric("Current Score", f"{brad_total:g}")
        m4.metric("Predicted Potential", f"{brad_predicted:.1f}")

    st.divider()

    img_base64 = get_base64_of_bin_file('image_5b6c44.png')
    bg_css = f'background-image: url("data:image/png;base64,{img_base64}");' if img_base64 else 'background-color: #f0f0f0;'

    court_css = f"""
    <style>
    [data-testid="stVegaLiteChart"] {{
        {bg_css}
        background-size: cover;
        background-position: center;
        border-radius: 12px;
        padding: 20px;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
    }}
    </style>
    """
    st.markdown(court_css, unsafe_allow_html=True)

    chart_data = pd.DataFrame({
        "Owner": ["Greg", "Brad"],
        "Total Points": [greg_total, brad_total]
    })
    
    bars = alt.Chart(chart_data).mark_bar(
        cornerRadiusTopRight=8, cornerRadiusBottomRight=8, size=50, opacity=0.85 
    ).encode(
        x=alt.X('Total Points:Q', axis=None), 
        y=alt.Y('Owner:N', sort='-x', axis=alt.Axis(labelAngle=0, title=None, labelFontSize=22, labelColor='black', labelFontWeight='bold', domain=False, ticks=False, labelPadding=15)), 
        color=alt.Color('Owner:N', scale=alt.Scale(domain=['Greg', 'Brad'], range=['#FF9500', '#FF3B30']), legend=None),
        tooltip=['Owner', 'Total Points']
    )

    text = alt.Chart(chart_data).mark_text(
        align='left', baseline='middle', dx=10, fontSize=24, fontWeight='bold', color='black', font='Helvetica Neue'
    ).encode(
        x='Total Points:Q', y=alt.Y('Owner:N', sort='-x'), text='Total Points:Q'
    )

    chart = (bars + text).properties(
        title=alt.TitleParams(text="TEAM TOTALS", font="Helvetica Neue", fontSize=28, anchor='middle', color='black', dy=-15),
        height=250, background='transparent'
    ).configure_view(strokeWidth=0, fill='transparent').configure_axis(grid=False)
    
    st.altair_chart(chart, width="stretch")
    
    st.divider()
    if st.button("🚨 Clear Draft & Reset Database"):
        empty_df = pd.DataFrame(columns=DB_COLUMNS)
        conn.update(spreadsheet=SHEET_URL, data=empty_df)
        
        # CACHE CLEAR: Empties the memory so the draft room reappears
        st.cache_data.clear()
        st.rerun()