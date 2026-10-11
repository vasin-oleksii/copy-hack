#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
copy-hack (Windows) — Ctrl+B types clipboard fast (NOT paste), delayMs=0.

Prints BOOT before importing keyboard so a blank console is diagnosable.
Auto-cleans old config + other copy_hack.py processes on every start.
"""

from __future__ import annotations

# --- BOOT (no third-party imports yet) ---------------------------------
import os
import sys

os.environ["PYTHONUNBUFFERED"] = "1"
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass


def boot(msg: str) -> None:
    """ASCII-safe immediate print (works on Russian cp866 consoles)."""
    try:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
    except Exception:
        try:
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()
        except Exception:
            pass


boot("BOOT: copy_hack.py file loaded (if you never see this, you are running an OLD file)")
boot("BOOT: python=" + sys.version.split()[0] + " exe=" + sys.executable)
boot("BOOT: pid=" + str(os.getpid()) + " cwd=" + os.getcwd())

import argparse
import ctypes
import json
import subprocess
import threading
import time
import traceback
from ctypes import wintypes
from pathlib import Path

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


def log(msg: str) -> None:
    line = "[" + time.strftime("%H:%M:%S") + "] " + msg
    boot(line)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def auto_cleanup() -> None:
    """Remove old config and kill OTHER copy_hack.py python processes."""
    boot("CLEANUP: starting auto-clean of previous runs...")
    # 1) wipe config dir contents (old unregister / hotkeys)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        for p in CONFIG_DIR.glob("*"):
            try:
                if p.is_file():
                    p.unlink()
                    boot("CLEANUP: deleted " + str(p))
            except Exception as exc:
                boot("CLEANUP: could not delete " + str(p) + " err=" + str(exc))
    except Exception as exc:
        boot("CLEANUP: config wipe failed: " + str(exc))

    # 2) kill other python processes whose command line contains copy_hack
    me = os.getpid()
    killed = 0
    try:
        # PowerShell: find python* with copy_hack in CommandLine, not our PID
        ps = (
            "$me=%d;"
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |"
            "Where-Object {"
            "  ($_.Name -match 'python') -and ($_.ProcessId -ne $me) -and "
            "  ($_.CommandLine -match 'copy_hack')"
            "} |"
            "ForEach-Object {"
            "  Write-Output ('KILL '+$_.ProcessId+' '+$_.CommandLine);"
            "  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue"
            "}"
        ) % me
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            stderr=subprocess.STDOUT,
            timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = out.decode("utf-8", errors="replace").strip()
        if text:
            for line in text.splitlines():
                boot("CLEANUP: " + line.strip())
                if line.strip().startswith("KILL"):
                    killed += 1
        else:
            boot("CLEANUP: no other copy_hack python processes found")
    except Exception as exc:
        boot("CLEANUP: process scan failed (ok to continue): " + str(exc))
        # Fallback: taskkill by window title is unreliable; try wmic
        try:
            out = subprocess.check_output(
                ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/FORMAT:LIST"],
                stderr=subprocess.STDOUT,
                timeout=15,
            )
            block = out.decode("utf-8", errors="replace")
            cur_pid = None
            cur_cmd = ""
            for raw in block.splitlines() + [""]:
                line = raw.strip()
                if line.startswith("CommandLine="):
                    cur_cmd = line.split("=", 1)[1]
                elif line.startswith("ProcessId="):
                    try:
                        cur_pid = int(line.split("=", 1)[1])
                    except ValueError:
                        cur_pid = None
                elif line == "" and cur_pid is not None:
                    if cur_pid != me and "copy_hack" in (cur_cmd or "").lower():
                        subprocess.call(["taskkill", "/F", "/PID", str(cur_pid)],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        boot("CLEANUP: taskkill PID " + str(cur_pid))
                        killed += 1
                    cur_pid = None
                    cur_cmd = ""
        except Exception as exc2:
            boot("CLEANUP: wmic fallback failed: " + str(exc2))

    boot("CLEANUP: done (killed=" + str(killed) + ")")
    if killed:
        time.sleep(0.4)  # let OS release keyboard hooks


def import_keyboard():
    boot("BOOT: importing keyboard package...")
    try:
        import keyboard as kb
    except ImportError:
        boot("ERROR: keyboard not installed. Run: pip install -r requirements.txt")
        sys.exit(1)
    boot("BOOT: keyboard import OK version=" + str(getattr(kb, "__version__", "?")))
    return kb


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


def _send_inputs(events):
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
                [(0, part, KEYEVENTF_UNICODE), (0, part, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
            )
            ok = ok and sent == 2
        return ok
    sent = _send_inputs(
        [(0, code, KEYEVENTF_UNICODE), (0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    )
    return sent == 2


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def force_reset_config(delay_ms: int = 0) -> dict:
    cfg = {
        "delayMs": int(delay_ms),
        "cancelOnEscape": True,
        "hotkeys": {"typewriter": "ctrl+b"},
        "enabled": {"typewriter": True},
    }
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    log("CONFIG RESET -> " + str(CONFIG_PATH))
    log("CONFIG BODY  -> " + json.dumps(cfg))
    return cfg


def _clipboard_via_win32() -> str:
    """
    Read CF_UNICODETEXT. Critical on 64-bit Python: GlobalLock MUST return c_void_p
    or the pointer is truncated and looks like GlobalLock failed / empty clipboard.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    CF_UNICODETEXT = 13
    CF_TEXT = 1

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p  # 64-bit safe
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GetLastError.restype = wintypes.DWORD

    # Retry — another app may briefly hold the clipboard.
    opened = False
    for _ in range(30):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        err = kernel32.GetLastError()
        log("DEBUG clipboard: OpenClipboard failed GetLastError=" + str(err))
        return ""

    try:
        text = ""
        if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if handle:
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    try:
                        text = ctypes.wstring_at(ptr) or ""
                    finally:
                        kernel32.GlobalUnlock(handle)
                else:
                    log(
                        "DEBUG clipboard: GlobalLock failed GetLastError="
                        + str(kernel32.GetLastError())
                        + " (will try fallbacks)"
                    )
        if not text and user32.IsClipboardFormatAvailable(CF_TEXT):
            handle = user32.GetClipboardData(CF_TEXT)
            if handle:
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    try:
                        text = ctypes.string_at(ptr).decode("mbcs", errors="replace")
                    finally:
                        kernel32.GlobalUnlock(handle)
        return text
    finally:
        user32.CloseClipboard()


