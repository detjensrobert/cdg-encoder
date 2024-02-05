#!/usr/bin/env python3

import os
import sys

from libcdg import libcdg

FRAMEDIR = "./frames"

if len(sys.argv) > 1:
    out = open(sys.argv[1], 'wb')
else:
    out = sys.stdout.buffer

# 3. convert to CDG
print(f":: Converting frames to CDG packets...")
frames = os.listdir(FRAMEDIR)
frames.sort()
for framefile in [f"{FRAMEDIR}/{f}" for f in frames]:
    # extract palette
    # partition to cells
    # encode cells
    # fill remaining time

    print(framefile)

    packets = libcdg.image_to_packets(framefile)

    # print(packets)
    out.writelines(packets)
