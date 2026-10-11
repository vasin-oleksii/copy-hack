import AppKit
import ApplicationServices
import Carbon
import Foundation

// MARK: - Config

enum InsertMode: String, Codable {
    /// Character-by-character CGEvent typing (default — not ⌘V).
    case typewriter
    /// Optional: simulate ⌘V — bulk paste of clipboard contents.
    case paste
}

struct Config: Codable {
    /// Delay between characters in typewriter mode (ms). 0 = no sleep between chars.
    var delayMs: UInt32
    /// Escape stops an in-progress typewriter typeout.
    var cancelOnEscape: Bool
    /// Default: typewriter (character-by-character), delayMs 0.
    var mode: InsertMode

    static let `default` = Config(delayMs: 0, cancelOnEscape: true, mode: .typewriter)

    enum CodingKeys: String, CodingKey {
        case delayMs, cancelOnEscape, mode
    }

    init(delayMs: UInt32, cancelOnEscape: Bool, mode: InsertMode) {
        self.delayMs = delayMs
        self.cancelOnEscape = cancelOnEscape
        self.mode = mode
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        delayMs = try c.decodeIfPresent(UInt32.self, forKey: .delayMs) ?? Config.default.delayMs
        cancelOnEscape = try c.decodeIfPresent(Bool.self, forKey: .cancelOnEscape) ?? Config.default.cancelOnEscape
        mode = try c.decodeIfPresent(InsertMode.self, forKey: .mode) ?? Config.default.mode
    }

    static var supportDir: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        return base.appendingPathComponent("TypewriterPaste", isDirectory: true)
    }

    static var configURL: URL {
        supportDir.appendingPathComponent("config.json")
    }

    static func load(cliDelayMs: UInt32?) -> Config {
        var config = Config.default
        if FileManager.default.fileExists(atPath: configURL.path) {
            do {
                let data = try Data(contentsOf: configURL)
                config = try JSONDecoder().decode(Config.self, from: data)
            } catch {
                fputs("TypewriterPaste: could not read config at \(configURL.path): \(error)\n", stderr)
            }
        }
        if let cliDelayMs {
            config.delayMs = cliDelayMs
        }
        return config
    }

    func save() {
        try? FileManager.default.createDirectory(at: Self.supportDir, withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(self) else { return }
        try? data.write(to: Self.configURL, options: .atomic)
    }
}

// MARK: - CLI

struct CLI {
    var delayMs: UInt32?
    var printHelp = false

    static func parse(_ args: [String]) -> CLI {
        var cli = CLI()
        var i = 0
        while i < args.count {
            let arg = args[i]
            switch arg {
            case "-h", "--help":
                cli.printHelp = true
            case "--delay-ms":
                i += 1
                if i < args.count, let v = UInt32(args[i]) {
                    cli.delayMs = v
                }
            case let s where s.hasPrefix("--delay-ms="):
                if let v = UInt32(s.dropFirst("--delay-ms=".count)) {
                    cli.delayMs = v
                }
            default:
                break
            }
            i += 1
        }
        return cli
    }

    static let helpText = """
    TypewriterPaste — Command+K types clipboard character-by-character (not ⌘V).

    Usage:
      TypewriterPaste [--delay-ms N]

    Options:
      --delay-ms N   Delay between characters in ms (default: 0 = no sleep)
      -h, --help     Show this help

    Config file:
      ~/Library/Application Support/TypewriterPaste/config.json

    Example:
      { "mode": "typewriter", "delayMs": 0, "cancelOnEscape": true }

    Modes (menu bar or config "mode"):
      typewriter  Character-by-character typing (default, delayMs 0)
      paste       Optional instant ⌘V paste

    Requires Accessibility permission (see README).
    """
}

// MARK: - Insert engine

final class InsertEngine {
    private let queue = DispatchQueue(label: "typewriter.paste.insert", qos: .userInitiated)
    private let lock = NSLock()
    private var cancelRequested = false
    private(set) var isTyping = false

    var delayMs: UInt32
    var cancelOnEscape: Bool
    var mode: InsertMode

    init(config: Config) {
        self.delayMs = config.delayMs
        self.cancelOnEscape = config.cancelOnEscape
        self.mode = config.mode
    }

    func requestCancel() {
        lock.lock()
        cancelRequested = true
        lock.unlock()
    }

    /// Hotkey entry: type (default) or paste depending on mode.
    func handleHotKey() {
        switch mode {
        case .typewriter:
            typeClipboard()
        case .paste:
            pasteClipboard()
        }
    }

    // MARK: Instant paste (⌘V)

    private func pasteClipboard() {
        // Wait for ⌘K to finish, then synthesize ⌘V.
        queue.asyncAfter(deadline: .now() + 0.08) {
            Self.releaseModifiers()
            Self.postCommandV()
        }
    }

    private static func postCommandV() {
        let source = CGEventSource(stateID: .hidSystemState)
        let keyV = CGKeyCode(kVK_ANSI_V)

        if let down = CGEvent(keyboardEventSource: source, virtualKey: keyV, keyDown: true) {
            down.flags = .maskCommand
            down.post(tap: .cghidEventTap)
        }
        if let up = CGEvent(keyboardEventSource: source, virtualKey: keyV, keyDown: false) {
            up.flags = .maskCommand
            up.post(tap: .cghidEventTap)
        }
    }

