# Windows

| Hotkey | Action |
|--------|--------|
| **Ctrl+B** | Type clipboard very fast (`delayMs: 0`, same as macOS — not paste) |

```bat
cd windows
pip install -r requirements.txt
python copy_hack.py
```

You **must** see `READY` and diagnostics in the console. Leave that window open.

1. Copy text (Ctrl+C)
2. Click a text field
3. Press **Ctrl+B**
4. Console should print `HOTKEY FIRED` then `DONE typed=…`

## Debug

```bat
python copy_hack.py --self-test
```

Log file: `%LOCALAPPDATA%\TypewriterPaste\debug.log`

Every start **force-resets** config to Ctrl+B / delayMs=0 / enabled (old `--unregister` cannot stick).

Remove / stop:

```bat
python copy_hack.py --unregister
```

Or **Ctrl+C** in the running window.

Run **as Administrator** if Ctrl+B does not print `HOTKEY FIRED`.
