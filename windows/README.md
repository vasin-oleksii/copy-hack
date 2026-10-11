# Windows

| Hotkey | Action |
|--------|--------|
| **Ctrl+K** | Type clipboard fast (`delayMs: 0`) |
| **Ctrl+L** | Paste (real Ctrl+V via SendInput) |

Full chords only. **Bare Ctrl does nothing** (no paste, no copy, no stuck modifier).

```powershell
pip install -r requirements.txt
python copy_hack.py
```

Remove shortcuts:

```powershell
python copy_hack.py --unregister
# aliases: --remove-hotkeys  --uninstall
python copy_hack.py --list-hotkeys
```

Closing the process (Ctrl+C) clears hotkeys. No separate OS install.
