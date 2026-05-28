#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
epaper_designer.py
──────────────────
Visual layout designer for the Waveshare 13.3" Spectra 6 e-Paper display.
Runs as a lightweight Tkinter desktop app on the Raspberry Pi.

Distinct from calendar_weekly_art.py (automated cron script) — this tool
is for students to interactively design, preview and push layouts.

Features:
  • 3 layout templates  : Weekly · Monthly · Yearly
  • Live canvas preview : scaled 1:3 representation of 1600×1200
  • Widget panel        : toggle/reposition Photo, Calendar, Events, Quote,
                          Tasks, Date header, custom Text blocks
  • Style controls      : accent colour per widget, font size sliders
  • Photo folder picker : same random-slideshow logic as main script
  • Google Calendar sync: fetches live events if token.pickle exists
  • Push to display     : sends rendered image directly to e-paper
  • Save layout         : exports config as JSON + rendered PNG

Usage:
  python3 epaper_designer.py
"""

import sys, os, json, datetime, pickle, copy, threading, random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

# ── Path setup (same convention as calendar_weekly_art.py) ───────────────────
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
picdir = os.path.join(os.path.dirname(SCRIPT_DIR), 'pic')
libdir = os.path.join(os.path.dirname(SCRIPT_DIR), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    print("ERROR: Pillow not installed. Run: pip3 install Pillow")
    sys.exit(1)

# ── Display constants ─────────────────────────────────────────────────────────
EPD_W, EPD_H = 1600, 1200
PREVIEW_SCALE = 3          # preview canvas = EPD / 3  →  533 × 400
PW = EPD_W // PREVIEW_SCALE
PH = EPD_H // PREVIEW_SCALE

# ── Spectra 6 safe palette (RGB tuples + display names) ──────────────────────
PALETTE = {
    "Black":  (0,   0,   0),
    "White":  (255, 255, 255),
    "Red":    (210, 50,  30),
    "Green":  (30,  140, 60),
    "Blue":   (25,  100, 200),
    "Yellow": (220, 180, 0),
}
PALETTE_NAMES = list(PALETTE.keys())

# ── Font size presets ─────────────────────────────────────────────────────────
FONT_PATH = os.path.join(picdir, "Font.ttc") if os.path.exists(
    os.path.join(picdir, "Font.ttc")) else None

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}

QUOTES = [
    ("The secret of getting ahead is getting started.", "Mark Twain"),
    ("It always seems impossible until it's done.",     "Nelson Mandela"),
    ("Simplicity is the ultimate sophistication.",      "Leonardo da Vinci"),
    ("Believe you can and you're halfway there.",       "Theodore Roosevelt"),
    ("Start where you are. Use what you have.",         "Arthur Ashe"),
    ("Act as if what you do makes a difference.",       "William James"),
    ("Create the things you wish existed.",             "Unknown"),
]

# ════════════════════════════════════════════════════════════════════════════════
#  DEFAULT LAYOUT CONFIGS
#  Each widget: { enabled, x, y, w, h, colour, font_size, ... }
#  Coordinates are in EPD pixel space (1600×1200).
# ════════════════════════════════════════════════════════════════════════════════

def default_weekly():
    return {
        "layout":  "weekly",
        "bg":      "White",
        "widgets": {
            "masthead": {
                "enabled": True, "x": 0,   "y": 0,
                "w": 1600, "h": 60,
                "colour": "Black", "text_colour": "White",
                "font_size": 28, "label": "Masthead bar"
            },
            "photo": {
                "enabled": True, "x": 0,   "y": 64,
                "w": 660,  "h": 756,
                "colour": "Black", "label": "Photo panel",
                "folder": "", "rotation": "random"
            },
            "week_strip": {
                "enabled": True, "x": 661, "y": 64,
                "w": 939,  "h": 680,
                "colour": "Blue", "font_size": 20, "label": "Week strip"
            },
            "tasks": {
                "enabled": True, "x": 661, "y": 744,
                "w": 939,  "h": 136,
                "colour": "Red", "font_size": 20, "label": "Task list"
            },
            "quote": {
                "enabled": True, "x": 0,   "y": 820,
                "w": 1600, "h": 190,
                "colour": "Black", "text_colour": "Yellow",
                "font_size": 26, "label": "Quote strip",
                "custom_text": "", "custom_author": ""
            },
        }
    }


def default_monthly():
    return {
        "layout":  "monthly",
        "bg":      "White",
        "widgets": {
            "masthead": {
                "enabled": True, "x": 0,   "y": 0,
                "w": 1600, "h": 60,
                "colour": "Black", "text_colour": "White",
                "font_size": 28, "label": "Masthead bar"
            },
            "photo": {
                "enabled": True, "x": 0,   "y": 64,
                "w": 500,  "h": 756,
                "colour": "Black", "label": "Photo panel",
                "folder": "", "rotation": "random"
            },
            "month_grid": {
                "enabled": True, "x": 504, "y": 64,
                "w": 1096, "h": 580,
                "colour": "Blue", "font_size": 24, "label": "Monthly grid"
            },
            "tasks": {
                "enabled": True, "x": 504, "y": 648,
                "w": 540,  "h": 240,
                "colour": "Red", "font_size": 20, "label": "Task list"
            },
            "events": {
                "enabled": True, "x": 1048, "y": 648,
                "w": 552,  "h": 240,
                "colour": "Blue", "font_size": 20, "label": "Events panel"
            },
            "quote": {
                "enabled": True, "x": 0,   "y": 820,
                "w": 1600, "h": 190,
                "colour": "Black", "text_colour": "Yellow",
                "font_size": 26, "label": "Quote strip",
                "custom_text": "", "custom_author": ""
            },
        }
    }


def default_yearly():
    return {
        "layout":  "yearly",
        "bg":      "White",
        "widgets": {
            "masthead": {
                "enabled": True, "x": 0,   "y": 0,
                "w": 1600, "h": 60,
                "colour": "Black", "text_colour": "White",
                "font_size": 28, "label": "Masthead bar"
            },
            "year_grid": {
                "enabled": True, "x": 0,   "y": 64,
                "w": 1200, "h": 950,
                "colour": "Blue", "font_size": 16, "label": "Year grid (12 months)"
            },
            "photo": {
                "enabled": True, "x": 1204, "y": 64,
                "w": 396,  "h": 460,
                "colour": "Black", "label": "Photo panel",
                "folder": "", "rotation": "random"
            },
            "tasks": {
                "enabled": True, "x": 1204, "y": 528,
                "w": 396,  "h": 240,
                "colour": "Red", "font_size": 18, "label": "Task list"
            },
            "events": {
                "enabled": True, "x": 1204, "y": 772,
                "w": 396,  "h": 242,
                "colour": "Blue", "font_size": 18, "label": "Events panel"
            },
            "quote": {
                "enabled": True, "x": 0,   "y": 1014,
                "w": 1600, "h": 186,
                "colour": "Black", "text_colour": "Yellow",
                "font_size": 22, "label": "Quote strip",
                "custom_text": "", "custom_author": ""
            },
        }
    }


TEMPLATES = {
    "weekly":  default_weekly,
    "monthly": default_monthly,
    "yearly":  default_yearly,
}

# ════════════════════════════════════════════════════════════════════════════════
#  RENDERER  —  turns a config dict into a PIL Image (1600×1200)
# ════════════════════════════════════════════════════════════════════════════════

def get_font(size):
    try:
        if FONT_PATH:
            return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()


def rgb(colour_name):
    return PALETTE.get(colour_name, (0, 0, 0))


def fit_cover(path, w, h):
    try:
        img   = Image.open(path).convert("RGB")
        ratio = max(w / img.width, h / img.height)
        nw, nh = int(img.width * ratio), int(img.height * ratio)
        img   = img.resize((nw, nh), Image.LANCZOS)
        left  = (nw - w) // 2
        top   = (nh - h) // 2
        return img.crop((left, top, left + w, top + h))
    except Exception:
        return None


def pick_photo(widget):
    folder = widget.get("folder", "")
    if not folder or not os.path.isdir(folder):
        return None
    images = sorted([
        os.path.join(folder, f) for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    ])
    if not images:
        return None
    if widget.get("rotation", "random") == "random":
        return random.choice(images)
    else:
        idx_file = os.path.join(SCRIPT_DIR, "photo_index.txt")
        try:
            idx = int(open(idx_file).read().strip()) % len(images)
        except Exception:
            idx = 0
        return images[idx]


def draw_masthead(img, draw, w, h, widget, today):
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    draw.rectangle((x, y, x+ww, y+wh), fill=rgb(widget["colour"]))
    draw.rectangle((x, y+wh, x+ww, y+wh+4), fill=rgb("Red"))
    font = get_font(widget.get("font_size", 28))
    tc   = rgb(widget.get("text_colour", "White"))
    date_str = today.strftime("WEEK OF  %d %b %Y").upper()
    draw.text((x+20, y+wh//2), date_str, font=font, fill=tc, anchor="lm")
    draw.text((x+ww-20, y+wh//2), str(today.year),
              font=get_font(widget.get("font_size", 28)+6),
              fill=rgb("Yellow"), anchor="rm")


def draw_photo_panel(img, draw, widget):
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    photo_path = pick_photo(widget)
    if photo_path:
        photo = fit_cover(photo_path, ww, wh)
        if photo:
            img.paste(photo, (x, y))
            draw.rectangle((x, y, x+ww, y+wh), outline=(255,255,255), width=3)
            return
    # Placeholder: coloured bands
    colours_list = [rgb("Red"), rgb("Yellow"), rgb("Green"),
                    rgb("Blue"), rgb("Black"), (180,180,180)]
    bh = wh // len(colours_list)
    for i, c in enumerate(colours_list):
        draw.rectangle((x, y+i*bh, x+ww, y+(i+1)*bh), fill=c)
    draw.text((x+ww//2, y+wh//2), "PHOTO", font=get_font(36),
              fill=(255,255,255), anchor="mm")
    draw.rectangle((x, y, x+ww, y+wh), outline=(0,0,0), width=3)


def draw_week_strip(draw, widget, today, schedule=None):
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    monday = today - datetime.timedelta(days=today.weekday())
    days   = [monday + datetime.timedelta(days=i) for i in range(7)]
    col_w  = ww // 7
    accent_keys = [rgb("Blue"), rgb("Green"), rgb("Red"),
                   rgb("Yellow"), rgb("Red"), rgb("Blue"), rgb("Green")]
    hdr_h  = 72
    font_lbl = get_font(widget.get("font_size", 20))
    font_num = get_font(widget.get("font_size", 20)+6)
    font_ev  = get_font(max(14, widget.get("font_size", 20)-4))

    for col, day in enumerate(days):
        cx = x + col * col_w
        draw.rectangle((cx, y, cx+col_w-1, y+wh), fill=(255,255,255))
        accent = accent_keys[col]
        stripe = 5 if day == today else 3
        draw.rectangle((cx, y, cx+stripe, y+wh), fill=accent)
        draw.rectangle((cx, y, cx+col_w-1, y+hdr_h), fill=accent)
        tc = (0,0,0) if accent == rgb("Yellow") else (255,255,255)
        draw.text((cx+col_w//2, y+14), day.strftime("%a").upper(),
                  font=font_lbl, fill=tc, anchor="mt")
        draw.text((cx+col_w//2, y+36), str(day.day),
                  font=font_num, fill=tc, anchor="mt")
        draw.rectangle((cx, y+hdr_h, cx+col_w-1, y+hdr_h+2), fill=(0,0,0))
        if schedule:
            abbr   = day.strftime("%a")
            events = schedule.get(abbr, [])
            ev_y   = y + hdr_h + 8
            lh     = font_ev.size + 6
            for ev in events:
                if ev_y + lh > y + wh - 4:
                    break
                draw.text((cx+8, ev_y), ev[:22], font=font_ev, fill=(0,0,0))
                ev_y += lh
        if col < 6:
            draw.rectangle((cx+col_w-1, y, cx+col_w, y+wh), fill=(200,200,200))


def draw_month_grid(draw, widget, today):
    import calendar as _cal
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    font_hdr = get_font(widget.get("font_size", 24)+4)
    font_day = get_font(widget.get("font_size", 24))
    font_lbl = get_font(max(14, widget.get("font_size", 24)-6))

    month_name = today.strftime("%B %Y").upper()
    draw.text((x+ww//2, y+8), month_name, font=font_hdr,
              fill=rgb(widget["colour"]), anchor="mt")

    header = ["Mo","Tu","We","Th","Fr","Sa","Su"]
    col_w  = ww // 7
    row_h  = (wh - 60) // 7
    y_grid = y + 52

    for col, lbl in enumerate(header):
        cx = x + col * col_w + col_w//2
        c  = rgb("Red") if col >= 5 else (0,0,0)
        draw.text((cx, y_grid), lbl, font=font_lbl, fill=c, anchor="mt")
    y_grid += row_h

    for week in _cal.monthcalendar(today.year, today.month):
        for col, day_num in enumerate(week):
            if day_num == 0:
                continue
            cx = x + col * col_w + col_w//2
            is_today = (day_num == today.day)
            is_wknd  = col >= 5
            if is_today:
                draw.ellipse((cx-18, y_grid, cx+18, y_grid+36),
                             fill=rgb("Red"))
                draw.text((cx, y_grid+18), str(day_num),
                          font=font_day, fill=(255,255,255), anchor="mm")
            else:
                c = rgb("Red") if is_wknd else (0,0,0)
                draw.text((cx, y_grid+18), str(day_num),
                          font=font_day, fill=c, anchor="mm")
        y_grid += row_h


def draw_year_grid(draw, widget, today):
    import calendar as _cal
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    font_mth = get_font(widget.get("font_size", 16)+2)
    font_day = get_font(widget.get("font_size", 16))

    cols, rows = 4, 3
    cell_w = ww // cols
    cell_h = wh // rows

    for m in range(1, 13):
        ci = (m-1) % cols
        ri = (m-1) // cols
        mx = x + ci * cell_w + 4
        my = y + ri * cell_h + 4

        mname = datetime.date(today.year, m, 1).strftime("%b").upper()
        draw.text((mx + cell_w//2, my+4), mname,
                  font=font_mth, fill=rgb(widget["colour"]), anchor="mt")

        col_w = (cell_w-8) // 7
        row_h = max(16, (cell_h-32) // 7)
        gy    = my + font_mth.size + 8

        for col, lbl in enumerate(["M","T","W","T","F","S","S"]):
            draw.text((mx+4 + col*col_w + col_w//2, gy), lbl,
                      font=font_day, fill=(100,100,100), anchor="mt")
        gy += row_h

        for week in _cal.monthcalendar(today.year, m):
            for col, dn in enumerate(week):
                if dn == 0:
                    continue
                cx = mx+4 + col*col_w + col_w//2
                is_today = (dn == today.day and m == today.month)
                if is_today:
                    draw.ellipse((cx-7, gy, cx+7, gy+14), fill=rgb("Red"))
                    draw.text((cx, gy+7), str(dn),
                              font=font_day, fill=(255,255,255), anchor="mm")
                else:
                    c = rgb("Red") if col >= 5 else (0,0,0)
                    draw.text((cx, gy+7), str(dn),
                              font=font_day, fill=c, anchor="mm")
            gy += row_h

        draw.rectangle((mx, my, mx+cell_w-8, my+cell_h-8),
                       outline=(200,200,200), width=1)


def draw_tasks(draw, widget, tasks):
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    draw.rectangle((x, y, x+ww, y+wh), fill=(255,255,255))
    draw.rectangle((x, y, x+ww, y+3), fill=(0,0,0))
    font_hdr  = get_font(widget.get("font_size", 20))
    font_item = get_font(max(14, widget.get("font_size", 20)-2))
    draw.text((x+14, y+8), "TASKS", font=font_hdr, fill=(0,0,0))
    uw   = int(draw.textlength("TASKS", font=font_hdr))
    draw.rectangle((x+14, y+8+font_hdr.size+2, x+14+uw, y+8+font_hdr.size+4),
                   fill=rgb(widget["colour"]))
    bullets = [rgb("Red"), rgb("Green"), rgb("Blue"),
               rgb("Yellow"), rgb("Red"), rgb("Green")]
    lh     = font_item.size + 7
    item_y = y + 8 + font_hdr.size + 10
    col_w2 = (ww-16) // 2
    for i, task in enumerate(tasks):
        ci = i // max(1, (wh - (item_y-y) - 8) // lh)
        ri = i %  max(1, (wh - (item_y-y) - 8) // lh)
        tx = x + 16 + ci * (col_w2+8)
        ty = item_y + ri * lh
        if ty + lh > y + wh - 4:
            break
        bc = bullets[i % len(bullets)]
        draw.ellipse((tx, ty+6, tx+9, ty+15), fill=bc)
        draw.text((tx+14, ty), task[:35], font=font_item, fill=(0,0,0))


def draw_events(draw, widget, events):
    """
    Upcoming-events panel.  Works in any layout — fully draggable/resizable.
    'events' is a list of dicts: { title, date_str, time_str, colour_hint }
    Falls back to placeholder rows when no live data is available.
    """
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]

    # Background
    draw.rectangle((x, y, x+ww, y+wh), fill=(255, 255, 255))
    draw.rectangle((x, y, x+ww, y+3), fill=rgb(widget.get("colour", "Blue")))

    font_hdr  = get_font(widget.get("font_size", 20))
    font_item = get_font(max(13, widget.get("font_size", 20) - 3))
    font_small = get_font(max(11, widget.get("font_size", 20) - 6))

    # Header
    header_h = font_hdr.size + 14
    draw.rectangle((x, y+3, x+ww, y+3+header_h),
                   fill=rgb(widget.get("colour", "Blue")))
    draw.text((x+14, y+3+header_h//2), "UPCOMING EVENTS",
              font=font_hdr, fill=(255, 255, 255), anchor="lm")
    draw.rectangle((x, y+3+header_h, x+ww, y+3+header_h+2), fill=(0, 0, 0))

    # Dot colours cycling through palette
    dot_colours = [rgb("Red"), rgb("Blue"), rgb("Green"),
                   rgb("Yellow"), rgb("Red"), rgb("Blue"), rgb("Green")]

    # Placeholder rows when no events fetched yet
    if not events:
        events = [
            {"title": "Connect Google Calendar",
             "date_str": "—", "time_str": ""},
            {"title": "Events will appear here",
             "date_str": "—", "time_str": ""},
        ]

    lh     = font_item.size + 10
    item_y = y + 3 + header_h + 10

    for i, ev in enumerate(events):
        if item_y + lh > y + wh - 4:
            break
        dc = dot_colours[i % len(dot_colours)]

        # Coloured left accent bar
        draw.rectangle((x+6, item_y, x+10, item_y + lh - 4), fill=dc)

        # Date badge
        date_txt = ev.get("date_str", "")
        if date_txt and date_txt != "—":
            bw = int(draw.textlength(date_txt, font=font_small)) + 10
            draw.rectangle((x+16, item_y+2, x+16+bw, item_y+font_small.size+6),
                           fill=dc)
            tc_badge = (0,0,0) if dc == rgb("Yellow") else (255,255,255)
            draw.text((x+21, item_y+4), date_txt,
                      font=font_small, fill=tc_badge)
            title_x = x + 16 + bw + 6
        else:
            title_x = x + 16

        # Title — truncate to fit width
        title   = ev.get("title", "")
        max_w   = x + ww - title_x - 8
        while title and draw.textlength(title, font=font_item) > max_w:
            title = title[:-1]
        if title != ev.get("title", ""):
            title = title[:-1] + "…"
        draw.text((title_x, item_y + 1), title, font=font_item, fill=(0, 0, 0))

        # Time (small, right-aligned)
        time_txt = ev.get("time_str", "")
        if time_txt:
            tw = int(draw.textlength(time_txt, font=font_small))
            draw.text((x + ww - tw - 10, item_y + font_item.size - font_small.size + 2),
                      time_txt, font=font_small, fill=(120, 120, 120))

        # Separator line
        item_y += lh
        draw.rectangle((x+12, item_y-3, x+ww-12, item_y-2), fill=(220,220,220))


def draw_quote(draw, widget, quote_text, quote_author):
    x, y, ww, wh = widget["x"], widget["y"], widget["w"], widget["h"]
    draw.rectangle((x, y, x+ww, y+wh), fill=rgb(widget["colour"]))
    draw.rectangle((x, y, x+ww, y+4), fill=rgb("Yellow"))
    font_q   = get_font(widget.get("font_size", 26))
    font_big = get_font(widget.get("font_size", 26)+12)
    font_att = get_font(max(14, widget.get("font_size", 26)-6))
    tc       = rgb(widget.get("text_colour", "White"))

    draw.text((x+16, y+6), "\u201c", font=font_big, fill=rgb("Yellow"))

    # Word-wrap quote
    words, lines, cur, max_w = quote_text.split(), [], [], ww*68//100 - 60
    for w in words:
        test = " ".join(cur+[w])
        if draw.textlength(test, font=font_q) <= max_w:
            cur.append(w)
        else:
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))

    qy = y+20
    for line in lines:
        draw.text((x+56, qy), line, font=font_q, fill=tc)
        qy += font_q.size + 5
    draw.text((x+56, qy+4), f"— {quote_author}",
              font=font_att, fill=rgb("Yellow"))

    # Colour bar decoration right side
    bar_x = x + int(ww*0.72)
    bar_w = (x+ww - bar_x) // 6
    for i, c in enumerate([rgb("Red"), rgb("Red"), rgb("Yellow"),
                            rgb("Green"), rgb("Blue"), (240,240,240)]):
        bx = bar_x + i*bar_w
        draw.rectangle((bx, y+4, bx+bar_w-2, y+wh-2), fill=c)


def render_layout(config, today=None, schedule=None, tasks=None, events=None):
    """
    Main render function.  Takes a config dict, returns a PIL Image (1600×1200).
    'events' is a flat list of dicts {title, date_str, time_str} for month/year views.
    """
    if today is None:
        today = datetime.date.today()
    if tasks is None:
        tasks = ["☐ Add your tasks here", "☐ Connect Google Tasks"]

    bg = PALETTE.get(config.get("bg", "White"), (255,255,255))
    img  = Image.new("RGB", (EPD_W, EPD_H), bg)
    draw = ImageDraw.Draw(img)

    widgets  = config.get("widgets", {})
    layout   = config.get("layout", "weekly")

    # Quote selection
    qi = today.timetuple().tm_yday % len(QUOTES)
    q_widget = widgets.get("quote", {})
    qt = q_widget.get("custom_text", "").strip() or QUOTES[qi][0]
    qa = q_widget.get("custom_author", "").strip() or QUOTES[qi][1]

    # Draw order: bg → photo → calendar → tasks → events → quote → masthead (top)
    order = ["photo", "week_strip", "month_grid", "year_grid",
             "tasks", "events", "quote", "masthead"]

    for key in order:
        w = widgets.get(key)
        if not w or not w.get("enabled", True):
            continue
        if key == "masthead":
            draw_masthead(img, draw, EPD_W, EPD_H, w, today)
        elif key == "photo":
            draw_photo_panel(img, draw, w)
        elif key == "week_strip":
            draw_week_strip(draw, w, today, schedule)
        elif key == "month_grid":
            draw_month_grid(draw, w, today)
        elif key == "year_grid":
            draw_year_grid(draw, w, today)
        elif key == "tasks":
            draw_tasks(draw, w, tasks)
        elif key == "events":
            draw_events(draw, w, events or [])
        elif key == "quote":
            draw_quote(draw, w, qt, qa)

    return img


# ════════════════════════════════════════════════════════════════════════════════
#  GCAL FETCH  (reused from calendar_weekly_art.py logic)
# ════════════════════════════════════════════════════════════════════════════════

TOKEN_PATH = os.path.join(SCRIPT_DIR, "token.pickle")

def try_fetch_gcal(week_days):
    """
    Returns (schedule, tasks, events).
    schedule : dict  abbr→[label, ...]   for weekly view
    tasks    : list  of task strings
    events   : list  of dicts {title, date_str, time_str} for month/year events panel
    """
    try:
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        if not os.path.exists(TOKEN_PATH):
            return None, None, None
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        if not creds or not creds.valid:
            return None, None, None

        cal = build("calendar", "v3", credentials=creds, cache_discovery=False)

        # ── Weekly schedule (next 7 days keyed by weekday abbr) ───────────────
        t_min = datetime.datetime.combine(week_days[0],  datetime.time.min).isoformat()+"Z"
        t_max = datetime.datetime.combine(week_days[-1], datetime.time.max).isoformat()+"Z"
        result = cal.events().list(
            calendarId="primary", timeMin=t_min, timeMax=t_max,
            singleEvents=True, orderBy="startTime", maxResults=50
        ).execute()
        schedule = {d.strftime("%a"): [] for d in week_days}
        for ev in result.get("items", []):
            start   = ev.get("start", {})
            summary = ev.get("summary", "")[:26]
            if "dateTime" in start:
                dt    = datetime.datetime.fromisoformat(
                    start["dateTime"].replace("Z", "+00:00")).astimezone()
                abbr  = dt.strftime("%a")
                label = f"{dt.strftime('%I:%M%p').lstrip('0')}  {summary}"
            elif "date" in start:
                d     = datetime.date.fromisoformat(start["date"])
                abbr  = d.strftime("%a")
                label = f"All day  {summary}"
            else:
                continue
            if abbr in schedule:
                schedule[abbr].append(label)

        # ── Upcoming events list for month/year views (next 30 days) ──────────
        today     = datetime.date.today()
        ev_tmin   = datetime.datetime.combine(today, datetime.time.min).isoformat()+"Z"
        ev_tmax   = datetime.datetime.combine(
            today + datetime.timedelta(days=30), datetime.time.max).isoformat()+"Z"
        ev_result = cal.events().list(
            calendarId="primary", timeMin=ev_tmin, timeMax=ev_tmax,
            singleEvents=True, orderBy="startTime", maxResults=20
        ).execute()
        events = []
        for ev in ev_result.get("items", []):
            start   = ev.get("start", {})
            summary = ev.get("summary", "(No title)")
            if "dateTime" in start:
                dt       = datetime.datetime.fromisoformat(
                    start["dateTime"].replace("Z", "+00:00")).astimezone()
                date_str = dt.strftime("%d %b")
                time_str = dt.strftime("%I:%M %p").lstrip("0")
            elif "date" in start:
                d        = datetime.date.fromisoformat(start["date"])
                date_str = d.strftime("%d %b")
                time_str = "All day"
            else:
                continue
            events.append({"title": summary, "date_str": date_str,
                           "time_str": time_str})

        # ── Tasks ─────────────────────────────────────────────────────────────
        tsk_svc  = build("tasks", "v1", credentials=creds, cache_discovery=False)
        t_result = tsk_svc.tasks().list(
            tasklist="@default", showCompleted=False, maxResults=8
        ).execute()
        tasks = [f"\u2610 {t['title']}" for t in t_result.get("items", [])
                 if t.get("status") != "completed" and t.get("title","").strip()]

        return schedule, tasks or None, events or None

    except Exception as e:
        print(f"[gcal] {e}")
        return None, None, None


# ════════════════════════════════════════════════════════════════════════════════
#  TKINTER DESIGNER APP
# ════════════════════════════════════════════════════════════════════════════════

class DesignerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("e-Paper Layout Designer  ·  Spectra 6  1600×1200")
        self.resizable(True, True)
        self.configure(bg="#1e1e2e")
        self.geometry("1200x720")
        self.minsize(900, 600)

        self.config_data  = default_weekly()
        self.schedule     = None
        self.tasks        = None
        self.events       = None   # flat list for month/year events panel
        self._preview_img = None   # current PIL image
        self._tk_img      = None   # current PhotoImage (keep ref)

        # Drag / resize / selection state
        self._selected_key  = None   # currently selected widget key
        self._drag_state    = None   # dict when dragging
        self._resize_state  = None   # dict when resizing
        self._section_refs  = {}     # key → LabelFrame widget in panel

        # Zoom state — must be set before _build_ui creates the canvas
        self._zoom_level  = PREVIEW_SCALE      # current divisor (3 = 1:3)
        self._zoom_levels = [1, 2, 3, 4, 6]   # zoom steps (1 = actual size)

        self._build_ui()
        # Defer first render until Tkinter has finished laying out the window.
        # Without this the canvas has zero size and the image is invisible.
        self.after(100, self._refresh_preview)

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Top toolbar ───────────────────────────────────────────────────────
        toolbar = tk.Frame(self, bg="#181825", pady=6)
        toolbar.pack(fill="x", side="top")

        tk.Label(toolbar, text="  Template:", bg="#181825",
                 fg="#cdd6f4", font=("Helvetica", 11)).pack(side="left")

        self._layout_var = tk.StringVar(value="weekly")
        for name in ["weekly", "monthly", "yearly"]:
            rb = tk.Radiobutton(
                toolbar, text=name.capitalize(),
                variable=self._layout_var, value=name,
                bg="#181825", fg="#cdd6f4", selectcolor="#313244",
                activebackground="#181825", activeforeground="#cdd6f4",
                font=("Helvetica", 11, "bold"),
                command=self._on_template_change
            )
            rb.pack(side="left", padx=6)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y",
                                                        padx=10, pady=4)

        self._btn(toolbar, "↻ GCal Sync",   self._sync_gcal,  "#a6e3a1")
        self._btn(toolbar, "👁 Preview",     self._refresh_preview, "#89b4fa")
        self._btn(toolbar, "💾 Save PNG",    self._save_png,   "#f9e2af")
        self._btn(toolbar, "📋 Save Config", self._save_config,"#cba6f7")
        self._btn(toolbar, "📂 Load Config", self._load_config,"#cba6f7")
        self._btn(toolbar, "🖥 Push Display",self._push_display,"#f38ba8")

        # ── Main area: draggable PanedWindow (left panel | preview) ─────────────
        paned = tk.PanedWindow(self, orient="horizontal",
                               bg="#45475a", sashwidth=6, sashpad=2,
                               sashrelief="raised", handlesize=10)
        paned.pack(fill="both", expand=True)

        # Left: widget controls
        left = tk.Frame(paned, bg="#181825")
        paned.add(left, minsize=200, width=320, stretch="never")

        tk.Label(left, text="  Widget Controls",
                 bg="#181825", fg="#89b4fa",
                 font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(10,4))

        self._panel_scroll = self._make_scrollframe(left)

        # Right: preview area
        right = tk.Frame(paned, bg="#1e1e2e")
        paned.add(right, minsize=300, stretch="always")

        # ── Preview top bar: label + zoom controls ───────────────────────────
        preview_bar = tk.Frame(right, bg="#1e1e2e")
        preview_bar.pack(fill="x", padx=10, pady=(10, 2))

        self._zoom_label = tk.StringVar(value=f"Preview  (1:{PREVIEW_SCALE} · 1600×1200)")
        tk.Label(preview_bar, textvariable=self._zoom_label,
                 bg="#1e1e2e", fg="#6c7086",
                 font=("Helvetica", 9)).pack(side="left")

        # Zoom buttons on the right side of the bar
        zoom_frame = tk.Frame(preview_bar, bg="#1e1e2e")
        zoom_frame.pack(side="right")
        for txt, cmd in [("🔍−", self._zoom_out),
                         ("⟳",   self._zoom_reset),
                         ("🔍+", self._zoom_in)]:
            tk.Button(zoom_frame, text=txt, command=cmd,
                      bg="#313244", fg="#89b4fa", relief="flat",
                      font=("Helvetica", 10, "bold"), padx=6, pady=2,
                      activebackground="#45475a", cursor="hand2"
                      ).pack(side="left", padx=2)

        # ── Scrollable canvas container ───────────────────────────────────────
        canvas_outer = tk.Frame(right, bg="#1e1e2e")
        canvas_outer.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._canvas_hscroll = ttk.Scrollbar(canvas_outer, orient="horizontal")
        self._canvas_vscroll = ttk.Scrollbar(canvas_outer, orient="vertical")
        self._canvas_hscroll.grid(row=1, column=0, sticky="ew")
        self._canvas_vscroll.grid(row=0, column=1, sticky="ns")
        canvas_outer.grid_rowconfigure(0, weight=1)
        canvas_outer.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(canvas_outer,
                                 bg="#313244", highlightthickness=1,
                                 highlightbackground="#45475a",
                                 xscrollcommand=self._canvas_hscroll.set,
                                 yscrollcommand=self._canvas_vscroll.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._canvas_hscroll.config(command=self._canvas.xview)
        self._canvas_vscroll.config(command=self._canvas.yview)

        # Ctrl+scroll to zoom
        def _canvas_zoom_scroll(event):
            direction = 0
            if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
                direction = -1   # zoom in
            elif event.num == 5 or (hasattr(event, "delta") and event.delta < 0):
                direction = 1    # zoom out
            if event.state & 0x4:   # Ctrl held
                if direction < 0: self._zoom_in()
                elif direction > 0: self._zoom_out()
            else:
                self._canvas.yview_scroll(direction * 2, "units")
        self._canvas.bind("<MouseWheel>", _canvas_zoom_scroll)
        self._canvas.bind("<Button-4>",   _canvas_zoom_scroll)
        self._canvas.bind("<Button-5>",   _canvas_zoom_scroll)

        # Bind click on canvas to show widget at that position
        self._canvas.bind("<Button-1>",        self._canvas_click)
        self._canvas.bind("<B1-Motion>",       self._canvas_drag)
        self._canvas.bind("<ButtonRelease-1>", self._canvas_release)

        # Status bar
        self._status = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self._status,
                 bg="#181825", fg="#6c7086",
                 font=("Helvetica", 9), anchor="w").pack(fill="x", side="bottom")

        self._rebuild_widget_panel()

    def _btn(self, parent, text, cmd, fg="#cdd6f4"):
        b = tk.Button(parent, text=text, command=cmd,
                      bg="#313244", fg=fg, relief="flat",
                      font=("Helvetica", 10, "bold"),
                      padx=8, pady=4,
                      activebackground="#45475a", activeforeground=fg,
                      cursor="hand2")
        b.pack(side="left", padx=4)
        return b

    def _make_scrollframe(self, parent):
        canvas = tk.Canvas(parent, bg="#181825", highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        frame  = tk.Frame(canvas, bg="#181825")
        frame.bind("<Configure>",
                   lambda e: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Mouse-wheel scrolling: bind to canvas and all child widgets
        def _on_mousewheel(event):
            # Linux uses Button-4/5, Windows/macOS use delta
            if event.num == 4:
                canvas.yview_scroll(-2, "units")
            elif event.num == 5:
                canvas.yview_scroll(2, "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_mousewheel(widget):
            widget.bind("<MouseWheel>", _on_mousewheel)
            widget.bind("<Button-4>",   _on_mousewheel)
            widget.bind("<Button-5>",   _on_mousewheel)
            for child in widget.winfo_children():
                _bind_mousewheel(child)

        # Re-bind whenever new children are added to the scrollable frame
        frame.bind("<Configure>", lambda e: (_bind_mousewheel(frame),
                                              canvas.configure(
                                                  scrollregion=canvas.bbox("all"))))
        canvas.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<Button-4>",   _on_mousewheel)
        canvas.bind("<Button-5>",   _on_mousewheel)

        self._panel_canvas    = canvas   # keep ref for scroll-into-view
        self._bind_mousewheel = _bind_mousewheel
        return frame

    def _rebuild_widget_panel(self):
        for child in self._panel_scroll.winfo_children():
            child.destroy()
        self._section_refs = {}

        widgets = self.config_data.get("widgets", {})

        # Background colour
        self._add_colour_row(self._panel_scroll, "Background",
                             self.config_data, "bg", self._refresh_preview)
        ttk.Separator(self._panel_scroll).pack(fill="x", pady=4)

        for key, widget in widgets.items():
            self._add_widget_section(self._panel_scroll, key, widget)

        # Custom text block
        ttk.Separator(self._panel_scroll).pack(fill="x", pady=4)
        self._add_custom_text_section(self._panel_scroll)

        # Re-bind mousewheel after panel is rebuilt
        if hasattr(self, "_bind_mousewheel"):
            self._bind_mousewheel(self._panel_scroll)

    def _add_widget_section(self, parent, key, widget):
        label = widget.get("label", key)

        sec = tk.LabelFrame(parent, text=f"  {label}  ",
                            bg="#181825", fg="#cdd6f4",
                            font=("Helvetica", 10, "bold"),
                            relief="groove", bd=1)
        sec.pack(fill="x", padx=8, pady=4)
        self._section_refs[key] = sec   # store for scroll-into-view

        # Enable toggle
        en_var = tk.BooleanVar(value=widget.get("enabled", True))
        def toggle(v=en_var, w=widget):
            w["enabled"] = v.get()
            self._refresh_preview()
        tk.Checkbutton(sec, text="Enabled", variable=en_var,
                       command=toggle, bg="#181825", fg="#a6e3a1",
                       selectcolor="#313244",
                       activebackground="#181825").pack(anchor="w", padx=6)

        # Position & size
        pos_frame = tk.Frame(sec, bg="#181825")
        pos_frame.pack(fill="x", padx=6, pady=2)
        for i, (lbl, field) in enumerate([("X", "x"), ("Y", "y"),
                                           ("W", "w"), ("H", "h")]):
            tk.Label(pos_frame, text=lbl, bg="#181825", fg="#6c7086",
                     font=("Helvetica", 9), width=2).grid(row=0, column=i*2, sticky="e")
            var = tk.IntVar(value=widget.get(field, 0))
            def on_pos(event, v=var, f=field, w=widget):
                try:
                    w[f] = v.get()
                    self._refresh_preview()
                except Exception:
                    pass
            sp = tk.Spinbox(pos_frame, from_=0, to=EPD_W, textvariable=var,
                            width=6, bg="#313244", fg="#cdd6f4",
                            buttonbackground="#45475a", relief="flat")
            sp.grid(row=0, column=i*2+1, padx=2)
            sp.bind("<FocusOut>", on_pos)
            sp.bind("<Return>",   on_pos)

        # Colour picker
        self._add_colour_row(sec, "Accent colour", widget, "colour",
                             self._refresh_preview)

        # Font size (if applicable)
        if "font_size" in widget:
            fs_frame = tk.Frame(sec, bg="#181825")
            fs_frame.pack(fill="x", padx=6, pady=2)
            tk.Label(fs_frame, text="Font size", bg="#181825",
                     fg="#6c7086", font=("Helvetica", 9)).pack(side="left")
            fs_var = tk.IntVar(value=widget["font_size"])
            def on_fs(v=fs_var, w=widget):
                w["font_size"] = v.get()
                self._refresh_preview()
            sl = tk.Scale(fs_frame, from_=10, to=60, orient="horizontal",
                          variable=fs_var, command=lambda _,f=on_fs: f(),
                          bg="#181825", fg="#cdd6f4", troughcolor="#313244",
                          highlightthickness=0, length=160)
            sl.pack(side="left", padx=4)

        # Photo folder picker
        if key == "photo":
            ph_frame = tk.Frame(sec, bg="#181825")
            ph_frame.pack(fill="x", padx=6, pady=2)
            folder_var = tk.StringVar(
                value=widget.get("folder", "") or "No folder selected")
            tk.Label(ph_frame, textvariable=folder_var,
                     bg="#181825", fg="#f9e2af",
                     font=("Helvetica", 8),
                     wraplength=240, justify="left").pack(side="left")
            def pick_folder(w=widget, v=folder_var):
                f = filedialog.askdirectory(title="Select photos folder")
                if f:
                    w["folder"] = f
                    v.set(f)
                    self._refresh_preview()
            tk.Button(ph_frame, text="📁 Browse",
                      command=pick_folder,
                      bg="#313244", fg="#f9e2af",
                      relief="flat", font=("Helvetica", 9),
                      cursor="hand2").pack(side="right")

            rot_var = tk.StringVar(value=widget.get("rotation","random"))
            def on_rot(w=widget, v=rot_var):
                w["rotation"] = v.get()
                self._refresh_preview()
            rot_f = tk.Frame(sec, bg="#181825")
            rot_f.pack(fill="x", padx=6, pady=2)
            for rval, rtxt in [("random","Random"),("sequential","Sequential")]:
                tk.Radiobutton(rot_f, text=rtxt, variable=rot_var, value=rval,
                               command=on_rot,
                               bg="#181825", fg="#cdd6f4",
                               selectcolor="#313244",
                               activebackground="#181825").pack(side="left")

        # Quote text editor — large multiline field for comfortable writing
        if key == "quote":
            # ── Quote text ────────────────────────────────────────────────
            tk.Label(sec, text="✏  Quote text",
                     bg="#181825", fg="#cba6f7",
                     font=("Helvetica", 9, "bold")).pack(anchor="w", padx=6, pady=(6,1))

            qt_frame = tk.Frame(sec, bg="#313244", bd=1, relief="flat")
            qt_frame.pack(fill="x", padx=6, pady=2)

            qt_box = tk.Text(qt_frame, height=4, wrap="word",
                             bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                             relief="flat", font=("Helvetica", 10),
                             padx=6, pady=4)
            qt_box.insert("1.0", widget.get("custom_text", ""))
            qt_box.pack(fill="x")

            qt_count = tk.StringVar(value="")
            tk.Label(sec, textvariable=qt_count,
                     bg="#181825", fg="#6c7086",
                     font=("Helvetica", 8)).pack(anchor="e", padx=8)

            def _qt_changed(event=None, w=widget, tb=qt_box, cv=qt_count):
                txt = tb.get("1.0", "end-1c")
                w["custom_text"] = txt
                cv.set(f"{len(txt)} chars")
                self._refresh_preview()

            qt_box.bind("<KeyRelease>", _qt_changed)
            qt_box.bind("<FocusOut>",   _qt_changed)

            # ── Author ─────────────────────────────────────────────────────
            tk.Label(sec, text="✒  Author / attribution",
                     bg="#181825", fg="#cba6f7",
                     font=("Helvetica", 9, "bold")).pack(anchor="w", padx=6, pady=(4,1))

            au_frame = tk.Frame(sec, bg="#313244", bd=1, relief="flat")
            au_frame.pack(fill="x", padx=6, pady=(0, 6))

            au_box = tk.Text(au_frame, height=2, wrap="word",
                             bg="#313244", fg="#f9e2af", insertbackground="#f9e2af",
                             relief="flat", font=("Helvetica", 10, "italic"),
                             padx=6, pady=4)
            au_box.insert("1.0", widget.get("custom_author", ""))
            au_box.pack(fill="x")

            def _au_changed(event=None, w=widget, tb=au_box):
                w["custom_author"] = tb.get("1.0", "end-1c")
                self._refresh_preview()

            au_box.bind("<KeyRelease>", _au_changed)
            au_box.bind("<FocusOut>",   _au_changed)

            # Hint
            tk.Label(sec,
                     text="💡 Leave blank to use a daily rotating quote",
                     bg="#181825", fg="#585b70",
                     font=("Helvetica", 8), wraplength=280,
                     justify="left").pack(anchor="w", padx=6, pady=(0, 4))

    def _add_colour_row(self, parent, label, data_dict, field, callback):
        row = tk.Frame(parent, bg="#181825")
        row.pack(fill="x", padx=6, pady=2)
        tk.Label(row, text=label, bg="#181825", fg="#6c7086",
                 font=("Helvetica", 9), width=14, anchor="w").pack(side="left")
        var = tk.StringVar(value=data_dict.get(field, "Black"))
        om  = ttk.Combobox(row, textvariable=var,
                           values=PALETTE_NAMES, width=10, state="readonly")
        om.pack(side="left", padx=4)
        swatch = tk.Label(row, width=3, bg=self._hex(var.get()), relief="flat")
        swatch.pack(side="left")
        def on_colour(*_, v=var, d=data_dict, f=field, s=swatch):
            d[f] = v.get()
            s.configure(bg=self._hex(v.get()))
            callback()
        om.bind("<<ComboboxSelected>>", on_colour)

    def _add_custom_text_section(self, parent):
        """Add a freeform text block anywhere on the layout."""
        sec = tk.LabelFrame(parent, text="  + Add Custom Text Block  ",
                            bg="#181825", fg="#89b4fa",
                            font=("Helvetica", 10, "bold"),
                            relief="groove", bd=1)
        sec.pack(fill="x", padx=8, pady=4)
        tk.Label(sec, text="Click canvas to place, or:",
                 bg="#181825", fg="#6c7086",
                 font=("Helvetica", 8)).pack(anchor="w", padx=6)

        fields = {}
        for lbl, key, default in [("Text", "text", "My Text"),
                                   ("X", "x", "100"), ("Y", "y", "100"),
                                   ("Size", "font_size", "24"),
                                   ("Colour", "colour", "Black")]:
            row = tk.Frame(sec, bg="#181825")
            row.pack(fill="x", padx=6, pady=1)
            tk.Label(row, text=lbl, bg="#181825", fg="#6c7086",
                     font=("Helvetica", 9), width=6,
                     anchor="w").pack(side="left")
            if lbl == "Colour":
                var = tk.StringVar(value=default)
                ttk.Combobox(row, textvariable=var,
                             values=PALETTE_NAMES,
                             width=10, state="readonly").pack(side="left")
            else:
                var = tk.StringVar(value=default)
                tk.Entry(row, textvariable=var,
                         bg="#313244", fg="#cdd6f4",
                         relief="flat", width=16).pack(side="left")
            fields[key] = var

        def add_block():
            try:
                key = f"custom_{len([k for k in self.config_data['widgets'] if k.startswith('custom')])}"
                self.config_data["widgets"][key] = {
                    "enabled": True,
                    "type": "text",
                    "text": fields["text"].get(),
                    "x": int(fields["x"].get()),
                    "y": int(fields["y"].get()),
                    "w": 400, "h": 60,
                    "font_size": int(fields["font_size"].get()),
                    "colour": fields["colour"].get(),
                    "label": f"Text: {fields['text'].get()[:12]}"
                }
                self._rebuild_widget_panel()
                self._refresh_preview()
            except Exception as e:
                self._set_status(f"Error adding block: {e}")

        tk.Button(sec, text="Add Text Block", command=add_block,
                  bg="#313244", fg="#89b4fa",
                  relief="flat", font=("Helvetica", 9, "bold"),
                  cursor="hand2").pack(padx=6, pady=4)

    @staticmethod
    def _hex(name):
        c = PALETTE.get(name, (200, 200, 200))
        return f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_template_change(self):
        layout = self._layout_var.get()
        if messagebox.askyesno("Change template",
                               f"Switch to {layout} template?\nUnsaved changes will be lost."):
            self.config_data = TEMPLATES[layout]()
            self._rebuild_widget_panel()
            self._refresh_preview()

    # ── Zoom helpers ──────────────────────────────────────────────────────────

    def _zoom_in(self):
        idx = self._zoom_levels.index(self._zoom_level)
        if idx > 0:
            self._zoom_level = self._zoom_levels[idx - 1]
            self._refresh_preview()

    def _zoom_out(self):
        idx = self._zoom_levels.index(self._zoom_level)
        if idx < len(self._zoom_levels) - 1:
            self._zoom_level = self._zoom_levels[idx + 1]
            self._refresh_preview()

    def _zoom_reset(self):
        self._zoom_level = PREVIEW_SCALE   # back to default 1:3
        self._refresh_preview()

    def _refresh_preview(self):
        self._set_status("Rendering preview…")
        try:
            img = render_layout(
                self.config_data,
                today=datetime.date.today(),
                schedule=self.schedule,
                tasks=self.tasks,
                events=self.events
            )
            # Draw any custom text blocks
            draw = ImageDraw.Draw(img)
            for key, w in self.config_data.get("widgets", {}).items():
                if w.get("type") == "text" and w.get("enabled", True):
                    font = get_font(w.get("font_size", 24))
                    draw.text((w["x"], w["y"]), w.get("text", ""),
                              font=font, fill=rgb(w.get("colour","Black")))

            self._preview_img = img

            # Scale the preview image according to current zoom level
            z  = self._zoom_level
            pw = EPD_W // z
            ph = EPD_H // z
            small = img.resize((pw, ph), Image.LANCZOS)
            self._tk_img = ImageTk.PhotoImage(small)

            self._canvas.delete("all")
            self._canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
            # Only update scrollregion — do NOT set width/height here because
            # that fights the grid geometry manager and shrinks the canvas.
            self._canvas.configure(scrollregion=(0, 0, pw, ph))

            # Update zoom label
            if z == 1:
                zlbl = "1:1 (actual size)"
            else:
                zlbl = f"1:{z} scale"
            self._zoom_label.set(f"Preview  ({zlbl}  ·  1600×1200)")

            self._draw_widget_outlines()
            self._set_status(f"Preview updated  ·  {datetime.datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            import traceback
            self._set_status(f"Render error: {e}")
            traceback.print_exc()

    # ── Canvas resize-handle size (in preview pixels) ────────────────────────
    _HANDLE = 7

    def _draw_widget_outlines(self):
        """Draw coloured bounding boxes, selection highlight, and resize handles."""
        outline_colours = {
            "masthead": "#89b4fa", "photo": "#f9e2af",
            "week_strip": "#a6e3a1", "month_grid": "#a6e3a1",
            "year_grid": "#a6e3a1", "tasks": "#f38ba8",
            "events": "#89dceb",
            "quote": "#cba6f7",
        }
        H = self._HANDLE
        z = self._zoom_level
        for key, w in self.config_data.get("widgets", {}).items():
            if not w.get("enabled", True):
                continue
            sx = w["x"] // z
            sy = w["y"] // z
            sw = w["w"] // z
            sh = w["h"] // z
            selected = (key == self._selected_key)
            c  = "#ffffff" if selected else outline_colours.get(key, "#6c7086")
            lw = 2 if selected else 1
            dash = () if selected else (4, 4)
            self._canvas.create_rectangle(
                sx, sy, sx+sw, sy+sh,
                outline=c, width=lw, dash=dash, tags=f"widget_{key}"
            )
            self._canvas.create_text(
                sx+4, sy+4, text=w.get("label", key),
                fill=c, anchor="nw",
                font=("Helvetica", 7), tags=f"widget_{key}"
            )
            # Draw resize handles at all four corners when selected
            if selected:
                for hx, hy in [(sx, sy), (sx+sw, sy),
                               (sx, sy+sh), (sx+sw, sy+sh)]:
                    self._canvas.create_rectangle(
                        hx-H, hy-H, hx+H, hy+H,
                        fill="#ffffff", outline="#89b4fa", width=1,
                        tags=f"handle_{key}"
                    )

    def _hit_handle(self, ex, ey):
        """Return (key, corner_str) if (ex,ey) is over a resize handle, else None."""
        H = self._HANDLE + 2
        z = self._zoom_level
        for key, w in self.config_data.get("widgets", {}).items():
            if not w.get("enabled", True):
                continue
            sx = w["x"] // z
            sy = w["y"] // z
            sw = w["w"] // z
            sh = w["h"] // z
            for corner, (hx, hy) in [("nw", (sx, sy)),
                                      ("ne", (sx+sw, sy)),
                                      ("sw", (sx, sy+sh)),
                                      ("se", (sx+sw, sy+sh))]:
                if abs(ex - hx) <= H and abs(ey - hy) <= H:
                    return key, corner
        return None

    def _hit_widget(self, ex, ey):
        """Return widget key at canvas point (ex, ey), topmost first."""
        keys = list(self.config_data.get("widgets", {}).keys())
        z = self._zoom_level
        for key in reversed(keys):
            w = self.config_data["widgets"][key]
            if not w.get("enabled", True):
                continue
            sx = w["x"] // z
            sy = w["y"] // z
            sw = w["w"] // z
            sh = w["h"] // z
            if sx <= ex <= sx+sw and sy <= ey <= sy+sh:
                return key
        return None

    def _canvas_click(self, event):
        ex, ey = event.x, event.y

        # Check resize handles first (only when a widget is selected)
        hit = self._hit_handle(ex, ey)
        if hit:
            key, corner = hit
            w = self.config_data["widgets"][key]
            self._resize_state = {
                "key": key, "corner": corner,
                "ox": w["x"], "oy": w["y"],
                "ow": w["w"], "oh": w["h"],
                "mx": ex,     "my": ey,
            }
            self._drag_state = None
            return

        # Check widget body hit
        key = self._hit_widget(ex, ey)
        if key:
            w = self.config_data["widgets"][key]
            self._selected_key = key
            self._drag_state = {
                "key": key,
                "ox": w["x"], "oy": w["y"],
                "mx": ex,     "my": ey,
            }
            self._resize_state = None
            self._set_status(
                f"Selected: {w.get('label', key)}  "
                f"[{w['x']},{w['y']}  {w['w']}×{w['h']}]"
            )
            self._draw_widget_outlines()
            self._scroll_panel_to(key)
        else:
            # Click on empty space → deselect
            self._selected_key = None
            self._drag_state   = None
            self._resize_state = None
            self._draw_widget_outlines()

    def _canvas_drag(self, event):
        ex, ey = event.x, event.y
        z = self._zoom_level

        if self._resize_state:
            rs     = self._resize_state
            dx     = (ex - rs["mx"]) * z
            dy     = (ey - rs["my"]) * z
            corner = rs["corner"]
            w      = self.config_data["widgets"][rs["key"]]

            # Adjust x/y/w/h based on which corner is being dragged
            if corner == "nw":
                w["x"] = max(0, rs["ox"] + dx)
                w["y"] = max(0, rs["oy"] + dy)
                w["w"] = max(40, rs["ow"] - dx)
                w["h"] = max(20, rs["oh"] - dy)
            elif corner == "ne":
                w["y"] = max(0, rs["oy"] + dy)
                w["w"] = max(40, rs["ow"] + dx)
                w["h"] = max(20, rs["oh"] - dy)
            elif corner == "sw":
                w["x"] = max(0, rs["ox"] + dx)
                w["w"] = max(40, rs["ow"] - dx)
                w["h"] = max(20, rs["oh"] + dy)
            elif corner == "se":
                w["w"] = max(40, rs["ow"] + dx)
                w["h"] = max(20, rs["oh"] + dy)

            # Snap to 4-px grid for clean alignment
            w["x"] = int((w["x"] // 4) * 4)
            w["y"] = int((w["y"] // 4) * 4)
            w["w"] = int((w["w"] // 4) * 4)
            w["h"] = int((w["h"] // 4) * 4)

            self._set_status(
                f"Resizing: {w.get('label', rs['key'])}  "
                f"[{w['x']},{w['y']}  {w['w']}×{w['h']}]"
            )
            self._refresh_preview()
            return

        if self._drag_state:
            ds = self._drag_state
            dx = (ex - ds["mx"]) * z
            dy = (ey - ds["my"]) * z
            w  = self.config_data["widgets"][ds["key"]]
            w["x"] = int(max(0, min(EPD_W - w["w"], ds["ox"] + dx)))
            w["y"] = int(max(0, min(EPD_H - w["h"], ds["oy"] + dy)))

            # Snap to 4-px grid
            w["x"] = (w["x"] // 4) * 4
            w["y"] = (w["y"] // 4) * 4

            self._set_status(
                f"Moving: {w.get('label', ds['key'])}  "
                f"[{w['x']},{w['y']}  {w['w']}×{w['h']}]"
            )
            self._refresh_preview()

    def _canvas_release(self, event):
        if self._drag_state or self._resize_state:
            # Final commit: sync spinboxes by rebuilding the panel section
            self._rebuild_widget_panel()
            self._refresh_preview()
        self._drag_state   = None
        self._resize_state = None

    def _scroll_panel_to(self, key):
        """Scroll the left widget panel so the section for 'key' is visible."""
        sec = self._section_refs.get(key)
        if sec is None or not hasattr(self, "_panel_canvas"):
            return
        try:
            self.update_idletasks()
            panel_canvas = self._panel_canvas
            frame_h = self._panel_scroll.winfo_reqheight()
            if frame_h <= 0:
                return
            sec_y  = sec.winfo_y()
            sec_h  = sec.winfo_height()
            vis_h  = panel_canvas.winfo_height()
            # Fraction to scroll to: centre the section in view
            frac = (sec_y + sec_h / 2 - vis_h / 2) / frame_h
            frac = max(0.0, min(1.0, frac))
            panel_canvas.yview_moveto(frac)
        except Exception:
            pass

    def _sync_gcal(self):
        self._set_status("Syncing Google Calendar…")
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        week_days = [monday + datetime.timedelta(days=i) for i in range(7)]
        def do_sync():
            s, t, ev = try_fetch_gcal(week_days)
            self.schedule = s
            self.tasks    = t
            self.events   = ev
            status = "GCal synced ✓" if s else "GCal unavailable (using fallback)"
            self.after(0, lambda: self._set_status(status))
            self.after(0, self._refresh_preview)
        threading.Thread(target=do_sync, daemon=True).start()

    def _save_png(self):
        if self._preview_img is None:
            self._refresh_preview()
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("BMP", "*.bmp")],
            title="Save rendered image"
        )
        if path:
            self._preview_img.save(path)
            self._set_status(f"Saved: {path}")

    def _save_config(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON config", "*.json")],
            title="Save layout config"
        )
        if path:
            with open(path, "w") as f:
                json.dump(self.config_data, f, indent=2)
            self._set_status(f"Config saved: {path}")

    def _load_config(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON config", "*.json")],
            title="Load layout config"
        )
        if path:
            try:
                with open(path) as f:
                    self.config_data = json.load(f)
                layout = self.config_data.get("layout", "weekly")
                self._layout_var.set(layout)
                self._rebuild_widget_panel()
                self._refresh_preview()
                self._set_status(f"Config loaded: {path}")
            except Exception as e:
                messagebox.showerror("Load error", str(e))

    def _push_display(self):
        if not messagebox.askyesno("Push to display",
                                   "This will refresh the e-paper display.\nContinue?"):
            return
        if self._preview_img is None:
            self._refresh_preview()
        self._set_status("Pushing to display…")
        def do_push():
            try:
                import epd13in3E
                epd = epd13in3E.EPD()
                epd.Init()
                epd.Clear()
                epd.display(epd.getbuffer(self._preview_img))
                epd.sleep()
                self.after(0, lambda: self._set_status("✓ Pushed to display successfully!"))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Display error: {e}"))
                self.after(0, lambda: messagebox.showerror("Display error", str(e)))
        threading.Thread(target=do_push, daemon=True).start()

    def _set_status(self, msg):
        self._status.set(f"  {msg}")


# ════════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = DesignerApp()
    app.mainloop()
