from PIL import Image
import numpy as np

# Color palette for Spectra 6
COLOR_MAP = {
    (255, 255, 255): 0x0,  # White
    (0,   0,   0  ): 0x1,  # Black
    (255, 255, 0  ): 0x2,  # Yellow
    (255, 0,   0  ): 0x3,  # Red
    (0,   0,   255): 0x4,  # Blue
    (0,   128, 0  ): 0x5,  # Green
}

def nearest_color(pixel):
    r, g, b = pixel[:3]
    best = min(COLOR_MAP.keys(), key=lambda c: (c[0]-r)**2 + (c[1]-g)**2 + (c[2]-b)**2)
    return COLOR_MAP[best]

def convert_image(input_path, output_path, width=1200, height=1600):
    img = Image.open(input_path).convert("RGB")
    img = img.resize((width, height))
    pixels = np.array(img)

    hex_data = []
    for row in pixels:
        for i in range(0, len(row), 2):
            high = nearest_color(row[i])
            low  = nearest_color(row[i+1]) if i+1 < len(row) else 0
            hex_data.append((high << 4) | low)

    # Write as C header
    with open(output_path, 'w') as f:
        f.write('#pragma once\n')
        f.write('#include <pgmspace.h>\n\n')
        f.write(f'// {width}x{height} image, 4bpp Spectra6\n')
        f.write(f'#define MY_IMAGE_W {width}\n')
        f.write(f'#define MY_IMAGE_H {height}\n\n')
        f.write('const unsigned char MY_IMAGE[] PROGMEM = {\n')
        for i, byte in enumerate(hex_data):
            if i % 16 == 0:
                f.write('    ')
            f.write(f'0x{byte:02X},')
            if i % 16 == 15:
                f.write('\n')
        f.write('\n};\n')

    print(f"Done! {len(hex_data)} bytes written to {output_path}")

convert_image("your_image.jpg", "MyImage.h")