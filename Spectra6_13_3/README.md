# E-Ink Google Calendar — Waveshare 13.3" Spectra 6 Edition

Ported from the GDEM102F91 (Good Display 10.2") build.  
Panel: **Waveshare 13.3inch e-Paper HAT+ (E)** · E Ink Spectra 6 · 1600 × 1200 · 6 colour  
MCU: standard **ESP32 dev board** (38-pin DevKitC or equivalent)

---

## Hardware wiring

The HAT+ exposes SPI signals on its 40-pin Raspberry Pi header.  
Use jumper wires to the ESP32 as shown:

| HAT label | Signal          | ESP32 GPIO |
|-----------|-----------------|------------|
| MOSI      | SPI data out    | 23         |
| SCK       | SPI clock       | 18         |
| **CS_M**  | Master chip-sel | **5**      |
| **CS_S**  | Slave  chip-sel | **17**     |
| DC        | Data/Command    | 27         |
| RST       | Reset (act. L)  | 26         |
| BUSY      | Busy  (act. H)  | 25         |
| 3.3V/5V   | VCC             | 3.3V or 5V |
| GND       | Ground          | GND        |

> The HAT has an onboard level-shifter, so 3.3 V GPIO is fine.

Buttons (same as before):

| Signal       | GPIO | Wiring                                    |
|--------------|------|-------------------------------------------|
| BTN_REFRESH  | 32   | GPIO32 → button → 3.3 V; 10 kΩ to GND   |
| BTN_READ     | 33   | GPIO33 → button → GND; internal pull-up  |
| Status LED   |  2   | GPIO2 → 10 kΩ → LED anode → GND         |

---

## Why two CS lines?

The 13.3" panel physically contains **two independent SSD1677-style controllers**:

- **Master (CS_M)** drives the **left 600 columns** (x = 0 … 599)
- **Slave  (CS_S)** drives the **right 600 columns** (x = 600 … 1199)

Both share the same SCK / MOSI / DC / RST / BUSY lines.  
`epd_driver.cpp` selects each controller independently and sends 300 bytes per row per half.

---

## Can a standard ESP32 drive this panel?

**Yes.** The driver never allocates a full frame buffer.  
It keeps only **800 bytes** (one 1600-pixel row) in RAM, renders it via the band callback,  
then streams 300 bytes to Master and 300 bytes to Slave before moving to the next row.  
Total heap consumption for rendering: < 4 KB.

A standard ESP32 (520 KB SRAM) is more than sufficient.

---

## Key differences from the Good Display (10.2") build

| | Good Display 10.2" | Spectra 6 13.3" |
|---|---|---|
| Resolution | 960 × 640 | **1600 × 1200** |
| Controller | SSD2677 (single) | **dual SSD1677** |
| CS lines | 1 (PIN_CS) | **2 (PIN_CS_M + PIN_CS_S)** |
| Colours | 4 (B/W/Y/R) | **6 (+ Blue + Green)** |
| Row bytes | 240 B (2bpp) | **800 B (4bpp)** |
| Refresh | ~5 s | **~30–40 s** (full colour) |
| Init reset | single | **double reset** (mandatory) |

---

## Getting started

1. Copy `credentials.template.h` → `credentials.h` and fill in your values.
2. Open the project in PlatformIO (VS Code extension or CLI).
3. Connect the ESP32 via USB; select **ESP32 Dev Module**.
4. `pio run --target upload`
5. Open the serial monitor (`pio device monitor`) and watch the boot log.

---

## Colour palette (4bpp nibble codes)

| Constant   | Value | Colour  |
|------------|-------|---------|
| PIX_BLACK  | 0x0   | Black   |
| PIX_WHITE  | 0x1   | White   |
| PIX_RED    | 0x3   | Red     |
| PIX_YELLOW | 0x4   | Yellow  |
| PIX_BLUE   | 0x5   | Blue    |
| PIX_GREEN  | 0x6   | Green   |

---

## Refresh time

Full-colour Spectra 6 refresh takes approximately **30–40 seconds**.  
The BUSY pin goes LOW during refresh; `_waitBusy()` has a 60 s timeout.  
This is normal — the E Ink Spectra 6 drives pigment particles through liquid
and requires a long settling time for all six colours.
