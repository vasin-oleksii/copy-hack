# copy-hack

Copy text, then use a hotkey.

## Windows (priority)

| Hotkey | Action |
|--------|--------|
| **Ctrl+K** | Type clipboard very fast (`delayMs: 0`) |
| **Ctrl+L** | Instant paste (Ctrl+V) |

Full chords only — **pressing Ctrl alone does nothing**.

```powershell
cd windows
pip install -r requirements.txt
python copy_hack.py
```

**Remove shortcuts:**

```powershell
python copy_hack.py --unregister
```

Hotkeys exist only while the script runs — **Ctrl+C** also removes them.  
`--list-hotkeys` shows bindings. Config: `%LOCALAPPDATA%\TypewriterPaste\config.json`.

If a hotkey fails in some apps, run PowerShell as Administrator.

---

## macOS

| Hotkey | Action |
|--------|--------|
| **⌘K** | Type clipboard very fast (`delayMs: 0`) |
| Menu | Optional instant paste (⌘V) |

```bash
cd macos && bash build.sh
open TypewriterPaste.app
```

Grant **Accessibility**, then copy → **⌘K**. Quit: menu bar **⌨ → Quit**.

---

## Layout

- `windows/` — Python: Ctrl+K type, Ctrl+L paste
- `macos/` — Swift menu-bar app
