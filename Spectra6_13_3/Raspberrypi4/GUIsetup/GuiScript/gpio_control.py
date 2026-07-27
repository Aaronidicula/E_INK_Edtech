#!/usr/bin/env python3
# gpio_control.py — physical button + LED controller for the e-paper frame.
#
# Runs as a standalone daemon (see epaper-gpio.service) started at boot.
# It does NOT modify epaper_designer.py or epaper_refresh.py — it simply
# calls epaper_refresh.py as a subprocess when the refresh button is pressed.
#
# ── Hardware (BCM numbering) ──────────────────────────────────────────────
#   GPIO4  — button : long-press (>= LONG_PRESS_SECONDS) while the Pi is
#                     running triggers a clean shutdown.
#   GPIO5  — button : short press triggers an immediate e-paper refresh
#                     (next photo / latest tasks & events).
#   GPIO6  — LED    : ON once this script has started (i.e. Pi fully booted),
#                     OFF right before shutdown.
#   GPIO12 — LED    : OFF when idle, blinks continuously while a refresh is
#                     in progress, OFF again the instant it finishes.
#
# ── Power on/off strategy used in this deployment ─────────────────────────
#   Power ON is handled by a physical slider switch on the 5V/USB-C power
#   line — a Pi boots automatically the moment power is applied, no button
#   or code involved. GPIO4 here only ever handles the "already running"
#   half: hold it for LONG_PRESS_SECONDS to trigger a clean shutdown.
#   IMPORTANT for whoever wires/labels the enclosure: the slider should only
#   ever be flipped OFF *after* a long-press shutdown has finished (GPIO6
#   LED goes off) — flipping it off while the Pi is still running is an
#   unclean power cut, same risk as yanking the cord (possible SD-card
#   corruption over time).

import os
import sys
import signal
import logging
import threading
import subprocess

from gpiozero import Button, LED

# ── Pin assignment ─────────────────────────────────────────────────────────
PIN_POWER_BUTTON   = 4
PIN_REFRESH_BUTTON = 5
PIN_POWER_LED      = 6
PIN_REFRESH_LED    = 12

LONG_PRESS_SECONDS = 3.0   # hold GPIO4 this long to shut down
BLINK_INTERVAL     = 0.4   # seconds on / seconds off while refreshing

SCRIPT_DIR     = os.path.dirname(os.path.realpath(__file__))
REFRESH_SCRIPT = os.path.join(SCRIPT_DIR, "epaper_refresh.py")
LOG_FILE       = os.path.join(SCRIPT_DIR, "gpio_control.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

power_led   = LED(PIN_POWER_LED)
refresh_led = LED(PIN_REFRESH_LED)

# hold_time = how long GPIO4 must stay pressed before when_held fires
power_btn   = Button(PIN_POWER_BUTTON, hold_time=LONG_PRESS_SECONDS, bounce_time=0.05)
refresh_btn = Button(PIN_REFRESH_BUTTON, bounce_time=0.2)

_blink_stop   = threading.Event()
_blink_thread = None
_refresh_lock = threading.Lock()


# ── Refresh-LED blinking ────────────────────────────────────────────────────
def _blink_loop():
    while not _blink_stop.is_set():
        refresh_led.on()
        if _blink_stop.wait(BLINK_INTERVAL):
            break
        refresh_led.off()
        if _blink_stop.wait(BLINK_INTERVAL):
            break
    refresh_led.off()


def start_blink():
    global _blink_thread
    _blink_stop.clear()
    _blink_thread = threading.Thread(target=_blink_loop, daemon=True)
    _blink_thread.start()


def stop_blink():
    _blink_stop.set()
    if _blink_thread:
        _blink_thread.join(timeout=2)
    refresh_led.off()


# ── Button actions ──────────────────────────────────────────────────────────
def do_refresh():
    """Runs epaper_refresh.py in a worker thread; GPIO12 blinks the whole time."""
    if not _refresh_lock.acquire(blocking=False):
        logging.info("Refresh already running — ignoring extra press")
        return
    try:
        logging.info("GPIO5 pressed — starting refresh")
        start_blink()
        result = subprocess.run(
            [sys.executable, REFRESH_SCRIPT],
            cwd=SCRIPT_DIR,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logging.info("Refresh finished OK")
        else:
            logging.error(
                f"Refresh exited with code {result.returncode}: "
                f"{result.stderr[-500:]}"
            )
    except Exception as e:
        logging.error(f"Refresh error: {e}")
    finally:
        stop_blink()
        _refresh_lock.release()


def do_shutdown():
    logging.info("GPIO4 long-press detected — shutting down")
    power_led.off()
    refresh_led.off()
    # Run as root (see epaper-gpio.service) so no sudo password is needed.
    subprocess.run(["shutdown", "-h", "now"])


def _on_signal(signum, frame):
    logging.info(f"Signal {signum} received — turning off LEDs before exit")
    power_led.off()
    refresh_led.off()
    sys.exit(0)


def main():
    logging.info("=== gpio_control starting ===")
    power_led.on()   # Pi is fully booted and this service is running

    refresh_btn.when_pressed = lambda: threading.Thread(
        target=do_refresh, daemon=True
    ).start()
    power_btn.when_held = do_shutdown

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    signal.pause()   # sleep until a signal arrives; gpiozero handles buttons via callbacks


if __name__ == "__main__":
    main()
