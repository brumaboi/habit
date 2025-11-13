from __future__ import annotations
import os, sys, json, subprocess, traceback
from pathlib import Path
from datetime import date, timedelta
from datetime import datetime

# ---------- logging & safe message box (no tkinter required) ----------
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "HabitTray"
APP_DIR.mkdir(parents=True, exist_ok=True)
LOG = APP_DIR / "habit_tray.log"

def log(msg: str) -> None:
    LOG.write_text((LOG.read_text(encoding="utf-8") if LOG.exists() else "") + msg + "\n", encoding="utf-8")

def msgbox(title: str, text: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x00000040)
    except Exception:
        pass

# ---------- data & config ----------
DB_FILE = APP_DIR / "habits.json"
CFG_FILE = APP_DIR / "settings.json"

DEFAULT_CFG = {"retention_days": None}

def load_cfg() -> dict:
    if not CFG_FILE.exists():
        save_cfg(DEFAULT_CFG)
        return DEFAULT_CFG.copy()
    try:
        cfg = json.loads(CFG_FILE.read_text(encoding="utf-8"))
        rd = cfg.get("retention_days")
        return {"retention_days": rd if (isinstance(rd, int) and rd >= 1) else None}
    except Exception:
        return DEFAULT_CFG.copy()

def save_cfg(cfg: dict) -> None:
    CFG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

def load_db() -> dict[str, list[str]]:
    if not DB_FILE.exists():
        save_db({})
        return {}
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_db(db: dict[str, list[str]]) -> None:
    DB_FILE.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")

def prune_inplace(db: dict[str, list[str]], retention_days: int | None) -> bool:
    if not retention_days or retention_days < 1:
        return False
    cutoff = date.today() - timedelta(days=retention_days - 1)
    changed = False
    for k, dates in list(db.items()):
        keep = []
        for s in dates:
            try:
                d = date.fromisoformat(s)
            except ValueError:
                changed = True
                continue
            if d >= cutoff:
                keep.append(s)
            else:
                changed = True
        db[k] = keep
    return changed

def apply_retention() -> None:
    cfg = load_cfg()
    db = load_db()
    if prune_inplace(db, cfg["retention_days"]):
        save_db(db)

# ---------- domain ----------
def habits() -> list[str]:
    return sorted(load_db().keys())

def is_done_today(name: str) -> bool:
    db = load_db()
    today = date.today().isoformat()
    return today in db.get(name, [])

def add_habit(name: str) -> None:
    name = (name or "").strip()
    if not name:
        return
    db = load_db()
    db.setdefault(name, [])
    prune_inplace(db, load_cfg()["retention_days"])
    save_db(db)

def mark_done(name: str) -> None:
    db = load_db()
    if name not in db:
        return
    today = date.today().isoformat()
    if today not in db[name]:
        db[name].append(today)
        db[name].sort()
    prune_inplace(db, load_cfg()["retention_days"])
    save_db(db)

if __name__ == "__main__":
    main()
