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
ROUNDS = ['Opening Round', 'Round of 32', 'Sweet 16', 'Elite 8', 'Final 4', 'Final']
DB_COLUMNS = ["Owner", "Player", "Team", "Seed", "PPG"] + ROUNDS + ["Total", "Predicted"]

LIGHT_TEAM_COLORS = {
    "#FFCD00", "#CEB888", "#7BAFD4", "#FFC20E", "#FFCC00",
    "#FF8200", "#FA4616", "#F56600", "#FF6000", "#BF5700"
}

# --- WIZARDING FONTS & STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/luminari');

    .wizard-title {
        font-family: 'Luminari', serif;
        font-size: 65px !important;
        color: #FFD700;
        text-shadow: 3px 3px 5px #000000;
        text-align: center;
        margin-bottom: 0px;
    }
    .wizard-subtitle {
        font-family: 'Luminari', serif;
        font-size: 24px !important;
        color: #f0f0f0;
        text-align: center;
        font-style: italic;
        margin-bottom: 30px;
    }
    h2, h3 {
        font-family: 'Luminari', serif !important;
        color: #FFD700 !important;
    }

    [data-testid="stDataFrame"] table,
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] td,
    [data-testid="stDataEditor"] table,
    [data-testid="stDataEditor"] th,
    [data-testid="stDataEditor"] td {
        font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif !important;
    }

    [data-testid="stMetric"] {
        background: rgba(0,0,0,0.3);
        border-radius: 10px;
        padding: 12px 16px;
        border: 1px solid rgba(255,215,0,0.3);
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Luminari', serif !important;
        color: #FFD700 !important;
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


# --- UTILITY FUNCTIONS ---
@st.cache_data
def get_base64_of_bin_file(bin_file):
    if os.path.exists(bin_file):
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return ""


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


@st.cache_resource
def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)


def read_sheet_to_df(ws):
    """Read entire sheet into a DataFrame. Returns empty DF on failure."""
    try:
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame(columns=DB_COLUMNS)
        df = pd.DataFrame(records)
        df = df.dropna(subset=['Player'])
        df = df[df['Player'].astype(str).str.strip() != '']
        # Migration from old column names
        df = df.rename(columns={'RD 1': 'Opening Round', 'RD 2': 'Round of 32'})
        if df.empty or "Player" not in df.columns:
            return pd.DataFrame(columns=DB_COLUMNS)
        return df
    except Exception:
        return pd.DataFrame(columns=DB_COLUMNS)


def write_df_to_sheet(ws, df):
    """Overwrite entire sheet with DataFrame contents."""
    ws.clear()
    # Convert everything to native Python types to avoid gspread serialization issues
    header = df.columns.tolist()
    rows = df.astype(str).values.tolist()
    ws.update(range_name='A1', values=[header] + rows)


# --- INIT ---
available_players_df = load_csv_data()
client = get_gspread_client()
sheet = client.open_by_url(SHEET_URL).sheet1
db_df = read_sheet_to_df(sheet)

# Ensure all round columns exist and are string
for r in ROUNDS:
    if r not in db_df.columns:
        db_df[r] = ""
    db_df[r] = db_df[r].fillna("").astype(str)

# Ensure numeric columns exist
for col in ['Total', 'Predicted']:
    if col not in db_df.columns:
        db_df[col] = 0.0


# --- STYLE ENGINE ---
def style_dataframe(df_input):
    """Pandas Styler for team colors. Works with st.dataframe(), NOT st.data_editor()."""
    df = df_input.copy()

    def apply_styles(row):
        styles = [''] * len(row)

        if 'Team' in row.index:
            team_idx = list(row.index).index('Team')
            color = TEAM_COLORS.get(row['Team'], "")
            if color:
                text_color = "black" if color in LIGHT_TEAM_COLORS else "white"
                styles[team_idx] = (
                    f'background-color: {color}; color: {text_color}; font-weight: bold;'
                )

        # Eliminated row — check ONLY round columns
        round_vals = [str(row.get(r, "")).strip().upper() for r in ROUNDS if r in row.index]
        if 'X' in round_vals:
            return [
                'background-color: #4a0000; text-decoration: line-through; color: #ff9999;'
            ] * len(row)

        return styles

    styler = df.style.apply(apply_styles, axis=1)
    if 'PPG' in df.columns:
        styler = styler.format({'PPG': '{:.1f}'})
    if 'Total' in df.columns:
        styler = styler.format(
            {'Total': lambda v: f'{v:g}' if isinstance(v, (int, float)) else v}
        )
    return styler


