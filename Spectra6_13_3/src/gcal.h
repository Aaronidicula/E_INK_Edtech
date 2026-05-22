#pragma once
#include <Arduino.h>

// Maximum events fetched per refresh
#define GCAL_MAX_EVENTS 8

struct CalEvent {
  char title[64];
  char timeStr[12];   // e.g. "9:00 AM"
  char dateStr[24];   // e.g. "Wed Mar 11"
  bool isAllDay;
};

// Call once after WiFi is connected
// Returns true if token was obtained successfully
bool gcal_init();

// Fetch upcoming calendar events
// Returns number of events fetched (0 on failure)
int gcal_getEvents(CalEvent* events, int maxEvents);

// Fetch incomplete tasks from Google Tasks default list
// Returns number of tasks fetched (0 on failure)
int gcal_getTasks(CalEvent* events, int maxEvents);

// Get current time as formatted strings (uses NTP)
void gcal_getNow(char* dateBuf, int dateLen, char* timeBuf, int timeLen);