def _clipboard_via_powershell() -> str:
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "try { Get-Clipboard -Raw } catch { '' }",
            ],
            stderr=subprocess.DEVNULL,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return out.decode("utf-8", errors="replace").replace("\r\n", "\n")
    except Exception as exc:
        log("DEBUG clipboard powershell fallback failed: " + str(exc))
        return ""


def _clipboard_via_tk() -> str:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception as exc:
        log("DEBUG clipboard tk fallback failed: " + str(exc))
        return ""


def clipboard_text(_keyboard_mod=None) -> str:
    """Return latest clipboard text; never treat 64-bit GlobalLock truncation as empty."""
    text = _clipboard_via_win32()
    if text:
        log("DEBUG clipboard source=win32 length=" + str(len(text)))
        return text
    text = _clipboard_via_powershell()
    if text:
        log("DEBUG clipboard source=powershell length=" + str(len(text)))
        return text
    text = _clipboard_via_tk()
    if text:
        log("DEBUG clipboard source=tk length=" + str(len(text)))
        return text
    log("DEBUG clipboard: all readers returned empty")
    return ""


def wait_keys_up(keyboard_mod, keys, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if not any(keyboard_mod.is_pressed(k) for k in keys):
                time.sleep(0.02)
                if not any(keyboard_mod.is_pressed(k) for k in keys):
                    return True
        except Exception:
            return True
        time.sleep(0.01)
    return False


class InsertEngine:
    def __init__(self, keyboard_mod, delay_ms: int) -> None:
        self.kb = keyboard_mod
        self.delay_ms = delay_ms
        self._lock = threading.Lock()
        self._busy = False
        self._n = 0

    def on_hotkey(self) -> None:
        self._n += 1
        log("HOTKEY FIRED #" + str(self._n) + " ctrl+b")
        threading.Thread(target=self._type, daemon=True).start()

    def _type(self) -> None:
        with self._lock:
            if self._busy:
                log("DEBUG skip: already typing")
                return
            self._busy = True
        try:
            text = clipboard_text(self.kb)
            preview = text[:80].replace("\n", "\\n") if text else ""
            log("DEBUG clipboard length=" + str(len(text)) + " preview=" + repr(preview))
            if not text:
                log("FAIL: clipboard empty - copy text with Ctrl+C first, then Ctrl+B")
                try:
                    ctypes.windll.user32.MessageBeep(0x00000030)
                except Exception:
                    pass
                return
            log("DEBUG waiting for Ctrl+B release...")
            if not wait_keys_up(self.kb, ["ctrl", "b"], timeout=2.0):
                log("FAIL: keys still held - release Ctrl and B, retry")
                return
            log("DEBUG typing " + str(len(text)) + " chars delayMs=" + str(self.delay_ms))
            typed = 0
            for ch in text:
                try:
                    if self.kb.is_pressed("esc"):
                        log("DEBUG cancelled by Escape")
                        break
                except Exception:
                    pass
                if ch in ("\n", "\r"):
                    send_vk(VK_RETURN)
                elif ch == "\t":
                    send_vk(VK_TAB)
                else:
                    if not send_unicode_char(ch):
                        try:
                            self.kb.write(ch, delay=0, restore_state_after=False)
                        except Exception as exc:
                            log("DEBUG write fail: " + str(exc))
                            continue
                typed += 1
                if self.delay_ms > 0:
                    time.sleep(self.delay_ms / 1000.0)
            log("DONE typed=" + str(typed) + "/" + str(len(text)))
        except Exception:
            log("ERROR typewriter:\n" + traceback.format_exc())
        finally:
            with self._lock:
                self._busy = False


def parse_args():
    p = argparse.ArgumentParser(description="copy-hack - Ctrl+B types clipboard (not paste)")
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--list-hotkeys", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--cleanup-only", action="store_true", help="Only auto-clean and exit")
    p.add_argument(
        "--unregister", "--remove-hotkeys", "--uninstall",
        dest="unregister", action="store_true",
    )
    p.add_argument("--no-cleanup", action="store_true", help="Skip killing other instances")
    return p.parse_args()


