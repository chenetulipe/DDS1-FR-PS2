import os
import json
import re
import struct
import subprocess
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

class ScriptManager:
    """
    Decodes Atlus PS2 BMD (MessageScript) / BF (FlowScript) files into JSON,
    and encodes modified JSON back to binary script files using AtlusScriptCompiler.
    """
    def __init__(self):
        # Character mapping table for DDS1 French localizations
        self.char_map = {
            "é": "[x 0x82 0xA0]",
            "è": "[x 0x82 0xA1]",
            "à": "[x 0x82 0xA2]",
            "ç": "[x 0x82 0xA3]",
            "â": "[x 0x82 0xA4]",
            "ê": "[x 0x82 0xA5]",
            "î": "[x 0x82 0xA6]",
            "ô": "[x 0x82 0xA7]",
            "û": "[x 0x82 0xA8]",
            "ù": "[x 0x82 0xA9]",
            "ë": "[x 0x82 0xAA]",
            "ï": "[x 0x82 0xAB]",
            "ü": "[x 0x82 0xAC]",
        }
        
        # Tools path
        self.tools_dir = Path(os.path.dirname(__file__)).parent / "tools"
        self.dotnet_exe = self.tools_dir / "dotnet" / "dotnet.exe"
        self.compiler_dll = self.tools_dir / "AtlusScriptCompiler.dll"

    def decode_bmd_file(self, path_str: str) -> Dict[str, Any]:
        """Decompiles a .bmd or .bf file to .msg using AtlusScriptCompiler, then parses it."""
        path = Path(path_str).resolve()
        if not path.exists():
            return {"file_name": path.name, "total_messages": 0, "messages": []}

        is_bf = path.suffix.lower() == ".bf"

        # Output path is always input filename + .msg (e.g. f021.bf.msg or mes_data.bmd.msg)
        msg_file = path.with_name(path.name + ".msg")

        cmd = [str(self.dotnet_exe), str(self.compiler_dll), str(path),
               "-Decompile", "-Library", "DDS"]

        try:
            subprocess.run(cmd, cwd=str(self.tools_dir),
                           capture_output=True, check=True, timeout=60)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return {"file_name": path.name, "total_messages": 0, "messages": []}

        if not msg_file.exists():
            return {"file_name": path.name, "total_messages": 0, "messages": []}

        # --- Parse .msg file ---
        try:
            content = msg_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {"file_name": path.name, "total_messages": 0, "messages": []}

        # Match [msg NAME] ... or [sel NAME top] ... blocks, handling nested brackets in headers
        pattern = re.compile(
            r'^\[(msg|sel)\s+([A-Za-z0-9_]+)[^\n]*\]\s*(.*?)(?=^\[(?:msg|sel)\s|\Z)',
            re.DOTALL | re.MULTILINE
        )

        messages = []
        msg_id = 0

        for match in pattern.finditer(content):
            block_type = match.group(1)   # "msg" or "sel"
            msg_name   = match.group(2).strip()
            raw_text   = match.group(3).strip()

            if not raw_text:
                continue

            # Collect individual lines within the block
            # Each line is separated by \n in the source; each ends with [e]
            line_texts = re.split(r'\n+', raw_text)
            display_lines = []

            for line in line_texts:
                line = line.strip()
                if not line:
                    continue

                # Check if line has ANY readable English (printable ASCII letters)
                # Strip control codes ([f ...], [n], [e], [sel ...]) first
                readable = re.sub(r'\[[^\]]+\]', '', line).strip()

                # Skip purely Japanese lines: only [x 0x8x/0x9x ...] bytes present
                jp_bytes = re.findall(r'\[x\s+(0x[89a-fA-F][0-9a-fA-F])\s', line)
                has_jp   = len(jp_bytes) > 0

                # Count actual readable ASCII characters
                ascii_chars = sum(1 for c in readable if c.isascii() and c.isprintable())

                if ascii_chars < 3 and has_jp:
                    # Purely Japanese – skip
                    continue

                # Apply character mapping (accented chars)
                for char, hex_tag in self.char_map.items():
                    line = line.replace(hex_tag, char)

                # Remove pure control codes from display text
                display = re.sub(r'\[f\s[^\]]+\]', '', line)  # remove [f ...] font tags
                display = re.sub(r'\[n\]', '\n', display)      # newlines
                display = re.sub(r'\[e\]', '', display)        # end marker
                display = re.sub(r'\[s\s[^\]]+\]', '', display)  # other tags
                display = display.strip()

                if display:
                    display_lines.append(display)

            if not display_lines:
                continue

            combined = "\n".join(display_lines)
            
            # Infer speaker name from offset (e.g. gale_01 -> Gale, heat_01 -> Heat)
            speaker_name = ""
            lower_name = msg_name.lower()
            if lower_name.startswith("gale"): speaker_name = "Gale"
            elif lower_name.startswith("heat"): speaker_name = "Heat"
            elif lower_name.startswith("arujila") or lower_name.startswith("argilla"): speaker_name = "Argilla"
            elif lower_name.startswith("ciero") or lower_name.startswith("cielo"): speaker_name = "Cielo"
            elif lower_name.startswith("sera"): speaker_name = "Sera"
            elif lower_name.startswith("surf"): speaker_name = "Surf"
            elif lower_name.startswith("jinana"): speaker_name = "Jinana"
            elif lower_name.startswith("harley"): speaker_name = "Harley"
            elif lower_name.startswith("mick"): speaker_name = "Mick"
            elif lower_name.startswith("lupa"): speaker_name = "Lupa"
            elif lower_name.startswith("bat"): speaker_name = "Bat"
            elif lower_name.startswith("angel"): speaker_name = "Angel"
            elif lower_name.startswith("npc"): speaker_name = "NPC"

            if block_type == "sel":
                choix_orig = combined.split("\n")
                choix_fr = [""] * len(choix_orig)
                messages.append({
                    "id":          msg_id,
                    "offset":      msg_name,
                    "block_type":  block_type,
                    "nom_orig":    speaker_name,
                    "nom_fr":      "",
                    "texte_orig":  combined,
                    "choix_orig":  choix_orig,
                    "texte_fr":    "",
                    "choix_fr":    choix_fr,
                    "notes":       ""
                })
            else:
                messages.append({
                    "id":          msg_id,
                    "offset":      msg_name,
                    "block_type":  block_type,
                    "nom_orig":    speaker_name,
                    "nom_fr":      "",
                    "texte_orig":  combined,
                    "texte_fr":    "",
                    "notes":       ""
                })
            msg_id += 1

        # Cleanup generated files
        for cleanup in [msg_file, path.with_name(path.name + ".msg.h"),
                        path.with_name(path.name + ".flow")]:
            try:
                if cleanup.exists():
                    cleanup.unlink()
            except Exception:
                pass

        return {
            "file_name":      path.name,
            "original_path":  "",
            "total_messages": len(messages),
            "messages":       messages
        }

    def decode_all_scripts(self, input_dir: str, output_dir: str, logger: Optional[Callable] = None) -> List[str]:
        """
        Batch decompiles all .bmd / .bf files in input_dir (recursively) to JSON files in output_dir.
        Also unpacks .LB archives (field/event libraries) to extract embedded .bmd dialogue files.
        """
        import tempfile, shutil
        in_path = Path(input_dir)
        out_path = Path(output_dir)

        # Clean output dir
        if out_path.exists():
            for child in out_path.rglob("*.json"):
                try:
                    child.unlink()
                except Exception:
                    pass
        out_path.mkdir(parents=True, exist_ok=True)

        decoded_files = []
        decoded_lock = __import__('threading').Lock()

        # --- Phase 1: direct .bmd / .bf files ---
        script_files = list(in_path.rglob("*.bmd")) + list(in_path.rglob("*.bf"))
        total = len(script_files)
        if logger:
            logger(f"Phase 1 : {total} scripts à décoder...", "info")

        for idx, fpath in enumerate(script_files, 1):
            try:
                decoded_data = self.decode_bmd_file(str(fpath))
            except Exception:
                decoded_data = {"total_messages": 0, "messages": []}

            n = decoded_data.get("total_messages", 0)
            if n > 0:
                rel = fpath.relative_to(in_path)
                decoded_data["original_path"] = rel.as_posix()
                
                parts = list(rel.parts)
                if parts[0] == 'event': cat = 'Cinematiques'
                elif parts[0] == 'fld': cat = 'Exploration'
                elif parts[0] == 'facility': cat = 'Boutiques_Menus'
                else: cat = 'Divers'
                
                basename = rel.with_suffix(".json").name
                if 'mes_data' in basename and len(parts) > 1:
                    basename = f"{parts[-2]}_{basename}"
                    
                json_dest = out_path / cat / basename
                json_dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with open(json_dest, "w", encoding="utf-8") as out_json:
                        json.dump(decoded_data, out_json, ensure_ascii=False, indent=2)
                    decoded_files.append(str(json_dest))
                    if logger:
                        logger(f"[{idx}/{total}] {fpath.name} -> {n} msgs extraits ({basename})", "info")
                except Exception:
                    pass
            else:
                if logger and idx % 20 == 0:
                    logger(f"[{idx}/{total}] progression...", "info")

        if logger:
            logger(f"Phase 1 terminee : {len(decoded_files)}/{total} fichiers avec dialogues anglais.", "success")




        # --- Phase 2: .LB archives (field libraries containing embedded .bmd) ---
        try:
            from core.lb_handler import LBHandler
        except ImportError:
            try:
                import sys
                sys.path.insert(0, str(Path(__file__).parent))
                from lb_handler import LBHandler
            except ImportError:
                LBHandler = None

        if LBHandler is not None:
            lb_files = list(in_path.rglob("*.LB")) + list(in_path.rglob("*.lb"))
            if logger:
                logger(f"Phase 2 : {len(lb_files)} archives .LB à scanner pour dialogues...", "info")

            tmp_root = Path(tempfile.mkdtemp(prefix="dds1_lb_"))
            lb_decoded = 0
            try:
                for lb_path in lb_files:
                    try:
                        handler = LBHandler(str(lb_path))
                        entries = handler.parse()
                        # Only extract .bmd entries
                        bmd_entries = [e for e in entries if e.extension.lower() == 'bmd']
                        if not bmd_entries:
                            continue

                        # Make a temp dir for this LB's extracted files
                        lb_tmp = tmp_root / lb_path.stem
                        lb_tmp.mkdir(parents=True, exist_ok=True)

                        extracted = handler.extract_all_by_extension(str(lb_tmp), ['bmd'], logger)

                        for uid, bmd_dest in extracted:
                            try:
                                decoded_data = self.decode_bmd_file(str(bmd_dest))
                                if decoded_data["total_messages"] > 0:
                                    # Output path: lb folder structure + lb name + user_id
                                    rel_lb = lb_path.relative_to(in_path)
                                    decoded_data["original_path"] = f"{rel_lb.as_posix()}#{uid}"
                                    
                                    parts = list(rel_lb.parts)
                                    if parts[0] == 'event': cat = 'Cinematiques'
                                    elif parts[0] == 'fld': cat = 'Exploration'
                                    elif parts[0] == 'facility': cat = 'Boutiques_Menus'
                                    else: cat = 'Divers'
                                    
                                    json_dest = out_path / cat / f"{lb_path.stem}_{uid}.json"
                                    json_dest.parent.mkdir(parents=True, exist_ok=True)
                                    # Tag the source
                                    decoded_data["file_name"] = f"{lb_path.name}#{uid}.bmd"
                                    with open(json_dest, "w", encoding="utf-8") as out_json:
                                        json.dump(decoded_data, out_json, ensure_ascii=False, indent=2)
                                    decoded_files.append(str(json_dest))
                                    lb_decoded += 1
                            except Exception:
                                pass
                    except Exception:
                        pass
            finally:
                try:
                    shutil.rmtree(str(tmp_root), ignore_errors=True)
                except Exception:
                    pass

            if logger:
                logger(f"Phase 2 terminée : {lb_decoded} scripts extraits des archives .LB.", "info")

        if logger:
            logger(f"Décodage terminé ! {len(decoded_files)} fichiers JSON générés au total.", "success")
        return decoded_files



    def encode_json_to_bmd(self, json_path: str, orig_bmd_path: str, out_bmd_path: str) -> bool:
        """Injects translated JSON strings back into binary .bmd file via AtlusScriptCompiler."""
        j_path = Path(json_path)
        orig_path = Path(orig_bmd_path)
        out_path = Path(out_bmd_path)

        if not j_path.exists() or not orig_path.exists():
            return False

        # 1. Decompile original to MSG
        msg_file = out_path.with_suffix(orig_path.suffix + ".msg")
        cmd_dec = [str(self.dotnet_exe), str(self.compiler_dll), str(orig_path), "-Decompile", "-Library", "DDS", "-Out", str(msg_file)]
        subprocess.run(cmd_dec, cwd=str(self.tools_dir), capture_output=True)

        if not msg_file.exists():
            return False

        with open(j_path, "r", encoding="utf-8") as jf:
            json_data = json.load(jf)

        with open(msg_file, "r", encoding="utf-8") as mf:
            msg_content = mf.read()

        # 2. Replace blocks in MSG text
        for item in json_data.get("messages", []):
            msg_name = item.get("offset", "")
            trans_text = item.get("texte_fr", "")
            
            # Ne remplacer que si la traduction existe et est différente de l'original
            if not trans_text.strip() or trans_text == item.get("texte_orig", ""):
                continue
                
            # Apply char mapping to insert Ghostlight hex tags
            for char, hex_tag in self.char_map.items():
                trans_text = trans_text.replace(char, hex_tag)
                
            # Regex to find the block and replace its content
            pattern = re.compile(r'(\[msg\s+' + re.escape(msg_name) + r'\s*(?:\[\d+\])?\])(.*?)((?=\[msg)|$)', re.DOTALL)
            msg_content = pattern.sub(r'\1\n' + trans_text + r'\n\3', msg_content)

        with open(msg_file, "w", encoding="utf-8") as mf:
            mf.write(msg_content)

        # 3. Compile MSG to BMD
        cmd_cmp = [str(self.dotnet_exe), str(self.compiler_dll), str(msg_file), "-Compile", "-Library", "DDS", "-OutFormat", "V1", "-Out", str(out_path)]
        subprocess.run(cmd_cmp, cwd=str(self.tools_dir), capture_output=True)

        # Cleanup
        try:
            msg_file.unlink()
            msg_file.with_suffix(".msg.h").unlink()
        except:
            pass

        return out_path.exists()

    def encode_all_scripts(self, input_json_dir: str, dds3data_dir: str, logger: Optional[Callable] = None) -> List[str]:
        """Encodes all JSON scripts in input_json_dir back into binary .bmd / .bf files inside dds3data_dir."""
        in_dir = Path(input_json_dir)
        orig_dir = Path(dds3data_dir)
        
        if not in_dir.exists():
            if logger:
                logger(f"Dossier JSON introuvable : {in_dir}", "error")
            return []

        json_files = list(in_dir.rglob("*.json"))
        encoded = []

        if logger:
            logger(f"Encodage de {len(json_files)} fichiers JSON vers {dds3data_dir}...", "info")

        for idx, jf in enumerate(json_files):
            rel_path = jf.relative_to(in_dir)
            matching_orig = None
            
            # Read JSON to get stored original_path
            try:
                with open(jf, "r", encoding="utf-8") as f_json:
                    j_data = json.load(f_json)
                    orig_rel = j_data.get("original_path")
                    if orig_rel:
                        cand = orig_dir / orig_rel
                        if cand.exists():
                            matching_orig = cand
            except Exception:
                pass

            # Fallback if original_path field not present
            if not matching_orig:
                for ext in [".bmd", ".bf"]:
                    cand = orig_dir / rel_path.with_suffix(ext)
                    if cand.exists():
                        matching_orig = cand
                        break

            if not matching_orig:
                if logger:
                    logger(f"Fichier original introuvable pour {rel_path}", "warn")
                continue

            out_bmd = matching_orig  # Overwrite in dds3data directly so repack_img uses it
            res = self.encode_json_to_bmd(str(jf), str(matching_orig), str(out_bmd))
            if res:
                encoded.append(str(out_bmd))
                if logger:
                    logger(f"Encodé : {rel_path}", "info")
            else:
                if logger:
                    logger(f"Échec de l'encodage (ou pas de modification) pour : {rel_path}", "warn")

        if logger:
            logger(f"Encodage terminé ! {len(encoded)} fichiers .bmd/.bf mis à jour.", "success")

        return encoded
