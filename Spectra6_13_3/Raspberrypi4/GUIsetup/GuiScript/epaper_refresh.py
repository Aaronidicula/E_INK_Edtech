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
CONFIG_PATH = os.path.join(SCRIPT_DIR, "layout.json")

# ── Waveshare lib path ────────────────────────────────────────────────────────
# Waveshare installs its Python lib here when you clone their repo.
# Adjust if your layout differs.
WAVESHARE_LIB = os.path.join(os.path.expanduser("~"),
                              "e-Paper", "RaspberryPi_JetsonNano",
                              "python", "lib")


def main():
    logging.info("=== epaper_refresh starting ===")

    # ── Load saved layout config ──────────────────────────────────────────────
    if not os.path.exists(CONFIG_PATH):
        logging.error(f"Config not found: {CONFIG_PATH}")
        logging.error("Run the designer and use File → Save Config first.")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        config = json.load(f)
    logging.info(f"Loaded config: {CONFIG_PATH}")

    # ── Import renderer from the designer (shared code) ───────────────────────
    sys.path.insert(0, SCRIPT_DIR)
    try:
        from epaper_designer import render_layout, try_fetch_gcal
        logging.info("Imported render_layout and try_fetch_gcal OK")
    except ImportError as e:
        logging.error(f"Cannot import epaper_designer: {e}")
        logging.error(f"Make sure epaper_designer.py is in {SCRIPT_DIR}")
        sys.exit(1)

    # ── Fetch live Google Calendar data ───────────────────────────────────────
    today     = datetime.date.today()
    monday    = today - datetime.timedelta(days=today.weekday())
    week_days = [monday + datetime.timedelta(days=i) for i in range(7)]

    logging.info("Fetching Google Calendar...")
    # try_fetch_gcal returns THREE values: schedule, tasks, events
    schedule, tasks, events = try_fetch_gcal(week_days)
    if schedule:
        logging.info("GCal OK — schedule fetched")
    else:
        logging.warning("GCal unavailable — using placeholder data")
    if tasks:
        logging.info(f"Tasks: {len(tasks)} items")
    if events:
        logging.info(f"Events: {len(events)} items")

    # ── Render ────────────────────────────────────────────────────────────────
    logging.info("Rendering layout...")
    try:
        img = render_layout(
            config,
            today    = today,
            schedule = schedule,
            tasks    = tasks,
            events   = events,
        )
        logging.info(f"Render complete — image size: {img.size}")
    except Exception as e:
        logging.error(f"Render failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)

    # ── Always save a PNG so you can inspect the last render ──────────────────
    png_path = os.path.join(SCRIPT_DIR, "last_render.png")
    img.save(png_path)
    logging.info(f"Saved preview PNG → {png_path}")

    # ── Push to e-paper ───────────────────────────────────────────────────────
    # Add Waveshare lib to path so epd13in3E can be imported
    for candidate in [WAVESHARE_LIB,
                      os.path.join(SCRIPT_DIR, "lib"),
                      os.path.join(os.path.dirname(SCRIPT_DIR), "lib")]:
        if os.path.isdir(candidate):
            sys.path.append(candidate)
            logging.info(f"Added lib path: {candidate}")

    try:
        import epd13in3E
        logging.info("Waveshare driver found — initialising display...")

        epd = epd13in3E.EPD()
        epd.init()                       # lowercase on newer Waveshare drivers

        # The Waveshare Spectra-6 driver expects a palette-mode image.
        # render_layout returns RGB — convert here.
        epd_img = img.convert("RGB")     # ensure no alpha channel
        epd.display(epd.getbuffer(epd_img))
        epd.sleep()
        logging.info("Display updated successfully ✓")

    except ImportError:
        logging.warning(
            "epd13in3E not found — not running on Pi or lib path wrong.\n"
            f"  Expected lib at: {WAVESHARE_LIB}\n"
            f"  PNG saved to:    {png_path}"
        )

    except AttributeError:
        # Some Waveshare driver versions use Init() (capital I) not init()
        try:
            epd.Init()
            epd_img = img.convert("RGB")
            epd.display(epd.getbuffer(epd_img))
            epd.sleep()
            logging.info("Display updated successfully (Init variant) ✓")
        except Exception as e2:
            logging.error(f"Display error (Init variant): {e2}")
            sys.exit(1)

    except Exception as e:
        logging.error(f"Display error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
