# copy-hack

Copy text, then insert it with a hotkey.

| OS | Hotkey | Default action |
|----|--------|----------------|
| macOS | **⌘K** | Instant paste (⌘V) |
| Windows | **Ctrl+K** | Instant paste (Ctrl+V) |

Optional typewriter (character-by-character) mode on both platforms.

---

## macOS

1. `cd macos && bash build.sh`
2. `open TypewriterPaste.app`
3. **System Settings → Privacy & Security → Accessibility** → enable **TypewriterPaste**
4. Copy (⌘C) → focus a field → **⌘K**

Quit: menu bar **⌨ → Quit**

Typewriter mode: menu bar **⌨ → Typewriter**

---

## Windows

1. Install [Python 3](https://www.python.org/downloads/) (check “Add to PATH”)
2. Open PowerShell in `windows/`:
   ```powershell
   pip install -r requirements.txt
   python copy_hack.py
   ```
3. If the hotkey fails in some apps, **Run PowerShell as Administrator** and start again
4. Copy (Ctrl+C) → focus a field → **Ctrl+K**

Quit: **Ctrl+C** in the PowerShell window

Typewriter mode:
```powershell
python copy_hack.py --mode typewriter
```
Or set `"mode": "typewriter"` in `%LOCALAPPDATA%\TypewriterPaste\config.json`

---

## Layout

- `macos/` — Swift menu-bar app (source of truth for Mac behavior)
- `windows/` — Python background script
