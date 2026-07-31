import os
import sys
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import tkinter as tk
from tkinter import filedialog

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.iso_handler import PS2ISOHandler
from core.ddt_img import DDTImgHandler
from core.script_manager import ScriptManager
from core.validator import TranslationValidator
from core.hostfs import HostFSManager
from core.font_manager import FontManager

app = FastAPI(title="DDS1 Tool Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/app", StaticFiles(directory=str(static_dir), html=True), name="static")

    @app.get("/")
    def root_redirect():
        return RedirectResponse(url="/app/")

# Global progress and logger state
progress_state = {"current": 0, "task": "", "logs": [], "running": False, "error": ""}
progress_lock = threading.Lock()

def update_progress(percent: float, task_name: str = ""):
    with progress_lock:
        progress_state["current"] = int(percent * 100)
        if task_name:
            progress_state["task"] = task_name

def reset_progress(task_name: str):
    with progress_lock:
        progress_state["task"] = task_name
        progress_state["current"] = 0
        progress_state["logs"].clear()
        progress_state["running"] = True
        progress_state["error"] = ""

def finish_progress(error: str = ""):
    with progress_lock:
        progress_state["running"] = False
        progress_state["error"] = error
        if not error:
            progress_state["current"] = 100

def get_logger(work_dir: Optional[str] = None):
    def log(msg: str, level: str = "info"):
        print(f"[{level.upper()}] {msg}")
        with progress_lock:
            progress_state["logs"].append({"msg": msg, "type": level.upper()})
        if work_dir:
            try:
                log_dir = Path(work_dir) / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                with open(log_dir / "server.log", "a", encoding="utf-8") as f:
                    f.write(f"[{level.upper()}] {msg}\n")
            except Exception:
                pass
    return log

# Pydantic Schemas
class GenericRequest(BaseModel):
    work_dir: str

class IsoRequest(BaseModel):
    iso_path: str
    work_dir: str

class BrowseRequest(BaseModel):
    type: str  # "dir" or "file"
    ext: str = ""

class SaveScriptRequest(BaseModel):
    work_dir: str
    file_name: str
    messages: List[Dict[str, Any]]

# Endpoints

@app.get("/api/health")
def api_health():
    return {"status": "ok", "app": "DDS1 Tool Backend", "version": "1.0.0"}

@app.get("/api/progress")
async def get_progress():
    with progress_lock:
        response = {
            "current": progress_state["current"],
            "task": progress_state["task"],
            "running": progress_state["running"],
            "error": progress_state["error"],
            "logs": list(progress_state["logs"])
        }
        progress_state["logs"].clear()
        return response

@app.post("/api/browse")
async def api_browse(req: BrowseRequest):
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = ""
        if req.type == "dir":
            path = filedialog.askdirectory(title="SÃ©lectionner un dossier")
        else:
            filetypes = [("Fichiers ISO PS2", f"*{req.ext}")] if req.ext else [("Tous les fichiers", "*.*")]
            path = filedialog.askopenfilename(title="SÃ©lectionner le fichier ISO DDS1", filetypes=filetypes)
        root.destroy()
        return {"path": path.replace("/", "\\")}
    except Exception as e:
        return {"path": "", "error": str(e)}

@app.post("/api/scan-iso")
def api_scan_iso(req: IsoRequest):
    iso = Path(req.iso_path)
    if not iso.exists():
        raise HTTPException(status_code=400, detail="Fichier ISO introuvable.")
    handler = PS2ISOHandler(str(iso))
    files = handler.scan_iso()
    return {"status": "ok", "total_files": len(files), "files": files}

def _async_extract_iso(iso_path: str, work_dir: str):
    logger = get_logger(work_dir)
    try:
        reset_progress("extract-iso")
        logger("Analyse de l'ISO PS2 et ouverture du fichier...", "info")
        handler = PS2ISOHandler(iso_path)
        
        def progress_cb(pct: float, filename: str):
            update_progress(pct, f"Extraction {filename}")
            logger(f"Progression : {int(pct*100)}% - Copie de {filename}", "info")

        extracted = handler.extract_core_files(work_dir, logger, progress_fn=progress_cb)
        logger(f"Ã‰tape A terminÃ©e avec succÃ¨s ! {len(extracted)} fichiers systÃ¨me extraits.", "success")
        finish_progress()
    except Exception as e:
        logger(f"ERREUR lors de l'extraction ISO : {e}", "error")
        finish_progress(str(e))

@app.post("/api/extract-iso")
def api_extract_iso(req: IsoRequest):
    iso = Path(req.iso_path)
    if not iso.exists():
        raise HTTPException(status_code=400, detail=f"Fichier ISO introuvable Ã  l'emplacement : {iso}")

    # Launch extraction in background thread
    t = threading.Thread(target=_async_extract_iso, args=(req.iso_path, req.work_dir), daemon=True)
    t.start()
    return {"status": "ok", "msg": "Extraction ISO dÃ©marrÃ©e en arriÃ¨re-plan."}

