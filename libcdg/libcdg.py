from PIL import Image
import itertools

import instructions
import constants

# information frhttps://ffmpeg.org/doxygen/trunk/cdgraphics_8c.htmlom https://jbum.com//revealed.html
# and https://ffmpeg.org/doxygen/trunk/cdgraphics_8c.html


def groups_of(it, n):
    it = iter(it)
    return iter(lambda: list(itertools.islice(it, n)), [])


def image_to_packets(image_path: str) -> bytes:
    """
    Encodes image at `image_path` to CD+G packets
    """

    packet = b""

    with Image.open(image_path) as image:
        # make sure image is 16 colors only
        image2 = image.convert("P", palette=Image.ADAPTIVE, colors=2)

        palette = iter(image2.getpalette())

        # set colors in palette


        # image2.convert("RGB").show()
