#!/usr/bin/env python3
"""
video2cdg: convert video to CD+G graphics

Usage:
    video2cdg <input.mp4> [-v] [--frames-dir <dir>] [--monitor <path/to.mp4>] [--mono]

Options:
    --frames-dir <dir>        Tempdir to store intermediary frames in [default: ./frames]
    --monitor <path/to.mp4>   Create a 'monitor' video from output frame data
    -v --verbose              Show ffmpeg transcode output

    --mono                    Use strict black/white for video instead of color

"""

import ffmpeg
import docopt
import PIL
import os
from pathlib import Path

from libcdg import libcdg

# SECONDS_PER_FRAME = 4.0
SECONDS_PER_FRAME = 2.79

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

# 1. convert input with ffmpeg

input = ffmpeg.input(infile)

# reduce framerate to CD+G full update speed
in_v = input.video.filter("fps", fps=(1 / SECONDS_PER_FRAME))


if ARGS["--mono"]:
    # == pure mono ==
    scaled = in_v.filter("scale", width=288, height=192)

    # force black or white
    black = ffmpeg.input("color=Black:s=288x192", f="lavfi")
    white = ffmpeg.input("color=White:s=288x192", f="lavfi")
    gray = ffmpeg.input("color=DarkGray:s=288x192", f="lavfi")

    final = ffmpeg.filter([scaled, gray, black, white], "threshold")

else: # --color
    # == scale then crunch ==
    scaled = in_v.filter("scale", width=288, height=192).split()

    # crunch colors to 16 colors per frame
    palette = scaled[0].filter("palettegen", stats_mode="single",
                            max_colors=16, reserve_transparent=0)
    crunched = ffmpeg.filter([scaled[1], palette], "paletteuse", new=1)

    # force 4-4-4 color depth
    final = crunched.filter("format", pix_fmts="rgb444be")


# # == crunch then scale ==
# in_vs = in_v.split()

# palette = (
#     in_vs[0]
#     # crunch colors to 16 colors per frame
#     .filter("palettegen", stats_mode="single", max_colors=16, reserve_transparent=0)
# )
# crunched = ffmpeg.filter([in_vs[1], palette], "paletteuse", new=1)

# scaled = in_v.filter("scale", width=288, height=192)

# # force 4-4-4 color depth
# final = scaled.filter("format", pix_fmts="rgb444be")



# 2. output frames as separate images
print(f":: Creating frames under {framedir}...")
os.makedirs(framedir, exist_ok=True)
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

# 3. convert to CDG
print(f":: Converting frames to CDG packets...")
packets = []

frames = os.listdir(framedir)
frames.sort()
for f in frames:
    # extract palette
    # partition to cells
    # encode cells
    # fill remaining time
    file = f"{framedir}/{f}"

    # print(file)
    fpk = libcdg.image_to_packets(file)
    packets += fpk


# 4. output .cdg + .mp3
print(f":: Writing output to {out}.cdg/.mp3...")
with open(f"{out}.cdg", "wb") as outfile:
    outfile.writelines(packets)

input.audio.output(f"{out}.mp3").overwrite_output().run(quiet=quiet)

print(f":: Done!")
