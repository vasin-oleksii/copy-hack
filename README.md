# copy-hack

Copy text, then press the hotkey — it **types** the clipboard character-by-character as fast as possible (not paste / not Ctrl+V / ⌘V).

| OS | Hotkey | Default |
|----|--------|---------|
| macOS | **⌘K** | Typewriter, `delayMs: 0` |
| Windows | **Ctrl+K** | Typewriter, `delayMs: 0` |

Paste mode (real Ctrl+V / ⌘V) is optional and non-default.

---

## macOS

1. `cd macos && bash build.sh`
2. `open TypewriterPaste.app`
3. **System Settings → Privacy & Security → Accessibility** → enable **TypewriterPaste**
4. Copy (⌘C) → focus a field → **⌘K**

Quit: menu bar **⌨ → Quit**

Optional paste mode: menu bar **⌨ → Instant paste (⌘V)**

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

Optional paste mode:
```powershell
python copy_hack.py --mode paste
```
Or set `"mode": "paste"` in `%LOCALAPPDATA%\TypewriterPaste\config.json`

---

## Layout

- `macos/` — Swift menu-bar app (source of truth for Mac behavior)
- `windows/` — Python background script
