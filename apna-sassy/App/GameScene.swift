import GameController
import GameCore
import SpriteKit
import UIKit

/// Draws a `World` and feeds it input every frame. All game rules live in GameCore.
@MainActor
final class GameScene: SKScene {
    let world: World
    /// Touch controls write here (see GameView); a controller or keyboard is merged in each frame.
    var touchInput = Input()
    var onEvent: (@MainActor (GameEvent) -> Void)?
    var onTick: (@MainActor (World) -> Void)?

    private let palette: Palette
    private let tileSet: TileSet
    private var tile: CGFloat = 40
    private let worldNode = SKNode()
    private let backdrop = SKNode()
    private let cam = SKCameraNode()
    private let sassy = SKSpriteNode(texture: Art.sassyIdle)
    private var tileNodes: [Int: SKSpriteNode] = [:]
    private var gemNodes: [Int: SKSpriteNode] = [:]
    private var enemyNodes: [Int: SKSpriteNode] = [:]
    private var checkpointNodes: [SKSpriteNode] = []
    private var built = false
    private var lastTime: TimeInterval?
    private var runFrame = 0.0
    private var padPresses = 0
    private var padJumpWasDown = false

    private typealias TileSet = Art.TileSet

    init(world: World) {
        self.world = world
        self.palette = Palette.of(world.level.definition.theme)
        self.tileSet = Art.tiles(palette)
        super.init(size: CGSize(width: 800, height: 400))
        scaleMode = .resizeFill
        anchorPoint = .zero
        backgroundColor = palette.skyBottom
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    override func didMove(to view: SKView) {
        guard !built else { return }
        built = true
        // Show about ten rows of the level whatever the phone's size.
        tile = max(24, (size.height / 10).rounded(.down))
        addChild(backdrop)
        addChild(worldNode)
        camera = cam
        addChild(cam)
        buildBackdrop()
        buildLevel()
        follow(immediately: true)
    }

    override func didChangeSize(_ oldSize: CGSize) {
        super.didChangeSize(oldSize)
        if built { follow(immediately: true) }
    }

    // MARK: - Building

    private func point(_ v: Vec2) -> CGPoint { CGPoint(x: v.x * tile, y: v.y * tile) }

    private func buildBackdrop() {
        let sky = SKSpriteNode(texture: gradient(top: palette.skyTop, bottom: palette.skyBottom))
        sky.size = CGSize(width: 4000, height: 4000)
        sky.zPosition = -100
        cam.addChild(sky)

        // Rolling shapes that move slower than the level, for depth.
        let width = CGFloat(world.level.width) * tile
        var x: CGFloat = 0
        var i = 0
        while x < width {
            let r = tile * CGFloat([3.5, 5, 4.2, 6][i % 4])
            let hill = SKShapeNode(circleOfRadius: r)
            hill.fillColor = palette.hills
            hill.strokeColor = .clear
            hill.position = CGPoint(x: x, y: tile * (world.level.definition.theme == .sky ? 3 : 1))
            hill.zPosition = -50
            backdrop.addChild(hill)
            x += r * 1.6
            i += 1
        }
        if world.level.definition.theme == .dusk || world.level.definition.theme == .cavern {
            for s in 0..<60 {
                let star = SKShapeNode(circleOfRadius: CGFloat(1 + s % 2))
                star.fillColor = .init(white: 1, alpha: world.level.definition.theme == .dusk ? 0.8 : 0.25)
                star.strokeColor = .clear
                star.position = CGPoint(x: CGFloat((s * 7919) % max(Int(width), 1)),
                                        y: tile * CGFloat(5 + (s * 31) % 7))
                star.zPosition = -60
                backdrop.addChild(star)
            }
        }
    }

    private func buildLevel() {
        let level = world.level
        let size = CGSize(width: tile, height: tile)
        for y in 0..<level.height {
            for x in 0..<level.width {
                guard let texture = texture(for: level.tile(x, y), x: x, y: y) else { continue }
                let node = SKSpriteNode(texture: texture, size: size)
                node.anchorPoint = .zero
                node.position = CGPoint(x: CGFloat(x) * tile, y: CGFloat(y) * tile)
                worldNode.addChild(node)
                tileNodes[y * level.width + x] = node
            }
        }

        let goal = SKSpriteNode(texture: Art.goal(), size: CGSize(width: tile, height: tile * 3))
        goal.anchorPoint = CGPoint(x: 0.5, y: 0)
        goal.position = point(level.goal)
        goal.zPosition = 1
        worldNode.addChild(goal)

        for cp in level.checkpoints {
            let node = SKSpriteNode(texture: Art.checkpoint(active: false), size: CGSize(width: tile, height: tile * 2))
            node.anchorPoint = CGPoint(x: 0.5, y: 0)
            node.position = point(cp)
            node.zPosition = 1
            worldNode.addChild(node)
            checkpointNodes.append(node)
        }

        for (i, gem) in level.gems.enumerated() {
            let node = SKSpriteNode(texture: Art.gem, size: CGSize(width: tile * 0.5, height: tile * 0.5))
            node.position = point(gem)
            node.zPosition = 2
            node.run(.repeatForever(.sequence([
                .moveBy(x: 0, y: tile * 0.08, duration: 0.6), .moveBy(x: 0, y: -tile * 0.08, duration: 0.6),
            ])))
            worldNode.addChild(node)
            gemNodes[i] = node
        }

        for enemy in world.enemies {
            let frames = textures(for: enemy.kind)
            let node = SKSpriteNode(texture: frames[0],
                                    size: CGSize(width: tile * 0.95, height: tile * 0.95 * 8 / 12))
            node.anchorPoint = CGPoint(x: 0.5, y: 0)
            node.zPosition = 3
            node.run(.repeatForever(.animate(with: frames, timePerFrame: enemy.kind == .bat ? 0.15 : 0.25)))
            worldNode.addChild(node)
            enemyNodes[enemy.id] = node
        }

        sassy.size = CGSize(width: tile * 1.35, height: tile * 0.975)   // 18x13 sprite
        sassy.anchorPoint = CGPoint(x: 0.5, y: 0)
        sassy.zPosition = 5
        worldNode.addChild(sassy)
        sync()
    }

    private func texture(for t: Tile, x: Int, y: Int) -> SKTexture? {
        switch t {
        case .empty: return nil
        case .ground: return world.level.tile(x, y + 1).isSolid ? tileSet.groundFill : tileSet.groundTop
        case .brick: return tileSet.brick
        case .crate: return tileSet.crate
        case .usedCrate: return tileSet.usedCrate
        case .platform: return tileSet.platform
        case .spike: return tileSet.spike
        case .spring: return tileSet.spring
        }
    }

    private func textures(for kind: EnemyKind) -> [SKTexture] {
        switch kind {
        case .beetle: return Art.beetle
        case .bat: return Art.bat
        case .spiker: return Art.spiker
        }
    }

    // MARK: - Frame loop

    override func update(_ currentTime: TimeInterval) {
        let dt = lastTime.map { currentTime - $0 } ?? 0
        lastTime = currentTime
        guard !isPaused else { return }
        world.update(dt: dt, input: mergedInput())
        for event in world.drainEvents() { play(event) }
        sync()
        follow(immediately: false)
        onTick?(world)
    }

    /// Unpausing must not hand the world one giant time step.
    func resetClock() { lastTime = nil }

    private func mergedInput() -> Input {
        var input = touchInput
        var jumpDown = false
        if let pad = GCController.current?.extendedGamepad {
            let x = pad.leftThumbstick.xAxis.value + pad.dpad.xAxis.value
            input.left = input.left || x < -0.3
            input.right = input.right || x > 0.3
            jumpDown = pad.buttonA.isPressed
        }
        if let keys = GCKeyboard.coalesced?.keyboardInput {
            func down(_ code: GCKeyCode) -> Bool { keys.button(forKeyCode: code)?.isPressed ?? false }
            input.left = input.left || down(.leftArrow) || down(.keyA)
            input.right = input.right || down(.rightArrow) || down(.keyD)
            jumpDown = jumpDown || down(.spacebar) || down(.upArrow) || down(.keyW)
        }
        if jumpDown && !padJumpWasDown { padPresses += 1 }
        padJumpWasDown = jumpDown
        input.jumpHeld = input.jumpHeld || jumpDown
        input.jumpPresses += padPresses
        return input
    }

    private func sync() {
        let p = world.player
        sassy.position = point(p.position)
        sassy.xScale = p.facing < 0 ? -1 : 1
        switch world.pose {
        case .run:
            runFrame += abs(p.velocity.x) / 60 * 1.6
            sassy.texture = Art.sassyRun[Int(runFrame) % 2]
        case .jump, .fall, .cheer, .hurt:
            sassy.texture = Art.sassyJump
        case .idle, .dead:
            sassy.texture = Art.sassyIdle
        }
        sassy.alpha = p.isInvulnerable && !p.isDead && Int(world.time * 12) % 2 == 0 ? 0.35 : 1
        sassy.zRotation = p.isDead ? .pi : 0
        sassy.isHidden = false

        for enemy in world.enemies {
            guard let node = enemyNodes[enemy.id], enemy.alive else { continue }
            node.position = point(enemy.position)
            node.xScale = enemy.facing > 0 ? -1 : 1
        }
    }

    private func follow(immediately: Bool) {
        let level = world.level
        let halfW = size.width / 2, halfH = size.height / 2
        let levelW = CGFloat(level.width) * tile, levelH = CGFloat(level.height) * tile
        let p = point(world.player.position)
        // Look a little ahead in the direction Apna Sassy faces.
        var target = CGPoint(x: p.x + CGFloat(world.player.facing) * tile * 1.5, y: p.y + tile * 1.5)
        target.x = min(max(target.x, halfW), max(halfW, levelW - halfW))
        target.y = min(max(target.y, halfH), max(halfH, levelH - halfH))
        if immediately {
            cam.position = target
        } else {
            cam.position.x += (target.x - cam.position.x) * 0.15
            cam.position.y += (target.y - cam.position.y) * 0.08
        }
        backdrop.position = CGPoint(x: cam.position.x * 0.6, y: cam.position.y * 0.5)
    }

    // MARK: - Effects

    private func play(_ event: GameEvent) {
        onEvent?(event)
        switch event {
        case .gemCollected(let i):
            gemNodes[i]?.removeAllActions()
            gemNodes[i]?.run(.sequence([
                .group([.moveBy(x: 0, y: tile * 0.8, duration: 0.25), .fadeOut(withDuration: 0.25),
                        .scale(to: 1.4, duration: 0.25)]),
                .removeFromParent(),
            ]))
            gemNodes[i] = nil
        case .crateOpened(let x, let y):
            let node = tileNodes[y * world.level.width + x]
            node?.texture = tileSet.usedCrate
            node?.run(.sequence([.moveBy(x: 0, y: tile * 0.2, duration: 0.06), .moveBy(x: 0, y: -tile * 0.2, duration: 0.08)]))
            let pop = SKSpriteNode(texture: Art.gem, size: CGSize(width: tile * 0.5, height: tile * 0.5))
            pop.position = CGPoint(x: (CGFloat(x) + 0.5) * tile, y: (CGFloat(y) + 1.2) * tile)
            pop.zPosition = 2
            worldNode.addChild(pop)
            pop.run(.sequence([.moveBy(x: 0, y: tile, duration: 0.3), .fadeOut(withDuration: 0.15), .removeFromParent()]))
        case .enemyStomped(let id):
            guard let node = enemyNodes[id] else { return }
            enemyNodes[id] = nil
            node.removeAllActions()
            node.run(.sequence([
                .scaleX(to: node.xScale * 1.2, y: 0.3, duration: 0.08),
                .wait(forDuration: 0.25), .fadeOut(withDuration: 0.2), .removeFromParent(),
            ]))
            burst(at: node.position, color: .white)
        case .checkpoint(let i):
            checkpointNodes[i].texture = Art.checkpoint(active: true)
            burst(at: checkpointNodes[i].position, color: .init(hex: 0x5bdc6a))
        case .sprang:
            sassy.run(.sequence([.scaleY(to: 0.7, duration: 0.05), .scaleY(to: 1, duration: 0.12)]))
        case .landed:
            sassy.run(.sequence([.scaleY(to: 0.85, duration: 0.04), .scaleY(to: 1, duration: 0.08)]))
        case .hurt:
            shake()
        case .died:
            shake()
        case .won:
            burst(at: point(world.level.goal), color: .init(hex: 0xffd447))
        case .jumped, .respawned:
            break
        }
    }

    private func burst(at position: CGPoint, color: UIColor) {
        for i in 0..<10 {
            let dot = SKShapeNode(rectOf: CGSize(width: tile * 0.12, height: tile * 0.12))
            dot.fillColor = color
            dot.strokeColor = .clear
            dot.position = CGPoint(x: position.x, y: position.y + tile * 0.4)
            dot.zPosition = 6
            worldNode.addChild(dot)
            let angle = CGFloat(i) / 10 * .pi * 2
            dot.run(.sequence([
                .group([.moveBy(x: cos(angle) * tile, y: sin(angle) * tile, duration: 0.35),
                        .fadeOut(withDuration: 0.35)]),
                .removeFromParent(),
            ]))
        }
    }

    private func shake() {
        let d = tile * 0.12
        worldNode.run(.sequence([
            .moveBy(x: d, y: 0, duration: 0.03), .moveBy(x: -2 * d, y: 0, duration: 0.05),
            .moveBy(x: d, y: 0, duration: 0.03),
        ]))
    }

    private func gradient(top: UIColor, bottom: UIColor) -> SKTexture {
        let image = UIGraphicsImageRenderer(size: CGSize(width: 4, height: 256)).image { ctx in
            let colors = [top.cgColor, bottom.cgColor] as CFArray
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                ctx.cgContext.drawLinearGradient(g, start: .zero, end: CGPoint(x: 0, y: 256), options: [])
            }
        }
        return SKTexture(image: image)
    }
}
