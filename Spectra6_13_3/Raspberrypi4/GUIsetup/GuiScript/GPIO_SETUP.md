# GPIO button / LED setup

## Files
- `gpio_control.py` — the daemon that watches the buttons and drives the LEDs.
  Drop it in the same folder as `epaper_refresh.py` (it calls that script as
  a subprocess — neither `epaper_refresh.py` nor `epaper_designer.py` needs
  any changes).
- `epaper-gpio.service` — systemd unit that starts `gpio_control.py`
  automatically on every boot.

## E-paper HAT boot config (required, one-time — not a script)

Per Waveshare's official manual, the 13.3" HAT+ (E) needs two lines added to
the Pi's boot config so the two chip-select lines are driven low at boot,
before anything in userspace (including this GPIO controller) starts:

```bash
sudo nano /boot/firmware/config.txt
# (or /boot/config.txt on older Raspberry Pi OS)

# add at the end:
gpio=7=op,dl
gpio=8=op,dl

# save (Ctrl+O, Enter), exit (Ctrl+X), then:
sudo reboot
```

This is a one-time kernel/bootloader setting, not something `gpio_control.py`
or any script needs to apply — the kernel enforces it on every boot by
itself, before Python ever runs. It also confirms GPIO7 and GPIO8 are
reserved for the e-paper HAT, alongside the other SPI/DC/RST/BUSY/PWR pins
listed below — none of them overlap with GPIO4, 5, 6, or 12.

## E-paper HAT pin reference (from Waveshare's manual)

| Signal | BCM GPIO | Physical pin # |
|---|---|---|
| VCC     | 3.3V   | 1 (or 17) |
| GND     | GND    | any GND pin, e.g. 6 |
| DIN (MOSI) | GPIO10 | 19 |
| CLK (SCLK) | GPIO11 | 23 |
| CS_M (CE0) | GPIO8  | 24 |
| CS_S (CE1) | GPIO7  | 26 |
| DC      | GPIO25 | 22 |
| RST     | GPIO17 | 11 |
| BUSY    | GPIO24 | 18 |
| PWR     | GPIO18 | 12 |

These 10 signals are what your custom pass-through PCB needs to route from
the Pi's 40-pin header to the e-paper HAT's connector.

## Wiring (BCM numbering) — GPIO breakout board
| Pin    | Function                         |
|--------|-----------------------------------|
| GPIO4  | Button → shutdown only (long press, Pi already on) |
| GPIO5  | Button → manual e-paper refresh   |
| GPIO6  | LED → on once booted, off at shutdown |
| GPIO12 | LED → blinks while refreshing      |

Wire each button between its GPIO pin and GND (gpiozero's `Button` uses the
internal pull-up by default, so no external resistor is required). Wire each
LED's anode through a ~330Ω resistor to its GPIO pin, cathode to GND.

## Power ON/OFF strategy: power bank's own button

Rather than relying on GPIO3's firmware wake-from-halt behaviour (which is
real, but has model/firmware-dependent conditions that are hard to verify
without hardware in hand — see earlier discussion) or a physical slider
switch (which doesn't suit a fixed USB power-bank cable), this deployment
uses the power bank's own physical power button:

- **Power ON**: press the power bank's button so it outputs 5V again. A
  Raspberry Pi boots automatically the instant it receives power — no
  button, no code, no config needed on the Pi side for this half. It just
  works, on any Pi model.
- **Power OFF**: long-press the GPIO4 button first. `gpio_control.py`
  detects the hold, runs a clean `shutdown -h now`, and turns the GPIO6
  LED off once the shutdown has actually happened. **Only consider the
  power bank "off" (i.e. don't rely on its own auto-shutoff, and don't
  press its button to cut output early) until the LED goes off.** Cutting
  power while the Pi is still running is the same risk as unplugging any
  computer mid-write — usually fine, but can corrupt the SD card over time
  if it happens repeatedly.

Notes specific to a power bank (vs. mains + switch):
- Most power banks — including budget/consumer models — auto-shutoff
  output after the connected device draws very little current for a
  while. After a clean shutdown, the halted Pi draws almost nothing, so
  the power bank will likely cut its own output on its own within a
  minute or so. That's fine and expected it just means you don't
  usually need to press the bank's button to turn things off, only to
  turn them back on.
- Because of that auto-shutoff, GPIO3 wake-from-halt isn't reliable here
  even if the firmware setting were configured for it — there may be no
  power left on the board by the time you'd want to wake it. The power
  bank's button is the dependable "turn it back on" action instead.
- A physical power-cycle via the bank's button is indistinguishable from
  a normal power-up from the Pi's point of view, so no special firmware
  config is required — same appeal as the slider-switch approach would
  have had, just adapted to the power-bank hardware actually in use.

If you switch to a mains supply + physical switch later, or revisit
GPIO3-based wake once you have hardware to test on, nothing here prevents
adding either back in — the earlier notes on `WAKE_ON_GPIO` still apply.

## Install

```bash
pip3 install gpiozero --break-system-packages   # usually already present on Raspberry Pi OS

sudo cp gpio_control.py /home/robotpi/Eink/RaspberryPi4/GUIsetup/GuiScript/
sudo cp epaper-gpio.service /etc/systemd/system/

# edit the ExecStart path in the service file if your folder differs
sudo nano /etc/systemd/system/epaper-gpio.service

sudo systemctl daemon-reload
sudo systemctl enable --now epaper-gpio.service

# check it's running and watch the log
sudo systemctl status epaper-gpio.service
tail -f /home/robotpi/Eink/RaspberryPi4/GUIsetup/GuiScript/gpio_control.log
```

## Adjusting timing
- Long-press duration: change `LONG_PRESS_SECONDS` in `gpio_control.py`.
- Refresh-LED blink speed: change `BLINK_INTERVAL`.
