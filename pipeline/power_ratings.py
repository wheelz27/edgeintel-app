#!/usr/bin/env python3
"""
EdgeIntel Power Ratings Builder
Pulls ESPN game logs and builds/updates power_ratings.json
Run this once to bootstrap, then daily pipeline keeps it updated.
"""

import json
import requests
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "public" / "data"
RATINGS_PATH = Path(__file__).parent / "power_ratings.json"

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_SPORTS = {
    "NBA":   f"{ESPN_BASE}/basketball/nba",
    "NHL":   f"{ESPN_BASE}/hockey/nhl",
    "NCAAB": f"{ESPN_BASE}/basketball/mens-college-basketball",
}

ET = ZoneInfo("America/New_York")

# ─── NBA Team abbreviations → full names ──────────────────────────────────────
NBA_TEAMS = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

NHL_TEAMS = {
    "ANA": "Anaheim Ducks", "ARI": "Arizona Coyotes", "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres", "CGY": "Calgary Flames", "CAR": "Carolina Hurricanes",
    "CHI": "Chicago Blackhawks", "COL": "Colorado Avalanche", "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars", "DET": "Detroit Red Wings", "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers", "LAK": "Los Angeles Kings", "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens", "NSH": "Nashville Predators", "NJD": "New Jersey Devils",
    "NYI": "New York Islanders", "NYR": "New York Rangers", "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers", "PIT": "Pittsburgh Penguins", "STL": "St. Louis Blues",
    "SJS": "San Jose Sharks", "SEA": "Seattle Kraken", "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs", "VAN": "Vancouver Canucks", "VGK": "Vegas Golden Knights",
    "WSH": "Washington Capitals", "WPG": "Winnipeg Jets",
}


def fetch_team_game_log(sport: str, team_id: str, limit: int = 15) -> list[dict]:
    """Pull last N games for a team from ESPN."""
    url = f"{ESPN_SPORTS[sport]}/teams/{team_id}/schedule"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        events = data.get("events", [])
        completed = [e for e in events
                     if e.get("competitions", [{}])[0].get("status", {})
                        .get("type", {}).get("name") in ("STATUS_FINAL", "STATUS_FULL_TIME")]
        return completed[-limit:]
    except Exception as e:
        return []


def extract_game_score(event: dict, team_id: str) -> tuple[int, int]:
    """Returns (team_score, opponent_score) from ESPN event."""
    comp = event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    team_comp = next((c for c in competitors if str(c.get("id")) == str(team_id)), None)
    opp_comp = next((c for c in competitors if str(c.get("id")) != str(team_id)), None)
    if not team_comp or not opp_comp:
        return 0, 0
    return int(team_comp.get("score", 0)), int(opp_comp.get("score", 0))


def build_ratings_for_sport(sport: str) -> dict:
    """Build power ratings for all teams in a sport."""
    print(f"Building {sport} power ratings...")
    teams_url = f"{ESPN_SPORTS[sport]}/teams?limit=50"
    try:
        r = requests.get(teams_url, timeout=10)
        r.raise_for_status()
        teams = r.json().get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
    except Exception as e:
        print(f"  Failed to fetch teams: {e}")
        return {}

    ratings = {}
    for team_entry in teams:
        team = team_entry.get("team", {})
        team_id = team.get("id")
        team_name = team.get("displayName", "")
        if not team_name:
            continue

        games = fetch_team_game_log(sport, team_id, limit=15)
        if not games:
            continue

        scores_for  = []
        scores_against = []
        for ev in games:
            ts, os_ = extract_game_score(ev, team_id)
            if ts > 0 or os_ > 0:
                scores_for.append(ts)
                scores_against.append(os_)

        if not scores_for:
            continue

        def avg(lst): return sum(lst) / len(lst) if lst else 0

        # Season average (all games we have)
        season_off = avg(scores_for)
        season_def = avg(scores_against)

        # L15 = last 15 (all we pulled)
        l15_off = avg(scores_for)
        l15_def = avg(scores_against)

        # L5 = last 5
        l5_off = avg(scores_for[-5:])
        l5_def = avg(scores_against[-5:])

        # L1 = last game
        l1_off = scores_for[-1] if scores_for else season_off
        l1_def = scores_against[-1] if scores_against else season_def

        ratings[team_name] = {
            "team_id": team_id,
            "sport": sport,
            "season_off": round(season_off, 1),
            "season_def": round(season_def, 1),
            "l15_off": round(l15_off, 1),
            "l15_def": round(l15_def, 1),
            "l5_off": round(l5_off, 1),
            "l5_def": round(l5_def, 1),
            "l1_off": round(l1_off, 1),
            "l1_def": round(l1_def, 1),
            "games": len(scores_for),
            "updated": datetime.date.today().isoformat(),
        }
        print(f"  {team_name}: Off={round(season_off,1)} Def={round(season_def,1)} ({len(scores_for)}g)")

    return ratings


def main():
    all_ratings = {}
    if RATINGS_PATH.exists():
        with open(RATINGS_PATH) as f:
            all_ratings = json.load(f)

    sports = ["NBA", "NHL"]
    today = datetime.date.today()
    if today.month in [11, 12, 1, 2, 3]:
        sports.append("NCAAB")

    for sport in sports:
        sport_ratings = build_ratings_for_sport(sport)
        all_ratings.update(sport_ratings)

    with open(RATINGS_PATH, "w") as f:
        json.dump(all_ratings, f, indent=2)
    print(f"\nSaved {len(all_ratings)} team ratings → {RATINGS_PATH}")


if __name__ == "__main__":
    main()
