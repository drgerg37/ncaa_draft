import gspread
import pandas as pd
import requests
import os
from datetime import datetime, date

BASE_DIR = "/Users/Shared/ligand_workspace/ncaa_scraper/"
JSON_KEY = os.path.join(BASE_DIR, "ncaa-draft-2026-490502-dccce68f1b28.json")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1IzvwmlYYt-exsXAMYZQXywGjRe3Cpi0swaR_OK5iZRc/edit#gid=0"

# 2026 NCAA Tournament date ranges -> sheet column mapping
ROUND_DATES = [
    (date(2026, 3, 19), date(2026, 3, 20), "Opening Round"),
    (date(2026, 3, 21), date(2026, 3, 22), "Round of 32"),
    (date(2026, 3, 26), date(2026, 3, 27), "Sweet 16"),
    (date(2026, 3, 28), date(2026, 3, 29), "Elite 8"),
    (date(2026, 4, 4),  date(2026, 4, 4),  "Final 4"),
    (date(2026, 4, 6),  date(2026, 4, 6),  "Final"),
]

ROUND_ORDER = ["Opening Round", "Round of 32", "Sweet 16", "Elite 8", "Final 4", "Final"]


def detect_round_by_date(event):
    """Determine tournament round from the game's start date."""
    try:
        start = event.get("date", "") or event.get("competitions", [{}])[0].get("date", "")
        if not start:
            return None
        game_date = datetime.fromisoformat(start.replace("Z", "+00:00")).date()
        for start_d, end_d, round_name in ROUND_DATES:
            if start_d <= game_date <= end_d:
                return round_name
    except (ValueError, IndexError):
        pass
    return None


def run_heartbeat():
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Waking up. Fetching ESPN tournament data...")

        gc = gspread.service_account(filename=JSON_KEY)
        sheet = gc.open_by_url(SHEET_URL).sheet1
        df = pd.DataFrame(sheet.get_all_records())

        if df.empty:
            print(f"[{ts}] Sheet is empty. Nothing to update.")
            return

        # Ensure round columns exist
        for r in ROUND_ORDER:
            if r not in df.columns:
                df[r] = ""

        # Build player->team lookup from sheet
        player_teams = {}
        for _, row in df.iterrows():
            player = str(row.get("Player", "")).strip()
            team = str(row.get("Team", "")).strip()
            if player and team:
                player_teams[player] = team

        # Track which teams lost
        losing_teams = set()

        # Fetch tournament scoreboard
        scoreboard = requests.get(
            "https://site.api.espn.com/apis/site/v2/sports/basketball/"
            "mens-college-basketball/scoreboard?groups=50&limit=200"
        ).json()

        # {round_col: {player_name: points}}
        round_scores = {}
        games_processed = 0

        for event in scoreboard.get("events", []):
            game_status = event.get("status", {}).get("type", {}).get("name", "")

            # Only process completed games
            if game_status != "STATUS_FINAL":
                continue

            round_col = detect_round_by_date(event)
            if not round_col:
                continue

            if round_col not in round_scores:
                round_scores[round_col] = {}

            game_id = event["id"]
            game_name = event.get("name", "Unknown")
            games_processed += 1

            # Determine losing team
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            for comp in competitors:
                if comp.get("winner") is False:
                    loser_name = comp.get("team", {}).get("displayName", "")
                    if loser_name:
                        losing_teams.add(loser_name)

            # Fetch box score for player stats
            try:
                summary = requests.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/basketball/"
                    f"mens-college-basketball/summary?event={game_id}"
                ).json()
            except Exception as e:
                print(f"  Warning: Could not fetch summary for {game_name}: {e}")
                continue

            for team_data in summary.get("boxscore", {}).get("players", []):
                stats_groups = team_data.get("statistics", [])
                if not stats_groups:
                    continue

                labels = stats_groups[0].get("labels", [])
                if "PTS" not in labels:
                    continue
                pts_idx = labels.index("PTS")

                for athlete in stats_groups[0].get("athletes", []):
                    name = athlete.get("athlete", {}).get("displayName", "")
                    stats = athlete.get("stats", [])
                    if name and len(stats) > pts_idx:
                        try:
                            pts = int(stats[pts_idx]) if str(stats[pts_idx]).isdigit() else 0
                        except (ValueError, IndexError):
                            pts = 0
                        round_scores[round_col][name] = pts

        print(f"  Processed {games_processed} final games. Losing teams: {losing_teams or 'none yet'}")
        for rc, players in round_scores.items():
            drafted_matches = [p for p in players if p in player_teams]
            print(f"  {rc}: {len(players)} players found, {len(drafted_matches)} match draft sheet")

        # Apply scores to the sheet dataframe
        updates = False

        for i, row in df.iterrows():
            player = str(row["Player"]).strip()
            team = str(row.get("Team", "")).strip()

            for round_col, player_pts in round_scores.items():
                if player in player_pts:
                    new_val = str(player_pts[player])
                    current_val = str(row.get(round_col, "")).strip()

                    if current_val.upper() == "X":
                        continue  # Don't overwrite manual eliminations

                    if current_val != new_val:
                        df.at[i, round_col] = new_val
                        updates = True
                        print(f"  >> {player}: {round_col} = {new_val}")

            # Mark eliminated: if team lost, mark X in all rounds after the one with a score
            if team in losing_teams:
                hit_loss = False
                for r in ROUND_ORDER:
                    val = str(df.at[i, r]).strip()
                    if hit_loss and val.upper() != "X":
                        df.at[i, r] = "X"
                        updates = True
                    elif val and val.upper() != "X" and val != "":
                        # This round has a score — next rounds should be X
                        r_idx = ROUND_ORDER.index(r)
                        if r_idx < len(ROUND_ORDER) - 1:
                            hit_loss = True

        if updates:
            sheet.update([df.columns.values.tolist()] + df.values.tolist())
            timestamp = f"Last Sync: {datetime.now().strftime('%m/%d %H:%M')}"
            sheet.update_acell("N1", timestamp)
            print(f"[{ts}] Flow synchronized. Standings updated.")
        else:
            print(f"[{ts}] Heartbeat stable. No score changes.")

    except Exception as e:
        print(f"CRITICAL ERROR - Sync Failed: {e}")


if __name__ == "__main__":
    run_heartbeat()
