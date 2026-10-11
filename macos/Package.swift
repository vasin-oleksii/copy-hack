// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TypewriterPaste",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "TypewriterPaste", targets: ["TypewriterPaste"])
    ],
    targets: [
        .executableTarget(
            name: "TypewriterPaste",
            path: "Sources/TypewriterPaste",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("Carbon"),
                .linkedFramework("ApplicationServices")
            ]
        )
    ]
)
