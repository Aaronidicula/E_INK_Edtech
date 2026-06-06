#!/usr/bin/python
# -*- coding:utf-8 -*-
"""
gcal_setup.py
─────────────
Run this ONCE on the Raspberry Pi (with a monitor/keyboard, or via SSH with
port-forwarding) to authorise Google Calendar + Tasks access.

After authorisation succeeds a token.pickle file is saved next to this script.
calendar_weekly_art.py reads that token on every refresh — no browser needed
after this one-time step.

Prerequisites
─────────────
1.  Install the Google client libraries:
      pip3 install --break-system-packages google-api-python-client \
                   google-auth-httplib2 google-auth-oauthlib

2.  Create a Google Cloud project and enable the Calendar API + Tasks API:
      https://console.cloud.google.com/

3.  Create an OAuth2 Desktop-app credential and download credentials.json.
    Place credentials.json in the same folder as this script.

Usage
─────
  python3 gcal_setup.py

    Opens a browser (or prints a URL to open on another device).
    After you grant access, token.pickle is written and the script
    prints a summary of your calendars and task lists.
"""

import os
import sys
import pickle

SCRIPT_DIR       = os.path.dirname(os.path.realpath(__file__))
CREDENTIALS_PATH = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_PATH       = os.path.join(SCRIPT_DIR, "token.pickle")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]


def authorise():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print(
            "\nERROR: Google client libraries not found.\n"
            "Install them with:\n\n"
            "  pip3 install --break-system-packages google-api-python-client "
            "google-auth-httplib2 google-auth-oauthlib\n"
        )
        sys.exit(1)

    if not os.path.exists(CREDENTIALS_PATH):
        print(
            f"\nERROR: credentials.json not found at:\n  {CREDENTIALS_PATH}\n\n"
            "Download it from Google Cloud Console:\n"
            "  https://console.cloud.google.com/apis/credentials\n"
            "  → Create credentials → OAuth client ID → Desktop app\n"
            "  → Download JSON → rename to credentials.json\n"
        )
        sys.exit(1)

    creds = None

    # Try to load an existing (possibly expired) token
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.valid:
        print("Token already valid — no re-authorisation needed.\n")
    else:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token…")
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            print("Starting OAuth2 flow…")
            flow  = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            # run_local_server opens a browser on the Pi.
            # If headless, use: run_console() instead.
            try:
                creds = flow.run_local_server(port=0)
            except Exception:
                print("Browser not available — switching to console flow.")
                creds = flow.run_console()

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
        print(f"Token saved to: {TOKEN_PATH}\n")

    return creds


def verify(creds):
    from googleapiclient.discovery import build

    print("=" * 55)
    print("  GOOGLE CALENDAR — available calendars")
    print("=" * 55)
    try:
        cal_svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        items   = cal_svc.calendarList().list().execute().get("items", [])
        for c in items:
            marker = " ← primary" if c.get("primary") else ""
            print(f"  ID: {c['id']}")
            print(f"      Name: {c.get('summary', '?')}{marker}")
    except Exception as e:
        print(f"  Calendar API error: {e}")

    print()
    print("=" * 55)
    print("  GOOGLE TASKS — available task lists")
    print("=" * 55)
    try:
        tsk_svc = build("tasks", "v1", credentials=creds, cache_discovery=False)
        items   = tsk_svc.tasklists().list().execute().get("items", [])
        for t in items:
            print(f"  ID: {t['id']}")
            print(f"      Name: {t.get('title', '?')}")
    except Exception as e:
        print(f"  Tasks API error: {e}")

    print()
    print("Setup complete!  You can now run:")
    print("  python3 calendar_weekly_art.py")


if __name__ == "__main__":
    creds = authorise()
    verify(creds)
