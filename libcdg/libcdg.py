import itertools
import os
import queue
import subprocess
import tempfile
from pathlib import Path

import ffmpeg
from PIL import Image
import numpy as np

from . import instructions
from .constants import *
from .helpers import groups_of, rgb_to_444, set_palette


class Video:
    FRAME_RATE = 30
    PACKETS_PER_FRAME = PACKETS_PER_SECOND / FRAME_RATE

    def __init__(self, source: str | os.PathLike, mono=False, quiet=True) -> None:
        self.source = str(source)
        self.mono = mono
        self.quiet = quiet

        self.current_frame = 0
        self.packets: list[bytes] = []

        # do this one at init
        self.palette = self.calc_palette()

    def calc_palette(self) -> list[tuple[int, int, int]]:
        scaled = (
            ffmpeg.input(self.source)
            # ensure 30fps to better match packet rate
            .filter("fps", fps=30)
            # scale to CDG canvas size
            .filter("scale", width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
            # annoying
        )

        if self.mono:  # force 1-bit black/white?
            black = ffmpeg.input("color=Black:s=288x192", f="lavfi")
            white = ffmpeg.input("color=White:s=288x192", f="lavfi")
            gray = ffmpeg.input("color=DarkGray:s=288x192", f="lavfi")

            scaled = ffmpeg.filter([scaled, gray, black, white], "threshold")

        # save scaling pipeline for output later
        self.scaled = scaled

        # crunch to 16 colors (global palette)
        palettegen = scaled.filter("palettegen", max_colors=16, reserve_transparent=0)
        # TODO remove the other 256-16 colors from output png

        # save palette to tempfile for later use
        self.palette_file = tempfile.NamedTemporaryFile(
            prefix="libcdg_pallette_", suffix=".png"
        )
        (
            palettegen.output(self.palette_file.name, vframes=1)
            .global_args("-hide_banner")
            .overwrite_output()
            .run(quiet=self.quiet)
        )

        with Image.open(self.palette_file) as palimg:
            palimg = palimg.convert("P")

            palette = list(groups_of(palimg.getpalette(), 3))
            # remove duplicates
            palette = list(set([tuple(rgb) for rgb in palette]))

            assert len(palette) <= 16, "too many colors in palette image!"
            return palette

    def start_ffmpeg(self) -> subprocess.Popen:
        "Captures output frames from ffmpeg over pipe"

        # from pallete gen
        palette = ffmpeg.input(filename=self.palette_file.name)

        ffprocess = (
            ffmpeg.filter([self.scaled, palette], "paletteuse")
            .output("pipe:", format="rawvideo", pix_fmt="rgb24")
            .global_args("-hide_banner")
            .run_async(pipe_stdout=True)
        )

        return ffprocess

    def encode(self):
        "Encode frames"

        FRAME_SIZE = DISPLAY_WIDTH * DISPLAY_HEIGHT * 3

        # set palette first
        self.packets += set_palette(self.palette)

        # set initial fg/bg
        # set canvas and border color
        self.packets += [instructions.preset_memory(0), instructions.preset_border(1)]

        # blank initial frame to match fill above
        prev = Image.new("P", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 0)
        prev.putpalette(itertools.chain(*self.palette))

        with self.start_ffmpeg() as ffpipe:
            # get next frame from ffmpeg subprocess until exhausted
            while len(framebytes := ffpipe.stdout.read(FRAME_SIZE)) > 0:
                self.current_frame += 1

                print(f"frame {self.current_frame} ")
                # calculate differences from prev frame

                frame = Image.frombytes(
                    "RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), framebytes
                )
                # should already be using this palette but make sure
                frame.quantize(palette=prev, dither=Image.Dither.NONE)

                deltas = self.calc_deltas(prev, frame)

                # set blocks with largest deltas until we run out of packets for this frame
                while len(self.packets) < self.current_frame * self.PACKETS_PER_FRAME:
                    #

                    self.packets += [b"x"]
                    pass

                return  # for now

    def calc_deltas(self, prev: Image.Image, next: Image.Image) -> queue.PriorityQueue:
        "calculate list of blocks to change in order of largest difference"

        # array shape: 16x48 (canvas blocks) x 12x6 (block pixels)
        prev_blocks = image_to_blocks(prev)
        next_blocks = image_to_blocks(next)

        deltas = queue.PriorityQueue()

        # count number of differing pixels
        diff = lambda a, b: len([True for ai, bi in zip(a, b) if ai != bi])

        # for pblk, nblk in zip(
        #     enumerate()
        # )


def image_to_blocks(image: Image.Image) -> np.array:
    "converts `image` data to (numpy) array of block tiles"
    # adapted from: https://stackoverflow.com/a/16858283

    arr = np.array(image)

    h, w = arr.shape
    assert h % BLOCK_HEIGHT == 0, f"{h} rows is not evenly divisible by {BLOCK_HEIGHT}"
    assert w % BLOCK_WIDTH == 0, f"{w} cols is not evenly divisible by {BLOCK_WIDTH}"

    # chunked, but one dimensional
    chunks = (
        arr.reshape(h // BLOCK_HEIGHT, BLOCK_HEIGHT, -1, BLOCK_WIDTH)
        .swapaxes(1, 2)
        .reshape(-1, BLOCK_HEIGHT, BLOCK_WIDTH)
    )
    # split chunk list back into 2d (split into X cols)
    return np.split(chunks, h / BLOCK_HEIGHT)
