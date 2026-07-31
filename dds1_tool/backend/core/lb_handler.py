import os
import struct
from pathlib import Path
from typing import List, Optional, Callable, Tuple


class LBEntry:
    """Entry in an Atlus .LB archive file."""
    def __init__(self):
        self.user_id: int = 0
        self.compressed: bool = False
        self.entry_type: int = 0
        self.size: int = 0          # compressed size (data after header)
        self.extension: str = ''
        self.decompressed_size: int = 0
        self.data_offset: int = 0   # byte offset of data in LB file


class LBHandler:
    """
    Parses Atlus PS2 .LB archive files (used in DDS1, Nocturne, DDS2).
    
    LB format: sequence of 16-byte headers + data blocks:
      entry_type    (1 byte)
      compressed    (1 byte)  0 = raw, 1 = custom LZ
      user_id       (2 bytes, LE uint16)
      total_size    (4 bytes, LE uint32)  — includes the 16-byte header
      extension     (4 bytes, ASCII, null-padded)
      decomp_size   (4 bytes, LE uint32)
      [data ...]    (total_size - 16 bytes)
    """

    HEADER_SIZE = 16

    def __init__(self, lb_path: str):
        self.lb_path = Path(lb_path)
        self.entries: List[LBEntry] = []

    def parse(self) -> List[LBEntry]:
        """Parse the LB file and return list of entries."""
        self.entries = []
        data = self.lb_path.read_bytes()
        pos = 0

        while pos + self.HEADER_SIZE <= len(data):
            hdr = data[pos:pos + self.HEADER_SIZE]
            entry = LBEntry()
            entry.entry_type  = hdr[0]
            entry.compressed  = bool(hdr[1])
            entry.user_id     = struct.unpack_from('<H', hdr, 2)[0]
            total_size        = struct.unpack_from('<I', hdr, 4)[0]
            entry.extension   = hdr[8:12].decode('ascii', errors='replace').replace('\x00', '').strip()
            entry.decompressed_size = struct.unpack_from('<I', hdr, 12)[0]

            if total_size < self.HEADER_SIZE:
                break  # corrupt/end

            entry.size        = total_size - self.HEADER_SIZE
            entry.data_offset = pos + self.HEADER_SIZE
            self.entries.append(entry)
            pos += total_size

        return self.entries

    def extract_entry(self, entry: LBEntry) -> bytes:
        """Return raw (decompressed if needed) bytes of an entry."""
        raw = self.lb_path.read_bytes()
        chunk = raw[entry.data_offset: entry.data_offset + entry.size]

        if not entry.compressed:
            return chunk

        # Simple LZ decompression (Atlus custom codec used in Nocturne / DDS)
        return self._decompress(chunk, entry.decompressed_size)

    def _decompress(self, data: bytes, expected_size: int) -> bytes:
        """Atlus custom LZ decompressor (sliding-window, handles forward overlap)."""
        out = bytearray()
        pos = 0

        def read_byte():
            nonlocal pos
            if pos >= len(data):
                raise EOFError("Unexpected end of compressed data")
            b = data[pos]
            pos += 1
            return b

        def read_halfword():
            nonlocal pos
            if pos + 1 >= len(data):
                raise EOFError("Unexpected end of compressed data")
            v = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            return v

        while len(out) < expected_size and pos < len(data):
            try:
                op = read_byte()
            except EOFError:
                break

            count = op & 0x1F
            if count == 0:
                try:
                    count = read_halfword()
                except EOFError:
                    break
            opcode = (op >> 4) & 0xE

            try:
                if opcode == 0x0:    # CopyBytes
                    for _ in range(count):
                        out.append(read_byte())
                elif opcode == 0x2:  # RepeatZero
                    out.extend(b'\x00' * count)
                elif opcode == 0x4:  # RepeatByte
                    b = read_byte()
                    out.extend(bytes([b]) * count)
                elif opcode == 0x6:  # CopyPrevious (LZ back-reference)
                    offset = read_halfword()
                    src = len(out) - offset
                    if src < 0:
                        # Invalid back-reference, just fill zeros
                        out.extend(b'\x00' * count)
                    else:
                        # Copy byte-by-byte to handle forward overlap (run-length style)
                        for i in range(count):
                            out.append(out[src + i])
                else:
                    break  # unknown opcode
            except (EOFError, IndexError):
                break

        return bytes(out)

    def extract_all_by_extension(
        self,
        output_dir: str,
        extensions: Optional[List[str]] = None,
        logger: Optional[Callable] = None,
    ) -> List[Tuple[str, Path]]:
        """
        Extract all entries (optionally filtered by extension) to output_dir.
        Returns list of (user_id_str, output_path) tuples.
        """
        if not self.entries:
            self.parse()

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        result = []
        ext_set = {e.lower().lstrip('.') for e in extensions} if extensions else None

        for entry in self.entries:
            ext = entry.extension.lower()
            if ext_set and ext not in ext_set:
                continue

            fname = f"{entry.user_id}.{entry.extension}" if entry.extension else str(entry.user_id)
            dest = out / fname

            try:
                content = self.extract_entry(entry)
                dest.write_bytes(content)
                result.append((str(entry.user_id), dest))
            except Exception as e:
                if logger:
                    logger(f"Erreur extraction LB entry {entry.user_id}: {e}", "warn")

        return result
