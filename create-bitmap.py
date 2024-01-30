#!/usr/bin/env python3

from PIL import Image, ImageOps
import sys, os
from itertools import takewhile

if len(sys.argv) != 2:
    print(f"usage: {__file__} <qr code to convert>")
    exit(1)

qr = Image.open(sys.argv[1])
qr = qr.convert("RGB")

## remove any padding around qr code
qr_i = ImageOps.invert(qr)
box = qr_i.getbbox()  # bbox works on black
contents = qr.crop(box)

# figure out how big image is
red = contents.getdata(band=0)
# qr code square is 7 'pixels'
square_len = len(list(takewhile(lambda p: p == 0, list(red))))
downscale_by = square_len // 7
print(f"resizing by 1/{downscale_by}x")

qr_pixels = contents.resize(
    (contents.width // downscale_by, contents.height // downscale_by),
    resample=Image.Resampling.NEAREST, # keep pixels crisp
)


qr_pixels.save("cropped.png")


bitmap_dir = os.mkdir("./bitmaps")
