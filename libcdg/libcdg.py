from PIL import Image, ImageOps
import itertools
import collections
import functools

# import numpy as np

from . import instructions
from .constants import *

# information from https://jbum.com/cdg_revealed.html
# and https://goughlui.com/2019/03/31/tech-flashback-the-cdgraphics-format-cdg/


def dbg(msg):
    import sys

    sys.stderr.write(repr(msg))


def groups_of(it, n):
    it = iter(it)
    return iter(lambda: list(itertools.islice(it, n)), [])


def image_to_packets(image_path: str, frame_time=0) -> bytes:
    """
    Encodes image at `image_path` to CD+G packets,
    with padding to meet minimum frame time set by `frame_time` in seconds
    (300 packets per second)
    """

    packets = b""

    with Image.open(image_path) as image:
        # make sure image is 16 colors only
        image = image.convert("P", palette=Image.ADAPTIVE, colors=16)

        if image.size == (FULL_WIDTH, FULL_HEIGHT):
            # print("  image covers full canvas")
            # image covers entire canvas
            r_range, c_range = range(0,BLOCK_WIDTH+1), range(0,BLOCK_HEIGHT+1)
        else:
            # print("  image covers visible area only")
            # restrict to visible canvas area
            r_range, c_range = range(1,BLOCK_WIDTH), range(1,BLOCK_HEIGHT)

        # do in two steps to avoid stretching
        image = ImageOps.pad(image, (image.size[0], FULL_HEIGHT))
        image = ImageOps.pad(image, (FULL_WIDTH, FULL_HEIGHT))


        # set colors in palette
        palette = image.getpalette()
        packets += set_palette(palette)

        # set canvas and border color
        packets += instructions.preset_memory(1)
        packets += instructions.preset_border(0)

        pixel_map = list(groups_of(image.tobytes(), FULL_WIDTH))

        # split image into tiles
        # right now we only care about the visible area (1..-2)
        for r in r_range:
            for c in c_range:
                b = block_pixels(pixel_map, r, c)

                packets += set_block(b, r, c)

    return packets






def set_palette(colors) -> bytes:
    # pad to 16 colors if needed
    colors = list(groups_of(colors, 3))
    colors += [(0, 0, 0)] * (16 - len(colors))

    assert len(colors) == 16

    # fmt: off
    return instructions.load_color_table_low(colors[0:8]) \
         + instructions.load_color_table_high(colors[8:16])
    # fmt: on


def block_pixels(pixels, block_r, block_c):
    "Extracts 6x12 block of pixels at specified block coordinates"
    assert (
        len(pixels) == FULL_HEIGHT and len(pixels[0]) == FULL_WIDTH
    ), f"pixel array is the wrong size ({len(pixels)}x{len(pixels[0])})! do not include border tiles!"

    pix_r, pix_c = block_r * 12, block_c * 6
    return [r[pix_c : pix_c + 6] for r in pixels[pix_r : pix_r + 12]]


def set_block(block_pixels, row, col):
    pix = list(itertools.chain.from_iterable(block_pixels))  # ensure pixel list is flat

    # convert tiles into bitfield
    # TODO: this will need to change for color!

    # collect colors used
    colors = collections.Counter(pix).keys()
    assert len(colors) in [1, 2], "too many colors in tile!"

    # fg, bg = colors + [0]

    if len(colors) == 1:
        fg, bg = *colors, 0
    else:
        fg, bg = colors

    # pack pixels into bits
    bools = [p == fg for p in pix]
    # dbg(bools)
    pix_bits = b"".join(
        [
            functools.reduce(lambda a, p: a << 1 | p, byte, 0).to_bytes()
            for byte in groups_of(bools, 6)
        ]
    )

    # breakpoint()

    return instructions.write_font_block(bg, fg, row, col, pix_bits)
