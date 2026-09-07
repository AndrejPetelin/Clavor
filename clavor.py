#!/usr/bin/env python3
"""
Clavor — Sticky Key Widget
─────────────────────────────────────────────────────────────────────────────
A tiny floating widget. Click a key to hold it system-wide,
click again (or press "Release All") to let it go.
Designed specifically for Blender workflows that need a modifier key held
while you do mouse operations — without the widget stealing Blender's focus.

Install:  pip install pynput
Run:      python clavor.py
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import os
import json
import tkinter as tk
from tkinter import messagebox

# ── Keyboard backend ──────────────────────────────────────────────────────────
try:
    from pynput.keyboard import Key, Controller as KB
    _keyboard = KB()
    PYNPUT = True
except ImportError:
    PYNPUT = False
    Key = None
    _keyboard = None


def _resolve_key(name: str):
    """Convert a key name string to a pynput key object or character."""
    if not PYNPUT:
        return None
    specials = {
        "shift":     Key.shift,
        "ctrl":      Key.ctrl,
        "alt":       Key.alt,
        "win":       Key.cmd,
        "tab":       Key.tab,
        "esc":       Key.esc,
        "space":     Key.space,
        "enter":     Key.enter,
        "backspace": Key.backspace,
        "delete":    Key.delete,
        "caps":      Key.caps_lock,
        "f1":  Key.f1,  "f2":  Key.f2,  "f3":  Key.f3,  "f4":  Key.f4,
        "f5":  Key.f5,  "f6":  Key.f6,  "f7":  Key.f7,  "f8":  Key.f8,
        "f9":  Key.f9,  "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
    }
    n = name.strip().lower()
    if n in specials:
        return specials[n]
    if len(n) == 1:
        return n   # single character — pynput accepts plain strings
    return None


# ── Config ────────────────────────────────────────────────────────────────────
def _cfg_dir() -> str:
    """
    Return the directory where the config file should live.
    - Frozen (PyInstaller): next to the .exe (sys.executable)
    - Script:               next to clavor.py
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CFG_PATH = os.path.join(_cfg_dir(), "clavor.json")

DEFAULTS: dict = {
    "keys": [
        {"label": "Shift", "key": "shift"},
        {"label": "Ctrl",  "key": "ctrl"},
        {"label": "Alt",   "key": "alt"},
        {"label": "Tab",   "key": "tab"},
    ],
    "always_on_top": True,
    "opacity":       0.93,
    "pos_x":         None,
    "pos_y":         None,
}


def _load_cfg() -> dict:
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH) as f:
                c = json.load(f)
            for k, v in DEFAULTS.items():
                c.setdefault(k, v)
            return c
        except Exception:
            pass
    return {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}


def _save_cfg(c: dict) -> None:
    try:
        with open(CFG_PATH, "w") as f:
            json.dump(c, f, indent=2)
    except Exception:
        pass


# ── Catppuccin Mocha palette ──────────────────────────────────────────────────
C = {
    "bg":          "#1e1e2e",
    "surface0":    "#313244",
    "surface1":    "#45475a",
    "overlay":     "#6c7086",
    "text":        "#cdd6f4",
    "green":       "#a6e3a1",
    "green_dark":  "#1e1e2e",
    "red":         "#f38ba8",
    "blue":        "#89b4fa",
    "yellow":      "#f9e2af",
    "peach":       "#fab387",
}


