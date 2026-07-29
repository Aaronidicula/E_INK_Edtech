# E_INK_Edtech

# 🖥️ Waveshare 13.3" Spectra 6 E-Paper Display — Student Guide

A complete guide to setting up, running, and customising your Waveshare 13.3" Spectra 6 e-Paper display on a Raspberry Pi 4. By the end of this guide, you'll have a live calendar dashboard on your desk that auto-refreshes with your Google Calendar events, tasks, photos, and daily quotes — plus physical buttons and LEDs for power, shutdown, and manual refresh.

---

## 📋 Table of Contents

1. [What You'll Build](#what-youll-build)
2. [Hardware & Software Requirements](#hardware--software-requirements)
3. [Project File Structure](#project-file-structure)
4. [Step 1 — Raspberry Pi Setup](#step-1--raspberry-pi-setup)
5. [Step 2 — Install Dependencies](#step-2--install-dependencies)
6. [Step 3 — Running the Demo (Optional step - can skip)](#step-3--running-the-demo)
7. [Step 4 — Google Calendar & Tasks Integration](#step-4--google-calendar--tasks-integration)
8. [Step 5 — The Visual Layout Designer (GUI)](#step-5--the-visual-layout-designer-gui)
9. [Step 6 — Auto-Refresh with Cron](#step-6--auto-refresh-with-cron)
10. [Step 7 — Physical Buttons & LEDs (GPIO)](#step-7--physical-buttons--leds-gpio)
11. [Troubleshooting](#troubleshooting)
12. [Quick Reference Cheatsheet](#quick-reference-cheatsheet)

---

## What You'll Build

You'll turn your Waveshare 13.3" Spectra 6 e-Paper display into a smart desk dashboard that shows:

- **Weekly / Monthly / Yearly calendar views** pulled live from Google Calendar
- **Task list** synced from Google Tasks
- **Photo slideshow** from a folder of your choice
- **Daily rotating inspirational quote**
- **Upcoming events panel**
- **A physical shutdown button, refresh button, power LED, and refresh-status LED**

The display auto-refreshes on a schedule you define (e.g., every 30 minutes during the day). A Tkinter-based **visual GUI designer** lets you drag, resize, and rearrange every element before pushing it to the screen. A small GPIO controller service handles the physical buttons and LEDs independently, running in the background from boot.

---

## Hardware & Software Requirements

### Hardware

| Item | Details |
|------|---------|
| Raspberry Pi 4 | Model B recommended (2GB RAM or more) |
| Waveshare 13.3" Spectra 6 e-Paper HAT | Resolution: 1600 × 1200 px, 6 colours |
| MicroSD Card | 16 GB minimum, Class 10 |
| Power Supply | Official Pi 4 USB-C adapter (5V/3A), or a power bank with its own physical power button and no forced auto-shutoff below light loads |
| Monitor + keyboard | Only needed for initial setup |
| 2× momentary push buttons | GPIO4 (shutdown) and GPIO5 (manual refresh) |
| 2× LEDs | GPIO6 (power status) and GPIO12 (refresh status) |
| 2× ~220Ω–330Ω resistors | One in series with each LED |

### Software

- Raspberry Pi OS (Bookworm or Bullseye, 64-bit recommended)
- Python 3.9+
- `gpiozero` (for the button/LED controller — usually preinstalled on Raspberry Pi OS)
- Internet connection (for Google Calendar sync)

### Display Colour Palette

The Spectra 6 driver supports exactly **6 colours**. All artwork is rendered using only these:

| Colour | RGB Value |
|--------|-----------|
| Black  | `(0, 0, 0)` |
| White  | `(255, 255, 255)` |
| Red    | `(210, 50, 30)` |
| Green  | `(30, 140, 60)` |
| Blue   | `(25, 100, 200)` |
| Yellow | `(220, 180, 0)` |

> ⚠️ Do not use any colours outside this set — the e-paper driver will map them to the nearest available colour, which may look wrong.

---

## Project File Structure

```
Spectra6_13_3/
└── Raspberrypi4/
    │
    ├── Readme.md                  # Cron quick-notes (separate from this file)
    ├── gcal_setup.py               # Duplicate copy of the demo-workflow auth script
    │                                # (identical to CustomDemoFIles/test_scripts/gcal_setup.py below)
    │
    ├── CustomDemoFIles/
    │   ├── lib/                    # Waveshare Python drivers (demo copy)
    │   │   ├── __init__.py
    │   │   ├── epdconfig.py
    │   │   └── epd13in3E.py
    │   ├── pic/                    # Fonts and assets (demo copy)
    │   │   ├── 13in3E.bmp
    │   │   └── Font.ttc
    │   └── test_scripts/            ── Demo & Classic Calendar scripts ──
    │       ├── editted.py                 # 🎓 STUDENT DEMO — learn how the display works
    │       ├── calendar_weekly_art.py     # Classic weekly calendar (code-first approach)
    │       ├── gcal_setup.py              # GCal auth for editted.py & calendar_weekly_art.py
    │       ├── epd_13in3E_test.py         # Raw Waveshare driver test script
    │       ├── credentials.json           # ← You create this (Google Cloud Console)
    │       ├── token.pickle               # ← Auto-created after running gcal_setup.py
    │       ├── photo_folder.txt           # ← Auto-saved when you pick a photo folder
    │       └── photo_index.txt            # ← Tracks slideshow position
    │
    └── GUIsetup/
        ├── lib/                       # Waveshare Python drivers
        │   ├── __init__.py
        │   ├── epdconfig.py
        │   └── epd13in3E.py
        ├── pic/                       # Fonts and assets
        │   ├── 13in3E.bmp
        │   ├── Font.ttc
        │   └── placeholder.txt
        └── GuiScript/                  ── GUI Designer, Auto-refresh & GPIO ──
            ├── epaper_designer.py     # Visual drag-and-drop layout designer
            ├── epaper_refresh.py      # Headless cron refresh (reads layout.json)
            ├── gpio_control.py        # Buttons + LEDs daemon (GPIO4/5/6/12)
            ├── epaper-gpio.service    # systemd unit — autostarts gpio_control.py
            ├── GPIO_SETUP.md          # Wiring, install steps, pin reference
            ├── layout.json            # ← Saved from designer, read by refresh
            ├── gcal_setup.py          # GCal auth for epaper_designer & epaper_refresh
            ├── credentials.json       # ← Your own copy here for the GUI workflow
            ├── token.pickle           # ← Auto-created after running GUIsetup/GuiScript/gcal_setup.py
            ├── epaper_refresh.log     # Auto-created refresh log
            └── gpio_control.log       # Auto-created GPIO controller log
```

> 📌 **Two separate `gcal_setup.py` files — use the right one!**
> - `Raspberrypi4/gcal_setup.py` → authorises **`editted.py`** and **`calendar_weekly_art.py`**
> - `GUIsetup/GuiScript/gcal_setup.py` → authorises **`epaper_designer.py`** and **`epaper_refresh.py`**
>
> Each script looks for `credentials.json` and `token.pickle` in its **own folder**. Keep them separate.

---

## Step 1 — Raspberry Pi Setup

### 1.1 Enable SPI Interface

The e-paper display communicates over SPI. You must enable it before anything works.

```bash
sudo raspi-config
```

Navigate to: **Interface Options → SPI → Enable → Yes → Finish**

Then reboot:

```bash
sudo reboot
```

### 1.2 Verify SPI is enabled

```bash
ls /dev/spi*
# Should show: /dev/spidev0.0  /dev/spidev0.1
```

If nothing shows up, SPI is not enabled — go back to `raspi-config`.

### 1.3 Required boot config for the e-paper HAT

Per Waveshare's manual for the 13.3" HAT+ (E), add these two lines to
`/boot/firmware/config.txt` (or `/boot/config.txt` on older Raspberry Pi OS)
so the display's two chip-select lines are held low at boot, before any
script runs:

```
gpio=7=op,dl
gpio=8=op,dl
```

Save, then `sudo reboot`. This is a one-time kernel-level setting — nothing
in this repo needs to apply it at runtime.

---

## Step 2 — Install Dependencies

### 2.1 System packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-pil python3-tk python3-pyqt5 git
```

### 2.2 Cloning & SettingUp the Repo in Laptop and RaspberryPi4

### 2.3 Clone

```bash
git clone https://github.com/Aaronidicula/E_INK_Edtech.git
```
### 2.4 Create a virtual environment (recommended)

Using a virtual environment keeps your project dependencies isolated and avoids conflicts with the system Python.

```bash
cd E_INK_Edtech/
python3 -m venv einkenv
source einkenv/bin/activate
```

> 💡 You'll need to activate this environment every time you open a new terminal: `source einkenv/bin/activate`

### 2.5 Install Python packages

```bash
pip install --upgrade pip
pip install Pillow PyQt5 ## if it fails --> pip install --break-system-packages Pillow && sudo apt install python3-tk
```

### 2.6 For Google Calendar support

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2.7 For the physical buttons & LEDs

```bash
pip install gpiozero --break-system-packages   # usually already present on Raspberry Pi OS
```

---

## Step 3 — Running the Demo

`editted.py` is a **teaching demo** — not a production script. It's designed to help you understand how the display pipeline works before you touch the calendar code. Read through it alongside running it.

### --> run with terminal inside <u>*raspberrypiconnect or with monitor and keyboard connected to raspberry pi*</u>
```bash
cd ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/CustomDemoFIles/test_scripts
source ~/E_INK_Edtech/einkenv/bin/activate
python3 editted.py
```

**What it does, step by step:**
1. Initialises the EPD driver and clears the screen
2. Creates a PIL `Image` canvas at the display's full 1600 × 1200 resolution
3. Uses `ImageDraw` to paint coloured text, lines, rectangles, arcs, and ellipses — demonstrating every drawing primitive
4. Calls `epd.display(epd.getbuffer(image))` to push the image to the screen
5. Opens a **Qt file picker** so you select any `.bmp`, `.png`, or `.jpg` from your filesystem
6. Resizes and centres your chosen image on a white canvas (preserving aspect ratio), then displays it

**What to learn from it:**
- How `Image.new("RGB", (width, height), colour)` creates a canvas
- How `ImageDraw.Draw(img)` lets you paint on it
- How `epd.getbuffer()` converts the PIL image for the driver
- How the `load_and_fit_image()` function handles aspect-ratio-safe resizing — a pattern reused throughout the project

> ✅ If you see the coloured shapes appear on screen, your SPI wiring and driver are working. You're ready to move on.

---

## Step 4 — Google Calendar & Tasks Integration

There are **two separate `gcal_setup.py` scripts** — one for each workflow. Run the correct one depending on which scripts you intend to use.

The Google Cloud setup steps are the same for both, so do them once:

### 4.1 Create a Google Cloud project (do this once)

1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/)
2. Create a new project (e.g., "EPaper Calendar")
3. Enable these two APIs:
   - **Google Calendar API**
   - **Google Tasks API**

### 4.2 Create OAuth2 credentials (do this once)

1. In the Cloud Console, go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Set Application type to **Desktop app**
4. Download the JSON file and rename it to `credentials.json`



### 4.3 Auth for `epaper_designer.py` and `epaper_refresh.py`

Copy `credentials.json` into `GUIsetup/GuiScript/`:

```bash
scp ~/Downloads(*give the folder path where credentials.json is located*)/credentials.json username@hostname.local:~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript
```

Then run the auth script from the GuiScript directory:

```bash
cd
cd ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript/
python3 gcal_setup.py
```

This saves `token.pickle` into `GuiScript` — right next to `epaper_designer.py` and `epaper_refresh.py`, which is where they look for it.

### 4.4 What successful auth looks like

Both scripts print the same confirmation output:

```
===== GOOGLE CALENDAR — available calendars =====
  ID: primary
      Name: Your Name ← primary

===== GOOGLE TASKS — available task lists =====
  ID: @default
      Name: My Tasks

Setup complete!
```

> 🔐 `token.pickle` contains your Google access token. Keep it private — treat it like a password. Never commit it to a public git repository.

> 💡 If your token ever expires or stops working, delete `token.pickle` and re-run the relevant `gcal_setup.py` to re-authorise.

### 4.5 Run the main calendar script
## Optional Step 
```bash
cd
cd ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/CustomDemoFIles/test_scripts
python3 calendar_weekly_art.py
```

**Command-line flags:**

| Flag | What it does |
|------|-------------|
| *(no flags)* | Fetch live GCal data and display |
| `--no-gcal` | Skip Google Calendar, use placeholder data |
| `--photo /path/to/img.jpg` | Use a specific photo this run |
| `--no-picker` | Skip the folder picker prompt (for cron) |
| `--save preview.png` | Save a PNG of the rendered layout |
| `--preview-only` | Render and save without touching the display |
| `--week-offset 1` | Show next week instead of this week |

---

## Step 5 — The Visual Layout Designer (GUI)

`epaper_designer.py` is a full Tkinter desktop app for designing your display layout interactively. Run it on the Pi (with a monitor) or on any Linux computer.

```bash
cd
cd ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript
python3 epaper_designer.py
```

### What you can do in the designer

**Template selector (top bar):**
Choose between three layouts — **Weekly**, **Monthly**, or **Yearly**. Switching will reset to that template's default widget positions.

**Left panel — Widget Controls:**
Each widget (Masthead, Photo, Calendar, Tasks, Events, Quote) has its own collapsible section where you can:
- Toggle it on/off with a checkbox
- Set X, Y position and Width, Height in pixels (e-paper pixel space: 1600 × 1200)
- Change accent colour (limited to the 6 Spectra colours)
- Adjust font size with a slider
- For the Photo panel: browse for a photos folder and choose random or sequential rotation
- For the Quote: type a custom quote and author, or leave blank for the daily auto-rotating quote

**Canvas (right panel):**
- Shows a **scaled preview** of the 1600 × 1200 display
- **Click** a widget on canvas to select it (its controls scroll into view on the left)
- **Drag** a selected widget to move it
- **Drag corner handles** to resize a widget
- **Ctrl + scroll** to zoom in/out; buttons `🔍+` / `🔍−` / `⟳` also work

**Toolbar actions:**

| Button | Action |
|--------|--------|
| ↻ GCal Sync | Fetch live calendar data to preview with real events |
| 👁 Preview | Manually trigger a re-render |
| 💾 Save PNG | Save the current render as a PNG file |
| 📋 Save Config | Save layout as `layout.json` (used by the cron script) |
| 📂 Load Config | Load a previously saved `layout.json` |
| 🖥 Push Display | Send the current render directly to the e-paper |

### Workflow for designing

1. Pick a template (Weekly / Monthly / Yearly)
2. Toggle and reposition widgets using the left panel or by dragging on canvas
3. Click **↻ GCal Sync** to see real calendar events in the preview
4. Click **👁 Preview** to refresh the canvas
5. Happy with the layout? Click **📋 Save Config** and save as `layout.json` in the `GUIsetup/GuiScript/` folder
6. Click **🖥 Push Display** to see it on the actual screen

---

## Step 6 — Auto-Refresh with Cron

Once you have your `layout.json` saved, `epaper_refresh.py` handles headless auto-refresh — no display or GUI needed.

### 6.1 Test the refresh script manually

```bash
cd ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript
python3 epaper_refresh.py
```

Check the log to see what happened:

```bash
cat epaper_refresh.log
```

### 6.2 Set up cron for automatic refresh

```bash
crontab -e
```

Add one of the following lines at the bottom of the file:

**Entered example path bellow to the epaper_refresh.py script. Enter your script path located in raspberypi. It would be inside ***E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript/*** in your pi**

**Refresh every 30 minutes, between 7am and 10pm:** 
```cron
*/30 7-22 * * * /home/robotpi/E_INK_Edtech/einkenv/bin/python3 /home/robotpi/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript/epaper_refresh.py >> /home/robotpi/epaper_refresh.log 2>&1
```

**Refresh at the 5th minute of every hour, between 7am and 10pm:**
```cron
5 7-22 * * * /home/robotpi/E_INK_Edtech/einkenv/bin/python3 /home/robotpi/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript/epaper_refresh.py >> /home/robotpi/epaper_refresh.log 2>&1
```

> ⚠️ **Important:** Replace `/home/robotpi/` with your actual home directory path. Use `echo $HOME` to find yours.

> ⚠️ **Use the venv Python:** Always use the full path to the Python inside your virtual environment (`einkenv/bin/python3`), not just `python3`. This ensures all your installed packages are available to cron.

### 6.3 Cron syntax quick reference

```
* * * * *  command
│ │ │ │ └── day of week (0–7, Sunday is 0 or 7)
│ │ │ └──── month (1–12)
│ │ └────── day of month (1–31)
│ └──────── hour (0–23)
└────────── minute (0–59)
```

| Pattern | Meaning |
|---------|---------|
| `*/30 7-22 * * *` | Every 30 minutes, 7am–10pm |
| `5 7-22 * * *` | At :05 every hour, 7am–10pm |
| `0 8 * * 1` | Every Monday at 8am |

---

## Step 7 — Physical Buttons & LEDs (GPIO)

A separate, always-on background service (`gpio_control.py`) watches two
buttons and drives two LEDs. It runs independently of `epaper_designer.py`
and `epaper_refresh.py` — it calls `epaper_refresh.py` as a subprocess when
the refresh button is pressed, but neither of those two scripts needed any
code changes to support it.

### 7.1 Hardware (BCM numbering)

| Pin | Component | Behaviour |
|-----|-----------|-----------|
| GPIO4  | Push button | Hold ≥3s while the Pi is running → clean shutdown (`shutdown -h now`) |
| GPIO5  | Push button | Short press → triggers `epaper_refresh.py` (next photo / latest tasks & events) |
| GPIO6  | LED (+ resistor) | On once the Pi has fully booted, off right before shutdown |
| GPIO12 | LED (+ resistor) | Off when idle, blinks continuously while a refresh is in progress |

Buttons wire straight to GND (gpiozero's internal pull-up is used, no
external resistor needed). Each LED needs a series resistor between its
GPIO pin and its anode; the cathode goes to GND.

**Power on/off:** power-on is handled physically — either by the power
bank's own button, or a slider switch on the power line, depending on your
setup — not by any GPIO pin. A Raspberry Pi always boots automatically the
instant it receives power. Only power-*off* runs through GPIO4, and only as
a long-press so a quick tap doesn't accidentally shut it down. See
`GPIO_SETUP.md` for the full reasoning, including why GPIO3 wake-from-halt
was considered and not used, and for the exact e-paper HAT pin list this
was cross-checked against to confirm there's no pin conflict.

### 7.2 Install as a boot service

```bash
cd ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript

sudo cp epaper-gpio.service /etc/systemd/system/

# edit the ExecStart path inside if your folder differs
sudo nano /etc/systemd/system/epaper-gpio.service

sudo systemctl daemon-reload
sudo systemctl enable --now epaper-gpio.service
```

`enable` adds it to startup so it runs on every future boot automatically;
`--now` also starts it immediately without needing a reboot.

### 7.3 Check it's working

```bash
sudo systemctl status epaper-gpio.service
tail -f ~/E_INK_Edtech/Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript/gpio_control.log
```

Full wiring diagrams, resistor values, the complete e-paper HAT pin
reference, and the reasoning behind each hardware decision live in
**`GPIO_SETUP.md`** in the same folder — read that before soldering.

---

## Choosing the Right Script for Your Use Case

| Goal | Script to use |
|------|--------------|
| Learn how the display works | `editted.py` (demo) |
| Display a weekly calendar with GCal | `calendar_weekly_art.py` |
| Authorise GCal for the above two | `Raspberrypi4/gcal_setup.py` |
| Design a custom layout visually | `GUIsetup/GuiScript/epaper_designer.py` |
| Auto-refresh from a saved layout | `GUIsetup/GuiScript/epaper_refresh.py` (via cron) |
| Authorise GCal for the above two | `GUIsetup/GuiScript/gcal_setup.py` |
| Handle physical buttons & LEDs | `GUIsetup/GuiScript/gpio_control.py` (via systemd) |

**There are two independent workflows — pick one (or both) — plus an optional third for physical controls:**

```
── Workflow A: Classic / Code-first ──────────────────────────────────────
  Spectra6_13_3/Raspberrypi4/CustomDemoFIles/test_scripts     →  Authorise Google (saves token here)
          ↓
  editted.py                      →  Demo: understand the display API
          ↓
  calendar_weekly_art.py          →  Run the weekly calendar (add to cron)


── Workflow B: GUI Designer ──────────────────────────────────────────────
  Spectra6_13_3/Raspberrypi4/GUIsetup/GuiScript          →  Authorise Google (saves token here)
          ↓
  GuiScript/epaper_designer.py     →  Design layout visually, save layout.json
          ↓
  GuiScript/epaper_refresh.py      →  Set up in cron for auto-refresh


── Workflow C: Physical controls (optional, alongside either workflow) ───
  GuiScript/epaper-gpio.service    →  Enable once via systemctl (runs at boot forever)
          ↓
  GuiScript/gpio_control.py        →  Watches GPIO4/5, drives GPIO6/12,
                                       calls epaper_refresh.py on demand
```

> Most students will use **Workflow B** (GUI) for the final display, **`editted.py`** to understand the code concepts first, and **Workflow C** if their build includes physical buttons/LEDs.

---

## Customisation Guide

### Changing the display photo

**On first run** of `calendar_weekly_art.py` (without `--no-picker`), a folder picker opens. Select a folder of photos. The path is saved to `photo_folder.txt` and re-used every time cron runs.

To change the folder later:
```bash
# Delete the saved path so the picker opens again on next manual run
rm photo_folder.txt
python3 calendar_weekly_art.py
```

Or edit `photo_folder.txt` directly:
```bash
echo "/home/pi/Pictures/holidays" > photo_folder.txt
```

### Photo rotation mode

In `calendar_weekly_art.py`, find this line near the top:
```python
PHOTO_ROTATION = "random"   # "random" or "sequential"
```

Change to `"sequential"` to cycle through photos in alphabetical order instead of picking randomly.

### Changing the quote

In `calendar_weekly_art.py`, the `QUOTES` list near the top contains all quotes. Add your own:
```python
QUOTES = [
    ("Your custom quote here.", "Author Name"),
    # ... existing quotes
]
```

The quote displayed changes daily (based on day-of-year), cycling through the list automatically.

Or in the **designer GUI**, type a custom quote directly into the Quote widget text box — it overrides the rotating quotes permanently once saved.

### Changing the refresh time

In `calendar_weekly_art.py`:
```python
DISPLAY_HOLD = 0   # seconds the display stays on before EPD sleep
```

The cron schedule itself controls how often the script runs — edit your `crontab -e` entry.

### Adjusting layout in code (without GUI)

All layout dimensions are defined as constants in `calendar_weekly_art.py`:
```python
W, H      = 1600, 1200   # Display resolution
MAST_H    = 60            # Masthead bar height
QUOTE_H   = 190           # Quote strip height
PHOTO_W   = 660           # Photo panel width
```

### Changing which calendars are shown

In `calendar_weekly_art.py`:
```python
CALENDAR_IDS = ["primary"]
# Add more calendar IDs from your Google Calendar settings:
# CALENDAR_IDS = ["primary", "your_other_calendar@group.calendar.google.com"]
```

### Changing GPIO button/LED behaviour

In `gpio_control.py`:
```python
LONG_PRESS_SECONDS = 3.0   # how long to hold GPIO4 before it triggers shutdown
BLINK_INTERVAL     = 0.4   # GPIO12 blink speed while refreshing
```

---

## Troubleshooting

### "No module named 'epd13in3E'"

The Waveshare driver isn't on the Python path. Check that `lib/epd13in3E.py` exists in your project, or that the `libdir` path at the top of the script points to the correct location.

```bash
ls ~/Eink/RaspberryPi/python/lib/epd13in3E.py
```

### "No module named 'PIL'"

Pillow isn't installed in your active environment:
```bash
source ~/einkenv/bin/activate
pip install Pillow
```

### Display shows nothing / all white

- Confirm SPI is enabled (`ls /dev/spi*`)
- Make sure the HAT is seated correctly on the GPIO pins
- Try calling `epd.Clear()` manually — the display needs an explicit clear on first use
- Confirm the `gpio=7=op,dl` / `gpio=8=op,dl` lines from Step 1.3 are present in `config.txt` and you've rebooted since adding them

### Google Calendar returns no events

- Check that `token.pickle` exists **in the same folder as the script you're running**:
  - `Raspberrypi4/token.pickle` for `calendar_weekly_art.py`
  - `GUIsetup/GuiScript/token.pickle` for `epaper_designer.py` / `epaper_refresh.py`
- Token may be expired — delete the relevant `token.pickle` and re-run the matching `gcal_setup.py`
- Verify your system clock is correct: `date`

### Cron job not running

Check the log file:
```bash
cat ~/epaper_refresh.log
```

Common issues:
- Wrong Python path in crontab (must be the venv Python, not system `python3`)
- Wrong path to the script
- Missing `layout.json` in the `GUIsetup/GuiScript/` folder

Test the exact cron command manually in your terminal first to confirm it works before relying on cron.

### "Font.ttc not found"

The font file is missing from the `pic/` directory. Copy it from the Waveshare repo:
```bash
cp ~/e-Paper/RaspberryPi_JetsonNano/python/pic/Font.ttc \
   ~/Eink/RaspberryPi/python/pic/
```

### Display shows garbled colours

You may be passing an image with colours outside the 6-colour Spectra palette. Make sure all rendered colours use only: Black, White, Red, Green, Blue, Yellow.

### Buttons/LEDs not responding

- Check the service is actually running: `sudo systemctl status epaper-gpio.service`
- Check the log: `tail -f gpio_control.log`
- Confirm wiring: buttons to GND (no resistor needed), LEDs through a resistor to GND, correct BCM pin numbers (4, 5, 6, 12)
- If the service shows a permissions error touching GPIO, confirm it's running as `User=root` in `epaper-gpio.service`
- If GPIO4/5/6/12 don't respond but the e-paper display works fine, double check nothing else is also claiming those pins — see the reserved-pin list in `GPIO_SETUP.md`

### Power bank cuts out shortly after shutdown

This is expected behaviour for most power banks (auto-shutoff under low
current draw), not a bug in `gpio_control.py`. See the "Power ON/OFF
strategy" section in `GPIO_SETUP.md`.

---

## Quick Reference Cheatsheet

```bash
# ── Setup ──────────────────────────────────────────────────────────────
source ~/einkenv/bin/activate          # Activate virtual environment
sudo raspi-config                      # Enable SPI (Interface Options → SPI)

# ── Demo (learn the display API) ───────────────────────────────────────
cd ~/Eink/RaspberryPi/python/examples/
python3 editted.py                     # Drawing demo + image picker

# ── GCal auth for editted.py & calendar_weekly_art.py ─────────────────
cd ~/Eink/RaspberryPi/python/examples/
python3 gcal_setup.py                  # Saves token.pickle here

# ── Classic weekly calendar ────────────────────────────────────────────
python3 calendar_weekly_art.py                      # Full run with GCal
python3 calendar_weekly_art.py --no-gcal            # Offline mode
python3 calendar_weekly_art.py --save preview.png --preview-only  # PNG only

# ── GCal auth for epaper_designer & epaper_refresh ────────────────────
cd ~/Eink/RaspberryPi/python/examples/GUIsetup/GuiScript/
python3 gcal_setup.py                  # Saves token.pickle here (separate!)

# ── Visual designer ────────────────────────────────────────────────────
python3 epaper_designer.py             # Launch GUI designer

# ── Manual refresh from saved layout ──────────────────────────────────
python3 epaper_refresh.py              # One-shot headless refresh

# ── Cron setup ─────────────────────────────────────────────────────────
crontab -e
# Add:
# */30 7-22 * * * /home/YOUR_USER/einkenv/bin/python3 /home/YOUR_USER/Eink/RaspberryPi/python/examples/GUIsetup/GuiScript/epaper_refresh.py >> /home/YOUR_USER/GUIsetup/epaper_refresh.log 2>&1

# ── Check refresh log ──────────────────────────────────────────────────
cat GUIsetup/GuiScript/epaper_refresh.log        # View last refresh output
tail -f GUIsetup/GuiScript/epaper_refresh.log    # Live log watching

# ── GPIO buttons/LEDs service ──────────────────────────────────────────
sudo systemctl enable --now epaper-gpio.service  # Install + start at boot
sudo systemctl status epaper-gpio.service        # Check it's running
tail -f GUIsetup/GuiScript/gpio_control.log      # Live GPIO log watching
sudo systemctl restart epaper-gpio.service       # Restart after editing gpio_control.py
```

---

## Tips for Students

- **Start by reading and running `editted.py`** — it's a teaching demo that walks through every concept (canvas, draw, buffer, display) in ~60 lines. Understanding it makes all the other scripts much easier to follow.
- **Use `--preview-only --save preview.png`** with `calendar_weekly_art.py` to see what the layout looks like without touching the physical display. Open `preview.png` on your laptop for a quick sanity check.
- **The designer GUI is your friend** — drag widgets around, see results instantly, then push to display when happy.
- **E-paper refreshes are slow** (~15–30 seconds) and the display flashes black/white during refresh — this is normal.
- **Don't refresh too often** — e-paper screens have a limited refresh cycle lifetime. Once every 15–30 minutes is plenty.
- **`token.pickle` must live next to the script that uses it** — `Raspberrypi4/token.pickle` for the classic scripts, `GUIsetup/GuiScript/token.pickle` for the designer. Run the matching `gcal_setup.py` from the correct directory.
- **Working on a PC first?** Both `epaper_designer.py` and the rendering code work on any computer with Pillow and Tkinter installed. The only part that needs the Pi is the actual `epd.display()` call to push to hardware.
- **The GPIO controller is independent of everything else** — it's a separate systemd service that just happens to call `epaper_refresh.py` as a subprocess. You can develop/test the calendar side entirely without wiring up any buttons or LEDs, and add Step 7 later whenever the hardware is ready.

---

*Happy developing! 🎉 If the display flashes and shows your calendar, you've done everything right.*
