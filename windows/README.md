# Windows

| Hotkey | Action |
|--------|--------|
| **Ctrl+K** | Type clipboard fast (`delayMs: 0`) |
| **Ctrl+L** | Paste (Ctrl+V) |

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

Closing the process (Ctrl+C) clears hotkeys. There is no separate OS install.
