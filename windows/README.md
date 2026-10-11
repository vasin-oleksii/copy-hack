# Windows

| Hotkey | Action |
|--------|--------|
| **Ctrl+B** | Type clipboard very fast (`delayMs: 0`) — **not paste** |

## Run (recommended)

Double-click or from Admin cmd:

```bat
cleanup_and_run.bat
```

Or:

```bat
python -u copy_hack.py
```

You **must** see lines starting with `BOOT:` then `READY`.

If the console stays **blank** with no `BOOT:` → you are running an **old** `copy_hack.py` (old ZIP). Replace the file.

## Why Admin still showed a blank line before

1. Old ZIP from GitHub (push of the debug build may not have reached the PC).
2. Script hung inside `keyboard` hook while a previous `copy_hack.py` was still running — prints happened **after** that hang in old builds.
3. This build prints `BOOT` **before** importing `keyboard`, then **auto-kills** other `copy_hack` processes and wipes `%LOCALAPPDATA%\TypewriterPaste`.

## Debug

```bat
python -u copy_hack.py --cleanup-only
python -u copy_hack.py --self-test
```

Log: `%LOCALAPPDATA%\TypewriterPaste\debug.log`
