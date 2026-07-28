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

## Power ON/OFF strategy: physical slider switch

Rather than relying on GPIO3's firmware wake-from-halt behaviour (which is
real, but has model/firmware-dependent conditions that are hard to verify
without hardware in hand — see earlier discussion), this deployment uses a
physical slider switch on the power line instead:

- **Power ON**: flip the slider on. A Raspberry Pi boots automatically the
  instant it receives power — no button, no code, no config needed for
  this half. It just works, on any Pi model.
- **Power OFF**: long-press the GPIO4 button first. `gpio_control.py`
  detects the hold, runs a clean `shutdown -h now`, and turns the GPIO6
  LED off once the shutdown has actually happened. **Only flip the slider
  off after the LED goes off.** Cutting power while the Pi is still
  running is the same risk as unplugging any computer mid-write — usually
  fine, but can corrupt the SD card over time if it happens repeatedly.

Practical wiring notes for the slider:
- It must be in series with the **power input** (5V/USB-C line), not
  connected to any GPIO — GPIO pins can't carry the current a Pi needs.
- Rate it (or the relay/MOSFET it's driving) for at least 3A to cover
  Pi 4 power spikes.
- A physical "off, then on" cycle is indistinguishable from a normal power
  cycle from the Pi's point of view, so no special firmware config is
  required for this approach — that's the main appeal versus GPIO3 wake.

If you revisit GPIO3-based wake later once you have hardware to test on,
the earlier notes on `WAKE_ON_GPIO` and the model-dependent caveats still
apply and nothing here prevents adding it back in.

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
