// swift-tools-version:5.9
// The game rules live in a plain Swift module so they can be unit-tested anywhere
// (`swift test`); the iOS app compiles the same sources alongside its SpriteKit renderer.
import PackageDescription

let package = Package(
    name: "ApnaSassy",
    products: [.library(name: "GameCore", targets: ["GameCore"])],
    targets: [
        .target(name: "GameCore"),
        .testTarget(name: "GameCoreTests", dependencies: ["GameCore"]),
    ]
)