# ── Main widget ───────────────────────────────────────────────────────────────
class Clavor:
    def __init__(self):
        self.cfg    = _load_cfg()
        self.active: dict[str, bool]     = {}   # key_name → currently held?
        self.btns:   dict[str, tk.Button] = {}

        root = tk.Tk()
        root.title("Clavor")
        root.configure(bg=C["bg"])
        root.resizable(False, False)
        root.overrideredirect(True)          # hide OS title bar — we draw our own

        self.root = root
        self._topmost = tk.BooleanVar(value=bool(self.cfg["always_on_top"]))
        root.attributes("-topmost", self._topmost.get())
        root.attributes("-alpha",   float(self.cfg.get("opacity", 0.93)))

        self._build_ui()
        self._restore_pos()

        # WS_EX_NOACTIVATE must be applied after window is rendered
        root.after(60, self._apply_no_activate)

    # ── Focus-theft prevention (Windows) ─────────────────────────────────────
    def _apply_no_activate(self):
        """
        Set WS_EX_NOACTIVATE so clicking the widget does NOT steal focus from
        Blender (or any other app). Critical for sticky-key usage.
        """
        if sys.platform != "win32":
            return
        import ctypes
        GWL_EXSTYLE       = -20
        WS_EX_NOACTIVATE  = 0x08000000
        hwnd  = self.root.winfo_id()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        # ── title / drag bar ─────────────────────────────────────────────────
        bar = tk.Frame(self.root, bg=C["bg"], pady=4, padx=8)
        bar.pack(fill="x")

        self._title = tk.Label(
            bar, text="⌨  Clavor",
            bg=C["bg"], fg=C["blue"],
            font=("Segoe UI", 8, "bold"), cursor="fleur"
        )
        self._title.pack(side="left")

        for widget in (bar, self._title):
            widget.bind("<ButtonPress-1>",   self._drag_start)
            widget.bind("<B1-Motion>",       self._drag_move)
            widget.bind("<ButtonRelease-1>", self._drag_end)

        close_lbl = self._icon_btn(bar, "✕", C["overlay"], C["red"], self._quit)
        close_lbl.pack(side="right", padx=(2, 0))

        gear_lbl = self._icon_btn(bar, "⚙", C["overlay"], C["blue"], self._open_settings)
        gear_lbl.pack(side="right")

        # ── separator ────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=C["surface1"], height=1).pack(fill="x")

        # ── keys area ────────────────────────────────────────────────────────
        self._keys_frame = tk.Frame(self.root, bg=C["bg"], padx=10, pady=10)
        self._keys_frame.pack()
        self._build_key_buttons()

        # ── separator ────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=C["surface1"], height=1).pack(fill="x")

        # ── footer ───────────────────────────────────────────────────────────
        foot = tk.Frame(self.root, bg=C["bg"], padx=8, pady=5)
        foot.pack(fill="x")

        rel_btn = tk.Button(
            foot, text="✦ Release All",
            bg=C["surface0"], fg=C["red"],
            font=("Segoe UI", 8), relief="flat",
            padx=8, pady=3, cursor="hand2",
            activebackground=C["red"], activeforeground=C["bg"],
            command=self.release_all
        )
        rel_btn.pack(side="left")

        tk.Checkbutton(
            foot, text="on top",
            variable=self._topmost,
            bg=C["bg"], fg=C["overlay"],
            selectcolor=C["bg"],
            activebackground=C["bg"], activeforeground=C["blue"],
            font=("Segoe UI", 8),
            command=self._toggle_topmost,
        ).pack(side="right")

    def _build_key_buttons(self):
        for w in self._keys_frame.winfo_children():
            w.destroy()
        self.btns.clear()

        for col, kd in enumerate(self.cfg["keys"]):
            label = kd["label"]
            key   = kd["key"]
            held  = self.active.get(key, False)

            btn = tk.Button(
                self._keys_frame,
                text=label,
                width=5,
                font=("Segoe UI", 14, "bold"),
                bg=C["green"]      if held else C["surface0"],
                fg=C["green_dark"] if held else C["text"],
                activebackground=C["green"],
                activeforeground=C["green_dark"],
                relief="flat", bd=0,
                padx=4, pady=16,
                cursor="hand2",
                command=lambda k=key: self._toggle_key(k),
            )
            btn.grid(row=0, column=col, padx=5)
            self.btns[key] = btn

    # ── Key toggling ──────────────────────────────────────────────────────────
    def _toggle_key(self, key_name: str):
        if not PYNPUT:
            messagebox.showerror(
                "pynput not installed",
                "Clavor needs pynput to send keystrokes.\n\n"
                "Open a terminal and run:\n    pip install pynput\n\n"
                "Then restart Clavor."
            )
            return

        held = self.active.get(key_name, False)
        pkey = _resolve_key(key_name)

        if held:
            # ── release ──
            if pkey:
                try:
                    _keyboard.release(pkey)
                except Exception as e:
                    print(f"[Clavor] release error ({key_name}): {e}")
            self.active[key_name] = False
            if key_name in self.btns:
                self.btns[key_name].config(bg=C["surface0"], fg=C["text"])
        else:
            # ── press and hold ──
            if pkey:
                try:
                    _keyboard.press(pkey)
                except Exception as e:
                    print(f"[Clavor] press error ({key_name}): {e}")
            self.active[key_name] = True
            if key_name in self.btns:
                self.btns[key_name].config(bg=C["green"], fg=C["green_dark"])

    def release_all(self):
        """Release every held key and reset all button states."""
        for key_name, held in list(self.active.items()):
            if held:
                pkey = _resolve_key(key_name)
                if pkey and PYNPUT:
                    try:
                        _keyboard.release(pkey)
                    except Exception:
                        pass
            self.active[key_name] = False
        for btn in self.btns.values():
            btn.config(bg=C["surface0"], fg=C["text"])

    # ── Dragging ──────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._ox = e.x_root - self.root.winfo_x()
        self._oy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._ox}+{e.y_root - self._oy}")

    def _drag_end(self, e):
        self.cfg["pos_x"] = self.root.winfo_x()
        self.cfg["pos_y"] = self.root.winfo_y()
        _save_cfg(self.cfg)

    def _restore_pos(self):
        self.root.update_idletasks()
        x = self.cfg.get("pos_x")
        y = self.cfg.get("pos_y")
        if x is None or y is None:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            rw = self.root.winfo_reqwidth()
            rh = self.root.winfo_reqheight()
            x  = (sw - rw) // 2
            y  = sh - rh - 80      # bottom-centre by default
        self.root.geometry(f"+{int(x)}+{int(y)}")

    # ── Settings ──────────────────────────────────────────────────────────────
    def _open_settings(self):
        SettingsWin(self.root, self.cfg, self._on_settings_saved)

    def _on_settings_saved(self, new_cfg: dict):
        self.release_all()
        self.cfg = new_cfg
        _save_cfg(self.cfg)
        self.root.attributes("-alpha", float(new_cfg.get("opacity", 0.93)))
        self._build_key_buttons()

    def _toggle_topmost(self):
        val = self._topmost.get()
        self.root.attributes("-topmost", val)
        self.cfg["always_on_top"] = val
        _save_cfg(self.cfg)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _icon_btn(parent, text, idle_fg, hover_fg, command):
        lbl = tk.Label(parent, text=text, bg=C["bg"], fg=idle_fg,
                       font=("Segoe UI", 10), cursor="hand2")
        lbl.bind("<Button-1>", lambda e: command())
        lbl.bind("<Enter>",    lambda e: lbl.config(fg=hover_fg))
        lbl.bind("<Leave>",    lambda e: lbl.config(fg=idle_fg))
        return lbl

    def _quit(self):
        self.release_all()
        _save_cfg(self.cfg)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ── Settings window ───────────────────────────────────────────────────────────
