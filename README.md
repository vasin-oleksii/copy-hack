# copy-hack

Copy text, then use a hotkey to **type** it (not paste).

## Windows (priority)

| Hotkey | Action |
|--------|--------|
| **Ctrl+B** | Type clipboard very fast (`delayMs: 0`) |

Full chord only — **Ctrl alone does nothing**.

```powershell
cd windows
pip install -r requirements.txt
python copy_hack.py
```

**Remove shortcut:**

```powershell
python copy_hack.py --unregister
```

Hotkeys exist only while the script runs — **Ctrl+C** also removes them.  
`--list-hotkeys` shows bindings. Config: `%LOCALAPPDATA%\TypewriterPaste\config.json`.

If the hotkey fails in some apps, run PowerShell as Administrator.

---

## macOS

| Hotkey | Action |
|--------|--------|
| **⌘K** | Type clipboard very fast (`delayMs: 0`) |

```bash
cd macos && bash build.sh
open TypewriterPaste.app
```

Grant **Accessibility**, then copy → **⌘K**. Quit: menu bar **⌨ → Quit**.

---

## Layout

- `windows/` — Python: Ctrl+B types clipboard fast
- `macos/` — Swift menu-bar app
