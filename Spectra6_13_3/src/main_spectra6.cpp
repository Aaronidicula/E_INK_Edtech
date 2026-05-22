// main_spectra6.cpp — E-Ink Google Calendar Display
// Panel: Waveshare 13.3" e-Paper HAT+ (E) — E Ink Spectra 6 — 1600×1200
//
// Layout (landscape, 1600 wide × 1200 tall)
// ─────────────────────────────────────────
//  ┌─────────────────────────────────────────────────────────────────────┐
//  │  RED HEADER  (month+year left, day-of-week, time right)   h=80     │
//  ├────────────────────────┬────────────────────────────────────────────┤
//  │  LEFT COLUMN  w=460    │  RIGHT COLUMN  w=~1120                     │
//  │  mini-month grid       │  UPCOMING 7 DAYS agenda                    │
//  │  ─────────────────     │  one card per event                        │
//  │  TASKS section         │                                            │
//  ├────────────────────────┴────────────────────────────────────────────┤
//  │  YELLOW FOOTER  (updated time, next refresh)              h=36      │
//  └─────────────────────────────────────────────────────────────────────┘
//
// Colour notes
// ─────────────
// Spectra 6 supports: Black, White, Yellow, Red, Blue, Green.
// We keep the same visual language as the Good Display build:
//   header = RED, footer = YELLOW, accents = RED/BLACK.

#include <Arduino.h>
#include <WiFi.h>
#include "credentials.h"
#include "epd_driver.h"
#include "gcal.h"
#include "driver/rtc_io.h"

#define REFRESH_MINUTES  15

// ── Buttons ──────────────────────────────────────────────────────────────────
// BTN_REFRESH: GPIO32 → button → 3.3V, 10 kΩ pulldown to GND
// Pressed = HIGH; EXT1 ANY_HIGH wakeup
#define BTN_REFRESH  32
#define BTN_READ     33

// ── Status LED ────────────────────────────────────────────────────────────────
#define PIN_LED      2
#define LED_ON()     digitalWrite(PIN_LED, HIGH)
#define LED_OFF()    digitalWrite(PIN_LED, LOW)

static void ledBlink(int times, int onMs, int offMs) {
  for (int i = 0; i < times; i++) {
    LED_ON();  delay(onMs);
    LED_OFF(); delay(offMs);
  }
}

static void ledBlinkTick(uint32_t intervalMs) {
  static uint32_t lastToggle = 0;
  static bool     ledState   = false;
  uint32_t now = millis();
  if (now - lastToggle >= intervalMs) {
    lastToggle = now;
    ledState = !ledState;
    digitalWrite(PIN_LED, ledState ? HIGH : LOW);
  }
}

// ── Global state ──────────────────────────────────────────────────────────────
static CalEvent  gEvents[GCAL_MAX_EVENTS];
static CalEvent  gTasks[GCAL_MAX_EVENTS];
static int       gTaskCount  = 0;
static int       gEventCount = 0;
static char      gDateStr[32] = "Loading...";
static char      gTimeStr[12] = "";

// ── Calendar math ─────────────────────────────────────────────────────────────
static int firstDayOfWeek(int year, int month) {
  struct tm t = {};
  t.tm_year = year - 1900;
  t.tm_mon  = month - 1;
  t.tm_mday = 1;
  mktime(&t);
  return t.tm_wday;
}

static int daysInMonth(int year, int month) {
  int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (month == 2 && ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0)) return 29;
  return days[month - 1];
}

// ── Layout constants (all in logical pixels, landscape 1600×1200) ─────────────
#define HEADER_H    80
#define FOOTER_H    36
#define FOOTER_Y    (EPD_HEIGHT - FOOTER_H)

// Left column: mini-month + tasks
#define LEFT_W      460
#define LEFT_PAD    16

// Right column: agenda
#define RIGHT_X     (LEFT_W + 4)    // +4 for divider
#define RIGHT_W     (EPD_WIDTH - RIGHT_X - 10)

// Mini-month grid inside left column
#define GRID_X0     (LEFT_PAD)
#define GRID_Y0     (HEADER_H + 10)
#define CELL_W      60
#define CELL_H      36

// Day-of-week label row
#define DOW_ROW_Y   (GRID_Y0 + CELL_H)

static int colX(int dow) { return GRID_X0 + dow * CELL_W + CELL_W / 2; }

