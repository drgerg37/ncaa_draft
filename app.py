import pandas as pd
import streamlit as st
import altair as alt
import base64
import os
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIG ---
st.set_page_config(page_title="Madness Managed!", layout="wide")

# --- GLOBAL VARIABLES ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"
ROUNDS = ['RD 1', 'RD 2', 'Sweet 16', 'Elite 8', 'Final 4', 'Final']
DB_COLUMNS = ["Owner", "Player", "Team", "Seed", "PPG"] + ROUNDS + ["Total", "Predicted", "Last Sync"]

# --- WIZARDING FONTS & STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Henny+Penny&display=swap');
    
    /* Apply magical font ONLY to specific classes */
    .wizard-title {
        font-family: 'Henny Penny', cursive;
        font-size: 65px !important;
        color: #FFD700;
        text-shadow: 3px 3px 5px #000000;
        text-align: center;
        margin-bottom: 0px;
        line-height: 1.2;
    }
    .wizard-subtitle {
        font-family: 'Henny Penny', cursive;
        font-size: 24px !important;
        color: #f0f0f0;
        text-align: center;
        font-style: italic;
        margin-bottom: 30px;
    }
    /* Ensure Subheaders also use the font */
    h2, h3 {
        font-family: 'Henny Penny', cursive !important;
        color: #FFD700 !important;
    }
    
    /* Standard font for dataframes and tables */
    .stDataFrame, [data-testid="stTable"] {
        font-family: 'Inter', sans-serif !important;
    }
    </style>
    """, unsafe_allow_html=True)

TEAM_COLORS = {
    "Illinois": "#E84A27", "Purdue": "#CEB888", "Northwestern": "#4E2A84", "Iowa": "#FFCD00",
    "Minnesota": "#7A0019", "Michigan": "#00274C", "Michigan State": "#18453B", "Ohio State": "#BB0000",
    "Indiana": "#990000", "Wisconsin": "#C5050C", "Maryland": "#E03A3E", "Rutgers": "#CC0033",
    "Penn State": "#041E42", "Nebraska": "#E41C38", "UCLA": "#2D68C4", "USC": "#990000",
    "Oregon": "#154733", "Washington": "#4B2E83", "Houston": "#C8102E", "Kansas": "#0051BA", 
    "Iowa State": "#C8102E", "Baylor": "#154734", "Texas": "#BF5700", "Texas Tech": "#CC0000", 
    "BYU": "#002255", "TCU": "#4D1979", "Kentucky": "#0033A0", "Tennessee": "#FF8200", 
    "Auburn": "#0C2340", "Alabama": "#9E1B32", "Florida": "#FA4616", "South Carolina": "#73000A", 
    "Texas A&M": "#500000", "Arkansas": "#9D2235", "Duke": "#003087", "North Carolina": "#7BAFD4", 
    "Virginia": "#232D4B", "Clemson": "#F56600", "UConn": "#000E2F", "Marquette": "#0033A0", 
    "Creighton": "#005CA9", "Villanova": "#002D72", "Gonzaga": "#041E42", "Arizona": "#CC0033", 
    "San Diego State": "#A6192E", "Colorado State": "#1E4D2B", "Utah State": "#0F2439", 
    "New Mexico": "#BA0C2F", "Nevada": "#003366", "Boise State": "#0033A0", "St. Mary's": "#E31837",
    "Dayton": "#004B8D", "Florida Atlantic": "#003366", "Drake": "#00447C", "Indiana State": "#005CA9", 
    "Princeton": "#FF6000", "Yale": "#00356B", "Grand Canyon": "#522398", "McNeese": "#FFCC00", 
    "Samford": "#00235D", "Howard": "#003A63", "UMBC": "#FFC20E"
}

@st.cache_data
def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""

@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

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

# --- THE UPDATED TITLE ---
st.markdown('<h1 class="wizard-title">🏀 Madness Managed!</h1>', unsafe_allow_html=True)
st.markdown('<p class="wizard-subtitle">I solemnly swear that I am up to no good (with this data).</p>', unsafe_allow_html=True)

if len(db_df) < 10:
    current_turn = "Greg" if len(db_df) % 2 == 0 else "Brad"
    st.header(f"👉 Currently Picking: **{current_turn}**")
    st.progress(len(db_df) / 10)
    drafted_names = db_df['Player'].tolist()
    filtered_df = available_players_df[~available_players_df['Player'].isin(drafted_names)]
    current_user_picks = len(db_df[db_df['Owner'] == current_turn])
    if current_user_picks == 4:
        filtered_df = filtered_df[filtered_df['Seed'] >= 7]
        st.warning("🚨 **5th Pick Constraint Active:** 7-seed or lower selection required!")
    selected_player_name = st.selectbox("Select Player:", filtered_df['Player'].tolist())
    if st.button(f"Draft {selected_player_name} for {current_turn}", type="primary"):
        player_data = filtered_df[filtered_df['Player'] == selected_player_name].iloc[0]
        new_row = [current_turn, player_data['Player'], player_data['Team'], int(player_data['Seed']), float(player_data['PPG']), "", "", "", "", "", "", 0, 0, ""]
        sheet.append_row(new_row)
        st.rerun() 
else:
    def process_scores(df_input):
        df_proc = df_input.copy()
        for index, row in df_proc.iterrows():
            total, blanks, hit_x = 0, 0, False
            for r in ROUNDS:
                if r not in df_proc.columns: continue
                val = str(row[r]).strip().upper()
                if hit_x or val == 'X':
                    hit_x = True
                    df_proc.at[index, r] = 'X'
                elif val and val != "NAN":
                    try:
                        total += float(val)
                        df_proc.at[index, r] = val
                    except:
                        df_proc.at[index, r] = ""; blanks += 1
                else:
                    df_proc.at[index, r] = ""; blanks += 1
            df_proc.at[index, 'Total'] = total
            df_proc.at[index, 'Predicted'] = total + (float(row.get('PPG', 0)) * blanks)
        return df_proc

    db_df = process_scores(db_df)
    greg_df = db_df[db_df['Owner'] == 'Greg'].reset_index(drop=True)
    brad_df = db_df[db_df['Owner'] == 'Brad'].reset_index(drop=True)

    def style_dataframe(df_styled):
        def row_style(row):
            if 'X' in row.values: return ['background-color: #4a0000; text-decoration: line-through; color: #ff9999'] * len(row)
            return [''] * len(row)
        def team_color(val):
            color = TEAM_COLORS.get(val, "")
            if color:
                text_color = "black" if color in ["#FFCD00", "#CEB888", "#7BAFD4", "#FFC20E", "#FFCC00"] else "white"
                return f'background-color: {color}; color: {text_color}; font-weight: bold;'
            return ''
        styler = df_styled.style.apply(row_style, axis=1)
        return styler.map(team_color, subset=['Team']) if hasattr(styler, 'map') else styler.applymap(team_color, subset=['Team'])

    def sync_edits(owner, session_key, original_df):
        edits = st.session_state[session_key]["edited_rows"]
        if edits:
            for idx, row_edits in edits.items():
                for col, val in row_edits.items(): original_df.at[int(idx), col] = val
            update_google_sheet(pd.concat([process_scores(original_df), db_df[db_df['Owner'] != owner]], ignore_index=True))

    col1, col2 = st.columns(2)
    display_cols = ['Player', 'Team', 'Seed', 'PPG', 'Opening Round', 'Round of 32', 'Sweet 16', 'Elite 8', 'Final 4', 'Final', 'Total']
    
    with col1:
        st.subheader("Greg's Marauders")
        st.data_editor(style_dataframe(greg_df), hide_index=True, column_order=display_cols, key="greg_editor", on_change=sync_edits, args=("Greg", "greg_editor", greg_df), use_container_width=True)
        st.metric("Score", f"{greg_df['Total'].sum():g}", delta=f"Potential: {greg_df['Predicted'].sum():.1f}")

    with col2:
        st.subheader("Brad's Marauders")
        st.data_editor(style_dataframe(brad_df), hide_index=True, column_order=display_cols, key="brad_editor", on_change=sync_edits, args=("Brad", "brad_editor", brad_df), use_container_width=True)
        st.metric("Score", f"{brad_df['Total'].sum():g}", delta=f"Potential: {brad_df['Predicted'].sum():.1f}")

    st.divider()

    # --- UPDATED BACKGROUND IMAGE CALL ---
    img_base64 = get_base64_of_bin_file('Gemini_Generated_Image_ij5asoij5asoij5a.png')
    st.markdown(f"""
        <style>
        [data-testid="stVegaLiteChart"] {{
            background-image: url("data:image/png;base64,{img_base64}");
            background-size: cover; background-position: center;
            border-radius: 15px; padding: 25px;
        }}
        </style>
        """, unsafe_allow_html=True)

    chart_data = pd.DataFrame({"Owner": ["Greg", "Brad"], "Points": [greg_df['Total'].sum(), brad_df['Total'].sum()]})
    bars = alt.Chart(chart_data).mark_bar(cornerRadius=8, size=50).encode(
        x=alt.X('Points:Q', axis=None), 
        y=alt.Y('Owner:N', sort='-x', axis=alt.Axis(labelFontSize=22, labelFont='Henny Penny', labelColor='white', labelFontWeight='bold', domain=False, ticks=False)), 
        color=alt.Color('Owner:N', scale=alt.Scale(domain=['Greg', 'Brad'], range=['#FF9500', '#FF3B30']), legend=None)
    )
    text = alt.Chart(chart_data).mark_text(align='left', dx=15, fontSize=28, font='Henny Penny', color='white').encode(
        x='Points:Q', y=alt.Y('Owner:N', sort='-x'), text='Points:Q'
    )
    st.altair_chart((bars + text).properties(title=alt.TitleParams(text="POINTS TRACKER", font='Henny Penny', fontSize=32, color='white', dy=-20), height=300, background='transparent').configure_view(strokeWidth=0), use_container_width=True)