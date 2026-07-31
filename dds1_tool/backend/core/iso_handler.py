import os
import struct
from pathlib import Path
from typing import Callable, Optional, Dict, List

class PS2ISOHandler:
    """
    Pure Python ISO9660 reader and binary LBA patcher for PS2 DVD ISOs.
    """
    SECTOR_SIZE = 2048

    def __init__(self, iso_path: str):
        self.iso_path = Path(iso_path)
        self.files_lba: Dict[str, Dict] = {}

    def scan_iso(self) -> Dict[str, Dict]:
        """Parses ISO9660 volume descriptor and directory record."""
        if not self.iso_path.exists():
            raise FileNotFoundError(f"ISO file not found: {self.iso_path}")

        self.files_lba.clear()

        with open(self.iso_path, "rb") as f:
            # Primary Volume Descriptor is at sector 16
            f.seek(16 * self.SECTOR_SIZE)
            vd = f.read(self.SECTOR_SIZE)
            
            if vd[1:6] != b"CD001":
                raise ValueError("Invalid ISO 9660 format.")

            root_rec = vd[156:156+34]
            root_lba = int.from_bytes(root_rec[2:6], "little")
            root_size = int.from_bytes(root_rec[10:14], "little")

            # Read root directory sector(s)
            f.seek(root_lba * self.SECTOR_SIZE)
            dir_data = f.read(root_size)

            offset = 0
            while offset < len(dir_data):
                length = dir_data[offset]
                if length == 0:
                    offset = ((offset // self.SECTOR_SIZE) + 1) * self.SECTOR_SIZE
                    continue

                rec = dir_data[offset:offset+length]
                name_len = rec[32]
                raw_name = rec[33:33+name_len].decode("ascii", errors="ignore")
                clean_name = raw_name.split(";")[0]

                lba = int.from_bytes(rec[2:6], "little")
                size = int.from_bytes(rec[10:14], "little")

                if clean_name and clean_name not in (".", "\x01"):
                    self.files_lba[clean_name] = {
                        "name": clean_name,
                        "raw_name": raw_name,
                        "lba": lba,
                        "byte_offset": lba * self.SECTOR_SIZE,
                        "size": size
                    }

                offset += length

        return self.files_lba

    def extract_core_files(self, output_dir: str, logger: Optional[Callable] = None, progress_fn: Optional[Callable] = None) -> Dict[str, str]:
        """Extracts essential PS2 files (ELF, DDT, IMG, SYSTEM.CNF) with live progress reporting."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        if not self.files_lba:
            self.scan_iso()

        extracted = {}
        targets = [fname for fname in self.files_lba if fname.startswith("SLES_") or fname.startswith("SLUS_") or fname in ("DDS3.DDT", "DDS3.IMG", "SYSTEM.CNF")]
        total_targets = len(targets)

        with open(self.iso_path, "rb") as f:
            for idx, fname in enumerate(targets):
                meta = self.files_lba[fname]
                dest = out_path / fname
                f.seek(meta["byte_offset"])
                
                if logger:
                    logger(f"Extraction : {fname} ({(meta['size']/1024/1024):.2f} Mo)...", "info")

                # Read in 16MB chunks for high-speed file copying
                chunk_size = 16 * 1024 * 1024
                remaining = meta["size"]
                copied = 0
                
                with open(dest, "wb") as f_out:
                    while remaining > 0:
                        to_read = min(remaining, chunk_size)
                        buf = f.read(to_read)
                        if not buf:
                            break
                        f_out.write(buf)
                        copied += len(buf)
                        remaining -= len(buf)

                        if progress_fn and meta["size"] > 0:
                            file_pct = copied / meta["size"]
                            overall_pct = (idx + file_pct) / total_targets
                            progress_fn(overall_pct, fname)

                extracted[fname] = str(dest)
                if logger:
                    logger(f"V {fname} extrait avec succÃ¨s !", "success")

                extracted[fname] = str(dest)
                if logger:
                    logger(f"V {fname} extrait avec succÃ¨s !", "success")

        return extracted

    def rebuild_iso(self, extracted_dir: str, out_iso_path: str, logger: Optional[Callable] = None, progress_fn: Optional[Callable] = None):
        """Rebuilds a new PS2 ISO using the modified files from extracted_dir."""
        try:
            import pycdlib
        except ImportError:
            if logger:
                logger("ERREUR: Le module 'pycdlib' n'est pas installÃ©. (pip install pycdlib)", "error")
            return

        if logger:
            logger(f"Ouverture de l'ISO originale pour reconstruction...", "info")

        iso = pycdlib.PyCdlib()
        iso.open(str(self.iso_path))

        out_root = Path(extracted_dir)
        
        # Files to inject
        targets = [fname for fname in self.files_lba if fname.startswith("SLES_") or fname.startswith("SLUS_") or fname in ("DDS3.DDT", "DDS3.IMG", "SYSTEM.CNF")]
        total = len(targets)
        
        for i, fname in enumerate(targets):
            mod_path = out_root / fname
            if mod_path.exists():
                iso_file_path = f"/{fname};1"
                try:
                    iso.rm_file(file_path=iso_file_path)
                except pycdlib.pycdlibexception.PyCdlibInvalidInput:
                    pass # might not exist exactly with this name
                
                if logger:
                    logger(f"Injection de {fname} modifiÃ©...", "info")
                iso.add_file(str(mod_path), iso_file_path)
            
            if progress_fn and total > 0:
                progress_fn((i + 1) / total, fname)

        if logger:
            logger("Ã‰criture de la nouvelle ISO (cela peut prendre quelques minutes)...", "info")
        
        iso.write(out_iso_path)
        iso.close()

        if logger:
            logger(f"ISO reconstruite avec succÃ¨s : {out_iso_path}", "success")

