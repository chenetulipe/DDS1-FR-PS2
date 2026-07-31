import struct
from pathlib import Path
from typing import Dict, List, Optional, Callable

class FontManager:
    """
    Manages PS2 TIM2 (.TM2) font textures and font width tables for DDS1.
    """
    def __init__(self):
        # Default character widths in pixels for PS2 font
        self.default_width = 16
        self.char_widths: Dict[str, int] = {
            "é": 14, "è": 14, "à": 14, "ç": 14, "ê": 14, "ù": 14,
            "É": 16, "À": 16, "Ç": 16,
            "i": 8, "l": 8, "f": 10, "t": 10, "m": 20, "w": 20, "W": 22, "M": 22
        }

    def load_width_table(self, table_path: str) -> Dict[str, int]:
        """Reads a binary font width table file."""
        path = Path(table_path)
        if not path.exists():
            return self.char_widths

        with open(path, "rb") as f:
            data = f.read()

        # Parse width entries (1 byte per char glyph)
        widths = {}
        for idx, width in enumerate(data[:256]):
            widths[chr(idx)] = width

        return widths

    def generate_french_width_table(self, out_path: str) -> str:
        """Creates an updated font width table with French character adjustments."""
        dest = Path(out_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        table_bytes = bytearray(256)
        for i in range(256):
            c = chr(i)
            table_bytes[i] = self.char_widths.get(c, self.default_width)

        with open(dest, "wb") as f:
            f.write(table_bytes)

        return str(dest)
