#!/usr/bin/env python3
"""
EdgeIntel Daily Pick Card Generator
Produces:
  - Twitter card:    1200 x 675 px  → cards/twitter_YYYY-MM-DD.png
  - Instagram card:  1080 x 1080 px → cards/instagram_YYYY-MM-DD.png
  - Story card:       1080 x 1920 px → cards/story_YYYY-MM-DD.png

Requires: pip install pillow
Run after daily_pipeline.py writes slate.json
"""

import json
import os
import datetime
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Pillow not installed — run: pip install pillow")

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "public" / "data"
CARDS_DIR = ROOT / "marketing" / "cards"
CARDS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Brand Colors ──────────────────────────────────────────────────────────────
BG_DARK     = (8, 10, 15)       # #080A0F
BG_CARD     = (15, 18, 26)      # #0F121A
BG_CARD2    = (20, 24, 35)      # #141823
GOLD        = (255, 215, 0)     # #FFD700
GOLD_DIM    = (180, 150, 0)
BLUE        = (0, 122, 255)     # #007AFF
GREEN       = (52, 199, 89)     # #34C759
RED         = (255, 59, 48)     # #FF3B30
WHITE       = (255, 255, 255)
WHITE_DIM   = (160, 170, 185)
PURPLE      = (138, 43, 226)

SPORT_COLORS = {
    "NBA":   BLUE,
    "NHL":   (0, 200, 200),    # teal
    "NCAAB": (255, 100, 0),   # orange
}


def load_fonts(base_size: int = 40) -> dict:
    """Try to load system fonts, fall back to default."""
    fonts = {}
    # Try common Linux font paths
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_path = None
    reg_path = None
    for p in candidates:
        if os.path.exists(p) and "Bold" in p and not bold_path:
            bold_path = p
        if os.path.exists(p) and "Bold" not in p and not reg_path:
            reg_path = p

    def make_font(path, size):
        try:
            if path:
                return ImageFont.truetype(path, size)
        except Exception:
            pass
        return ImageFont.load_default()

    fonts["hero"]    = make_font(bold_path, base_size * 2)
    fonts["title"]   = make_font(bold_path, int(base_size * 1.3))
    fonts["body"]    = make_font(reg_path or bold_path, base_size)
    fonts["small"]   = make_font(reg_path or bold_path, int(base_size * 0.7))
    fonts["tiny"]    = make_font(reg_path or bold_path, int(base_size * 0.55))
    fonts["sport"]   = make_font(bold_path, int(base_size * 0.75))
    return fonts


def draw_rounded_rect(draw: ImageDraw, xy: tuple, radius: int, fill, outline=None, outline_width=2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill,
                            outline=outline, width=outline_width)