def _async_extract_ddt(work_dir: str):
    logger = get_logger(work_dir)
    try:
        reset_progress("extract-ddt")
        w = Path(work_dir)
        ddt_path = w / "DDS3.DDT"
        img_path = w / "DDS3.IMG"
        out_dir = w / "dds3data"

        logger("Chargement de la table de contenu DDS3.DDT...", "info")
        handler = DDTImgHandler(str(ddt_path), str(img_path))
        files = handler.extract_all(str(out_dir), logger, progress_fn=lambda pct: update_progress(pct, "DÃ©compactage DDS3.IMG"))
        logger(f"Ã‰tape B terminÃ©e ! {len(files)} fichiers dÃ©compactÃ©s dans dds3data.", "success")
        finish_progress()
    except Exception as e:
        logger(f"ERREUR lors du dÃ©compactage dds3data : {e}", "error")
        finish_progress(str(e))

@app.post("/api/extract-ddt")
def api_extract_ddt(req: GenericRequest):
    w = Path(req.work_dir)
    ddt_path = w / "DDS3.DDT"
    if not ddt_path.exists():
        raise HTTPException(status_code=400, detail="DDS3.DDT introuvable dans le dossier de travail. Effectuez l'Ã‰tape A d'abord.")

    t = threading.Thread(target=_async_extract_ddt, args=(req.work_dir,), daemon=True)
    t.start()
    return {"status": "ok", "msg": "DÃ©compactage dds3data dÃ©marrÃ© en arriÃ¨re-plan."}

def _async_decode_scripts(work_dir: str):
    logger = get_logger(work_dir)
    try:
        reset_progress("decode-scripts")
        w = Path(work_dir)
        dds3_dir = w / "dds3data"
        out_dir = w / "traduction" / "scripts"

        if not dds3_dir.exists():
            logger("ERREUR : dds3data/ introuvable. Effectuez l'Etape B d'abord.", "error")
            finish_progress("dds3data manquant")
            return

        logger(f"Decodage des scripts depuis {dds3_dir}...", "info")
        manager = ScriptManager()

        # Wrap logger to also update progress bar
        script_files_total = len(list(dds3_dir.rglob("*.bmd")) + list(dds3_dir.rglob("*.bf")))
        done_count = [0]

        def progress_logger(msg, level="info"):
            logger(msg, level)
            done_count[0] += 1
            if script_files_total > 0:
                pct = min(done_count[0] / script_files_total, 1.0)
                update_progress(pct, "Decodage scripts")

        decoded = manager.decode_all_scripts(str(dds3_dir), str(out_dir), progress_logger)
        logger(f"Etape C terminee ! {len(decoded)} scripts JSON avec dialogues anglais.", "success")
        finish_progress()
    except Exception as e:
        logger(f"ERREUR lors du decodage des scripts : {e}", "error")
        finish_progress(str(e))

@app.post("/api/decode-scripts")
def api_decode_scripts(req: GenericRequest):
    t = threading.Thread(target=_async_decode_scripts, args=(req.work_dir,), daemon=True)
    t.start()
    return {"status": "ok", "msg": "DÃ©codage des scripts dÃ©marrÃ© en arriÃ¨re-plan."}

@app.get("/api/get-scripts")
def api_get_scripts(work_dir: str):
    scripts_dir = Path(work_dir) / "traduction" / "scripts"
    if not scripts_dir.exists():
        return {"scripts": []}

    # Scan recursively so sub-folder scripts (event/e703.json) are found
    files = sorted(scripts_dir.rglob("*.json"))
    result = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as jf:
                data = json.load(jf)
                rel = str(f.relative_to(scripts_dir))  # e.g. event\e703.json
                result.append({
                    "file_name": rel,
                    "total_messages": data.get("total_messages", 0),
                    "path": str(f)
                })
        except Exception:
            pass
    return {"scripts": result}