// ── Render callback ───────────────────────────────────────────────────────────
void renderCalendar(int bt, int bb) {

  // Short helpers that guard on band overlap
  auto R = [&](int x, int y, int w, int h, uint8_t c) {
    if (y < bb && y + h > bt) EPD_fillRect(x, y, w, h, c);
  };
  auto T = [&](int x, int y, const char* s, uint8_t c, int sc = 1) {
    if (y < bb && y + 8 * sc > bt) EPD_drawText(x, y, s, c, sc);
  };

  // ── Parse today from gDateStr ("Wednesday  March 05 2025") ──────────────
  char _dow[16] = "", _mon[16] = "";
  int  todayDay = 1, todayYear = 2024, todayMonth = 3;
  sscanf(gDateStr, "%s %s %d %d", _dow, _mon, &todayDay, &todayYear);

  const char* monNames[] = {
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
  };
  for (int m = 0; m < 12; m++) {
    if (strncmp(_mon, monNames[m], 3) == 0) { todayMonth = m + 1; break; }
  }

  // ── 1. RED HEADER ────────────────────────────────────────────────────────
  R(0, 0, EPD_WIDTH, HEADER_H, PIX_RED);

  // Month + year (scale 4 = 32 px tall)
  {
    char header[32];
    snprintf(header, sizeof(header), "%s %d", _mon, todayYear);
    for (int i = 0; header[i]; i++)
      if (header[i] >= 'a' && header[i] <= 'z') header[i] -= 32;
    T(20, 16, header, PIX_WHITE, 4);
  }

  // Day-of-week (scale 2)
  {
    char dowUp[16];
    strncpy(dowUp, _dow, sizeof(dowUp) - 1);
    dowUp[sizeof(dowUp) - 1] = 0;
    for (int i = 0; dowUp[i]; i++)
      if (dowUp[i] >= 'a' && dowUp[i] <= 'z') dowUp[i] -= 32;
    T(20, 56, dowUp, PIX_WHITE, 2);
  }

  // Time (top-right, scale 3)
  T(EPD_WIDTH - 260, 24, gTimeStr, PIX_WHITE, 3);

  // Header bottom border
  R(0, HEADER_H, EPD_WIDTH, 2, PIX_BLACK);

  // ── 2. MINI MONTH GRID ───────────────────────────────────────────────────
  // Day-of-week header bar
  R(GRID_X0, GRID_Y0, LEFT_W - 2 * LEFT_PAD, CELL_H, PIX_BLACK);
  const char* dowLabels[] = {"SU","MO","TU","WE","TH","FR","SA"};
  for (int d = 0; d < 7; d++) {
    T(colX(d) - 8, GRID_Y0 + 11, dowLabels[d], PIX_WHITE, 1);
  }

  int fdow   = firstDayOfWeek(todayYear, todayMonth);
  int dimLen = daysInMonth(todayYear, todayMonth);

  // Build bitmask of days that have events this month
  uint32_t eventDays = 0;
  char curAbbr[4] = { _mon[0], _mon[1], _mon[2], 0 };
  for (int i = 0; i < gEventCount; i++) {
    int  eday = 0;
    char emon[8] = "";
    sscanf(gEvents[i].dateStr + 4, "%s %d", emon, &eday);
    if (strncmp(emon, curAbbr, 3) == 0 && eday >= 1 && eday <= 31)
      eventDays |= (1u << eday);
  }

  for (int day = 1; day <= dimLen; day++) {
    int slot    = fdow + day - 1;
    int col     = slot % 7;
    int row     = slot / 7;
    int cellTop = DOW_ROW_Y + row * CELL_H;
    int cx      = colX(col);
    bool isToday = (day == todayDay);

    // Highlight today in red
    if (isToday)
      R(GRID_X0 + col * CELL_W, cellTop, CELL_W, CELL_H, PIX_RED);

    char dStr[4];
    snprintf(dStr, sizeof(dStr), "%d", day);
    int tx = cx - (strlen(dStr) == 1 ? 4 : 8);
    T(tx, cellTop + 12, dStr, isToday ? PIX_WHITE : PIX_BLACK, 1);

    // Small event dot
    if (!isToday && (eventDays & (1u << day)))
      R(cx - 2, cellTop + CELL_H - 6, 4, 4, PIX_RED);
  }

  // ── 3. TASKS SECTION ─────────────────────────────────────────────────────
  int usedRows = (fdow + dimLen - 1) / 7 + 1;
  int taskDivY = DOW_ROW_Y + usedRows * CELL_H + 8;

  // Divider line
  R(GRID_X0, taskDivY, LEFT_W - 2 * LEFT_PAD, 1, PIX_BLACK);

  int tasksY = taskDivY + 8;
  // TASKS header bar
  R(GRID_X0, tasksY, LEFT_W - 2 * LEFT_PAD, 22, PIX_YELLOW);
  T(GRID_X0 + 6, tasksY + 5, "TASKS", PIX_BLACK, 1);

  int tItemY = tasksY + 30;
  for (int i = 0; i < gTaskCount && i < 5 && tItemY + 36 < FOOTER_Y; i++) {
    // Checkbox
    R(GRID_X0 + 2, tItemY,      12, 12, PIX_BLACK);
    R(GRID_X0 + 3, tItemY + 1,  10, 10, PIX_WHITE);

    char buf[28];
    strncpy(buf, gTasks[i].title, 27);
    buf[27] = 0;
    T(GRID_X0 + 18, tItemY,      buf,               PIX_BLACK, 1);
    T(GRID_X0 + 18, tItemY + 13, gTasks[i].dateStr, PIX_BLACK, 1);

    tItemY += 36;
    R(GRID_X0, tItemY - 4, LEFT_W - 2 * LEFT_PAD, 1, PIX_BLACK);
  }

  if (gTaskCount == 0)
    T(GRID_X0 + 6, tasksY + 30, "No tasks due", PIX_BLACK, 1);

  // ── 4. VERTICAL DIVIDER ──────────────────────────────────────────────────
  R(LEFT_W, HEADER_H + 2, 3, FOOTER_Y - HEADER_H - 2, PIX_BLACK);

  // ── 5. AGENDA PANEL ──────────────────────────────────────────────────────
  int agendaHeaderY = HEADER_H + 10;
  R(RIGHT_X, agendaHeaderY, RIGHT_W, 24, PIX_BLACK);
  T(RIGHT_X + 10, agendaHeaderY + 6, "UPCOMING  7 DAYS", PIX_WHITE, 1);

  if (gEventCount == 0) {
    T(RIGHT_X + 30, agendaHeaderY + 50, "No upcoming events", PIX_BLACK, 2);
  } else {
    int evY        = agendaHeaderY + 30;
    const int EV_H = 76;   // taller cards to fill the bigger panel

    for (int i = 0; i < gEventCount && evY + EV_H < FOOTER_Y; i++) {
      int  eday = 0;
      char emon[8] = "";
      sscanf(gEvents[i].dateStr + 4, "%s %d", emon, &eday);
      bool isToday = (strncmp(emon, curAbbr, 3) == 0 && eday == todayDay);

      // Coloured left edge bar
      R(RIGHT_X, evY, 5, EV_H - 5, isToday ? PIX_RED : PIX_BLACK);

      int labelX = RIGHT_X + 14;

      // Date or "TODAY"
      if (isToday)
        T(labelX, evY + 4,  "TODAY", PIX_RED, 1);
      else
        T(labelX, evY + 4,  gEvents[i].dateStr, PIX_BLACK, 1);

      // Title (scale 2 — 16 px tall characters)
      char titleBuf[42];
      int  maxChars = (RIGHT_W - 20) / 17;   // ~17px per char at scale 2
      if (maxChars > 41) maxChars = 41;
      strncpy(titleBuf, gEvents[i].title, maxChars);
      titleBuf[maxChars] = 0;
      T(labelX, evY + 18, titleBuf, PIX_BLACK, 2);

      // Time
      T(labelX, evY + 52, gEvents[i].timeStr, PIX_BLACK, 1);

      evY += EV_H;
      R(RIGHT_X, evY - 3, RIGHT_W, 1, PIX_BLACK);
    }
  }

  // ── 6. YELLOW FOOTER ─────────────────────────────────────────────────────
  R(0, FOOTER_Y, EPD_WIDTH, FOOTER_H, PIX_YELLOW);
  char footer[48];
  snprintf(footer, sizeof(footer), "Updated: %s", gTimeStr);
  T(20, FOOTER_Y + 10, footer, PIX_BLACK, 1);
  T(EPD_WIDTH - 200, FOOTER_Y + 10, "Next: 15 min", PIX_BLACK, 1);
}

