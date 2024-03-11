import itertools
import logging
import os
import queue
import subprocess
import sys
import tempfile

import ffmpeg
import numpy as np
from PIL import Image

from . import instructions
from .constants import *
from .helpers import groups_of, rgb_to_444, set_palette
from .types import Block, DisplayFrame, FullFrame


class Video:
    FRAME_RATE = 15
    PACKETS_PER_FRAME = PACKETS_PER_SECOND // FRAME_RATE

    log = logging.getLogger("libcdg")
    log.setLevel("DEBUG")

    def __init__(self, source: str | os.PathLike, mono=False, quiet=True, palette: str | os.PathLike=None) -> None:
        self.source = str(source)
        self.mono = mono
        self.quiet = quiet

        self.current_frame = 0
        self.packets: list[bytes] = []

        # do this one at init
        self.palette = self.calc_palette(palette)

    def ff_scale_input(self):
        "shared scale input video scale ffmpeg pipeline"

        # create scale pipeline
        scaled = (
            ffmpeg.input(self.source)
            # ensure 30fps to better match packet rate
            .filter("fps", fps=self.FRAME_RATE)
            # scale to CDG canvas size
            .filter("scale", width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
        )

        if self.mono:  # force 1-bit black/white (a la Bad Apple)
            black = ffmpeg.input("color=Black:s=288x192", f="lavfi")
            white = ffmpeg.input("color=White:s=288x192", f="lavfi")
            gray = ffmpeg.input("color=DarkGray:s=288x192", f="lavfi")

            scaled = ffmpeg.filter([scaled, gray, black, white], "threshold")

        return scaled

    def calc_palette(self, palette_img) -> list[tuple[int, int, int]]:
        "Calculate target palette based on input, or from given image"

        if palette_img and self.mono:
            self.log.warning("both palette image and mono flag give, using palette image!", file=sys.stderr)


        if palette_img:
            self.log.info(f"using palette from {palette_img}")
            with Image.open(palette_img) as p:
                assert len(p.getcolors()) <= 16, f"palette file {palette_img} has more than 16 colors!"

            # use given image as source for ffmpeg palettegen
            # (ffmpeg wants specific size later so let it generate for itself)
            palette_input = ffmpeg.input(palette_img)

        else:
            if not self.mono:
                self.log.info(f"deriving palette from input video")
            # no image, calculate from source
            palette_input = self.ff_scale_input()


        # crunch source vid or palette image to 16 colors (for global palette)
        palettegen = palette_input.filter("palettegen", max_colors=16, reserve_transparent=0)
        # TODO remove the other 256-16 colors from output png?

        # save palette to tempfile for later use
        self.palette_file = tempfile.NamedTemporaryFile(prefix="libcdg_pallette_", suffix=".png")
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

        # from palette gen
        palette = ffmpeg.input(filename=self.palette_file.name)

        ffprocess = (
            ffmpeg.filter([self.ff_scale_input(), palette], "paletteuse")
            .output("pipe:", format="rawvideo", pix_fmt="rgb24")
            .global_args("-hide_banner", "-loglevel", "warning")
            .run_async(pipe_stdout=True)
        )

        return ffprocess

    def encode(self):
        "Encode frames"

        self.log.info("starting encode...")

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
                self.log.debug(f"frame #{self.current_frame} ")

                frame = Image.frombytes("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), framebytes)
                # should already be using this palette but make sure
                frame = frame.quantize(palette=prev, dither=Image.Dither.NONE)

                # get blocks to update
                deltas = self.calc_updates(frame, prev)
                frame_packets = []

                # fetch the first however-many frames we can fit this round
                updates_this_frame = list(deltas.queue)[:self.PACKETS_PER_FRAME]
                for _pri, row, col, data in updates_this_frame:
                    # write out instruction packet
                    frame_packets.append(self.write_block(data, row, col))
                    # and update prev frame with changes
                    change = Image.fromarray(data, mode="P")
                    prev.paste(change, (col * BLOCK_WIDTH, row * BLOCK_HEIGHT))

                # self.log.trace(f"processed {len(frame_packets)} packets")

                # pad out if we need to
                if len(frame_packets) < self.PACKETS_PER_FRAME:
                    # self.log.trace(f"padding extra {self.PACKETS_PER_FRAME - len(frame_packets)}")

                    frame_packets += [instructions.nop()] * (self.PACKETS_PER_FRAME - len(frame_packets))

                assert len(frame_packets) == self.PACKETS_PER_FRAME, f"{len(frame_packets)} is more than {self.PACKETS_PER_FRAME}!"

                self.packets += frame_packets

        return self


    def save(self, name: str, overwrite=False):
        "Save encoded CDG stream to `name`.cdg and `name`.mp3"
        assert len(self.packets) != 0, "cannot save before encoding! run `encode()` first"
        self.log.info(f"saving to {name}.cdg/.mp3")

        mode = "wb" if overwrite else "xb"
        with open(f"{name}.cdg", mode=mode) as cdgfile:
            cdgfile.writelines(self.packets)

        # also write out audio
        mp3 = ffmpeg.input(self.source).output(f"{name}.mp3").global_args("-hide_banner")
        if overwrite:
            mp3 = mp3.overwrite_output()
        mp3.run(quiet=self.quiet)


    def image_to_blocks(self, image: Image.Image) -> DisplayFrame | FullFrame:
        "groups `image` pixel data into (numpy) array of block tiles"
        # adapted from: https://stackoverflow.com/a/16858283

        assert image.mode == "P"
        arr = np.array(image)

        h, w = arr.shape
        assert h % BLOCK_HEIGHT == 0, f"{h} rows is not evenly divisible by {BLOCK_HEIGHT}"
        assert w % BLOCK_WIDTH == 0, f"{w} cols is not evenly divisible by {BLOCK_WIDTH}"

        # chunked, but one dimensional
        blocks_1d = (
            arr.reshape(h // BLOCK_HEIGHT, BLOCK_HEIGHT, -1, BLOCK_WIDTH)
            .swapaxes(1, 2)
            .reshape(-1, BLOCK_HEIGHT, BLOCK_WIDTH)
        )

        # need to convert each block to two colors only
        # nested func for map
        def squash_colors(block: Block) -> Block:
            bimg = Image.fromarray(block, mode="P")
            bimg.putpalette(itertools.chain(*self.palette))

            # tiles need max two colors from the overall 16
            # this two-step-monty isnt great and probably loses some color, but it does work
            # colors= and palette= are exclusive
            # TODO: can this be made any better?
            squashed = (
                bimg
                # squish to two arbitrary colors
                .convert("RGB").quantize(colors=2)
                # fit back in original palette (no dither to preserve the two colors)
                .convert("RGB").quantize(palette=image, dither=Image.Dither.NONE)
            )
            # (palette index is the same as original)

            # convert back to byte array
            return np.array(squashed)

        blocks_1d = np.array([squash_colors(block) for block in blocks_1d])

        # split chunk list back into 2d (split into X cols)
        return np.split(blocks_1d, h / BLOCK_HEIGHT)


    def calc_updates(self, next: Image.Image, prev: Image.Image) -> queue.PriorityQueue:
        "calculate list of blocks to change in order of largest difference"

        # array shape: 16x48 x 12x6
        # (blocks in canvas)   (pixels in block)
        prev_blocks = self.image_to_blocks(prev)
        next_blocks = self.image_to_blocks(next)

        updates = queue.PriorityQueue()
        # delta entry format:
        # (priority, row, col, new_block_data)

        # count number of differing pixels
        diff = lambda a, b: len([True for ai, bi in zip(a.flat, b.flat) if ai != bi])

        for row_i, rows in enumerate(np.stack((prev_blocks, next_blocks), 2), start=0):
            for col_i, (pblock, nblock) in enumerate(rows, start=0):
                block_diff = diff(pblock, nblock)
                if block_diff > 0:
                    # negative delta, since PQ fetches lowest values first
                    updates.put((-block_diff, row_i, col_i, nblock))

        self.log.debug(f"generated {updates.qsize()} updates")
        return updates


    def write_block(self, block: Block, row: int, col: int) -> bytes:
        "converts block to fg/bg and returns generated instruction"

        # self.log.trace(f"writing block at {row=} {col=}")
        colors = np.unique(block).tolist()

        assert len(colors) in [1, 2], "too many colors in block!"

        if len(colors) == 1:
            fg = bg = colors[0]
        else:
            fg, bg = colors

        # turn palette index into fg/bg bools
        bools = np.vectorize(lambda x: x == fg)(block)
        # only lower 6 bits are used, so pad to 8 bits for packing
        padded = np.pad(bools, ((0,0), (2,0)))
        # pack bools into bitfield
        bits = b"".join(np.packbits(padded))

        return instructions.write_font_block(bg, fg, row, col, bits)
