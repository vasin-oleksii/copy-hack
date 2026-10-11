# copy-hack

Copy text, then use a hotkey to **type** it (not paste).

## Windows (priority)

| Hotkey | Action |
|--------|--------|
| **Ctrl+B** | Type clipboard very fast (`delayMs: 0`, like macOS) |

```bat
cd windows
pip install -r requirements.txt
python copy_hack.py
```

Console must show `READY`. Then copy → click field → **Ctrl+B**.  
You should see `HOTKEY FIRED` in that window.

**Debug:** `python copy_hack.py --self-test`  
**Log:** `%LOCALAPPDATA%\TypewriterPaste\debug.log`  
**Stop:** Ctrl+C in the script window, or `python copy_hack.py --unregister`

Every start resets config (ignores old commands / disabled flags). Run as Administrator if the hotkey never fires.

---

## macOS

| Hotkey | Action |
|--------|--------|
| **⌘K** | Type clipboard very fast (`delayMs: 0`) |

```bash
cd macos && bash build.sh
open TypewriterPaste.app
```

---

## Layout

- `windows/` — Python: Ctrl+B types clipboard fast
- `macos/` — Swift menu-bar app