# --- HEADER ---
st.markdown(
    '<h1 class="wizard-title">🏀 Madness Managed!</h1>',
    unsafe_allow_html=True
)
st.markdown(
    '<p class="wizard-subtitle">I solemnly swear that I am up to no good (with this data).</p>',
    unsafe_allow_html=True
)


# ============================================================
# 1. DRAFT MODE (< 10 players drafted)
# ============================================================
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

    if not filtered_df.empty:
        selected_player_name = st.selectbox(
            "Search & Select a Player to Draft:", filtered_df['Player']
        )

        if st.button(
            f"Draft {selected_player_name} for {current_turn}", type="primary"
        ):
            player_data = filtered_df[
                filtered_df['Player'] == selected_player_name
            ].iloc[0]

            # Build new row as DataFrame, concat, write ENTIRE frame back
            # (same full-overwrite pattern that worked in v1)
            new_row = pd.DataFrame([{
                "Owner": current_turn,
                "Player": player_data['Player'],
                "Team": player_data['Team'],
                "Seed": int(player_data['Seed']),
                "PPG": float(player_data['PPG']),
                "Opening Round": "",
                "Round of 32": "",
                "Sweet 16": "",
                "Elite 8": "",
                "Final 4": "",
                "Final": "",
                "Total": 0.0,
                "Predicted": 0.0
            }])

            updated_db = pd.concat([db_df, new_row], ignore_index=True)
            write_df_to_sheet(sheet, updated_db)
            st.cache_data.clear()
            st.rerun()
    else:
        st.error("No players available to draft!")

    st.divider()
    d1, d2 = st.columns(2)
    with d1:
        st.subheader("Greg's Marauders")
        g_team = db_df[db_df['Owner'] == 'Greg']
        if not g_team.empty:
            st.dataframe(
                style_dataframe(g_team),
                hide_index=True,
                column_order=['Player', 'Team', 'Seed', 'PPG'],
                use_container_width=True
            )
    with d2:
        st.subheader("Brad's Marauders")
        b_team = db_df[db_df['Owner'] == 'Brad']
        if not b_team.empty:
            st.dataframe(
                style_dataframe(b_team),
                hide_index=True,
                column_order=['Player', 'Team', 'Seed', 'PPG'],
                use_container_width=True
            )


