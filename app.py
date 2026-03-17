import pandas as pd
import streamlit as st
import altair as alt
import base64
import os
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Project Ligand Draft", layout="wide")

# --- GLOBAL VARIABLES ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"
ROUNDS = ['RD 1', 'RD 2', 'Sweet 16', 'Elite 8', 'Final 4', 'Final']
DB_COLUMNS = ["Owner", "Player", "Team", "Seed", "PPG"] + ROUNDS + ["Total", "Predicted", "Last Sync"]

TEAM_COLORS = {
    # The Big Ten
    "Illinois": "#E84A27", "Purdue": "#CEB888", "Northwestern": "#4E2A84", "Iowa": "#FFCD00",
    "Minnesota": "#7A0019", "Michigan": "#00274C", "Michigan State": "#18453B", "Ohio State": "#BB0000",
    "Indiana": "#990000", "Wisconsin": "#C5050C", "Maryland": "#E03A3E", "Rutgers": "#CC0033",
    "Penn State": "#041E42", "Nebraska": "#E41C38", "UCLA": "#2D68C4", "USC": "#990000",
    "Oregon": "#154733", "Washington": "#4B2E83",

    # Big 12 Heavyweights
    "Houston": "#C8102E", "Kansas": "#0051BA", "Iowa State": "#C8102E", "Baylor": "#154734",
    "Texas": "#BF5700", "Texas Tech": "#CC0000", "BYU": "#002255", "TCU": "#4D1979",

    # SEC Powerhouses
    "Kentucky": "#0033A0", "Tennessee": "#FF8200", "Auburn": "#0C2340", "Alabama": "#9E1B32",
    "Florida": "#FA4616", "South Carolina": "#73000A", "Texas A&M": "#500000", "Arkansas": "#9D2235",

    # ACC & Big East
    "Duke": "#003087", "North Carolina": "#7BAFD4", "Virginia": "#232D4B", "Clemson": "#F56600",
    "UConn": "#000E2F", "Marquette": "#0033A0", "Creighton": "#005CA9", "Villanova": "#002D72",

    # West Coast & Mountain West
    "Gonzaga": "#041E42", "Arizona": "#CC0033", "San Diego State": "#A6192E", "Colorado State": "#1E4D2B",
    "Utah State": "#0F2439", "New Mexico": "#BA0C2F", "Nevada": "#003366", "Boise State": "#0033A0",
    "St. Mary's": "#E31837",

    # Mid-Majors, Cinderellas & First Four
    "Dayton": "#004B8D", "Florida Atlantic": "#003366", "Drake": "#00447C", "Indiana State": "#005CA9",
    "Princeton": "#FF6000", "Yale": "#00356B", "Grand Canyon": "#522398", "McNeese": "#FFCC00",
    "Samford": "#00235D", "Howard": "#003A63", "UMBC": "#FFC20E"
}

# --- HELPER: LOAD LOCAL IMAGE FOR BACKGROUND ---
@st.cache_data
def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

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
        return pd.DataFrame(columns=['Player', 'Team', 'Seed', 'PPG'])

available_players_df = load_csv_data()

# --- 3. GOOGLE SHEET HELPER FUNCTIONS ---
client = get_gspread_client()
sheet = client.open_by_url(SHEET_URL).sheet1

def update_google_sheet(df):
    sheet.clear()
    sheet.update(range_name='A1', values=[df.columns.values.tolist()] + df.values.tolist())

try:
    data = sheet.get_all_records()
    db_df = pd.DataFrame(data)
    db_df = db_df.dropna(subset=['Player'])
    db_df = db_df[db_df['Player'].astype(str).str.strip() != '']
    if db_df.empty or "Player" not in db_df.columns:
        db_df = pd.DataFrame(columns=DB_COLUMNS)
except Exception:
    db_df = pd.DataFrame(columns=DB_COLUMNS)

for r in ROUNDS:
    if r in db_df.columns:
        db_df[r] = db_df[r].fillna("").astype(str)