def main() -> int:
    boot("BOOT: entered main()")
    args = parse_args()

    if sys.platform != "win32":
        boot("ERROR: Windows only")
        return 1

    if not args.no_cleanup:
        auto_cleanup()
    else:
        boot("CLEANUP: skipped (--no-cleanup)")

    if args.cleanup_only:
        boot("CLEANUP-ONLY done")
        return 0

    cfg = force_reset_config(0 if args.delay_ms is None else args.delay_ms)

    if args.reset or args.list_hotkeys or args.self_test:
        log("admin=" + str(is_admin()))
        log("hotkey=ctrl+b delayMs=" + str(cfg["delayMs"]))
        log("OK")
        return 0

    if args.unregister:
        cfg["enabled"]["typewriter"] = False
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        log("Unregister wrote enabled=false (NEXT start will wipe this again)")
        log("To stop a running copy_hack: Ctrl+C in its window, or python copy_hack.py --cleanup-only")
        return 0

    log("admin=" + str(is_admin()))
    if not is_admin():
        log("WARN: not admin - hotkeys often fail. You said you are admin; if admin=False, this is NOT an elevated python.")

    kb = import_keyboard()

    engine = InsertEngine(kb, int(cfg["delayMs"]))
    boot("BOOT: registering hotkey ctrl+b ...")
    try:
        kb.add_hotkey("ctrl+b", engine.on_hotkey, suppress=True, trigger_on_release=False)
    except Exception:
        log("ERROR add_hotkey failed:\n" + traceback.format_exc())
        log("FIX: close other copy_hack windows, run: python copy_hack.py --cleanup-only")
        log("Then: python -u copy_hack.py")
        return 1
    boot("BOOT: hotkey registered OK")

    log("READY - copy text, click a field, press Ctrl+B")
    log("You MUST see HOTKEY FIRED in this window when Ctrl+B works")
    log("If Ctrl+B prints nothing: another app ate the chord, or hook failed - run --cleanup-only")
    log("quit: Ctrl+C   log: " + str(LOG_PATH))
    log("NOTE: blank console with NO BOOT lines = you are still running OLD copy_hack.py from an old ZIP")

    try:
        kb.wait()
    except KeyboardInterrupt:
        try:
            kb.unhook_all_hotkeys()
        except Exception:
            pass
        log("Bye")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        boot("FATAL:\n" + traceback.format_exc())
        raise
