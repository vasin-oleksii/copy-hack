# copy-hack

Copy text, then use a hotkey.

## Windows (priority)

| Hotkey | Action |
|--------|--------|
| **Ctrl+K** | Type clipboard very fast (`delayMs: 0`, not paste) |
| **Ctrl+L** | Instant paste (simulates Ctrl+V) |

```powershell
cd windows
pip install -r requirements.txt
python copy_hack.py
```

**Remove shortcuts:**

```powershell
python copy_hack.py --unregister
```

Hotkeys exist only while the script runs — **Ctrl+C** in that window also removes them.  
`--unregister` / `--remove-hotkeys` disables them in config too.

```powershell
python copy_hack.py --list-hotkeys
```

Config: `%LOCALAPPDATA%\TypewriterPaste\config.json` (see `windows/config.example.json`).

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
