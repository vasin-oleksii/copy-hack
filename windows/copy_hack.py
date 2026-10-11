#!/usr/bin/env python3
"""
copy-hack (Windows) — Ctrl+K types clipboard character-by-character.

Default: typewriter (not Ctrl+V paste), delayMs=0 (no sleeps between chars).
Optional: paste mode (Ctrl+V) via --mode paste or config.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

try:
    import keyboard
except ImportError:
    print("Missing dependency. Run:  pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)

CONFIG_DIR = Path.home() / "AppData" / "Local" / "TypewriterPaste"
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_CONFIG = {
    "mode": "typewriter",  # "typewriter" | "paste"
    "delayMs": 0,
    "cancelOnEscape": True,
}


def load_config(cli_delay_ms: int | None) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"copy-hack: could not read {CONFIG_PATH}: {exc}", file=sys.stderr)
    if cli_delay_ms is not None:
        cfg["delayMs"] = cli_delay_ms
    if cfg.get("mode") not in ("paste", "typewriter"):
        cfg["mode"] = "typewriter"
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def clipboard_text() -> str:
    """Read Unicode text from the Windows clipboard (CF_UNICODETEXT)."""
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    CF_UNICODETEXT = 13

    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


class InsertEngine:
    def __init__(self, config: dict) -> None:
        self.mode = config["mode"]
        self.delay_ms = int(config.get("delayMs", 0))
        self.cancel_on_escape = bool(config.get("cancelOnEscape", True))
        self._lock = threading.Lock()
        self._typing = False
        self._cancel = False

    def handle_hotkey(self) -> None:
        if self.mode == "paste":
            threading.Thread(target=self._paste, daemon=True).start()
        else:
            threading.Thread(target=self._typewriter, daemon=True).start()

    def _paste(self) -> None:
        # Optional non-default mode: let Ctrl+K finish, then send Ctrl+V.
        time.sleep(0.08)
        keyboard.release("ctrl")
        keyboard.release("k")
        keyboard.send("ctrl+v")

    def _typewriter(self) -> None:
        with self._lock:
            if self._typing:
                return
            self._typing = True
            self._cancel = False

        try:
            text = clipboard_text()
            if not text:
                return
            # Brief pause so Ctrl+K can finish before we inject keystrokes.
            time.sleep(0.12)
            keyboard.release("ctrl")
            keyboard.release("k")
            for ch in text:
                if self._cancel:
                    break
                if self.cancel_on_escape and keyboard.is_pressed("esc"):
                    break
                if ch in ("\n", "\r"):
                    keyboard.send("enter")
                elif ch == "\t":
                    keyboard.send("tab")
                else:
                    keyboard.write(ch, delay=0, restore_state_after=False)
                # delayMs=0 → no sleep between characters (as fast as possible).
                if self.delay_ms > 0:
                    time.sleep(self.delay_ms / 1000.0)
        finally:
            with self._lock:
                self._typing = False
                self._cancel = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="copy-hack — Ctrl+K types clipboard character-by-character (not Ctrl+V)."
    )
    p.add_argument(
        "--delay-ms",
        type=int,
        default=None,
        help="Delay between characters in ms (default: 0 = no sleep).",
    )
    p.add_argument(
        "--mode",
        choices=("typewriter", "paste"),
        default=None,
        help="Override insert mode for this run (default: typewriter).",
    )
    return p.parse_args()


def main() -> int:
    if sys.platform != "win32":
        print("This script is for Windows. On macOS use ../macos/", file=sys.stderr)
        return 1

    args = parse_args()
    cfg = load_config(args.delay_ms)
    if args.mode:
        cfg["mode"] = args.mode
    save_config(cfg)

    engine = InsertEngine(cfg)
    keyboard.add_hotkey("ctrl+k", engine.handle_hotkey, suppress=False)

    print("copy-hack running.")
    print(f"  mode:     {cfg['mode']}")
    print(f"  delayMs:  {cfg['delayMs']} (0 = instant typing, no sleeps)")
    print(f"  config:   {CONFIG_PATH}")
    print("  hotkey:   Ctrl+K")
    print("  quit:     Ctrl+C in this window")
    print()
    print("Tip: run this terminal as Administrator if the hotkey does not fire in some apps.")

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        print("\nBye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
