#!/usr/bin/python3
# epaper_refresh.py — headless cron script
# Reads the last saved config JSON and pushes a fresh render to the e-paper.
# No display/GUI needed. Run via crontab.

import sys, os, json, datetime, logging

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LOG_FILE   = os.path.join(SCRIPT_DIR, "epaper_refresh.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M"
)

# ── Config path ───────────────────────────────────────────────────────────────
# This is whatever you last saved from the designer (File → Save Config)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "layout.json")

def main():
    logging.info("=== epaper_refresh starting ===")

    # ── Load saved layout config ──────────────────────────────────────────────
    if not os.path.exists(CONFIG_PATH):
        logging.error(f"Config not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    logging.info(f"Loaded config: {CONFIG_PATH}")

    # ── Import renderer from the designer (shared code) ───────────────────────
    sys.path.insert(0, SCRIPT_DIR)
    from epaper_designer import render_layout, try_fetch_gcal

    # ── Fetch live Google Calendar data ───────────────────────────────────────
    today    = datetime.date.today()
    monday   = today - datetime.timedelta(days=today.weekday())
    week_days = [monday + datetime.timedelta(days=i) for i in range(7)]

    logging.info("Fetching Google Calendar...")
    schedule, tasks = try_fetch_gcal(week_days)
    if schedule:
        logging.info("GCal OK")
    else:
        logging.warning("GCal unavailable — using placeholder data")

    # ── Render ────────────────────────────────────────────────────────────────
    logging.info("Rendering layout...")
    img = render_layout(config, today=today, schedule=schedule, tasks=tasks)

    # ── Push to e-paper ───────────────────────────────────────────────────────
    try:
        libdir = os.path.join(os.path.dirname(SCRIPT_DIR), "lib")
        if os.path.exists(libdir):
            sys.path.append(libdir)

        import epd13in3E
        epd = epd13in3E.EPD()
        logging.info("Initialising display...")
        epd.Init()
        epd.display(epd.getbuffer(img))
        epd.sleep()
        logging.info("Display updated successfully ✓")

    except ImportError:
        # Not on Pi — save PNG instead so you can test on desktop
        out = os.path.join(SCRIPT_DIR, "last_render.png")
        img.save(out)
        logging.info(f"No epd driver found — saved preview to {out}")

    except Exception as e:
        logging.error(f"Display error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