def confidence_bar(draw: ImageDraw, x: int, y: int, width: int, height: int,
                   confidence: float, fonts: dict):
    """Draw a horizontal confidence bar."""
    # Background track
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, fill=(40, 45, 60))
    # Fill
    fill_w = int(width * confidence / 100)
    color = GREEN if confidence >= 80 else GOLD if confidence >= 65 else RED
    if fill_w > height:
        draw.rounded_rectangle([x, y, x + fill_w, y + height], radius=height // 2, fill=color)
    # Label
    draw.text((x + width + 8, y - 2), f"{confidence:.0f}%", fill=WHITE_DIM, font=fonts["small"])


def draw_pick_block(draw: ImageDraw, pick: dict, x: int, y: int,
                    width: int, fonts: dict, is_edge: bool = True) -> int:
    """
    Draw a single pick card block. Returns bottom y position.
    """
    padding = 24
    line_h = fonts["body"].size + 10 if hasattr(fonts["body"], "size") else 50

    # Card background
    card_h = 220
    border_color = GOLD if is_edge else (40, 50, 70)
    draw_rounded_rect(draw, (x, y, x + width, y + card_h), 16,
                      fill=BG_CARD2, outline=border_color, outline_width=3 if is_edge else 1)

    # Sport pill
    sport = pick.get("sport", "NBA")
    sport_color = SPORT_COLORS.get(sport, BLUE)
    pill_w = 80
    pill_h = 28
    draw_rounded_rect(draw, (x + padding, y + padding, x + padding + pill_w, y + padding + pill_h),
                      14, fill=sport_color)
    draw.text((x + padding + 12, y + padding + 4), sport, fill=WHITE, font=fonts["tiny"])

    # Edge badge
    if is_edge:
        badge_text = "⭐ EDGE PICK"
        draw.text((x + padding + pill_w + 12, y + padding + 4),
                  badge_text, fill=GOLD, font=fonts["tiny"])

    # Game
    game = pick.get("game", "")
    draw.text((x + padding, y + padding + pill_h + 10), game,
              fill=WHITE, font=fonts["sport"])

    # Time
    time_str = pick.get("time", "")
    draw.text((x + padding, y + padding + pill_h + 10 + 36), time_str,
              fill=WHITE_DIM, font=fonts["tiny"])

    # Best bet
    best = pick.get("best_bet", {})
    bet_text = f"{best.get('pick', '')}  {best.get('odds', '')}"
    draw.text((x + padding, y + padding + pill_h + 60), bet_text,
              fill=GOLD, font=fonts["title"])

    # Confidence bar
    conf = pick.get("confidence", 75)
    bar_y = y + card_h - 50
    confidence_bar(draw, x + padding, bar_y, width - padding * 2 - 60, 12, conf, fonts)

    return y + card_h + 20


# ═══════════════════════════════════════════════════════════════════════════════
# TWITTER CARD — 1200 x 675
# ═══════════════════════════════════════════════════════════════════════════════
def make_twitter_card(games: list[dict], results: dict, date_str: str) -> Path:
    W, H = 1200, 675
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(base_size=28)

    edge_picks = [g for g in games if g.get("isEdgePick")]

    # ── Background gradient strips ──
    for i in range(H):
        alpha = int(15 * (1 - i / H))
        draw.line([(0, i), (W, i)], fill=(0, 30, 60))

    # ── Header bar ──
    draw.rectangle([(0, 0), (W, 80)], fill=(12, 15, 22))
    draw.text((30, 20), "EDGEINTEL", fill=GOLD, font=fonts["hero"])
    # Season record on right
    at = results.get("allTime", {})
    record = f"{at.get('wins', 0)}-{at.get('losses', 0)}  {at.get('winPct', 0)}%  ROI:{at.get('roi', 0)}%"
    draw.text((W - 420, 28), record, fill=WHITE_DIM, font=fonts["body"])

    # ── Date + subtitle ──
    today_label = datetime.date.today().strftime("%A, %B %-d")
    draw.text((30, 95), f"Today's Edge Picks — {today_label}", fill=WHITE, font=fonts["title"])
    draw.text((30, 135), f"{len(edge_picks)} high-confidence picks flagged by the model",
              fill=WHITE_DIM, font=fonts["small"])

    # ── Pick blocks ──
    col_w = (W - 80) // max(len(edge_picks), 1) - 20
    x = 30
    y_start = 175

    for pick in edge_picks[:3]:
        draw_pick_block(draw, pick, x, y_start, col_w, fonts, is_edge=True)
        x += col_w + 20

    # ── Footer ──
    footer_y = H - 50
    draw.rectangle([(0, footer_y - 10), (W, H)], fill=(12, 15, 22))
    draw.text((30, footer_y), "edgeintel.app  |  Full board + Scotty AI inside",
              fill=WHITE_DIM, font=fonts["small"])
    daily_code = f"EDGE{datetime.date.today().strftime('%m%d')}"
    draw.text((W - 250, footer_y), f"Code: {daily_code}", fill=GOLD, font=fonts["small"])

    out_path = CARDS_DIR / f"twitter_{date_str}.png"
    img.save(out_path, "PNG", optimize=True)
    print(f"Twitter card → {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# INSTAGRAM CARD — 1080 x 1080
# ═══════════════════════════════════════════════════════════════════════════════
def make_instagram_card(games: list[dict], results: dict, date_str: str) -> Path:
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(base_size=32)

    edge_picks = [g for g in games if g.get("isEdgePick")]

    # ── Gold accent bar at top ──
    draw.rectangle([(0, 0), (W, 8)], fill=GOLD)

    # ── Logo + date ──
    draw.text((50, 40), "EDGEINTEL", fill=GOLD, font=fonts["hero"])
    draw.text((50, 120), datetime.date.today().strftime("%A • %B %-d, %Y"),
              fill=WHITE_DIM, font=fonts["body"])

    # ── Record strip ──
    at = results.get("allTime", {})
    strip_y = 175
    draw.rounded_rectangle([(50, strip_y), (W - 50, strip_y + 60)], radius=12,
                            fill=(20, 25, 40), outline=GOLD, width=1)
    record_text = (f"Season:  {at.get('wins', 0)}-{at.get('losses', 0)}  ({at.get('winPct', 0)}%)   "
                   f"ROI: {at.get('roi', 0)}%   Units: {at.get('units', '+0')}   "
                   f"Streak: {at.get('streak', 'N/A')}")
    draw.text((70, strip_y + 16), record_text, fill=WHITE, font=fonts["small"])

    # ── Headline ──
    headline_y = strip_y + 80
    draw.text((50, headline_y), f"Today's {len(edge_picks)} Edge Pick{'s' if len(edge_picks) != 1 else ''}",
              fill=WHITE, font=fonts["title"])

    # ── Pick blocks ──
    pick_y = headline_y + 60
    card_w = W - 100
    for pick in edge_picks[:3]:
        pick_y = draw_pick_block(draw, pick, 50, pick_y, card_w, fonts, is_edge=True)

    # ── "Remaining board locked" teaser ──
    locked_count = len([g for g in games if not g.get("isEdgePick")])
    if locked_count > 0:
        lock_y = pick_y + 10
        draw.rounded_rectangle([(50, lock_y), (W - 50, lock_y + 70)], radius=12,
                                fill=(25, 30, 45), outline=(50, 60, 90), width=1)
        draw.text((80, lock_y + 20),
                  f"🔒  +{locked_count} more picks available — $29/mo at edgeintel.app",
                  fill=WHITE_DIM, font=fonts["body"])

    # ── CTA footer ──
    footer_y = H - 80
    draw.rectangle([(0, footer_y - 10), (W, H)], fill=(12, 15, 22))
    draw.text((50, footer_y), "edgeintel.app",
              fill=GOLD, font=fonts["title"])
    draw.text((50, footer_y + 40),
              "AI-powered sports analytics • Full slate • Scotty AI",
              fill=WHITE_DIM, font=fonts["small"])

    # Gold bottom bar
    draw.rectangle([(0, H - 8), (W, H)], fill=GOLD)

    out_path = CARDS_DIR / f"instagram_{date_str}.png"
    img.save(out_path, "PNG", optimize=True)
    print(f"Instagram card → {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# RESULTS CARD — 1080 x 675 (yesterday's results flex)
# ═══════════════════════════════════════════════════════════════════════════════
def make_results_card(results: dict, date_str: str) -> Path:
    W, H = 1080, 675
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    fonts = load_fonts(base_size=30)

    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    yesterday_picks = [h for h in results.get("history", []) if h.get("date") == yesterday]

    # ── Header ──
    draw.rectangle([(0, 0), (W, 70)], fill=(12, 15, 22))
    draw.text((30, 15), "EDGEINTEL", fill=GOLD, font=fonts["title"])
    draw.text((30, 50), f"Results — {datetime.date.fromisoformat(yesterday).strftime('%B %-d')}",
              fill=WHITE_DIM, font=fonts["small"])

    # ── Season stats row ──
    at = results.get("allTime", {})
    stats = [
        (str(at.get("wins", 0)), "WINS"),
        (str(at.get("losses", 0)), "LOSSES"),
        (f"{at.get('winPct', 0)}%", "WIN RATE"),
        (f"{at.get('roi', 0)}%", "ROI"),
        (str(at.get("units", "+0")), "UNITS"),
        (str(at.get("streak", "N/A")), "STREAK"),
    ]
    stat_w = W // len(stats)
    stat_y = 90
    for i, (val, label) in enumerate(stats):
        sx = i * stat_w + stat_w // 2
        val_color = GREEN if "+" in str(val) or (val.replace(".", "").replace("-", "").isdigit() and float(val.replace("%", "")) > 0) else WHITE
        draw.text((sx - 30, stat_y), val, fill=GOLD if label in ("WIN RATE", "ROI") else WHITE, font=fonts["title"])
        draw.text((sx - 30, stat_y + 45), label, fill=WHITE_DIM, font=fonts["tiny"])

    # ── Yesterday's picks ──
    draw.text((30, 185), "Yesterday's Edge Picks:", fill=WHITE, font=fonts["body"])
    pick_y = 220
    for pick in yesterday_picks[:5]:
        result = pick.get("result", "?")
        color = GREEN if result == "W" else RED if result == "L" else WHITE_DIM
        result_icon = "✓" if result == "W" else "✗" if result == "L" else "~"
        line = f"{result_icon}  {pick.get('sport', '')} | {pick.get('game', '')} | {pick.get('pick', '')} | {pick.get('units', '')}"
        draw.rounded_rectangle([(30, pick_y), (W - 30, pick_y + 50)], radius=8,
                                fill=(20, 25, 40), outline=color, width=2)
        draw.text((50, pick_y + 12), line, fill=color, font=fonts["small"])
        pick_y += 60

    if not yesterday_picks:
        draw.text((30, 220), "No picks graded yet — check back after games complete",
                  fill=WHITE_DIM, font=fonts["body"])

    # ── Footer ──
    footer_y = H - 50
    draw.rectangle([(0, footer_y - 10), (W, H)], fill=(12, 15, 22))
    draw.text((30, footer_y), "edgeintel.app  |  Full slate + Scotty AI",
              fill=WHITE_DIM, font=fonts["small"])

    out_path = CARDS_DIR / f"results_{date_str}.png"
    img.save(out_path, "PNG", optimize=True)
    print(f"Results card → {out_path}")
    return out_path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    if not PIL_AVAILABLE:
        print("Install Pillow: pip install pillow")
        return

    date_str = datetime.date.today().isoformat()
    slate_path = DATA_DIR / "slate.json"
    results_path = DATA_DIR / "results.json"

    if not slate_path.exists():
        print(f"No slate.json at {slate_path}")
        return
    if not results_path.exists():
        print(f"No results.json at {results_path}")
        return

    with open(slate_path) as f:
        slate = json.load(f)
    with open(results_path) as f:
        results = json.load(f)

    games = slate.get("games", [])
    print(f"Generating cards for {date_str} — {len(games)} games, "
          f"{sum(1 for g in games if g.get('isEdgePick'))} edge picks")

    make_twitter_card(games, results, date_str)
    make_instagram_card(games, results, date_str)
    make_results_card(results, date_str)

    print(f"\nAll cards saved → {CARDS_DIR}")


if __name__ == "__main__":
    main()
