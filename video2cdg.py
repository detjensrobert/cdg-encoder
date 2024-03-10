#!/usr/bin/env python3
"""
video2cdg: convert video to CD+G graphics

Usage:
    video2cdg <input.mp4> [--output <output.cdg>] [-v] [--mono] [--palette <image>] [--monitor <path/to.mp4>]

Options:
    -o, --output <output.cdg>   Target filename. Will also create output.mp3. Default: input filename
    -v, --verbose               Show ffmpeg transcode output
    --palette <image>           Palette to use instead of generating one from input
    --mono                      Use 1-bit black/white for video instead of color
"""

import os
from pathlib import Path

import docopt
import ffmpeg

from libcdg import libcdg
from libcdg.constants import DISPLAY_HEIGHT, DISPLAY_WIDTH

import logging
logging.basicConfig(level="DEBUG")

# === STEPS ===
# 1. transcode input file to 288x192 (usable resolution of CD+G)
# 2. output as bitmaps
# 3. convert bitmaps to CDG video packets
# 4. output as .mp3 + .cdg file pair

ARGS = docopt.docopt(__doc__)

infile = ARGS["<input.mp4>"]
monfile = ARGS["--monitor"]
palette = ARGS["--palette"]
quiet = not ARGS["--verbose"]
mono = ARGS["--mono"]

# remove ext
outpath = Path(ARGS["--output"] or infile)
out = outpath.parent / outpath.stem

if not quiet:
    print(f"args: {ARGS}")



cdg = libcdg.Video(infile, palette=palette, mono=mono, quiet=quiet)
cdg.encode().save(out, overwrite=True)


# # 4. output .cdg + .mp3
# print(f":: Writing output to {out}.cdg/.mp3...")
# with open(f"{out}.cdg", "wb") as outfile:
#     outfile.writelines(packets)

# input.audio.output(f"{out}.mp3").overwrite_output().run(quiet=quiet)

# print(f":: Done!")
