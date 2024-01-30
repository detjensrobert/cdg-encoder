#!/usr/bin/env python3
"""
video2cdg: convert video to CD+G graphics

Usage:
    video2cdg INPUT [-v] [--frames-dir <dir>] [--monitor <path/to.mp4>]

Options:
    --frames-dir <dir>        Tempdir to store intermediary frames in [default: ./frames]
    --monitor <path/to.mp4>   Create a 'monitor' video from output frame data
    -v --verbose              Show ffmpeg transcode output

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
in_v = input.video.filter("fps", fps=(1 / SECONDS_PER_FRAME))


# # == scale then crunch ==
# scaled = in_v.filter("scale", width=288, height=192).split()

# # crunch colors to 16 colors per frame
# palette = scaled[0].filter("palettegen", stats_mode="single",
#                            max_colors=16, reserve_transparent=0)
# crunched = ffmpeg.filter([scaled[1], palette], "paletteuse", new=1)

# # force 4-4-4 color depth
# final = crunched.filter("format", pix_fmts="rgb444be")


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


# == pure mono ==
scaled = in_v.filter("scale", width=288, height=192)

# # crunch colors to 16 colors per frame
# palette = scaled[0].filter("palettegen", stats_mode="single",
#                            max_colors=16, reserve_transparent=0)
# crunched = ffmpeg.filter([scaled[1], palette], "paletteuse", new=1)

# # force 4-4-4 color depth
# final = crunched.filter("format", pix_fmts="rgb444be")
black = ffmpeg.input('color=Black:s=288x192', f='lavfi')
white = ffmpeg.input('color=White:s=288x192', f='lavfi')
gray = ffmpeg.input('color=DarkGray:s=288x192', f='lavfi')

final = ffmpeg.filter([scaled, gray, black, white], "threshold")




# 2. output frames as separate images
print(f":: Creating frames under {framedir}...")
os.makedirs(framedir, exist_ok=True)
print(final.output("test").compile())
final.output(f"{framedir}/%05d.bmp").run(quiet=quiet)


# 'monitor' video of converted frames
if monfile:
    print(f":: Creating monitor file {monfile}...")
    frames = ffmpeg.input(f"{framedir}/*.bmp", pattern_type='glob', framerate=(1 / SECONDS_PER_FRAME))
    (
        ffmpeg.concat(frames, input.audio, v=1, a=1)
        .output(monfile)
        .overwrite_output()
        .run(quiet=quiet)
    )

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
