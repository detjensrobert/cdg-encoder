#!/usr/bin/env python3
"""
video2cdg: convert video to CD+G graphics

Usage:
    video2cdg INPUT [-v] [--frames-dir DIR] [--monitor MON]

Options:
    --frames-dir DIR    Tempdir to store intermediary frames in [default: ./frames]
    --monitor MON       Create a 'monitor' video MON from output frame data
    -v --verbose        Show ffmpeg's output

Generates

"""

import ffmpeg
import docopt
import PIL
import os

import libcdg

SECONDS_PER_FRAME = 4.0

# === STEPS ===
# 1. transcode input file to 288x192 (usable resolution of CD+G)
# 2. output as bitmaps
# 3. convert bitmaps to CDG video packets
# 4. output as .mp3 + .cdg file pair

ARGS = docopt.docopt(__doc__)

infile = ARGS["INPUT"]
framedir = ARGS["--frames-dir"]
monfile = ARGS["--monitor"]
quiet = not ARGS["--verbose"]

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
in_v = input["v"].filter("fps", fps=(1 / SECONDS_PER_FRAME))


# scale then crunch
scaled = in_v.filter("scale", width=288, height=192).split()

# crunch colors to 16 colors per frame
palette = scaled[0].filter("palettegen", stats_mode="single",
                           max_colors=16, reserve_transparent=0)
crunched = ffmpeg.filter([scaled[1], palette], "paletteuse", new=1)

# force 4-4-4 color depth
final = crunched.filter("format", pix_fmts="rgb444be")


# # crunch then scale
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


# 'monitor' video to examine what frames would be
if monfile:
    print(f":: Creating monitor file {monfile}...")
    (
        ffmpeg.concat(final, input["a"], v=1, a=1)
        .output(monfile)
        .overwrite_output()
        .run(quiet=quiet)
    )


# 2. output frames as separate images
print(f":: Creating frames under {framedir}...")
os.makedirs(framedir, exist_ok=True)
(final.output(f"{framedir}/%05d.png").run(quiet=quiet))


# 3. convert to CDG
print(f":: Converting frames to CDG packets...")
for framefile in [f"{framedir}/{f}" for f in os.listdir(framedir)]:
    # extract palette
    # partition to cells
    # encode cells
    # fill remaining time

    print(framefile)
    libcdg.packets_from_img(framefile)

    exit()
