#include "EPD_13in3e.h"
#include "GUI_Paint.h"
#include "fonts.h"

// Tile size — adjust to fit in free heap
// 200x200 at 4bpp = 200*200/2 = 20000 bytes
#define TILE_W  200
#define TILE_H  200
#define TILE_BUF_SIZE ((TILE_W / 2) * TILE_H)  // 4bpp = 2 pixels per byte

UBYTE *tileBuffer = NULL;

void drawTile(int x, int y, int w, int h) {
    // Example: fill tile with a pattern or image slice
    Paint_NewImage(tileBuffer, w, h, 0, EPD_13IN3E_WHITE);
    Paint_SelectImage(tileBuffer);
    Paint_Clear(EPD_13IN3E_WHITE);

    // Draw something in this tile — coordinates are LOCAL to tile
    Paint_DrawRectangle(10, 10, w - 10, h - 10, EPD_13IN3E_RED, DOT_PIXEL_2X2, DRAW_FILL_EMPTY);
    Paint_DrawString_EN(20, 20, "Hello!", &Font16, EPD_13IN3E_BLACK, EPD_13IN3E_WHITE);

    // Push tile to display at global position (x, y)
    EPD_13IN3E_DisplayPart(tileBuffer, x, y, w, h);
}

void setup() {
    Serial.begin(115200);
    Serial.println("EPD 13.3 inch 6-color init...");

    DEV_Module_Init();
    EPD_13IN3E_Init();
    EPD_13IN3E_Clear(EPD_13IN3E_WHITE);
    DEV_Delay_ms(500);

    // Allocate one tile buffer
    tileBuffer = (UBYTE *)malloc(TILE_BUF_SIZE);
    if (tileBuffer == NULL) {
        Serial.println("ERROR: malloc failed! Not enough heap.");
        while (1);
    }
    Serial.printf("Free heap after malloc: %d bytes\n", ESP.getFreeHeap());

    // Tile the entire screen with 200x200 chunks
    // Screen is 1200 wide x 1600 tall
    for (int y = 0; y < 1600; y += TILE_H) {
        for (int x = 0; x < 1200; x += TILE_W) {
            int w = min(TILE_W, 1200 - x);
            int h = min(TILE_H, 1600 - y);
            drawTile(x, y, w, h);
            Serial.printf("Tile drawn at (%d, %d)\n", x, y);
        }
    }

    Serial.println("Done. Sleeping display.");
    EPD_13IN3E_Sleep();
    free(tileBuffer);
    DEV_Module_Exit();
}

void loop() {}