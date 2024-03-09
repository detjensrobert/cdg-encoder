#!/usr/bin/env python3
"""
video2cdg: convert video to CD+G graphics

Usage:
    video2cdg <input.mp4> [-v] [--frames-dir <dir>] [--monitor <path/to.mp4>] [--mono] [--frame-palettes]

Options:
    --frames-dir <dir>        Tempdir to store intermediary frames in [default: ./frames]
    --monitor <path/to.mp4>   Create a 'monitor' video from output frame data (before CDG conversion)
    -v, --verbose             Show ffmpeg transcode output
    --mono                    Use 1-bit black/white for video instead of color
    --frame-palettes          Use a new palette for each frame instead of one for the whole video
"""

import os
from pathlib import Path

import docopt
import ffmpeg

from libcdg import helpers
from libcdg.constants import DISPLAY_HEIGHT, DISPLAY_WIDTH

# SECONDS_PER_FRAME = 4.0
SECONDS_PER_FRAME = 2.79
PALETTE_FILE = "_palette.png"

# === STEPS ===
# 1. transcode input file to 288x192 (usable resolution of CD+G)
# 2. output as bitmaps
# 3. convert bitmaps to CDG video packets
# 4. output as .mp3 + .cdg file pair

ARGS = docopt.docopt(__doc__)

infile = ARGS["<input.mp4>"]
framedir = ARGS["--frames-dir"]
monfile = ARGS["--monitor"]
quiet = not ARGS["--verbose"]

out = Path(infile).stem

if not quiet:
    print(f"args: {ARGS}")


# check dir
if os.path.exists(framedir) and len(os.listdir(framedir)) > 0:
    print("ERR:")
    print(f"ERR: frames dir '{framedir}' is not empty!")
    print("ERR:")
    exit(1)
# make sure it exists
os.makedirs(framedir, exist_ok=True)


# 1. convert input with ffmpeg

input = ffmpeg.input(infile)

# reduce framerate to CD+G full update speed, resolution, and bit depth
# fmt: off
# hands off my line breaks, black!
scaled = (
    input.video
    .filter("fps", fps=(1 / SECONDS_PER_FRAME))
    .filter("scale", width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
    # .filter("format", pix_fmts="rgb444be")
)
# fmt: on

if ARGS["--mono"]:  # force 1-bit black/white
    black = ffmpeg.input("color=Black:s=288x192", f="lavfi")
    white = ffmpeg.input("color=White:s=288x192", f="lavfi")
    gray = ffmpeg.input("color=DarkGray:s=288x192", f="lavfi")

    scaled = ffmpeg.filter([scaled, gray, black, white], "threshold")


print(f":: Generating palette...")
# crunch to 16 colors (global palette)
palettegen = (
    scaled
    # crunch to 16 colors (global palette)
    .filter("palettegen", max_colors=16, reserve_transparent=0)
    # force 4-4-4 color depth for palette
    # .filter("format", pix_fmts="rgb444be")
)
# TODO remove the other 256-16 colors from output png
# write out palette for later use
palettegen.output(f"{framedir}/{PALETTE_FILE}").overwrite_output().run(quiet=quiet)

# crunch according to palette
palette = ffmpeg.input(f"{framedir}/{PALETTE_FILE}")
final = ffmpeg.filter([scaled, palette], "paletteuse")


# 2. output frames as separate images
print(f":: Creating frames under {framedir}...")
final.output(f"{framedir}/%05d.png").run(quiet=quiet)


# 'monitor' video of converted frames
if monfile:
    print(f":: Creating monitor file {monfile}...")
    frames = ffmpeg.input(
        f"{framedir}/*.png", pattern_type="glob", framerate=(1 / SECONDS_PER_FRAME)
    )
    (
        ffmpeg.concat(frames, input.audio, v=1, a=1)
        .output(monfile)
        .overwrite_output()
        .run(quiet=quiet)
    )


# 3. convert frames to CDG
print(f":: Converting frames to CDG packets...")
packets = []

palettefile = f"{framedir}/{PALETTE_FILE}"

frames = os.listdir(framedir)
frames.remove(PALETTE_FILE)
frames.sort()

for f in frames:
    file = f"{framedir}/{f}"
    packets += helpers.image_to_packets(file, palettefile=(not ARGS["--frame-palettes"] and palettefile))


# 4. output .cdg + .mp3
print(f":: Writing output to {out}.cdg/.mp3...")
with open(f"{out}.cdg", "wb") as outfile:
    outfile.writelines(packets)

input.audio.output(f"{out}.mp3").overwrite_output().run(quiet=quiet)

print(f":: Done!")
