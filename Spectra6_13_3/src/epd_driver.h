#pragma once
#include <Arduino.h>
#include <SPI.h>

// ── Pin config — ESP32 dev board wired to Waveshare 13.3" HAT+ (E) ──────────
// Adjust these to the actual GPIOs you wire up.
// The HAT exposes a standard 40-pin Pi header; break out the SPI signals below.
//
//  HAT pin name   →  function         →  ESP32 GPIO (suggested)
//  ─────────────────────────────────────────────────────────────
//  MOSI / SDA     →  SPI data out     →  GPIO 23
//  SCK  / CLK     →  SPI clock        →  GPIO 18
//  CS_M           →  Master chip-sel  →  GPIO  5   (left half, y 0-799)
//  CS_S           →  Slave  chip-sel  →  GPIO 17   (right half, y 800-1599)
//  DC             →  Data / Command   →  GPIO 27
//  RST            →  Reset (active L) →  GPIO 26
//  BUSY           →  Busy (active H)  →  GPIO 25
//
// !! The HAT has its own level-shifter so 3.3 V GPIO is fine. !!

#define PIN_MOSI    14   // DIN — hardwired on PCB
#define PIN_CLK     13   // SCK — hardwired on PCB
#define PIN_CS_M    15   // CS_M — the board's single CS pin
#define PIN_CS_S     4   // CS_S — free GPIO, wire manually to HAT CS_S pin
#define PIN_DC      27   // hardwired on PCB
#define PIN_RST     26   // hardwired on PCB
#define PIN_BUSY    25   // hardwired on PCB

// ── Panel dimensions: 13.3" Spectra 6 (1200 × 1600) ────────────────────────
// The panel is physically PORTRAIT (1200 wide × 1600 tall) but we address it
// as LANDSCAPE by swapping axes in software: WIDTH = 1600, HEIGHT = 1200.
// Each SPI controller drives one 600-column half → 300 bytes per row (4bpp).
#define EPD_WIDTH   1600   // logical horizontal pixels (source, landscape)
#define EPD_HEIGHT  1200   // logical vertical   pixels (gate,   landscape)

// Bytes per row sent to each controller (600 pixels × 4 bpp = 300 bytes)
#define EPD_HALF_COLS   600
#define EPD_ROW_BYTES   (EPD_HALF_COLS / 2)   // 300 bytes

// ── 4bpp pixel colors (Spectra 6 palette) ──────────────────────────────────
#define PIX_BLACK   0x0
#define PIX_WHITE   0x1
#define PIX_YELLOW  0x4   // check datasheet — these map 1:1 to the ACeP6 codes
#define PIX_RED     0x3
#define PIX_BLUE    0x5
#define PIX_GREEN   0x6

// ── Band renderer callback ──────────────────────────────────────────────────
// EPD_flush() calls your render function once per horizontal band.
// bandTop / bandBot are row indices in the logical coordinate space
// (0 = top, EPD_HEIGHT-1 = bottom).  Draw only within [bandTop, bandBot).
typedef void (*EPD_RenderFn)(int bandTop, int bandBot);

// ── Public API ──────────────────────────────────────────────────────────────
void EPD_init();
void EPD_sleep();
void EPD_flush(EPD_RenderFn fn);   // full-frame render via band callback

// Drawing primitives — call ONLY from inside your EPD_RenderFn callback
void EPD_fillRect(int x, int y, int w, int h, uint8_t pix);
void EPD_drawText(int x, int y, const char* txt, uint8_t pix, int scale = 1);
void EPD_drawChar(int x, int y, char c, uint8_t pix, int scale = 1);
