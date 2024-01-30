from PIL import Image
import itertools

# information frhttps://ffmpeg.org/doxygen/trunk/cdgraphics_8c.htmlom https://jbum.com//revealed.html
# and https://ffmpeg.org/doxygen/trunk/cdgraphics_8c.html

FULL_WIDTH = 300
FULL_HEIGHT = 216
DISPLAY_WIDTH = 294
DISPLAY_HEIGHT = 204
BORDER_WIDTH = 6
BORDER_HEIGHT = 12

COMMAND = 0x09
MASK = 0x3F

INST_MEMORY_PRESET = 1
INST_BORDER_PRESET = 2
INST_TILE_BLOCK = 6
INST_SCROLL_PRESET = 20
INST_SCROLL_COPY = 24
INST_LOAD_PAL_LO = 30
INST_LOAD_PAL_HIGH = 31
INST_TILE_BLOCK_XOR = 38

PACKET_SIZE = 24
DATA_SIZE = 16
TILE_HEIGHT = 12
TILE_WIDTH = 6
MINIMUM_PKT_SIZE = 6
MINIMUM_SCROLL_SIZE = 3
HEADER_SIZE = 8
PALETTE_SIZE = 16


def groups_of(it, n):
    """
    >>> list(grouper(3, 'ABCDEFG'))
    [['A', 'B', 'C'], ['D', 'E', 'F'], ['G']]
    """
    it = iter(it)
    return iter(lambda: list(itertools.islice(it, n)), [])


def packets_from_img(image_path: str) -> bytes:
    "Encodes image at `image_path` to CD+G packets"

    packet = b""

    with Image.open(image_path) as image:
        # make sure image is 16 colors only
        image2 = image.convert("P", palette=Image.ADAPTIVE, colors=16)

        palette = iter(image2.getpalette())

        [print((rgb)) for rgb in groups_of(palette, 3)]