# --- 4. THE DRAFTING ROOM (< 10 Players) ---
if len(db_df) < 10:
    st.title("🏀 NCAA Tournament Player Draft")
    
    current_turn = "Greg" if len(db_df) % 2 == 0 else "Brad"
    st.header(f"👉 Currently Picking: **{current_turn}**")
    st.progress(len(db_df) / 10, text=f"{len(db_df)} out of 10 players drafted")
    st.divider()
    
    drafted_names = db_df['Player'].tolist()
    filtered_df = available_players_df[~available_players_df['Player'].isin(drafted_names)]
    
    current_user_picks = len(db_df[db_df['Owner'] == current_turn])
    if current_user_picks == 4:
        filtered_df = filtered_df[filtered_df['Seed'] >= 7]
        st.warning("🚨 **5th Pick Constraint Active:** The pool has been filtered. You may only select a 7-seed or lower!")
    
    selected_player_name = st.selectbox("Search & Select a Player to Draft:", filtered_df['Player'].tolist())
    
    if st.button(f"Draft {selected_player_name} for {current_turn}", type="primary"):
        player_data = filtered_df[filtered_df['Player'] == selected_player_name].iloc[0]
        
        new_row = [
            current_turn, player_data['Player'], player_data['Team'], 
            int(player_data['Seed']), float(player_data['PPG']),
            "", "", "", "", "", "", 0, 0, ""
        ]
        
        sheet.append_row(new_row)
        st.rerun() 

    st.divider()
    
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
    st.title("🏆 March Madness 2026")
    st.success("The Draft is Complete! The system is now waiting for Melvin to sync live scores.")
    
    def process_scores(df_input):
        df_proc = df_input.copy()
        for index, row in df_proc.iterrows():
            total = 0
            blanks = 0
            hit_x = False
            for r in ROUNDS:
                if r not in df_proc.columns: continue
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
            try:
                df_proc.at[index, 'Predicted'] = total + (float(row.get('PPG', 0)) * blanks)
            except ValueError:
                df_proc.at[index, 'Predicted'] = total
        return df_proc

    db_df = process_scores(db_df)

    greg_df = db_df[db_df['Owner'] == 'Greg'].reset_index(drop=True)
    brad_df = db_df[db_df['Owner'] == 'Brad'].reset_index(drop=True)

    def style_dataframe(df_styled):
        def row_style(row):
            if 'X' in row.values:
                return ['background-color: #4a0000; text-decoration: line-through; color: #ff9999'] * len(row)
            return [''] * len(row)
            
        def team_color(val):
            color = TEAM_COLORS.get(val, "")
            if color:
                text_color = "black" if color in ["#FFCD00", "#CEB888", "#7BAFD4", "#FFC20E", "#FFCC00"] else "white"
                return f'background-color: {color}; color: {text_color}; font-weight: bold; text-align: center;'
            return ''

        styler = df_styled.style.apply(row_style, axis=1)
        
        if hasattr(styler, 'map'):
            styler = styler.map(team_color, subset=['Team'])
        else:
            styler = styler.applymap(team_color, subset=['Team'])
            
        return styler

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
            update_google_sheet(final_db)

    col1, col2 = st.columns(2)
    display_cols = ['Player', 'Team', 'Seed', 'PPG', 'RD 1', 'RD 2', 'Sweet 16', 'Elite 8', 'Final 4', 'Final', 'Total']
    col_config = {"PPG": st.column_config.NumberColumn("PPG", format="%.1f")}

    with col1:
        st.subheader("Greg's Players")
        st.data_editor(
            style_dataframe(greg_df), 
            hide_index=True,
            column_order=[c for c in display_cols if c in greg_df.columns],
            column_config=col_config,
            disabled=['Player', 'Team', 'Seed', 'PPG', 'Total'],
            key="greg_editor",
            on_change=sync_edits_to_cloud,
            args=("Greg", "greg_editor", greg_df),
            use_container_width=True
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
            column_order=[c for c in display_cols if c in brad_df.columns],
            column_config=col_config,
            disabled=['Player', 'Team', 'Seed', 'PPG', 'Total'],
            key="brad_editor",
            on_change=sync_edits_to_cloud,
            args=("Brad", "brad_editor", brad_df),
            use_container_width=True
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

    chart_data = pd.DataFrame({"Owner": ["Greg", "Brad"], "Total Points": [greg_total, brad_total]})
    
    bars = alt.Chart(chart_data).mark_bar(
        cornerRadiusTopRight=8, cornerRadiusBottomRight=8, size=50, opacity=0.85 
    ).encode(
        x=alt.X('Total Points:Q', axis=None), 
        y=alt.Y('Owner:N', sort='-x', axis=alt.Axis(labelAngle=0, title=None, labelFontSize=22, labelColor='black', labelFontWeight='bold', domain=False, ticks=False, labelPadding=15)), 
        color=alt.Color('Owner:N', scale=alt.Scale(domain=['Greg', 'Brad'], range=['#FF9500', '#FF3B30']), legend=None),
        tooltip=['Owner', 'Total Points']
    )

    text = alt.Chart(chart_data).mark_text(
        align='left', baseline='middle', dx=10, fontSize=24, fontWeight='bold', color='black'
    ).encode(
        x='Total Points:Q', y=alt.Y('Owner:N', sort='-x'), text='Total Points:Q'
    )

    chart = (bars + text).properties(
        title=alt.TitleParams(text="TEAM TOTALS", fontSize=28, anchor='middle', color='black', dy=-15),
        height=250, background='transparent'
    ).configure_view(strokeWidth=0, fill='transparent').configure_axis(grid=False)
    
    st.altair_chart(chart, use_container_width=True)
    
    st.divider()
    if st.button("🚨 Clear Draft & Reset Database"):
        update_google_sheet(pd.DataFrame(columns=DB_COLUMNS))
        st.rerun()