// ── WiFi ──────────────────────────────────────────────────────────────────────
bool connectWifi() {
  Serial.printf("WiFi: connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries++ < 30) {
    for (int t = 0; t < 10; t++) {
      ledBlinkTick(250);
      delay(50);
    }
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi: FAILED");
    return false;
  }
  Serial.printf("WiFi: connected, IP=%s\n", WiFi.localIP().toString().c_str());
  return true;
}

// ── setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== E-Ink Calendar (Spectra 6  13.3\") ===");

  pinMode(PIN_LED, OUTPUT);
  LED_OFF();
  pinMode(BTN_READ, INPUT_PULLUP);

  esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
  bool wokeFromButton = (wakeup_reason == ESP_SLEEP_WAKEUP_EXT1);
  bool wokeFromTimer  = (wakeup_reason == ESP_SLEEP_WAKEUP_TIMER);
  bool coldBoot       = (wakeup_reason == ESP_SLEEP_WAKEUP_UNDEFINED);

  Serial.print("Wake reason: "); Serial.println(wakeup_reason);

  // Debounce button wakeup
  if (wokeFromButton) {
    Serial.println("EXT1 wakeup — waiting for button release...");
    uint32_t t0 = millis();
    while (digitalRead(BTN_REFRESH) == HIGH) {
      if (millis() - t0 > 3000) { Serial.println("Warning: held >3s"); break; }
      delay(10);
    }
    delay(50);
    Serial.println("Button released");
  }

  if (wokeFromButton)  Serial.println("Manual refresh triggered");
  else if (wokeFromTimer) Serial.println("Timer refresh");
  else if (coldBoot)   Serial.println("Cold boot");

  // ── Startup blink, then LED solid during sync ─────────────────────────────
  ledBlink(2, 100, 100);
  LED_ON();

  // ── Display init ─────────────────────────────────────────────────────────
  EPD_init();

  // ── WiFi ─────────────────────────────────────────────────────────────────
  if (!connectWifi()) {
    gEventCount = 0;
    strncpy(gDateStr, "WiFi failed", sizeof(gDateStr));
    LED_OFF();
    ledBlink(3, 300, 200);
    EPD_flush(renderCalendar);
    EPD_sleep();
    goto SLEEP;
  }

  // ── Google Calendar ───────────────────────────────────────────────────────
  LED_ON();
  if (!gcal_init()) {
    strncpy(gDateStr, "Auth failed", sizeof(gDateStr));
    LED_OFF();
    ledBlink(3, 300, 200);
    EPD_flush(renderCalendar);
    EPD_sleep();
    WiFi.disconnect(true);
    goto SLEEP;
  }

  // ── Fetch ─────────────────────────────────────────────────────────────────
  gcal_getNow(gDateStr, sizeof(gDateStr), gTimeStr, sizeof(gTimeStr));
  gEventCount = gcal_getEvents(gEvents, GCAL_MAX_EVENTS);
  gTaskCount  = gcal_getTasks(gTasks,  GCAL_MAX_EVENTS);

  // ── Render ────────────────────────────────────────────────────────────────
  EPD_flush(renderCalendar);
  EPD_sleep();

  WiFi.disconnect(true);

  LED_OFF();
  ledBlink(1, 500, 0);
  LED_OFF();
  Serial.println("LED: sync complete");

SLEEP:
  Serial.println("Entering deep sleep...");
  LED_OFF();

  rtc_gpio_init(GPIO_NUM_32);
  rtc_gpio_set_direction(GPIO_NUM_32, RTC_GPIO_MODE_INPUT_ONLY);
  rtc_gpio_pullup_dis(GPIO_NUM_32);
  rtc_gpio_pulldown_en(GPIO_NUM_32);

  esp_sleep_enable_ext1_wakeup((1ULL << BTN_REFRESH), ESP_EXT1_WAKEUP_ANY_HIGH);
  esp_sleep_enable_timer_wakeup((uint64_t)REFRESH_MINUTES * 60ULL * 1000000ULL);

  Serial.println("Good night.");
  Serial.flush();
  esp_deep_sleep_start();
}

void loop() {
  // Never reached — deep sleep reboots on each wake
}
