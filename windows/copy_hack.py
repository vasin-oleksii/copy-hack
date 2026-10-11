#!/usr/bin/env python3
"""
copy-hack (Windows)

  Ctrl+B  — type clipboard character-by-character (delayMs=0, same as macOS)

NOT paste. Full chord only. Bare Ctrl does nothing.
Every normal start FORCE-RESETS config (ignores old --unregister / old hotkeys).
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

# Unbuffered stdout so Windows cmd.exe always shows logs immediately.
os.environ.setdefault("PYTHONUNBUFFERED", "1")
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

try:
    import keyboard
except ImportError:
    print("ERROR: Missing dependency. Run:  pip install -r requirements.txt", file=sys.stderr, flush=True)
    sys.exit(1)

CONFIG_DIR = Path.home() / "AppData" / "Local" / "TypewriterPaste"
CONFIG_PATH = CONFIG_DIR / "config.json"
LOG_PATH = CONFIG_DIR / "debug.log"

DEFAULT_CONFIG = {
    "delayMs": 0,
    "cancelOnEscape": True,
    "hotkeys": {"typewriter": "ctrl+b"},
    "enabled": {"typewriter": True},
}

VK_RETURN = 0x0D
VK_TAB = 0x09
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

DEBUG = True  # always on for now — Oleksii needs to see what fails


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


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


def _send_inputs(events: list[tuple[int, int, int]]) -> int:
    n = len(events)
    arr = (INPUT * n)()
    for i, (vk, scan, flags) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return int(ctypes.windll.user32.SendInput(n, ctypes.byref(arr), ctypes.sizeof(INPUT)))


def send_vk(vk: int) -> None:
    _send_inputs([(vk, 0, 0), (vk, 0, KEYEVENTF_KEYUP)])


def send_unicode_char(ch: str) -> bool:
    code = ord(ch)
    if code > 0xFFFF:
        high = 0xD800 + ((code - 0x10000) >> 10)
        low = 0xDC00 + ((code - 0x10000) & 0x3FF)
        ok = True
        for part in (high, low):
            sent = _send_inputs(
                [
                    (0, part, KEYEVENTF_UNICODE),
                    (0, part, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
                ]
            )
            ok = ok and sent == 2
        return ok
    sent = _send_inputs(
        [
            (0, code, KEYEVENTF_UNICODE),
            (0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP),
        ]
    )
    return sent == 2


def chord_keys(hotkey: str) -> list[str]:
    return [p.strip().lower() for p in hotkey.split("+") if p.strip()]


def wait_keys_up(keys: list[str], timeout: float = 2.0) -> bool:
    if not keys:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if not any(keyboard.is_pressed(k) for k in keys):
                time.sleep(0.02)
                if not any(keyboard.is_pressed(k) for k in keys):
                    return True
        except Exception as exc:
            log(f"DEBUG wait_keys_up probe error (continuing): {exc}")
            time.sleep(0.03)
            return True
        time.sleep(0.01)
    return False


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def force_reset_config(cli_delay_ms: int | None = None) -> dict:
    """Overwrite config every start — ignore old unregister / old hotkeys."""
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["delayMs"] = 0 if cli_delay_ms is None else int(cli_delay_ms)
    cfg["hotkeys"] = {"typewriter": "ctrl+b"}
    cfg["enabled"] = {"typewriter": True}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    log(f"CONFIG RESET → {CONFIG_PATH}")
    log(f"CONFIG BODY  → {json.dumps(cfg)}")
    return cfg


def clipboard_text() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_UNICODETEXT = 13
    if not user32.OpenClipboard(None):
        log("DEBUG clipboard: OpenClipboard failed")
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            log("DEBUG clipboard: empty / not text")
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            log("DEBUG clipboard: GlobalLock failed")
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
        self.type_hotkey = "ctrl+b"
        self._lock = threading.Lock()
        self._busy = False
        self._fire_count = 0

    def on_hotkey(self) -> None:
        self._fire_count += 1
        log(f"HOTKEY FIRED #{self._fire_count} ({self.type_hotkey}) — starting typewriter thread")
        threading.Thread(target=self._typewriter, daemon=True).start()

    def _typewriter(self) -> None:
        with self._lock:
            if self._busy:
                log("DEBUG skip: already typing")
                return
            self._busy = True
        try:
            text = clipboard_text()
            preview = text[:60].replace("\n", "\\n") if text else ""
            log(f"DEBUG clipboard length={len(text)} preview={preview!r}")
            if not text:
                log("FAIL: clipboard empty — copy text first (Ctrl+C), then Ctrl+B")
                try:
                    ctypes.windll.user32.MessageBeep(0x00000030)
                except Exception:
                    pass
                return

            keys = chord_keys(self.type_hotkey)
            log(f"DEBUG waiting for keys up: {keys}")
            if not wait_keys_up(keys, timeout=2.0):
                log("FAIL: Ctrl/B still held after timeout — release keys and retry")
                return
            log(f"DEBUG typing {len(text)} chars, delayMs={self.delay_ms}")

            typed = 0
            send_fail = 0
            for ch in text:
                if self.cancel_on_escape:
                    try:
                        if keyboard.is_pressed("esc"):
                            log("DEBUG cancelled by Escape")
                            break
                    except Exception:
                        pass
                ok = True
                if ch in ("\n", "\r"):
                    send_vk(VK_RETURN)
                elif ch == "\t":
                    send_vk(VK_TAB)
                else:
                    ok = send_unicode_char(ch)
                    if not ok:
                        # Fallback: keyboard.write (still not Ctrl+V paste)
                        try:
                            keyboard.write(ch, delay=0, restore_state_after=False)
                            ok = True
                        except Exception as exc:
                            send_fail += 1
                            if send_fail <= 3:
                                log(f"DEBUG SendInput/write failed for {ch!r}: {exc}")
                if ok:
                    typed += 1
                if self.delay_ms > 0:
                    time.sleep(self.delay_ms / 1000.0)
            log(f"DONE typed={typed}/{len(text)} send_fail={send_fail}")
        except Exception:
            log("ERROR in typewriter:\n" + traceback.format_exc())
        finally:
            with self._lock:
                self._busy = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="copy-hack — Ctrl+B types clipboard very fast (not paste)."
    )
    p.add_argument("--delay-ms", type=int, default=None, help="Delay ms (default 0).")
    p.add_argument("--list-hotkeys", action="store_true", help="Show hotkey + config and exit.")
    p.add_argument(
        "--unregister",
        "--remove-hotkeys",
        "--uninstall",
        dest="unregister",
        action="store_true",
        help="Stop tip: Ctrl+C the running window. Also writes enabled=false.",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Force-reset config to Ctrl+B / delayMs=0 / enabled and exit.",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Print diagnostics (admin, clipboard, config) and exit.",
    )
    return p.parse_args()


def print_diagnostics(cfg: dict) -> None:
    log("=== DIAGNOSTICS ===")
    log(f"python:     {sys.version.split()[0]} {sys.executable}")
    log(f"admin:      {is_admin()}")
    log(f"platform:   {sys.platform}")
    log(f"config:     {CONFIG_PATH}")
    log(f"debug log:  {LOG_PATH}")
    log(f"delayMs:    {cfg.get('delayMs')}")
    log(f"hotkey:     {cfg.get('hotkeys', {}).get('typewriter')}")
    log(f"enabled:    {cfg.get('enabled', {}).get('typewriter')}")
    text = clipboard_text()
    log(f"clipboard:  {len(text)} chars")
    if text:
        log(f"clip preview: {text[:80]!r}")
    else:
        log("clip preview: (empty) — copy something before Ctrl+B")
    if not is_admin():
        log("WARN: not Administrator — hotkeys often fail in some apps. Re-run cmd as Admin.")
    log("=== END DIAGNOSTICS ===")


def main() -> int:
    log("copy-hack starting…")
    if sys.platform != "win32":
        log("ERROR: Windows only. On macOS use ../macos/")
        return 1

    args = parse_args()

    # Always force-reset defaults (wipes old unregister / ctrl+l / paste junk).
    cfg = force_reset_config(args.delay_ms)

    if args.reset:
        log("OK: config reset. Run: python copy_hack.py")
        return 0

    if args.list_hotkeys or args.self_test:
        print_diagnostics(cfg)
        return 0

    if args.unregister:
        cfg["enabled"]["typewriter"] = False
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        try:
            keyboard.unhook_all_hotkeys()
            keyboard.unhook_all()
        except Exception:
            pass
        log("Hotkeys disabled in config for this moment.")
        log("IMPORTANT: next `python copy_hack.py` will RESET and re-enable automatically.")
        log("To stop a running instance: press Ctrl+C in THAT window.")
        return 0

    print_diagnostics(cfg)

    engine = InsertEngine(cfg)
    type_hk = "ctrl+b"

    try:
        # Fire on PRESS (release-trigger is unreliable on some Windows builds).
        # Then we wait until Ctrl+B are up before typing — never fake Ctrl+V.
        keyboard.add_hotkey(
            type_hk,
            engine.on_hotkey,
            suppress=True,
            trigger_on_release=False,
        )
        log(f"HOTKEY REGISTERED: {type_hk} (suppress=True, on press)")
    except Exception:
        log("ERROR registering hotkey:\n" + traceback.format_exc())
        log("FIX: run this Command Prompt as Administrator, then retry.")
        return 1

    log("READY — copy text, click a text field, press Ctrl+B")
    log("You MUST see 'HOTKEY FIRED' here when Ctrl+B works.")
    log("If nothing appears on Ctrl+B → hook blocked (Admin / other app / wrong window).")
    log("quit: Ctrl+C   |   log file: " + str(LOG_PATH))

    try:
        keyboard.wait()
    except KeyboardInterrupt:
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        log("Bye. Hotkeys cleared for this process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