# ============================================================
# 2. DASHBOARD MODE (draft complete)
# ============================================================
else:
    st.markdown(
        "Enter points below. Enter **X** if a player's team is eliminated. "
        "Edits save to the cloud automatically."
    )

    def process_scores(df_input):
        df_proc = df_input.copy()
        for index, row in df_proc.iterrows():
            total, blanks, hit_x = 0, 0, False
            for r in ROUNDS:
                if r not in df_proc.columns:
                    continue
                val = str(row[r]).strip().upper()
                if val.endswith(".0"):
                    val = val[:-2]
                if hit_x or val == 'X':
                    hit_x = True
                    df_proc.at[index, r] = 'X'
                elif val and val != "" and val != "NAN":
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
            ppg = 0
            try:
                ppg = float(row.get('PPG', 0))
            except (ValueError, TypeError):
                pass
            df_proc.at[index, 'Predicted'] = total + (ppg * blanks)
        return df_proc

    db_df = process_scores(db_df)
    greg_df = db_df[db_df['Owner'] == 'Greg'].reset_index(drop=True)
    brad_df = db_df[db_df['Owner'] == 'Brad'].reset_index(drop=True)

    roster_cols = ['Player', 'Team', 'Seed', 'PPG'] + ROUNDS + ['Total']
    disabled_cols = ['Player', 'Team', 'Seed', 'PPG', 'Total', 'Predicted', 'Owner']

    def sync_edits_to_cloud(owner, session_key, original_df):
        """Write edits back to Google Sheets."""
        edits = st.session_state[session_key]["edited_rows"]
        if edits:
            for row_idx, row_edits in edits.items():
                for col, val in row_edits.items():
                    original_df.at[int(row_idx), col] = val

            processed_df = process_scores(original_df)
            other_df = db_df[db_df['Owner'] != owner]
            final_db = pd.concat([processed_df, other_df], ignore_index=True)
            write_df_to_sheet(sheet, final_db)
            st.cache_data.clear()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Greg's Marauders")

        st.dataframe(
            style_dataframe(greg_df),
            hide_index=True,
            column_order=roster_cols,
            use_container_width=True
        )

        with st.expander("✏️ Edit Scores", expanded=False):
            st.data_editor(
                greg_df,
                hide_index=True,
                column_order=['Player'] + ROUNDS,
                disabled=disabled_cols,
                key="greg_editor",
                on_change=sync_edits_to_cloud,
                args=("Greg", "greg_editor", greg_df),
                use_container_width=True
            )

        st.metric(
            "Score",
            f"{greg_df['Total'].sum():g}",
            delta=f"Potential: {greg_df['Predicted'].sum():.1f}"
        )

    with col2:
        st.subheader("Brad's Marauders")

        st.dataframe(
            style_dataframe(brad_df),
            hide_index=True,
            column_order=roster_cols,
            use_container_width=True
        )

        with st.expander("✏️ Edit Scores", expanded=False):
            st.data_editor(
                brad_df,
                hide_index=True,
                column_order=['Player'] + ROUNDS,
                disabled=disabled_cols,
                key="brad_editor",
                on_change=sync_edits_to_cloud,
                args=("Brad", "brad_editor", brad_df),
                use_container_width=True
            )

        st.metric(
            "Score",
            f"{brad_df['Total'].sum():g}",
            delta=f"Potential: {brad_df['Predicted'].sum():.1f}"
        )

    st.divider()

    # ============================================================
    # THE COURT TRACKER
    # ============================================================
    img_base64 = get_base64_of_bin_file('Gemini_Generated_Image_ij5asoij5asoij5a.png')
    if img_base64:
        st.markdown(f"""
            <style>
            [data-testid="stVegaLiteChart"] {{
                background-image: url("data:image/png;base64,{img_base64}");
                background-size: cover; background-position: center;
                border-radius: 15px; padding: 25px;
            }}
            </style>
            """, unsafe_allow_html=True)

    greg_total = float(greg_df['Total'].sum())
    brad_total = float(brad_df['Total'].sum())
    chart_data = pd.DataFrame({
        "Owner": ["Greg", "Brad"],
        "Points": [greg_total, brad_total]
    })

    bars = alt.Chart(chart_data).mark_bar(cornerRadius=8, size=50).encode(
        x=alt.X('Points:Q', axis=None),
        y=alt.Y(
            'Owner:N', sort='-x',
            axis=alt.Axis(
                labelFontSize=22, labelFont='Luminari',
                labelFontWeight='bold', labelColor='white',
                domain=False, ticks=False
            )
        ),
        color=alt.condition(
            alt.datum.Owner == 'Brad',
            alt.value('#A6192E'),
            alt.value('#003366')
        )
    )

    text = alt.Chart(chart_data).mark_text(
        align='left', dx=15, fontSize=28, font='Luminari',
        fontWeight='bold', color='white'
    ).encode(
        x='Points:Q',
        y=alt.Y('Owner:N', sort='-x'),
        text=alt.Text('Points:Q', format='.0f')
    )

    chart = (bars + text).properties(
        title=alt.TitleParams(
            text="POINTS TRACKER", font='Luminari',
            fontSize=32, color='#2E7D32', dy=-20
        ),
        height=300, background='transparent'
    ).configure_axis(labelColor='white').configure_view(strokeWidth=0)

    st.altair_chart(chart, use_container_width=True)

    # --- Admin ---
    with st.expander("⚠️ Admin"):
        if st.button("🚨 Reset Database", type="secondary"):
            write_df_to_sheet(sheet, pd.DataFrame(columns=DB_COLUMNS))
            st.cache_data.clear()
            st.rerun()
