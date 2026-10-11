# Windows

| Hotkey | Action |
|--------|--------|
| **Ctrl+L** | Type clipboard very fast (`delayMs: 0`, character-by-character) |

Full chord only. **Bare Ctrl does nothing** (no paste, no copy).

```powershell
pip install -r requirements.txt
python copy_hack.py
```

Remove shortcut:

```powershell
python copy_hack.py --unregister
# aliases: --remove-hotkeys  --uninstall
python copy_hack.py --list-hotkeys
```

Closing the process (Ctrl+C) also clears the hotkey. No separate OS install.
