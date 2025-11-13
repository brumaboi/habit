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

# ---------- ensure deps (no tkinter required) ----------
def ensure_deps() -> None:
    try:
        import pystray
        import PIL
        return
    except Exception as e:
        log(f"Deps missing: {e!r}. Installing...")
        msgbox("Habit Tray", "Installing required packages (pystray, Pillow)...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "pystray", "Pillow"])
        except Exception as e2:
            tb = traceback.format_exc()
            log(f"pip install failed: {e2!r}\n{tb}")
            msgbox("Habit Tray - Error", "Failed to install dependencies.\nSee log:\n" + str(LOG))
            raise
        os.execl(sys.executable, sys.executable, *sys.argv)

ensure_deps()

import pystray
from PIL import Image, ImageDraw

try:
    import tkinter as tk
    from tkinter import simpledialog, messagebox
    import queue
    import threading

    _tk_queue: "queue.Queue[tuple]" = queue.Queue()
    _tk_ready = threading.Event()

    def _tk_thread() -> None:
        root = tk.Tk()
        root.withdraw()
        _tk_ready.set()

        def process_queue() -> None:
            try:
                while True:
                    func, args, kwargs, resp_q = _tk_queue.get_nowait()

                    def wrapper(f=func, a=args, kw=kwargs, rq=resp_q):
                        try:
                            kw2 = dict(kw) if kw else {}
                            if 'parent' not in kw2:
                                kw2['parent'] = root
                            res = f(*a, **kw2)
                        except Exception as e:
                            res = (False, str(e))
                        finally:
                            try:
                                rq.put(res)
                            except Exception:
                                pass
                    try:
                        root.after(200, wrapper)
                    except Exception:
                        wrapper()
            except Exception:
                pass
            root.after(100, process_queue)

        root.after(100, process_queue)
        root.mainloop()

    _tk_worker = threading.Thread(target=_tk_thread, daemon=True)
    _tk_worker.start()
    _tk_ready.wait(timeout=5)

    def _call_on_tk(func, *args, **kwargs):
        """Post a callable to the Tk thread and wait for its result."""
        resp_q = queue.Queue()
        _tk_queue.put((func, args, kwargs, resp_q))
        try:
            return resp_q.get(timeout=30)
        except Exception:
            return None

    def prompt_str(title: str, prompt: str, initial: str | None = None) -> str | None:
        try:
            res = _call_on_tk(simpledialog.askstring, title, prompt, initialvalue=initial)
            return res
        except Exception:
            msgbox(title, f"{prompt}\n\n(Tk not available or dialog failed.)")
            return None

    def info(title: str, text: str) -> None:
        try:
            _call_on_tk(messagebox.showinfo, title, text)
        except Exception:
            msgbox(title, text)

    def confirm(title: str, text: str) -> bool:
        try:
            res = _call_on_tk(messagebox.askyesno, title, text)
            return bool(res)
        except Exception:
            msgbox(title, text + "\n\n(Tk not available; assuming No.)")
            return False
except Exception:
    def prompt_str(title: str, prompt: str, initial: str | None = None) -> str | None:
        msgbox(title, f"{prompt}\n\n(Tk not available; cannot prompt.)")
        return None
    def info(title: str, text: str) -> None:
        msgbox(title, text)
    def confirm(title: str, text: str) -> bool:
        msgbox(title, text + "\n\n(Tk not available; assuming No.)")
        return False

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

# ---------- tray ----------
def icon_image():
    im = Image.new("RGBA", (64,64), (0,0,0,0))
    d = ImageDraw.Draw(im)
    d.ellipse((8,8,56,56), fill=(255,130,70,255))
    d.line((20,34,30,44), fill=(255,255,255,255), width=5)
    d.line((30,44,46,24), fill=(255,255,255,255), width=5)
    return im

def retention_label(cfg: dict) -> str:
    rd = cfg.get("retention_days")
    return f"Keep last {rd} days" if isinstance(rd, int) and rd >= 1 else "Keep forever"

def rebuild_menu(icon: pystray.Icon) -> None:
    names = habits()
    if names:
        def _make_done_cb(n):
            def _cb(i, j):
                log(f'done menu clicked: {n!r}')
                return on_done(icon, n)
            return _cb
        done_menu = tuple(pystray.MenuItem(("✓ " if is_done_today(n) else "✗ ") + n, _make_done_cb(n)) for n in names)
    else:
        done_menu = (pystray.MenuItem("No habits yet", lambda i,j: None, enabled=False),)
    cfg = load_cfg()
    icon.menu = pystray.Menu(
        pystray.MenuItem("Add Habit", lambda i,j: on_add(icon)),
        pystray.MenuItem("Mark Done", pystray.Menu(*done_menu)),
        pystray.MenuItem("List Habits", lambda i,j: on_list()),
        pystray.MenuItem(f"Settings: {retention_label(cfg)}", lambda i,j: on_retention(icon)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Reset data…", lambda i,j: on_reset(icon)),
        pystray.MenuItem("Quit", lambda i,j: icon.stop()),
    )
    log('rebuild_menu called')
    icon.update_menu()

def on_add(icon: pystray.Icon) -> None:
    log('on_add invoked')
    name = prompt_str("Habit Tray", "New habit name:")
    if name:
        add_habit(name)
        info("Habit Tray", f"Added: {name}")
        rebuild_menu(icon)

def on_done(icon: pystray.Icon, name: str) -> None:
    log(f'on_done invoked for {name!r}')
    mark_done(name)
    info("Habit Tray", f"Marked done today: {name}")
    try:
        rebuild_menu(icon)
    except Exception:
        pass

def on_list() -> None:
    log('on_list invoked')
    ns = habits()
    if ns:
        lines = [("✓ " if is_done_today(n) else "✗ ") + n for n in ns]
        info("Habit Tray", "\n".join(lines))
    else:
        info("Habit Tray", "No habits yet.")

def on_reset(icon: pystray.Icon) -> None:
    log('on_reset invoked')
    if confirm("Habit Tray", "Delete all habits and history?"):
        save_db({})
        info("Habit Tray", "All data cleared.")
        rebuild_menu(icon)

def on_retention(icon: pystray.Icon) -> None:
    log('on_retention invoked')
    cfg = load_cfg()
    rd = cfg.get("retention_days")
    initial = str(rd) if isinstance(rd, int) and rd >= 1 else "0"
    val = prompt_str("Habit Tray", "Retention days (0 = keep forever):", initial)
    if val is None:
        return
    try:
        n = int(val)
        if n < 0:
            raise ValueError
    except ValueError:
        info("Habit Tray", "Please enter a non-negative integer.")
        return
    cfg["retention_days"] = n if n >= 1 else None
    save_cfg(cfg)
    apply_retention()
    info("Habit Tray", f"Retention set: {retention_label(cfg)}")
    rebuild_menu(icon)

def main():
    try:
        apply_retention()
        ic = pystray.Icon("HabitTray", icon_image(), "Habit Tray")
        rebuild_menu(ic)
        ic.run()
    except Exception as e:
        tb = traceback.format_exc()
        log(f"CRASH: {e!r}\n{tb}")
        msgbox("Habit Tray - Crash", f"Something went wrong.\nSee log:\n{LOG}")

if __name__ == "__main__":
    main()
