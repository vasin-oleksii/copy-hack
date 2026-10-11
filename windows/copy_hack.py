#!/usr/bin/env python3
"""
copy-hack (Windows)

  Ctrl+K  — type clipboard character-by-character (delayMs=0 by default)
  Ctrl+L  — instant paste (Ctrl+V via SendInput)

Full chords only. Bare Ctrl never triggers paste/copy.
Never force-releases Ctrl (avoids stuck modifier / false Ctrl+V).
Hotkeys exist only while this process runs.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import threading
import time
from ctypes import wintypes
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

VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
VK_TAB = 0x09
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    )


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = (
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    )


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT))

    _anonymous_ = ("_input",)
    _fields_ = (("type", wintypes.DWORD), ("_input", _INPUT))


def _send_inputs(events: list[tuple[int, int, int]]) -> None:
    """events: list of (wVk, wScan, dwFlags)."""
    n = len(events)
    arr = (INPUT * n)()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    sent = ctypes.windll.user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT))
    if sent != n:
        # Fallback: keybd_event for Ctrl+V-style vk pairs only.
        user32 = ctypes.windll.user32
        for vk, scan, flags in events:
            if flags & KEYEVENTF_UNICODE:
                continue
            user32.keybd_event(vk, scan & 0xFF, flags, 0)


def send_ctrl_v() -> None:
    """Paste via a clean Ctrl+V down/up pair. Does not use keyboard.release()."""
    _send_inputs(
        [
            (VK_CONTROL, 0, 0),
            (VK_V, 0, 0),
            (VK_V, 0, KEYEVENTF_KEYUP),
            (VK_CONTROL, 0, KEYEVENTF_KEYUP),
        ]
    )


def send_vk(vk: int) -> None:
    _send_inputs([(vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP)])


def send_unicode_char(ch: str) -> None:
    """Type one character via KEYEVENTF_UNICODE (no Ctrl involved)."""
    code = ord(ch)
    if code > 0xFFFF:
        high = 0xD800 + ((code - 0x10000) >> 10)
        low = 0xDC00 + ((code - 0x10000) & 0x3FF)
        for part in (high, low):
            _send_inputs(
                [
                    (0, part, KEYEVENTF_UNICODE),
                    (0, part, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
                ]
            )
        return
    _send_inputs(
        [
            (0, code, KEYEVENTF_UNICODE),
            (0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
        ]
    )


def chord_keys(hotkey: str) -> list[str]:
    return [p.strip().lower() for p in hotkey.split("+") if p.strip()]


def wait_keys_up(keys: list[str], timeout: float = 1.5) -> bool:
    """Wait until chord keys are up. Never force-releases modifiers."""
    if not keys:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if not any(keyboard.is_pressed(k) for k in keys):
                time.sleep(0.015)
                if not any(keyboard.is_pressed(k) for k in keys):
                    return True
        except Exception:
            time.sleep(0.03)
            return True
        time.sleep(0.01)
    return False


def load_config(cli_delay_ms: int | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG_PATH.exists():
        try:
            on_disk = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(on_disk, dict):
                for key, value in on_disk.items():
                    if key in ("hotkeys", "enabled") and isinstance(value, dict):
                        cfg[key].update(value)
                    else:
                        cfg[key] = value
        except (OSError, json.JSONDecodeError) as exc:
            print(f"copy-hack: could not read {CONFIG_PATH}: {exc}", file=sys.stderr)
    if cli_delay_ms is not None:
        cfg["delayMs"] = cli_delay_ms
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
        self.type_hotkey = config.get("hotkeys", {}).get("typewriter", "ctrl+k")
        self.paste_hotkey = config.get("hotkeys", {}).get("paste", "ctrl+l")
        self._lock = threading.Lock()
        self._busy = False
        self._cancel = False

    def trigger_typewriter(self) -> None:
        threading.Thread(target=self._typewriter, daemon=True).start()

    def trigger_paste(self) -> None:
        threading.Thread(target=self._paste, daemon=True).start()

    def _begin(self) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._cancel = False
            return True

    def _end(self) -> None:
        with self._lock:
            self._busy = False
            self._cancel = False

    def _paste(self) -> None:
        if not self._begin():
            return
        try:
            # Fired on chord release (see add_hotkey). Double-check keys are up —
            # never keyboard.release("ctrl"), never act on bare Ctrl.
            keys = chord_keys(self.paste_hotkey)
            if not wait_keys_up(keys, timeout=0.8):
                return
            send_ctrl_v()
        finally:
            self._end()

    def _typewriter(self) -> None:
        if not self._begin():
            return
        try:
            text = clipboard_text()
            if not text:
                return
            keys = chord_keys(self.type_hotkey)
            if not wait_keys_up(keys, timeout=0.8):
                return
            for ch in text:
                if self._cancel:
                    break
                if self.cancel_on_escape:
                    try:
                        if keyboard.is_pressed("esc"):
                            break
                    except Exception:
                        pass
                if ch in ("\n", "\r"):
                    send_vk(VK_RETURN)
                elif ch == "\t":
                    send_vk(VK_TAB)
                else:
                    send_unicode_char(ch)
                if self.delay_ms > 0:
                    time.sleep(self.delay_ms / 1000.0)
        finally:
            self._end()


def list_hotkeys(cfg: dict) -> None:
    hotkeys = cfg.get("hotkeys", {})
    enabled = cfg.get("enabled", {})
    print("Configured hotkeys (full chords only — bare Ctrl does nothing):")
    print(
        f"  typewriter: {hotkeys.get('typewriter', 'ctrl+k')}  "
        f"({'on' if enabled.get('typewriter', True) else 'OFF'})"
    )
    print(
        f"  paste:      {hotkeys.get('paste', 'ctrl+l')}  "
        f"({'on' if enabled.get('paste', True) else 'OFF'})"
    )
    print(f"  config:     {CONFIG_PATH}")
    print()
    print("Hotkeys are active only while copy_hack.py is running.")
    print("Closing the process (Ctrl+C or --unregister) removes them.")


def remove_hotkeys(cfg: dict) -> dict:
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
        description="copy-hack — Ctrl+K types clipboard fast; Ctrl+L pastes (Ctrl+V)."
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
        print(f"Edit {CONFIG_PATH} or re-enable enabled.typewriter / enabled.paste.", file=sys.stderr)
        return 1

    engine = InsertEngine(cfg)

    # Full chord only (keyboard lib). Fire on release so modifiers are already up —
    # never call keyboard.release("ctrl"). suppress swallows the chord letter.
    if enabled.get("typewriter", True):
        keyboard.add_hotkey(
            type_hk,
            engine.trigger_typewriter,
            suppress=True,
            trigger_on_release=True,
        )
    if enabled.get("paste", True):
        keyboard.add_hotkey(
            paste_hk,
            engine.trigger_paste,
            suppress=True,
            trigger_on_release=True,
        )

    print("copy-hack running.")
    print(f"  delayMs:     {cfg['delayMs']} (0 = instant typing, no sleeps)")
    print(f"  config:      {CONFIG_PATH}")
    if enabled.get("typewriter", True):
        print(f"  typewriter:  {type_hk}  (types clipboard; full chord only)")
    else:
        print("  typewriter:  OFF")
    if enabled.get("paste", True):
        print(f"  paste:       {paste_hk}  (Ctrl+V via SendInput; full chord only)")
    else:
        print("  paste:       OFF")
    print("  quit:        Ctrl+C in this window")
    print("  remove:      python copy_hack.py --unregister")
    print()
    print("Bare Ctrl does nothing. Tip: run as Administrator if hotkeys miss in some apps.")

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
