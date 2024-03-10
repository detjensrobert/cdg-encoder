import functools
import itertools
import random
from math import floor

from PIL import Image, ImageOps

from . import instructions
from .constants import *

# information from https://jbum.com/cdg_revealed.html
# and https://goughlui.com/2019/03/31/tech-flashback-the-cdgraphics-format-cdg/

"""
Tools for creating CD+G graphics packets
"""

def dbg(msg):
    import sys

    sys.stderr.write(repr(msg) + "\n")


def groups_of(it: iter, n: int) -> iter:
    "split iterable `it` into groups of size `n`"
    it = iter(it)
    return iter(lambda: list(itertools.islice(it, n)), [])


def rgb_to_444(color: tuple[int]):
    "convert `color` triplet in RGB24 (0-255) to RBG444 (0-16)"
    r, g, b = color
    rf = lambda c: min(round(c), 15)  # rf = round or floor at 16
    return (rf(r / 16), rf(g / 16), rf(b / 16))


def show(img):
    img.convert("RGB").show()


def image_to_packets(image_path: str, frame_time=0, palettefile: str = None, paletteimg: Image = None) -> list[bytes]:
    """
    Encodes image at `image_path` to CD+G packets.

    Conversion will use an explicit `palette` from a PIL Image, or load one from
    image at `palettefile`, or calculate one internally.
    """

    # read palettefile
    if palettefile and not paletteimg:
        paletteimg = Image.open(palettefile).convert("P")

    packets = []

    with Image.open(image_path) as image:
        # make sure image is 16 colors only
        if paletteimg: # use explicit palette if given
            image = image.convert("RGB").quantize(palette=paletteimg, dither=Image.Dither.NONE)
        else:
            image = image.convert("P", palette=Image.ADAPTIVE, colors=16)

        if image.size == (FULL_WIDTH, FULL_HEIGHT):
            # print("  image covers full canvas")
            # image covers entire canvas
            r_range, c_range = range(0, FULL_WIDTH_BLOCKS), range(0, FULL_HEIGHT_BLOCKS)
        else:
            # print("  image covers visible area only")
            # restrict to visible canvas area
            r_range, c_range = range(1, DISPLAY_WIDTH_BLOCKS), range(1, DISPLAY_HEIGHT_BLOCKS)

        # do in two steps to avoid stretching
        image = ImageOps.pad(image, (image.size[0], FULL_HEIGHT))
        image = ImageOps.pad(image, (FULL_WIDTH, FULL_HEIGHT))

        # set colors in palette
        palette = groups_of(image.getpalette(), 3)
        # remove duplicates
        palette = list(set([tuple(rgb) for rgb in palette]))
        packets.append(set_palette(palette))

        # set canvas and border color
        packets.append(instructions.preset_memory(1))
        packets.append(instructions.preset_border(0))

        # shuffle block orders to make this more Fun:TM:
        blocks = list(itertools.product(r_range, c_range))
        transitions = {
            "row":      lambda: blocks.sort(),
            "row_rev":  lambda: blocks.sort(reverse=True),
            "col":      lambda: blocks.sort(key=(lambda b: (b[1], b[0]))),
            "col_rev":  lambda: blocks.sort(key=(lambda b: (b[1], b[0])), reverse=True),
            "random":   lambda: random.shuffle(blocks)
        }
        random.choice(list(transitions.values()))()

        # convert tiles to instruction packets
        packets += [
            set_block(image, r, c)
            for r, c in blocks
        ]

    return packets


# def image_to_packets_mono(image_path: str, frame_time=0) -> list[bytes]:
#     """
#     Encodes monochrome image at `image_path` to CD+G packets.

#     Conversion will use an explicit `palette` from a PIL Image, or load one from
#     image at `palettefile`, or calculate one internally.
#     """

#     # read palettefile
#     if palettefile and not paletteimg:
#         paletteimg = Image.open(palettefile).convert("P")

#     packets = []

#     with Image.open(image_path) as image:
#         # make sure image is 16 colors only
#         if paletteimg:  # use explicit palette if given
#             image = image.convert("RGB").quantize(
#                 palette=paletteimg, dither=Image.Dither.NONE
#             )
#         else:
#             image = image.convert("P", palette=Image.ADAPTIVE, colors=16)

#         if image.size == (FULL_WIDTH, FULL_HEIGHT):
#             # print("  image covers full canvas")
#             # image covers entire canvas
#             r_range, c_range = range(0, FULL_WIDTH_BLOCKS), range(0, FULL_HEIGHT_BLOCKS)
#         else:
#             # print("  image covers visible area only")
#             # restrict to visible canvas area
#             r_range, c_range = range(1, DISPLAY_WIDTH_BLOCKS), range(1, DISPLAY_HEIGHT_BLOCKS)

#         # do in two steps to avoid stretching
#         image = ImageOps.pad(image, (image.size[0], FULL_HEIGHT))
#         image = ImageOps.pad(image, (FULL_WIDTH, FULL_HEIGHT))

#         # set colors in palette
#         palette = groups_of(image.getpalette(), 3)
#         # remove duplicates
#         palette = list(set([tuple(rgb) for rgb in palette]))
#         packets.append(set_palette(palette))

#         # set canvas and border color
#         packets.append(instructions.preset_memory(1))
#         packets.append(instructions.preset_border(0))

#         # shuffle block orders to make this more Fun:TM:
#         blocks = list(itertools.product(r_range, c_range))
#         transitions = {
#             "row": lambda: blocks.sort(),
#             "row_rev": lambda: blocks.sort(reverse=True),
#             "col": lambda: blocks.sort(key=(lambda b: (b[1], b[0]))),
#             "col_rev": lambda: blocks.sort(key=(lambda b: (b[1], b[0])), reverse=True),
#             "random": lambda: random.shuffle(blocks),
#         }
#         random.choice(list(transitions.values()))()

#         # convert tiles to instruction packets
#         packets += [set_block(image, r, c) for r, c in blocks]

#     return packets


def set_palette(colors: list[tuple[int]]) -> tuple[bytes]:
    assert all([len(c) == 3 for c in colors]), "palette should be list of RGB tuples!"

    # pad to 16 colors if needed
    colors += [(0, 0, 0)] * (16 - len(colors))

    assert len(colors) == 16

    colors_444 = list(map(rgb_to_444, colors))

    # fmt: off
    return (instructions.load_color_table_low(colors_444[0:8]), \
            instructions.load_color_table_high(colors_444[8:16]))
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
    block = full_image.crop((pix_x, pix_y, pix_x+BLOCK_WIDTH, pix_y+BLOCK_HEIGHT))

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
