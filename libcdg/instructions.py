from struct import pack

from .constants import *

# todo: handle masking? check int sizes?


"""
The plumbing.

Low level functions for creating CD+G packets directly.
"""


# meta packet assembler
def _packet(instruction, data):
    parity_q = b"\x00" * 2
    parity_p = b"\x00" * 4

    return pack(
        "> B B 2s 16s 4s",
        CDG_COMMAND_MAGIC_BYTE,
        instruction,
        parity_q,
        data,
        parity_p,
    )


def nop():
    return pack(f">{PACKET_SIZE}x")


def preset_memory(color: int, repeat: int = 4):
    return _packet(INST_PRESET_MEMORY, pack(">BB14x", color, repeat))


def preset_border(color: int):
    return _packet(INST_PRESET_BORDER, pack(">B15x", color))


def write_font_block(bg_color, fg_color, row, column, pixels, channel=0):
    return _packet(
        INST_WRITE_FONT_BLOCK,
        pack(">BBBB12s", bg_color, fg_color, row, column, pixels),
    )


def xor_font_block(bg_color, fg_color, row, column, pixels, channel=0):
    return _packet(
        INST_XOR_FONT_BLOCK,
        pack(">BBBB12s", bg_color, fg_color, row, column, pixels),
    )


def scroll_preset(color, h_scroll, v_scroll):
    return _packet(INST_SCROLL_PRESET, pack(">BBB13x", color, h_scroll, v_scroll))


def scroll_copy(h_scroll, v_scroll):
    return _packet(INST_SCROLL_PRESET, pack(">xBB13x", h_scroll, v_scroll))


def set_transparency_color(alpha_levels):
    return _packet(INST_DEFINE_TRANSP_COLOR, pack(">16B", alpha_levels))


def load_color_table_low(colors: list[list[int]]):
    return _load_colors(INST_LOAD_COLOR_TABLE_LOW, colors)


def load_color_table_high(colors: list[list[int]]):
    return _load_colors(INST_LOAD_COLOR_TABLE_HIGH, colors)


def _load_colors(instr, colors):
    # pack rgb 444 into the two bytes expected
    # xxRRRRGG xxGGBBBB
    colors_packed = [
        ((r & 0x0F) << 10) + ((g & 0x0C) << 6) + ((g & 0x03) << 4) + (b & 0x0F)
        for r, g, b in colors
    ]
    return _packet(instr, pack(">8H", *colors_packed))
