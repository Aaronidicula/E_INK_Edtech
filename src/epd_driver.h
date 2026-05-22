#pragma once
#include <Arduino.h>
#include <SPI.h>

// ── Pin config (Waveshare ESP32 Driver Board Rev.3) ───────────────────────────
#define PIN_BUSY  25
#define PIN_RST   26
#define PIN_DC    27
#define PIN_CS    15
#define PIN_CLK   13
#define PIN_MOSI  14
#define PIN_MISO  12

// ── Panel dimensions: GDEM102F91 (960×640) ───────────────────────────────────
#define EPD_SOURCE  960   // horizontal pixels
#define EPD_GATE    640   // vertical pixels

// ── 2bpp pixel colors ─────────────────────────────────────────────────────────
#define PIX_BLACK   0x00
#define PIX_WHITE   0x01
#define PIX_YELLOW  0x02
#define PIX_RED     0x03

// ── Band renderer callback type ───────────────────────────────────────────────
// Your render function receives the current band's top/bottom row.
// Only draw pixels where y >= bandTop && y < bandBot.
typedef void (*EPD_RenderFn)(int bandTop, int bandBot);

// ── Public API ────────────────────────────────────────────────────────────────
void EPD_init();
void EPD_sleep();
void EPD_flush(EPD_RenderFn fn);   // render full frame via band callback

// Drawing primitives (call only from inside your EPD_RenderFn)
void EPD_fillRect(int x, int y, int w, int h, uint8_t pix);
void EPD_drawText(int x, int y, const char* txt, uint8_t pix, int scale=1);
void EPD_drawChar(int x, int y, char c, uint8_t pix, int scale=1);