    // MARK: Typewriter

    private func typeClipboard() {
        lock.lock()
        if isTyping {
            lock.unlock()
            return
        }
        isTyping = true
        cancelRequested = false
        lock.unlock()

        let text = Self.clipboardString()
        guard let text, !text.isEmpty else {
            lock.lock()
            isTyping = false
            lock.unlock()
            NSSound.beep()
            return
        }

        queue.asyncAfter(deadline: .now() + 0.12) { [weak self] in
            self?.type(text)
        }
    }

    private func type(_ text: String) {
        defer {
            lock.lock()
            isTyping = false
            cancelRequested = false
            lock.unlock()
        }

        Self.releaseModifiers()

        for scalar in text.unicodeScalars {
            lock.lock()
            let cancelled = cancelRequested
            lock.unlock()
            if cancelled { break }

            if cancelOnEscape, Self.isEscapePressed() {
                break
            }

            Self.typeScalar(scalar)
            if delayMs > 0 {
                usleep(useconds_t(delayMs) * 1000)
            }
        }
    }

    private static func clipboardString() -> String? {
        NSPasteboard.general.string(forType: .string)
    }

    private static func releaseModifiers() {
        let keys: [CGKeyCode] = [
            CGKeyCode(kVK_Command),
            CGKeyCode(kVK_RightCommand),
            CGKeyCode(kVK_Shift),
            CGKeyCode(kVK_RightShift),
            CGKeyCode(kVK_Option),
            CGKeyCode(kVK_RightOption),
            CGKeyCode(kVK_Control),
            CGKeyCode(kVK_RightControl)
        ]
        for key in keys {
            if let up = CGEvent(keyboardEventSource: nil, virtualKey: key, keyDown: false) {
                up.flags = []
                up.post(tap: .cghidEventTap)
            }
        }
    }

    private static func isEscapePressed() -> Bool {
        CGEventSource.keyState(.combinedSessionState, key: CGKeyCode(kVK_Escape))
    }

    private static func typeScalar(_ scalar: UnicodeScalar) {
        switch scalar.value {
        case 0x000A, 0x000D:
            postKey(CGKeyCode(kVK_Return))
            return
        case 0x0009:
            postKey(CGKeyCode(kVK_Tab))
            return
        default:
            break
        }

        var chars = Array(String(scalar).utf16)
        guard !chars.isEmpty else { return }

        let source = CGEventSource(stateID: .hidSystemState)

        if let down = CGEvent(keyboardEventSource: source, virtualKey: 0, keyDown: true) {
            down.flags = []
            down.keyboardSetUnicodeString(stringLength: chars.count, unicodeString: &chars)
            down.post(tap: .cghidEventTap)
        }
        if let up = CGEvent(keyboardEventSource: source, virtualKey: 0, keyDown: false) {
            up.flags = []
            up.keyboardSetUnicodeString(stringLength: chars.count, unicodeString: &chars)
            up.post(tap: .cghidEventTap)
        }
    }

    private static func postKey(_ key: CGKeyCode) {
        let source = CGEventSource(stateID: .hidSystemState)
        if let down = CGEvent(keyboardEventSource: source, virtualKey: key, keyDown: true) {
            down.flags = []
            down.post(tap: .cghidEventTap)
        }
        if let up = CGEvent(keyboardEventSource: source, virtualKey: key, keyDown: false) {
            up.flags = []
            up.post(tap: .cghidEventTap)
        }
    }
}

// MARK: - Global hotkey (Carbon)

final class HotKeyCenter {
    private var hotKeyRef: EventHotKeyRef?
    private var handlerRef: EventHandlerRef?
    private let engine: InsertEngine

    init(engine: InsertEngine) {
        self.engine = engine
    }

    func register() {
        var eventType = EventTypeSpec(
            eventClass: OSType(kEventClassKeyboard),
            eventKind: UInt32(kEventHotKeyPressed)
        )

        let userData = Unmanaged.passUnretained(self).toOpaque()
        InstallEventHandler(
            GetApplicationEventTarget(),
            hotKeyEventHandler,
            1,
            &eventType,
            userData,
            &handlerRef
        )

        let hotKeyID = EventHotKeyID(signature: OSType(0x54575054), /* 'TWPT' */ id: 1)
        RegisterEventHotKey(
            UInt32(kVK_ANSI_K),
            UInt32(cmdKey),
            hotKeyID,
            GetApplicationEventTarget(),
            0,
            &hotKeyRef
        )
    }

    fileprivate func handleHotKey() {
        engine.handleHotKey()
    }

    deinit {
        if let hotKeyRef { UnregisterEventHotKey(hotKeyRef) }
        if let handlerRef { RemoveEventHandler(handlerRef) }
    }
}