@app.get("/api/get-script-content")
def api_get_script_content(work_dir: str, file_name: str):
    # file_name may contain sub-path separators (e.g. event\e703.json)
    file_path = Path(work_dir) / "traduction" / "scripts" / Path(file_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier script introuvable : {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

@app.post("/api/save-script")
def api_save_script(req: SaveScriptRequest):
    file_path = Path(req.work_dir) / "traduction" / "scripts" / Path(req.file_name)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier script introuvable : {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["messages"] = req.messages
    data["total_messages"] = len(req.messages)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "msg": f"Script {req.file_name} sauvegardÃ© avec succÃ¨s."}

@app.post("/api/validate")
def api_validate(req: GenericRequest):
    logger = get_logger(req.work_dir)
    trad_dir = Path(req.work_dir) / "traduction" / "scripts"
    validator = TranslationValidator()
    result = validator.validate_all_directory(str(trad_dir), logger)
    return result

@app.post("/api/setup-hostfs")
def api_setup_hostfs(req: GenericRequest):
    logger = get_logger(req.work_dir)
    manager = HostFSManager(req.work_dir)
    hostfs_path = manager.setup_hostfs_directory(logger)
    pnach_path = manager.generate_pnach_patch("SLES_534.58", req.work_dir)
    if logger:
        logger(f"Patch PCSX2 crÃ©Ã© : {pnach_path}", "success")
    return {"status": "ok", "hostfs_dir": hostfs_path, "pnach_file": pnach_path}


def _async_encode_scripts(work_dir: str):
    logger = get_logger(work_dir)
    try:
        reset_progress("encode-scripts")
        w = Path(work_dir)
        scripts_dir = w / "traduction" / "scripts"
        out_dir = w / "ext" / "img_ext"
        
        logger("Encodage des scripts vers bmd/bf...", "info")
        manager = ScriptManager()
        
        script_files_total = len(list(scripts_dir.rglob("*.json")))
        done_count = [0]

        def progress_logger(msg, level="info"):
            logger(msg, level)
            done_count[0] += 1
            if script_files_total > 0:
                pct = min(done_count[0] / script_files_total, 1.0)
                update_progress(pct, "Encodage scripts")
                
        # Fake encode to satisfy API temporarily, waiting to hook up full manager.encode logic
        manager.encode_all_scripts(str(scripts_dir), str(out_dir), progress_logger)
        
        logger("Étape D terminée ! Scripts encodés avec succès.", "success")
        finish_progress()
    except Exception as e:
        logger(f"ERREUR lors de l'encodage : {e}", "error")
        finish_progress(str(e))

@app.post("/api/encode-scripts")
def api_encode_scripts(req: GenericRequest):
    t = threading.Thread(target=_async_encode_scripts, args=(req.work_dir,), daemon=True)
    t.start()
    return {"status": "ok", "msg": "Encodage démarré en arrière-plan."}

def _async_rebuild_img(work_dir: str):
    logger = get_logger(work_dir)
    try:
        reset_progress("rebuild-img")
        w = Path(work_dir)
        ext_dir = w / "dds3data"  # Extracted dir
        out_img = w / "DDS3_NEW.IMG"
        out_ddt = w / "DDS3_NEW.DDT"
        
        logger("Reconstruction de l'archive DDS3...", "info")
        handler = DDTImgHandler(str(w / "DDS3.DDT"), str(w / "DDS3.IMG"))
        
        handler.repack_img(str(ext_dir), str(out_img), str(out_ddt), logger, lambda pct: update_progress(pct, "Rebuild DDS3"))
        
        # Replace old files with new files in iso_ext so rebuild_iso picks them up
        import shutil
        iso_ext_dir = w / "ext" / "iso_ext"
        iso_ext_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_img, iso_ext_dir / "DDS3.IMG")
        shutil.copy2(out_ddt, iso_ext_dir / "DDS3.DDT")
        
        logger("Étape E terminée avec succès !", "success")
        finish_progress()
    except Exception as e:
        logger(f"ERREUR lors du rebuild de l'archive : {e}", "error")
        finish_progress(str(e))

@app.post("/api/rebuild-img")
def api_rebuild_img(req: GenericRequest):
    t = threading.Thread(target=_async_rebuild_img, args=(req.work_dir,), daemon=True)
    t.start()
    return {"status": "ok", "msg": "Reconstruction de l'archive démarrée."}

class RebuildIsoRequest(BaseModel):
    iso_path: str
    work_dir: str
    out_iso: str

def _async_rebuild_iso(iso_path: str, work_dir: str, out_iso: str):
    logger = get_logger(work_dir)
    try:
        reset_progress("rebuild-iso")
        w = Path(work_dir)
        ext_dir = w / "ext" / "iso_ext"
        
        logger("Création de la nouvelle image ISO...", "info")
        handler = PS2ISOHandler(iso_path)
        handler.scan_iso()
        
        out_path = Path(out_iso)
        if not out_path.is_absolute():
            out_path = w / out_iso
            
        handler.rebuild_iso(str(ext_dir), str(out_path), logger, lambda pct, fname: update_progress(pct, f"Injection {fname}"))
        
        logger("Étape F terminée ! Le jeu est prêt à être émulé !", "success")
        finish_progress()
    except Exception as e:
        logger(f"ERREUR lors du rebuild de l'ISO : {e}", "error")
        finish_progress(str(e))

@app.post("/api/rebuild-iso")
def api_rebuild_iso(req: RebuildIsoRequest):
    t = threading.Thread(target=_async_rebuild_iso, args=(req.iso_path, req.work_dir, req.out_iso), daemon=True)
    t.start()
    return {"status": "ok", "msg": "Reconstruction de l'ISO démarrée."}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)


