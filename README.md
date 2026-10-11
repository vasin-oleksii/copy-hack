# copy-hack

Copy text, then **type** it with a hotkey (not paste).

## Windows

| Hotkey | Action |
|--------|--------|
| **Ctrl+B** | Type clipboard very fast (`delayMs: 0`) |

**Recommended (Admin cmd):**

```bat
cd windows
cleanup_and_run.bat
```

Or: `python -u copy_hack.py`

You must see `BOOT:` then `READY`. Blank console with no `BOOT:` = old file — replace `copy_hack.py`.

Every start auto-cleans old config and other `copy_hack` processes.

---

## macOS

| Hotkey | Action |
|--------|--------|
| **⌘K** | Type clipboard very fast (`delayMs: 0`) |

```bash
cd macos && bash build.sh && open TypewriterPaste.app
```
