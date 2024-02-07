from PIL import Image, ImageOps
import itertools
import functools
import random

# import numpy as np

from . import instructions
from .constants import *

# information from https://jbum.com/cdg_revealed.html
# and https://goughlui.com/2019/03/31/tech-flashback-the-cdgraphics-format-cdg/


def dbg(msg):
    import sys

    sys.stderr.write(repr(msg) + "\n")


def groups_of(it, n) -> iter:
    it = iter(it)
    return iter(lambda: list(itertools.islice(it, n)), [])


def image_to_packets(image_path: str, frame_time=0) -> list[bytes]:
    """
    Encodes image at `image_path` to CD+G packets,
    with padding to meet minimum frame time set by `frame_time` in seconds
    (300 packets per second)
    """

    packets = []

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
        palette = list(groups_of(image.getpalette(), 3))
        dbg(f"PALETTE IS: {len(palette)}: {palette}")

        packets.append(set_palette(palette))

        # set canvas and border color
        packets.append(instructions.preset_memory(1))
        packets.append(instructions.preset_border(0))

        pixel_map = list(groups_of(image.tobytes(), FULL_WIDTH))


        blocks = list(itertools.product(r_range, c_range))
        transitions = {
            "row":      lambda: blocks.sort(),
            "row_rev":  lambda: blocks.sort(reverse=True),
            "col":      lambda: blocks.sort(key=(lambda b: (b[1], b[0]))),
            "col_rev":  lambda: blocks.sort(key=(lambda b: (b[1], b[0])), reverse=True),
            "random":   lambda: random.shuffle(blocks)
        }
        # random.choice(list(transitions.values()))()
        # random.choice(list(transitions.values()))()
        transitions["row"]()

        # split image into tiles
        # right now we only care about the visible area (1..-2)

        packets += [
            set_block(image, r, c)
            for r, c in blocks
        ]


    return packets


def set_palette(colors: list[tuple[int]]) -> bytes:
    assert len(colors[0]) == 3, "palette should be list of RGB tuples!"

    # pad to 16 colors if needed
    colors += [(0, 0, 0)] * (16 - len(colors))

    assert len(colors) == 16

    # fmt: off
    return instructions.load_color_table_low(colors[0:8]) \
         + instructions.load_color_table_high(colors[8:16])
    # fmt: on


# def block_pixels(pixels, block_r, block_c):
#     "Extracts 6x12 block of pixels at specified block coordinates"
#     assert (
#         len(pixels) == FULL_HEIGHT and len(pixels[0]) == FULL_WIDTH
#     ), f"pixel array is the wrong size ({len(pixels)}x{len(pixels[0])})! do not include border tiles!"

#     pix_r, pix_c = block_r * 12, block_c * 6
#     return [r[pix_c : pix_c + 6] for r in pixels[pix_r : pix_r + 12]]


def set_block(full_image, row, col):
    # crop to tile
    pix_x, pix_y = col * 6, row * 12
    block = full_image.crop((pix_x, pix_y, pix_x+TILE_WIDTH, pix_y+TILE_HEIGHT))

    # tiles need max two colors from the overall 16
    # (this two-step-monty isnt great,
    #  but this is the easiest and it will probably work for most things)
    two_color = (
        block
        # squish to two arbitrary colors
        .convert("RGB").quantize(colors=2)
        # fit back in original palette (no dither to preserve the two colors)
        .convert("RGB").quantize(palette=full_image, dither=Image.Dither.NONE)
    )
    # (palette index is the same as original)

    # collect colors used
    pix_data = two_color.tobytes()

    colors = [idx for _cnt, idx in two_color.getcolors()]

    dbg(f"tile colors: {colors}")
    assert len(colors) in [1, 2], "too many colors in tile!"

    if len(colors) == 1:
        fg = bg = colors[0]
    else:
        fg, bg = colors

    # pack pixels into bits
    bools = [p == fg for p in pix_data]
    pix_bits = b"".join(
        [
            functools.reduce(lambda a, p: a << 1 | p, byte, 0).to_bytes()
            for byte in groups_of(bools, 6)
        ]
    )

    return instructions.write_font_block(bg, fg, row, col, pix_bits)



def show(img):
    img.convert("RGB").show()