class SettingsWin:
    def __init__(self, parent, cfg: dict, on_save):
        self.on_save = on_save
        # deep copy
        self.cfg  = {k: ([dict(x) for x in v] if k == "keys" else v)
                     for k, v in cfg.items()}
        self.rows: list[tuple[tk.Frame, tk.StringVar, tk.StringVar]] = []

        w = tk.Toplevel(parent)
        w.title("Clavor — Settings")
        w.configure(bg=C["bg"])
        w.resizable(False, False)
        w.grab_set()
        self.win = w
        self._build()

    def _build(self):
        p = dict(padx=12, pady=4)

        tk.Label(self.win, text="Sticky Keys",
                 bg=C["bg"], fg=C["blue"],
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", **p)

        tk.Label(self.win,
                 text="key names: shift  ctrl  alt  tab  esc  space  enter  "
                      "or any single letter",
                 bg=C["bg"], fg=C["overlay"],
                 font=("Segoe UI", 7)).pack(anchor="w", padx=12)

        # ── existing key rows ─────────────────────────────────────────────────
        self._list = tk.Frame(self.win, bg=C["bg"])
        self._list.pack(fill="x", padx=12, pady=(6, 2))

        for kd in self.cfg["keys"]:
            self._add_row(kd["label"], kd["key"])

        # ── add new key ───────────────────────────────────────────────────────
        add = tk.Frame(self.win, bg=C["bg"])
        add.pack(fill="x", padx=12, pady=(2, 6))

        tk.Label(add, text="Label:", bg=C["bg"], fg=C["overlay"],
                 font=("Segoe UI", 8)).grid(row=0, column=0, sticky="w")
        self._nl = tk.Entry(add, width=9, bg=C["surface0"], fg=C["text"],
                            insertbackground=C["text"], relief="flat")
        self._nl.grid(row=0, column=1, padx=(3, 10))

        tk.Label(add, text="Key:", bg=C["bg"], fg=C["overlay"],
                 font=("Segoe UI", 8)).grid(row=0, column=2, sticky="w")
        self._nk = tk.Entry(add, width=9, bg=C["surface0"], fg=C["text"],
                            insertbackground=C["text"], relief="flat")
        self._nk.grid(row=0, column=3, padx=3)

        tk.Button(add, text="+ Add",
                  bg=C["surface0"], fg=C["green"],
                  relief="flat", font=("Segoe UI", 8),
                  command=self._add_key).grid(row=0, column=4, padx=(8, 0))

        # ── separator ─────────────────────────────────────────────────────────
        tk.Frame(self.win, bg=C["surface1"], height=1).pack(fill="x", padx=12, pady=4)

        # ── opacity slider ────────────────────────────────────────────────────
        op = tk.Frame(self.win, bg=C["bg"])
        op.pack(fill="x", padx=12, pady=(2, 6))
        tk.Label(op, text="Opacity:", bg=C["bg"], fg=C["overlay"],
                 font=("Segoe UI", 8)).pack(side="left")
        self._opacity = tk.DoubleVar(value=float(self.cfg.get("opacity", 0.93)))
        tk.Scale(op, from_=0.3, to=1.0, resolution=0.05,
                 orient="horizontal", variable=self._opacity,
                 length=160, bg=C["bg"], fg=C["text"],
                 troughcolor=C["surface0"], highlightthickness=0,
                 sliderrelief="flat").pack(side="left", padx=6)

        # ── save / cancel ─────────────────────────────────────────────────────
        btns = tk.Frame(self.win, bg=C["bg"])
        btns.pack(fill="x", padx=12, pady=(4, 10))

        tk.Button(btns, text="Save",
                  bg=C["green"], fg=C["green_dark"],
                  font=("Segoe UI", 9, "bold"), relief="flat", padx=12,
                  command=self._save).pack(side="right", padx=4)
        tk.Button(btns, text="Cancel",
                  bg=C["surface0"], fg=C["text"],
                  font=("Segoe UI", 9), relief="flat", padx=8,
                  command=self.win.destroy).pack(side="right")

    def _add_row(self, label: str = "", key: str = ""):
        row = tk.Frame(self._list, bg=C["bg"])
        row.pack(fill="x", pady=2)

        lv = tk.StringVar(value=label)
        kv = tk.StringVar(value=key)

        tk.Label(row, text="Label", bg=C["bg"], fg=C["overlay"],
                 font=("Segoe UI", 7), width=5, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=lv, width=9, bg=C["surface0"], fg=C["text"],
                 insertbackground=C["text"], relief="flat").pack(side="left", padx=2)

        tk.Label(row, text="Key", bg=C["bg"], fg=C["overlay"],
                 font=("Segoe UI", 7), width=4, anchor="w").pack(side="left", padx=(6, 0))
        tk.Entry(row, textvariable=kv, width=9, bg=C["surface0"], fg=C["text"],
                 insertbackground=C["text"], relief="flat").pack(side="left", padx=2)

        del_lbl = tk.Label(row, text="✕", bg=C["bg"], fg=C["overlay"],
                           font=("Segoe UI", 9), cursor="hand2")
        del_lbl.pack(side="left", padx=6)
        del_lbl.bind("<Button-1>", lambda e, r=row: self._del_row(r))
        del_lbl.bind("<Enter>",    lambda e, d=del_lbl: d.config(fg=C["red"]))
        del_lbl.bind("<Leave>",    lambda e, d=del_lbl: d.config(fg=C["overlay"]))

        self.rows.append((row, lv, kv))

    def _del_row(self, row: tk.Frame):
        self.rows = [(r, l, k) for r, l, k in self.rows if r is not row]
        row.destroy()

    def _add_key(self):
        l = self._nl.get().strip()
        k = self._nk.get().strip()
        if l and k:
            self._add_row(l, k)
            self._nl.delete(0, "end")
            self._nk.delete(0, "end")

    def _save(self):
        keys = [
            {"label": lv.get().strip(), "key": kv.get().strip()}
            for _, lv, kv in self.rows
            if lv.get().strip() and kv.get().strip()
        ]
        new_cfg = {**self.cfg, "keys": keys, "opacity": float(self._opacity.get())}
        self.on_save(new_cfg)
        self.win.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not PYNPUT:
        print(
            "\n  pynput is not installed.\n"
            "  Run:  pip install pynput\n"
            "  Then restart Clavor.\n"
        )
        # Still launch in visual-only mode so the user sees the error in the GUI
    Clavor().run()
