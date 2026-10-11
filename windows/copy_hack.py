#!/usr/bin/env python3
"""
copy-hack (Windows)

  Ctrl+K  — type clipboard character-by-character (delayMs=0 by default)
  Ctrl+L  — instant paste (simulates Ctrl+V)

Hotkeys exist only while this process runs. Closing it removes them.
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
    "delayMs": 0,
    "cancelOnEscape": True,
    "hotkeys": {
        "typewriter": "ctrl+k",
        "paste": "ctrl+l",
    },
    "enabled": {
        "typewriter": True,
        "paste": True,
    },
}


def load_config(cli_delay_ms: int | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if CONFIG_PATH.exists():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                # Merge nested dicts shallowly for hotkeys/enabled.
                for key, value in on_disk.items():
                    if key in ("hotkeys", "enabled") and isinstance(value, dict):
                        cfg[key].update(value)
                    else:
                        cfg[key] = value
        except (OSError, json.JSONDecodeError) as exc:
            print(f"copy-hack: could not read {CONFIG_PATH}: {exc}", file=sys.stderr)
    if cli_delay_ms is not None:
        cfg["delayMs"] = cli_delay_ms
    # Normalize hotkeys / enabled.
    hotkeys = cfg.setdefault("hotkeys", {})
    enabled = cfg.setdefault("enabled", {})
    hotkeys.setdefault("typewriter", DEFAULT_CONFIG["hotkeys"]["typewriter"])
    hotkeys.setdefault("paste", DEFAULT_CONFIG["hotkeys"]["paste"])
    enabled.setdefault("typewriter", True)
    enabled.setdefault("paste", True)
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
        self.delay_ms = int(config.get("delayMs", 0))
        self.cancel_on_escape = bool(config.get("cancelOnEscape", True))
        self._lock = threading.Lock()
        self._typing = False
        self._cancel = False

    def trigger_typewriter(self) -> None:
        threading.Thread(target=self._typewriter, daemon=True).start()

    def trigger_paste(self) -> None:
        threading.Thread(target=self._paste, daemon=True).start()

    def _paste(self) -> None:
        # Let Ctrl+L finish, then send Ctrl+V.
        time.sleep(0.08)
        keyboard.release("ctrl")
        keyboard.release("l")
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


def list_hotkeys(cfg: dict) -> None:
    hotkeys = cfg.get("hotkeys", {})
    enabled = cfg.get("enabled", {})
    print("Configured hotkeys:")
    print(f"  typewriter: {hotkeys.get('typewriter', 'ctrl+k')}  "
          f"({'on' if enabled.get('typewriter', True) else 'OFF'})")
    print(f"  paste:      {hotkeys.get('paste', 'ctrl+l')}  "
          f"({'on' if enabled.get('paste', True) else 'OFF'})")
    print(f"  config:     {CONFIG_PATH}")
    print()
    print("Hotkeys are active only while copy_hack.py is running.")
    print("Closing the process (Ctrl+C or --unregister) removes them.")


def remove_hotkeys(cfg: dict) -> dict:
    """Disable both hotkeys in config and clear any keyboard hooks in this process."""
    cfg.setdefault("enabled", {})
    cfg["enabled"]["typewriter"] = False
    cfg["enabled"]["paste"] = False
    save_config(cfg)
    try:
        keyboard.unhook_all_hotkeys()
    except Exception:
        pass
    try:
        keyboard.unhook_all()
    except Exception:
        pass
    print("Hotkeys disabled in config:")
    print(f"  {CONFIG_PATH}")
    print('  "enabled": { "typewriter": false, "paste": false }')
    print()
    print("Also: stop any running copy_hack.py (Ctrl+C in its window).")
    print("There is no OS-level install — closing the process removes the shortcuts.")
    return cfg


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "copy-hack — Ctrl+K types clipboard fast; Ctrl+L pastes (Ctrl+V)."
        )
    )
    p.add_argument(
        "--delay-ms",
        type=int,
        default=None,
        help="Typewriter delay between characters in ms (default: 0 = no sleep).",
    )
    p.add_argument(
        "--list-hotkeys",
        action="store_true",
        help="Print configured hotkeys and exit.",
    )
    p.add_argument(
        "--unregister",
        "--remove-hotkeys",
        "--uninstall",
        dest="unregister",
        action="store_true",
        help="Disable hotkeys in config, unhook this process, print how to stop.",
    )
    return p.parse_args()


def main() -> int:
    if sys.platform != "win32":
        print("This script is for Windows. On macOS use ../macos/", file=sys.stderr)
        return 1

    args = parse_args()
    cfg = load_config(args.delay_ms)

    if args.list_hotkeys:
        list_hotkeys(cfg)
        return 0

    if args.unregister:
        remove_hotkeys(cfg)
        return 0

    save_config(cfg)

    enabled = cfg.get("enabled", {})
    hotkeys = cfg.get("hotkeys", {})
    type_hk = hotkeys.get("typewriter", "ctrl+k")
    paste_hk = hotkeys.get("paste", "ctrl+l")

    if not enabled.get("typewriter", True) and not enabled.get("paste", True):
        print("Both hotkeys are disabled in config.", file=sys.stderr)
        print(f"Edit {CONFIG_PATH} or run without --unregister after re-enabling.", file=sys.stderr)
        print('Set "enabled": { "typewriter": true, "paste": true }', file=sys.stderr)
        return 1

    engine = InsertEngine(cfg)

    if enabled.get("typewriter", True):
        keyboard.add_hotkey(type_hk, engine.trigger_typewriter, suppress=False)
    if enabled.get("paste", True):
        keyboard.add_hotkey(paste_hk, engine.trigger_paste, suppress=False)

    print("copy-hack running.")
    print(f"  delayMs:     {cfg['delayMs']} (0 = instant typing, no sleeps)")
    print(f"  config:      {CONFIG_PATH}")
    if enabled.get("typewriter", True):
        print(f"  typewriter:  {type_hk.upper().replace('+', '+')}  (types clipboard)")
    else:
        print("  typewriter:  OFF")
    if enabled.get("paste", True):
        print(f"  paste:       {paste_hk.upper().replace('+', '+')}  (Ctrl+V)")
    else:
        print("  paste:       OFF")
    print("  quit:        Ctrl+C in this window")
    print("  remove:      python copy_hack.py --unregister")
    print()
    print("Tip: run this terminal as Administrator if the hotkey does not fire in some apps.")

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        print("\nBye. Hotkeys cleared for this process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