private func hotKeyEventHandler(
    _: EventHandlerCallRef?,
    _: EventRef?,
    userData: UnsafeMutableRawPointer?
) -> OSStatus {
    guard let userData else { return OSStatus(eventNotHandledErr) }
    let center = Unmanaged<HotKeyCenter>.fromOpaque(userData).takeUnretainedValue()
    center.handleHotKey()
    return noErr
}

// MARK: - Accessibility

enum AccessibilityGate {
    static func ensureTrusted() -> Bool {
        let opts = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
        return AXIsProcessTrustedWithOptions(opts)
    }
}

// MARK: - Menu bar app

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem?
    private var hotKeys: HotKeyCenter?
    private let engine: InsertEngine
    private var config: Config

    init(config: Config) {
        self.config = config
        self.engine = InsertEngine(config: config)
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if !AccessibilityGate.ensureTrusted() {
            presentAccessibilityAlert()
        }

        hotKeys = HotKeyCenter(engine: engine)
        hotKeys?.register()

        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = item.button {
            button.title = "⌨"
            button.toolTip = "TypewriterPaste — Command+K types clipboard"
        }
        item.menu = buildMenu()
        statusItem = item
    }

    private func buildMenu() -> NSMenu {
        let menu = NSMenu()

        let statusTitle: String
        switch config.mode {
        case .typewriter:
            statusTitle = "Command+K: Typewriter (\(config.delayMs) ms/char)"
        case .paste:
            statusTitle = "Command+K: Instant paste (⌘V)"
        }
        let status = NSMenuItem(title: statusTitle, action: nil, keyEquivalent: "")
        status.isEnabled = false
        menu.addItem(status)
        menu.addItem(.separator())

        let typeMode = NSMenuItem(
            title: "Typewriter (character-by-character)",
            action: #selector(setTypewriterMode),
            keyEquivalent: ""
        )
        typeMode.target = self
        typeMode.state = config.mode == .typewriter ? .on : .off
        menu.addItem(typeMode)

        let pasteMode = NSMenuItem(
            title: "Instant paste (⌘V) — optional",
            action: #selector(setPasteMode),
            keyEquivalent: ""
        )
        pasteMode.target = self
        pasteMode.state = config.mode == .paste ? .on : .off
        menu.addItem(pasteMode)

        menu.addItem(.separator())

        let speed = NSMenuItem(title: "Typing speed (typewriter mode)", action: nil, keyEquivalent: "")
        let speedMenu = NSMenu()
        for (label, ms) in [("Instant (0 ms)", 0), ("Fast (15 ms)", 15), ("Medium (35 ms)", 35), ("Slow (80 ms)", 80), ("Very slow (150 ms)", 150)] {
            let mi = NSMenuItem(title: label, action: #selector(setSpeed(_:)), keyEquivalent: "")
            mi.target = self
            mi.representedObject = ms
            mi.state = (config.delayMs == UInt32(ms)) ? .on : .off
            speedMenu.addItem(mi)
        }
        speed.submenu = speedMenu
        menu.addItem(speed)

        let openConfig = NSMenuItem(title: "Open config folder", action: #selector(openConfigFolder), keyEquivalent: "")
        openConfig.target = self
        menu.addItem(openConfig)

        menu.addItem(.separator())

        let quit = NSMenuItem(title: "Quit TypewriterPaste", action: #selector(quit), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)

        return menu
    }

    @objc private func setPasteMode() {
        config.mode = .paste
        engine.mode = .paste
        config.save()
        statusItem?.menu = buildMenu()
    }

    @objc private func setTypewriterMode() {
        config.mode = .typewriter
        engine.mode = .typewriter
        config.save()
        statusItem?.menu = buildMenu()
    }

    @objc private func setSpeed(_ sender: NSMenuItem) {
        guard let ms = sender.representedObject as? Int else { return }
        config.delayMs = UInt32(ms)
        engine.delayMs = config.delayMs
        config.save()
        statusItem?.menu = buildMenu()
    }

    @objc private func openConfigFolder() {
        try? FileManager.default.createDirectory(at: Config.supportDir, withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: Config.configURL.path) {
            config.save()
        }
        NSWorkspace.shared.open(Config.supportDir)
    }

    @objc private func quit() {
        config.save()
        NSApp.terminate(nil)
    }

    private func presentAccessibilityAlert() {
        let alert = NSAlert()
        alert.messageText = "Accessibility permission required"
        alert.informativeText = """
        TypewriterPaste needs Accessibility access to simulate keystrokes.

        1. Open System Settings → Privacy & Security → Accessibility
        2. Enable TypewriterPaste (or the Terminal you launched it from)
        3. Quit and reopen TypewriterPaste
        """
        alert.alertStyle = .warning
        alert.addButton(withTitle: "Open Settings")
        alert.addButton(withTitle: "Continue anyway")
        let response = alert.runModal()
        if response == .alertFirstButtonReturn {
            if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility") {
                NSWorkspace.shared.open(url)
            }
        }
    }
}

// MARK: - Entry

let cli = CLI.parse(Array(CommandLine.arguments.dropFirst()))
if cli.printHelp {
    print(CLI.helpText)
    exit(0)
}

let config = Config.load(cliDelayMs: cli.delayMs)
let app = NSApplication.shared
let delegate = AppDelegate(config: config)
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
