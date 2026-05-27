#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
calendar_weekly_art.py
──────────────────────
Artistic weekly calendar for the Waveshare 13.3" Spectra 6 e-Paper display.
Resolution : 1600 × 1200 px
Colours    : BLACK · WHITE · RED · GREEN · BLUE · YELLOW (6 safe driver colours)

Google Calendar + Tasks sync via OAuth2 (token stored in TOKEN_PATH).
Run gcal_setup.py once to authorise; after that this script fetches live data.

Usage:
  python calendar_weekly_art.py                        # fetch GCal + render
  python calendar_weekly_art.py --no-gcal              # offline / fallback data
  python calendar_weekly_art.py --photo /path/img.jpg  # explicit photo
  python calendar_weekly_art.py --save preview.png --preview-only
  python calendar_weekly_art.py --week-offset 1        # next week
"""

import sys, os, argparse, datetime, json, pickle

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import epd13in3E
from PIL import Image, ImageDraw, ImageFont

# ════════════════════════════════════════════════════════════════════════════════
#  ★  USER CONFIGURATION  — edit this section
# ════════════════════════════════════════════════════════════════════════════════

TODAY       = datetime.date.today()
WEEK_OFFSET = 0   # 0 = this week, 1 = next, -1 = last

# ── Google API credentials paths ─────────────────────────────────────────────
# credentials.json  → downloaded from Google Cloud Console (OAuth2 client)
# token.pickle      → auto-created after first authorisation run
CREDENTIALS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "credentials.json")
TOKEN_PATH       = os.path.join(os.path.dirname(os.path.realpath(__file__)), "token.pickle")

# ── Which Google Calendars to show ───────────────────────────────────────────
# "primary" = your main calendar.  Add more IDs from Google Calendar settings.
CALENDAR_IDS = ["primary"]

# ── Which Google Task Lists to show ──────────────────────────────────────────
# "@default" = your default task list.  Set to [] to disable tasks.
TASK_LIST_IDS = ["@default"]

# Max tasks to show (the panel has limited space)
MAX_TASKS = 8

# ── Fallback data (used when --no-gcal or network fails) ─────────────────────
FALLBACK_SCHEDULE = {
    "Mon": ["9 AM  Standup"],
    "Tue": ["10 AM  Meeting"],
    "Wed": [],
    "Thu": [],
    "Fri": [],
    "Sat": [],
    "Sun": [],
}
FALLBACK_TASKS = [
    "No tasks loaded",
    "Run gcal_setup.py to authorise",
]

# ── Daily quote (auto-rotates by day-of-year) ────────────────────────────────
QUOTES = [
    ("The secret of getting ahead is getting started.",    "Mark Twain"),
    ("It always seems impossible until it's done.",        "Nelson Mandela"),
    ("In every difficulty lies opportunity.",              "Albert Einstein"),
    ("Simplicity is the ultimate sophistication.",         "Leonardo da Vinci"),
    ("What you do today can improve all your tomorrows.",  "Ralph Marston"),
    ("Believe you can and you're halfway there.",          "Theodore Roosevelt"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Start where you are. Use what you have. Do what you can.", "Arthur Ashe"),
    ("Keep your face always toward the sunshine.",         "Walt Whitman"),
    ("Act as if what you do makes a difference. It does.", "William James"),
    ("Success is not final. Failure is not fatal.",        "Winston Churchill"),
    ("You are never too old to set another goal.",         "C. S. Lewis"),
    ("It does not matter how slowly you go — only that you do not stop.", "Confucius"),
    ("The present moment always will have been.",          "Epictetus"),
    ("Create the things you wish existed.",                "Unknown"),
]
_qi = TODAY.timetuple().tm_yday % len(QUOTES)
QUOTE_TEXT, QUOTE_AUTHOR = QUOTES[_qi]

# ── Accent colour per weekday ─────────────────────────────────────────────────
DAY_ACCENT_KEYS = {
    0: "BLUE",
    1: "GREEN",
    2: "RED",
    3: "YELLOW",
    4: "RED",
    5: "BLUE",
    6: "GREEN",
}

# ── Photo folder config ──────────────────────────────────────────────────────
# Run the script once manually — a GUI folder picker opens, you choose a folder,
# and the path is saved to photo_folder.txt.  Every cron refresh picks the next
# photo from that folder in sequence (like a slideshow).
# To change the folder: run manually once → new folder picker opens → saved.
PHOTO_CONFIG_PATH  = os.path.join(os.path.dirname(os.path.realpath(__file__)), "photo_folder.txt")
PHOTO_INDEX_PATH   = os.path.join(os.path.dirname(os.path.realpath(__file__)), "photo_index.txt")
IMAGE_EXTENSIONS   = {".jpg", ".jpeg", ".png", ".bmp"}
PHOTO_ROTATION     = "random"   # "random" or "sequential"

# ── Display hold time (seconds before EPD sleeps; 0 = instant) ───────────────
DISPLAY_HOLD = 0

# ════════════════════════════════════════════════════════════════════════════════
#  LAYOUT CONSTANTS
# ════════════════════════════════════════════════════════════════════════════════

W, H      = 1600, 1200
MAST_H    = 60
QUOTE_H   = 190
BODY_Y    = MAST_H
BODY_H    = H - MAST_H - QUOTE_H
BODY_BTM  = BODY_Y + BODY_H
PHOTO_W   = 660
RIGHT_X   = PHOTO_W + 1
RIGHT_W   = W - RIGHT_X
WEEK_H    = 680
TASK_Y    = BODY_Y + WEEK_H
TASK_H    = BODY_H - WEEK_H
COL_W     = RIGHT_W // 7

FS = dict(
    mast    = 38,
    date_lg = 24,
    day_lbl = 20,
    event   = 17,
    task    = 20,
    quote   = 26,
    attr    = 20,
    micro   = 16,
)

PALETTE_KEYS = ["BLACK", "WHITE", "RED", "GREEN", "BLUE", "YELLOW"]

# ════════════════════════════════════════════════════════════════════════════════
#  GOOGLE CALENDAR + TASKS FETCH
# ════════════════════════════════════════════════════════════════════════════════

GCAL_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]


def _get_credentials():
    """Load stored OAuth2 token, refreshing if expired."""
    from google.auth.transport.requests import Request
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return creds


def fetch_gcal_events(week_days):
    """
    Fetch events from Google Calendar for the given week.
    Returns dict: { "Mon": ["HH:MM Title", ...], "Tue": [...], ... }
    """
    try:
        from googleapiclient.discovery import build
        creds = _get_credentials()
        if not creds or not creds.valid:
            print("   [gcal] No valid credentials — use gcal_setup.py to authorise.")
            return None

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Time window: Monday 00:00 → Sunday 23:59 (UTC)
        tz_offset = datetime.timezone(datetime.timedelta(hours=0))
        t_min = datetime.datetime.combine(week_days[0],  datetime.time.min).isoformat() + "Z"
        t_max = datetime.datetime.combine(week_days[-1], datetime.time.max).isoformat() + "Z"

        schedule = {d.strftime("%a"): [] for d in week_days}

        for cal_id in CALENDAR_IDS:
            try:
                result = service.events().list(
                    calendarId=cal_id,
                    timeMin=t_min,
                    timeMax=t_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                ).execute()
            except Exception as e:
                print(f"   [gcal] Calendar '{cal_id}' error: {e}")
                continue

            for event in result.get("items", []):
                start = event.get("start", {})
                summary = event.get("summary", "Untitled")[:28]

                # All-day events have a "date" key; timed events have "dateTime"
                if "dateTime" in start:
                    dt = datetime.datetime.fromisoformat(
                        start["dateTime"].replace("Z", "+00:00"))
                    local_dt = dt.astimezone()
                    abbr = local_dt.strftime("%a")
                    label = f"{local_dt.strftime('%I:%M %p').lstrip('0')}  {summary}"
                elif "date" in start:
                    d = datetime.date.fromisoformat(start["date"])
                    abbr = d.strftime("%a")
                    label = f"All day  {summary}"
                else:
                    continue

                if abbr in schedule:
                    schedule[abbr].append(label)

        print(f"   [gcal] Fetched events for {len(week_days)} days.")
        return schedule

    except ImportError:
        print("   [gcal] google-api-python-client not installed.")
        return None
    except Exception as e:
        print(f"   [gcal] Unexpected error: {e}")
        return None


def fetch_gcal_tasks():
    """
    Fetch incomplete tasks from Google Tasks.
    Returns list of strings, e.g. ["☐ Buy milk", "☐ Review PR"]
    """
    try:
        from googleapiclient.discovery import build
        creds = _get_credentials()
        if not creds or not creds.valid:
            return None

        service = build("tasks", "v1", credentials=creds, cache_discovery=False)
        tasks = []

        for list_id in TASK_LIST_IDS:
            try:
                result = service.tasks().list(
                    tasklist=list_id,
                    showCompleted=False,
                    showHidden=False,
                    maxResults=MAX_TASKS,
                ).execute()
            except Exception as e:
                print(f"   [tasks] List '{list_id}' error: {e}")
                continue

            for item in result.get("items", []):
                if item.get("status") == "completed":
                    continue
                title = item.get("title", "").strip()
                if title:
                    tasks.append(f"\u2610 {title}")  # ☐ checkbox

        print(f"   [tasks] Fetched {len(tasks)} task(s).")
        return tasks if tasks else None

    except ImportError:
        print("   [tasks] google-api-python-client not installed.")
        return None
    except Exception as e:
        print(f"   [tasks] Unexpected error: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════════
#  DRAWING UTILITIES
# ════════════════════════════════════════════════════════════════════════════════

def get_week_days(today, offset=0):
    monday = today - datetime.timedelta(days=today.weekday()) \
             + datetime.timedelta(weeks=offset)
    return [monday + datetime.timedelta(days=i) for i in range(7)]


def load_fonts(picdir, sizes):
    fp = os.path.join(picdir, "Font.ttc")
    return {k: ImageFont.truetype(fp, v) for k, v in sizes.items()}


def browse_folder_qt(start_dir):
    """
    Open a GUI folder picker so the user selects a photos folder.
    Falls back to a terminal prompt if no display is available.
    """
    # ── Attempt Qt GUI folder picker ─────────────────────────────────────────
    try:
        from PyQt5.QtWidgets import QApplication, QFileDialog
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError("No display environment variable set")
        app = QApplication.instance() or QApplication(sys.argv)
        folder = QFileDialog.getExistingDirectory(
            parent=None,
            caption="Select folder containing your photos",
            directory=start_dir if os.path.isdir(start_dir) else os.path.expanduser("~"),
            options=QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            return folder
        print("   [photo] No folder selected.")
        return None
    except Exception as e:
        print(f"   [photo] GUI picker unavailable ({e})")

    # ── Terminal fallback ─────────────────────────────────────────────────────
    print()
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │  Enter the full path to your photos folder          │")
    print("  │  Example: /home/robotpi/Pictures                    │")
    print("  │  Leave blank to use the geometric placeholder.      │")
    print("  └─────────────────────────────────────────────────────┘")
    try:
        raw = input("  Folder path: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("   [photo] Non-interactive session — skipping prompt.")
        return None
    if not raw:
        return None
    if os.path.isdir(raw):
        return raw
    print(f"   [photo] Folder not found: {raw}")
    return None


def list_images(folder):
    """Return sorted list of image file paths in folder."""
    files = sorted([
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])
    return files


def load_saved_folder():
    """Return the saved photos folder path, or None if not set / missing."""
    if os.path.exists(PHOTO_CONFIG_PATH):
        folder = open(PHOTO_CONFIG_PATH).read().strip()
        if folder and os.path.isdir(folder):
            return folder
        print(f"   [photo] Saved folder not found: {folder}")
    return None


def save_folder_path(folder):
    """Save chosen folder; reset index to 0."""
    with open(PHOTO_CONFIG_PATH, 'w') as f:
        f.write(folder)
    with open(PHOTO_INDEX_PATH, 'w') as f:
        f.write("0")
    images = list_images(folder)
    print(f"   [photo] Folder saved: {folder}  ({len(images)} images found)")


def next_photo(folder):
    """
    Return the next image from the folder.
    Mode is controlled by PHOTO_ROTATION:
      "sequential" — cycles through files alphabetically, remembers position
      "random"     — picks a different random image each time
    """
    import random as _random
    images = list_images(folder)
    if not images:
        print(f"   [photo] No images found in {folder}")
        return None

    if PHOTO_ROTATION == "random":
        # Pick randomly, but avoid repeating the last image if possible
        last_index = 0
        if os.path.exists(PHOTO_INDEX_PATH):
            try:
                last_index = int(open(PHOTO_INDEX_PATH).read().strip())
            except ValueError:
                last_index = 0
        candidates = [i for i in range(len(images)) if i != last_index]
        index = _random.choice(candidates if candidates else list(range(len(images))))
    else:
        # Sequential — read saved index
        index = 0
        if os.path.exists(PHOTO_INDEX_PATH):
            try:
                index = int(open(PHOTO_INDEX_PATH).read().strip())
            except ValueError:
                index = 0
        index = index % len(images)

    chosen = images[index]

    # Save index for next run
    with open(PHOTO_INDEX_PATH, 'w') as f:
        f.write(str((index + 1) % len(images)))

    mode_label = "random" if PHOTO_ROTATION == "random" else f"{index + 1}/{len(images)}"
    print(f"   [photo] [{mode_label}] {os.path.basename(chosen)}")
    return chosen


def fit_cover(path, w, h):
    img   = Image.open(path).convert("RGB")
    ratio = max(w / img.width, h / img.height)
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    img   = img.resize((nw, nh), Image.LANCZOS)
    left  = (nw - w) // 2
    top   = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def text_w(draw, text, font):
    return draw.textlength(text, font=font)


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], []
    for w in words:
        test = " ".join(cur + [w])
        if text_w(draw, test, font) <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def resolve_palette(epd):
    FALLBACKS = {"ORANGE": "RED"}
    palette   = {}
    for k in PALETTE_KEYS + ["ORANGE"]:
        if hasattr(epd, k):
            palette[k] = getattr(epd, k)
        else:
            fb = FALLBACKS.get(k, "BLACK")
            palette[k] = getattr(epd, fb, (0, 0, 0))
    return palette


# ════════════════════════════════════════════════════════════════════════════════
#  SECTION RENDERERS
# ════════════════════════════════════════════════════════════════════════════════

fonts_g = {}   # global font reference for placeholder panel


def draw_masthead(draw, epd, fonts, week_days, gcal_ok):
    draw.rectangle((0, 0, W, MAST_H), fill=epd.BLACK)
    monday, sunday = week_days[0], week_days[-1]
    rng = f"WEEK OF  {monday.strftime('%d %b').upper()}  –  {sunday.strftime('%d %b %Y').upper()}"
    draw.text((22, MAST_H // 2), rng,
              font=fonts["day_lbl"], fill=epd.WHITE, anchor="lm")
    # Sync indicator (small dot top-right)
    dot_colour = epd.GREEN if gcal_ok else epd.RED
    draw.ellipse((W - 60, 18, W - 44, 34), fill=dot_colour)
    draw.text((W - 40, MAST_H // 2), "LIVE" if gcal_ok else "OFFLINE",
              font=fonts["micro"], fill=dot_colour, anchor="lm")
    draw.rectangle((0, MAST_H, W, MAST_H + 4), fill=epd.RED)


def draw_photo_panel(img, draw, epd, photo_path):
    panel_y = BODY_Y + 4
    panel_h = BODY_H - 8

    if photo_path and os.path.isfile(photo_path):
        photo = fit_cover(photo_path, PHOTO_W - 8, panel_h)
        img.paste(photo, (4, panel_y))
        draw.rectangle((4, panel_y, PHOTO_W - 4, panel_y + panel_h),
                       outline=epd.WHITE, width=3)
    else:
        colours = [epd.RED, epd.RED, epd.YELLOW,
                   epd.GREEN, epd.BLUE, epd.BLACK, epd.WHITE]
        band_h = panel_h // len(colours)
        for i, c in enumerate(colours):
            y0 = panel_y + i * band_h
            draw.rectangle((4, y0, PHOTO_W - 4, y0 + band_h), fill=c)
        draw.text((PHOTO_W // 2, panel_y + panel_h // 2),
                  "NO PHOTO", font=fonts_g["mast"],
                  fill=epd.WHITE, anchor="mm")
        draw.rectangle((4, panel_y, PHOTO_W - 4, panel_y + panel_h),
                       outline=epd.BLACK, width=3)

    draw.rectangle((PHOTO_W, BODY_Y, PHOTO_W + 1, BODY_BTM), fill=epd.BLACK)


def draw_week_strip(draw, epd, fonts, week_days, palette, schedule):
    for col, day in enumerate(week_days):
        x0 = RIGHT_X + col * COL_W
        x1 = x0 + COL_W
        y0 = BODY_Y
        y1 = BODY_Y + WEEK_H
        is_today = (day == TODAY)
        accent   = palette[DAY_ACCENT_KEYS[col]]

        draw.rectangle((x0, y0, x1 - 1, y1), fill=epd.WHITE)
        stripe_w = 5 if is_today else 3
        draw.rectangle((x0, y0, x0 + stripe_w, y1), fill=accent)

        # Header
        hdr_h = 72
        draw.rectangle((x0, y0, x1 - 1, y0 + hdr_h), fill=accent)
        lbl_colour = epd.BLACK if accent == epd.YELLOW else epd.WHITE
        draw.text((x0 + COL_W // 2, y0 + 14),
                  day.strftime("%a").upper(),
                  font=fonts["day_lbl"], fill=lbl_colour, anchor="mt")
        draw.text((x0 + COL_W // 2, y0 + 36),
                  str(day.day),
                  font=fonts["date_lg"], fill=lbl_colour, anchor="mt")
        draw.rectangle((x0, y0 + hdr_h, x1 - 1, y0 + hdr_h + 2), fill=epd.BLACK)

        # Events from schedule dict
        abbr    = day.strftime("%a")
        events  = schedule.get(abbr, [])
        ev_y    = y0 + hdr_h + 8
        ev_lh   = fonts["event"].size + 6
        for ev in events:
            if ev_y + ev_lh > y1 - 4:
                # Show overflow indicator
                draw.text((x0 + 8, ev_y), f"+{len(events) - events.index(ev)} more",
                          font=fonts["micro"], fill=epd.BLUE)
                break
            # Truncate to column width
            while ev and text_w(draw, ev, fonts["event"]) > COL_W - 14:
                ev = ev[:-1]
            draw.text((x0 + 8, ev_y), ev,
                      font=fonts["event"], fill=epd.BLACK)
            ev_y += ev_lh

        # Column border
        if col < 6:
            draw.rectangle((x1 - 1, y0, x1, y1), fill=(200, 200, 200))


def draw_task_panel(draw, epd, fonts, tasks):
    x0 = RIGHT_X
    y0 = TASK_Y
    x1 = W - 1
    y1 = BODY_BTM

    draw.rectangle((x0, y0, x1, y1), fill=epd.WHITE)
    draw.rectangle((x0, y0, x1, y0 + 3), fill=epd.BLACK)

    lbl_x = x0 + 16
    draw.text((lbl_x, y0 + 8), "TASKS",
              font=fonts["day_lbl"], fill=epd.BLACK)
    lbl_w = int(text_w(draw, "TASKS", fonts["day_lbl"]))
    draw.rectangle((lbl_x, y0 + 8 + fonts["day_lbl"].size + 2,
                    lbl_x + lbl_w, y0 + 8 + fonts["day_lbl"].size + 4),
                   fill=epd.RED)

    bullet_colours = [epd.RED, epd.GREEN, epd.BLUE,
                      epd.YELLOW, epd.RED, epd.GREEN, epd.BLUE, epd.YELLOW]
    col_split   = (RIGHT_W - 16) // 2
    task_lh     = fonts["task"].size + 7
    item_y      = y0 + 8 + fonts["day_lbl"].size + 10
    max_rows    = max(1, (y1 - item_y - 8) // task_lh)

    for i, task in enumerate(tasks[:MAX_TASKS]):
        col_idx = i // max_rows
        row_idx = i % max_rows
        tx = x0 + 16 + col_idx * (col_split + 8)
        ty = item_y + row_idx * task_lh
        if ty + task_lh > y1 - 4:
            break
        bc = bullet_colours[i % len(bullet_colours)]
        draw.ellipse((tx, ty + 6, tx + 9, ty + 15), fill=bc)
        # Truncate task text to fit column
        t = task
        while t and text_w(draw, t, fonts["task"]) > col_split - 20:
            t = t[:-1]
        draw.text((tx + 14, ty), t, font=fonts["task"], fill=epd.BLACK)


def draw_quote_strip(draw, epd, fonts):
    y0 = BODY_BTM
    y1 = H

    draw.rectangle((0, y0, W, y1), fill=epd.BLACK)
    draw.rectangle((0, y0, W, y0 + 4), fill=epd.YELLOW)
    draw.text((18, y0 + 8), "\u201c",
              font=fonts["mast"], fill=epd.YELLOW)

    text_area_w = int(W * 0.68) - 60
    q_lines = wrap(draw, QUOTE_TEXT, fonts["quote"], text_area_w)
    q_y = y0 + 18
    for line in q_lines:
        draw.text((60, q_y), line, font=fonts["quote"], fill=epd.WHITE)
        q_y += fonts["quote"].size + 6
    draw.text((60, q_y + 4), f"— {QUOTE_AUTHOR}",
              font=fonts["attr"], fill=epd.YELLOW)

    bar_x = int(W * 0.72)
    bar_w = (W - bar_x) // 6
    bar_colours = [epd.RED, epd.RED, epd.YELLOW,
                   epd.GREEN, epd.BLUE, epd.WHITE]
    for i, c in enumerate(bar_colours):
        bx = bar_x + i * bar_w
        draw.rectangle((bx, y0 + 4, bx + bar_w - 2, y1 - 2), fill=c)

    stamp = TODAY.strftime("%d · %m · %Y")
    draw.text((18, y1 - 20), stamp, font=fonts["micro"], fill=(160, 160, 160))


# ════════════════════════════════════════════════════════════════════════════════
#  COMPOSITOR
# ════════════════════════════════════════════════════════════════════════════════

def render(epd, fonts, photo_path, schedule, tasks, week_offset=0):
    week_days = get_week_days(TODAY, week_offset)
    palette   = resolve_palette(epd)
    gcal_ok   = schedule is not None

    img  = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    draw_masthead(draw, epd, fonts, week_days, gcal_ok)
    draw_photo_panel(img, draw, epd, photo_path)
    draw_week_strip(draw, epd, fonts, week_days, palette,
                    schedule if schedule else FALLBACK_SCHEDULE)
    draw_task_panel(draw, epd, fonts,
                    tasks if tasks else FALLBACK_TASKS)
    draw_quote_strip(draw, epd, fonts)

    return img


# ════════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="Artistic weekly calendar for Spectra 6 13.3\" e-Paper")
    p.add_argument("--photo",        default=None)
    p.add_argument("--no-picker",    action="store_true")
    p.add_argument("--week-offset",  type=int, default=WEEK_OFFSET)
    p.add_argument("--save",         default=None, metavar="FILE")
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--no-gcal",      action="store_true",
                   help="Skip Google Calendar fetch; use fallback data")
    return p.parse_args()


def main():
    global fonts_g
    args = parse_args()

    week_days     = get_week_days(TODAY, args.week_offset)
    monday, sunday = week_days[0], week_days[-1]
    print("=== Artistic Weekly Calendar ===")
    print(f"    Week : {monday.strftime('%d %b')} – {sunday.strftime('%d %b %Y')}")

    # ── Google Calendar + Tasks ────────────────────────────────────────────────
    schedule, tasks = None, None
    if not args.no_gcal:
        print("Fetching Google Calendar…")
        schedule = fetch_gcal_events(week_days)
        print("Fetching Google Tasks…")
        tasks    = fetch_gcal_tasks()
    else:
        print("Skipping GCal (--no-gcal).")

    # ── Resolve photo ──────────────────────────────────────────────────────────
    if args.photo:
        # --photo flag points to a specific file; use it directly this run only
        photo_path = args.photo
    else:
        folder = load_saved_folder()
        if not folder and not args.no_picker:
            # No folder saved yet — open GUI folder picker
            print("   [photo] No photo folder set — opening folder picker…")
            chosen = browse_folder_qt(os.path.expanduser("~"))
            if chosen:
                save_folder_path(chosen)
                folder = chosen
            else:
                print("   [photo] No folder selected — using geometric placeholder.")

        if folder:
            photo_path = next_photo(folder)   # advances slideshow index
        else:
            print("   [photo] No folder set and --no-picker active — using placeholder.")
            photo_path = None

    # ── Initialise EPD ─────────────────────────────────────────────────────────
    epd = epd13in3E.EPD()
    if not args.preview_only:
        print("Initialising display…")
        epd.Init()
        print("Clearing display…")
        epd.Clear()

    # ── Load fonts ─────────────────────────────────────────────────────────────
    fonts  = load_fonts(picdir, FS)
    fonts_g = fonts

    # ── Render ─────────────────────────────────────────────────────────────────
    print("Rendering…")
    image = render(epd, fonts, photo_path, schedule, tasks, args.week_offset)

    if args.save:
        image.save(args.save)
        print(f"    Saved: {args.save}")

    if not args.preview_only:
        print("Sending to display…")
        epd.display(epd.getbuffer(image))
        if DISPLAY_HOLD > 0:
            import time
            time.sleep(DISPLAY_HOLD)
        print("Going to sleep.")
        epd.sleep()
    else:
        print("Preview-only — display not touched.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:
        import traceback
        print(f"Error: {exc}")
        traceback.print_exc()
