#!/usr/bin/python
# -*- coding:utf-8 -*-
#Editted from the official python example demo for spectra from wavesharewiki
#Added the image browser to pick the custom image and editted the loading section
import sys
import os

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import epd13in3E
import time
from PIL import Image, ImageDraw, ImageFont

from PyQt5.QtWidgets import QApplication, QFileDialog


def browse_image_qt():
    """
    Opens a native file-picker dialog using PyQt5.
    Returns the selected file path, or None if cancelled.
    """
    app = QApplication.instance() or QApplication(sys.argv)

    path, _ = QFileDialog.getOpenFileName(
        parent=None,
        caption="Select an image for the e-Paper display",
        directory=picdir if os.path.isdir(picdir) else os.path.expanduser("~"),
        filter="Images (*.bmp *.png *.jpg *.jpeg);;All Files (*)"
    )

    return path if path else None


def load_and_fit_image(path, width, height):
    """
    Open any supported image, convert to RGB, resize to fit the display
    while preserving aspect ratio, and centre on a white canvas.
    """
    img = Image.open(path).convert("RGB")
    img.thumbnail((width, height), Image.LANCZOS)

    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    x = (width  - img.width)  // 2
    y = (height - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


# ── MAIN ─────────────────────────────────────────────────────────────────────

print("13.3inch e-paper (E) Demo...")

epd = epd13in3E.EPD()

try:
    epd.Init()
    print("Clearing display...")
    epd.Clear()

    font24 = ImageFont.truetype(os.path.join(picdir, "Font.ttc"), 24)
    font18 = ImageFont.truetype(os.path.join(picdir, "Font.ttc"), 18)
    font40 = ImageFont.truetype(os.path.join(picdir, "Font.ttc"), 40)
    font100 = ImageFont.truetype(os.path.join(picdir, "Font.ttc"), 100)

    # ── Step 1: drawing demo ──────────────────────────────────────────────────
    print("1. Drawing on the image...")
    Himage = Image.new("RGB", (epd.width, epd.height), epd.WHITE)
    draw   = ImageDraw.Draw(Himage)
    draw.text((5,   0), "hello world",           font=font18, fill=epd.RED)
    draw.text((5,  20), "13.3 inch e-Paper (E)", font=font24, fill=epd.YELLOW)
    draw.text((300,  500), u"Loading.",              font=font100, fill=epd.GREEN)
    draw.text((400,  600), u"Loading..",              font=font100, fill=epd.BLUE)
    draw.text((500, 700), u"Loading...",              font=font100, fill=epd.BLACK)
    draw.line((5, 170, 80, 245),        fill=epd.BLUE)
    draw.line((80, 170, 5, 245),        fill=epd.YELLOW)
    draw.rectangle((5,  170, 80,  245), outline=epd.BLACK)
    draw.rectangle((90, 170, 165, 245), fill=epd.GREEN)
    draw.arc((5,  250, 80,  325), 0, 360, fill=epd.RED)
    draw.chord((90, 250, 165, 325), 0, 360, fill=epd.YELLOW)
    epd.display(epd.getbuffer(Himage))
    time.sleep(3)

    # ── Step 2: user picks an image via Qt file dialog ────────────────────────
    print("2. Opening image picker...")
    selected = browse_image_qt()

    if selected:
        print(f"   Selected: {selected}")
        Himage = load_and_fit_image(selected, epd.width, epd.height)
        epd.display(epd.getbuffer(Himage))
        time.sleep(5)
    else:
        print("   No image selected, skipping.")

    # ── Clean up ──────────────────────────────────────────────────────────────
    #print("Clearing display...")
    #epd.Clear()
    print("Going to sleep...")
    epd.sleep()

except Exception as e:
    print(f"Error: {e}")
    print("Going to sleep...")
    epd.sleep()
