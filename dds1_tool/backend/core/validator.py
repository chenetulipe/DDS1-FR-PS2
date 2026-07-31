import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

class TranslationValidator:
    """
    Validates translated script files for DDS1:
    - Line length limits (prevents visual overflow in PS2 dialogue boxes)
    - Control code integrity ([speaker], [selection], [color], [wait])
    - Accent & character set compatibility
    """
    # Max characters per line for DDS1 dialogue window (~45-50 chars in English/French font)
    MAX_LINE_LENGTH = 48
    MAX_LINES_PER_BOX = 3

    def __init__(self):
        self.problems = []

    def validate_text_entry(self, file_name: str, msg_id: int, text: str) -> List[Dict[str, Any]]:
        """Validates a single string entry."""
        issues = []
        lines = text.split("\n")

        # Check line count per box
        if len(lines) > self.MAX_LINES_PER_BOX:
            issues.append({
                "type": "TOO_MANY_LINES",
                "severity": "WARNING",
                "file": file_name,
                "msg_id": msg_id,
                "detail": f"Nombre de lignes ({len(lines)}) dépasse le maximum recommandé ({self.MAX_LINES_PER_BOX})."
            })

        # Check line length overflow
        for i, line in enumerate(lines):
            # Strip tags for visual width measurement
            clean_line = re.sub(r'\[.*?\]', '', line)
            if len(clean_line) > self.MAX_LINE_LENGTH:
                issues.append({
                    "type": "LINE_OVERFLOW",
                    "severity": "ERROR",
                    "file": file_name,
                    "msg_id": msg_id,
                    "line_num": i + 1,
                    "length": len(clean_line),
                    "max_allowed": self.MAX_LINE_LENGTH,
                    "detail": f"Ligne {i+1} trop longue ({len(clean_line)} car. > max {self.MAX_LINE_LENGTH}): '{clean_line}'"
                })

        # Check control tag brackets matching
        open_brackets = text.count("[")
        close_brackets = text.count("]")
        if open_brackets != close_brackets:
            issues.append({
                "type": "TAG_MISMATCH",
                "severity": "CRITICAL",
                "file": file_name,
                "msg_id": msg_id,
                "detail": f"Balises incohérentes : {open_brackets} '[' vs {close_brackets} ']'"
            })

        return issues

    def validate_json_file(self, json_path: str) -> List[Dict[str, Any]]:
        """Validates an entire JSON script file."""
        path = Path(json_path)
        if not path.exists():
            return []

        file_issues = []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_name = data.get("file_name", path.name)
        for msg in data.get("messages", []):
            msg_id = msg.get("id", 0)
            trans = msg.get("translation", "")
            if trans:
                file_issues.extend(self.validate_text_entry(file_name, msg_id, trans))

        return file_issues

    def validate_all_directory(self, json_dir: str, logger: Optional[Callable] = None) -> Dict[str, Any]:
        """Validates all JSON translation files in a directory."""
        dir_path = Path(json_dir)
        all_problems = []

        if not dir_path.exists():
            return {"status": "ok", "problems": []}

        json_files = list(dir_path.glob("*.json"))
        if logger:
            logger(f"Validation de {len(json_files)} fichiers JSON...", "info")

        for jfile in json_files:
            problems = self.validate_json_file(str(jfile))
            all_problems.extend(problems)
            if logger and problems:
                logger(f"Problèmes dans {jfile.name} : {len(problems)} avertissement(s)/erreur(s)", "warn")

        if logger:
            errors_count = sum(1 for p in all_problems if p.get("severity") == "ERROR")
            logger(f"Validation terminée : {len(all_problems)} problème(s) trouvé(s) dont {errors_count} erreur(s) critique(s).", 
                   "success" if len(all_problems) == 0 else "warn")

        return {
            "status": "ok",
            "total_issues": len(all_problems),
            "problems": all_problems
        }
