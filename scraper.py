cat << 'EOF' > /Users/Shared/ligand_workspace/ncaa_scraper/scraper.py
import gspread
import pandas as pd
import requests
import os
from datetime import datetime

BASE_DIR = "/Users/Shared/ligand_workspace/ncaa_scraper/"
JSON_KEY = os.path.join(BASE_DIR, "ncaa-draft-2026-490502-dccce68f1b28.json")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"

def run_heartbeat():
    try:
        gc = gspread.service_account(filename=JSON_KEY)
        sheet = gc.open_by_url(SHEET_URL).sheet1
        df = pd.DataFrame(sheet.get_all_records())
        stats_map = {}

        # Fetch D1 Games
        res = requests.get("https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?groups=50").json()
        
        for event in res.get('events', []):
            gid = event['id']
            summary = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={gid}").json()
            
            for team in summary.get('boxscore', {}).get('players', []):
                # Find the 'PTS' index dynamically for this game
                labels = team.get('statistics', [{}])[0].get('labels', [])
                if "PTS" not in labels: continue
                pts_idx = labels.index("PTS")
                
                for athlete in team.get('statistics', [{}])[0].get('athletes', []):
                    name = athlete.get('athlete', {}).get('displayName')
                    stats = athlete.get('stats', [])
                    if len(stats) > pts_idx:
                        stats_map[name] = int(stats[pts_idx]) if str(stats[pts_idx]).isdigit() else 0

        # Sync with Google Sheet Column 'Total'
        updates = False
        for i, row in df.iterrows():
            player = str(row['Player']).strip()
            if player in stats_map:
                new_pts = stats_map[player]
                # Handle empty cells or strings in 'Total'
                current_total = int(row['Total']) if str(row['Total']).isdigit() else 0
                if current_total != new_pts:
                    df.at[i, 'Total'] = new_pts
                    updates = True

        if updates:
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            print(f"[{datetime.now()}] Flow synchronized. Standings updated.")
        else:
            print(f"[{datetime.now()}] Heartbeat stable. No score changes.")

    except Exception as e:
        print(f"Brutal Fact - Sync Error: {e}")

if __name__ == "__main__":
    run_heartbeat()