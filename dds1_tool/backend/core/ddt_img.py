import os
import struct
from pathlib import Path
from io import BytesIO
from typing import Callable, List, Dict, Optional

SECTOR_SIZE = 2048

# Based on reverse engineering by TGEnigma / AtlusFileSystemLibrary + nmarkro/Nocturne-Randomizer
# Each DDT entry = 12 bytes:
#   name_offset (uint32) : byte offset in DDT to the null-terminated file name
#   location    (uint32) : sector index in DDS3.IMG  (0 for directories)
#   size        (int32)  : if negative → directory (abs value = number of children)
#                          if positive → file size in bytes

class DDS3FileEntry:
    def __init__(self):
        self.name = ""
        self.name_offset = 0
        self.location = 0     # sector index
        self.size = 0         # bytes (positive) or child count (negative → directory)
        self.is_dir = False
        self.children: Dict[str, "DDS3FileEntry"] = {}
        self.parent: Optional["DDS3FileEntry"] = None
        self.path = ""
        self.offset = 0       # byte offset of this entry in DDT


class DDTImgHandler:
    """
    Handler for Atlus PS2 DDS3.DDT (virtual filesystem index) and DDS3.IMG (data container).
    Compatible with Nocturne, Digital Devil Saga 1 & 2.

    DDT node format (12 bytes each):
      - name_offset (4 bytes, unsigned) : offset in DDT of the null-terminated ASCII name
      - location    (4 bytes, unsigned) : starting sector in the IMG file
      - size        (4 bytes, signed)   : file size in bytes; if negative → directory,
                                          abs(size) = number of direct children
    """

    def __init__(self, ddt_path: str, img_path: str):
        self.ddt_path = Path(ddt_path)
        self.img_path = Path(img_path)
        self.root: Optional[DDS3FileEntry] = None
        self.file_entries: Dict[str, DDS3FileEntry] = {}

    # ------------------------------------------------------------------
    # Reading the DDT tree
    # ------------------------------------------------------------------

    def _read_name(self, ddt_file, name_offset: int) -> str:
        if name_offset == 0:
            return ""
        saved = ddt_file.tell()
        ddt_file.seek(name_offset)
        name = b""
        while True:
            c = ddt_file.read(1)
            if not c or c == b"\x00":
                break
            name += c
        ddt_file.seek(saved)
        try:
            return name.decode("ascii")
        except UnicodeDecodeError:
            return name.decode("latin-1", errors="replace")

    def _read_entry(self, ddt_file, parent: Optional[DDS3FileEntry]) -> DDS3FileEntry:
        entry = DDS3FileEntry()
        entry.offset = ddt_file.tell()

        raw = ddt_file.read(12)
        if len(raw) < 12:
            raise ValueError("Unexpected end of DDT file")

        name_offset, location, size = struct.unpack("<IIi", raw)
        entry.name_offset = name_offset
        entry.location    = location
        entry.name        = self._read_name(ddt_file, name_offset)

        if parent:
            entry.path = parent.path + "/" + entry.name if parent.path else entry.name
        else:
            entry.path = entry.name

        entry.parent = parent

        if size < 0:
            # Directory: abs(size) = number of children
            entry.is_dir = True
            child_count = -size

            # The directory's "location" field is the byte offset in the DDT where
            # its children start (NOT a sector — it points back into the DDT itself).
            child_start = location
            ddt_file.seek(child_start)

            for _ in range(child_count):
                child = self._read_entry(ddt_file, entry)
                entry.children[child.name] = child

            # After reading children, seek back to just after this entry header
            ddt_file.seek(entry.offset + 12)
        else:
            entry.is_dir = False
            entry.size = size

        self.file_entries[entry.path] = entry
        return entry

    def load_index(self) -> Dict[str, DDS3FileEntry]:
        """Parses DDS3.DDT and builds the full virtual file tree. Returns a dict path→entry."""
        if not self.ddt_path.exists():
            raise FileNotFoundError(f"DDT not found: {self.ddt_path}")

        with open(self.ddt_path, "rb") as ddt_file:
            self.file_entries = {}
            self.root = self._read_entry(ddt_file, None)

        return self.file_entries

    # ------------------------------------------------------------------
    # Extracting files
    # ------------------------------------------------------------------

    def extract_all(
        self,
        output_dir: str,
        logger: Optional[Callable] = None,
        progress_fn: Optional[Callable] = None,
    ) -> List[str]:
        """Extracts every file from DDS3.IMG, recreating the directory tree under output_dir."""
        if not self.file_entries:
            self.load_index()

        if not self.img_path.exists():
            if logger:
                logger(f"IMG introuvable : {self.img_path}", "warn")
            return []

        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)

        # Collect all file (non-directory) entries
        file_list = [e for e in self.file_entries.values() if not e.is_dir and e.size > 0]
        total = len(file_list)
        extracted = []

        if logger:
            logger(f"Extraction de {total} fichiers depuis DDS3.IMG...", "info")

        with open(self.img_path, "rb") as img:
            for i, entry in enumerate(file_list):
                # Reconstruct full output path
                dest = out_root / entry.path
                dest.parent.mkdir(parents=True, exist_ok=True)

                byte_offset = entry.location * SECTOR_SIZE
                img.seek(byte_offset)
                data = img.read(entry.size)

                with open(dest, "wb") as f_out:
                    f_out.write(data)

                extracted.append(str(dest))

                if progress_fn and total > 0:
                    progress_fn((i + 1) / total)

                if logger and (i + 1) % 500 == 0:
                    logger(f"Extraction en cours : {i+1}/{total} fichiers...", "info")

        if logger:
            logger(f"Extraction terminée : {len(extracted)} fichiers extraits dans {output_dir}", "success")

        return extracted

    def extract_by_extension(
        self,
        output_dir: str,
        extensions: List[str],
        logger: Optional[Callable] = None,
    ) -> List[str]:
        """Extracts only files matching the given extensions, preserving directory structure."""
        if not self.file_entries:
            self.load_index()

        out_root = Path(output_dir)
        out_root.mkdir(parents=True, exist_ok=True)

        ext_set = {e.lower() for e in extensions}
        extracted = []

        with open(self.img_path, "rb") as img:
            for path_str, entry in self.file_entries.items():
                if entry.is_dir or entry.size <= 0:
                    continue
                if Path(entry.name).suffix.lower() not in ext_set:
                    continue

                dest = out_root / path_str
                dest.parent.mkdir(parents=True, exist_ok=True)

                img.seek(entry.location * SECTOR_SIZE)
                data = img.read(entry.size)

                with open(dest, "wb") as f_out:
                    f_out.write(data)

                extracted.append(str(dest))
                if logger:
                    logger(f"Extrait : {path_str}", "info")

        return extracted

    def list_files(self) -> List[str]:
        """Returns a list of all file paths in the archive."""
        if not self.file_entries:
            self.load_index()
        return [p for p, e in self.file_entries.items() if not e.is_dir]
