import Foundation

/// What the player is pressing. `jumpPresses` counts every press, so a tap that
/// starts and ends between two frames is never lost.
public struct Input: Equatable {
    public var left = false
    public var right = false
    public var jumpHeld = false
    public var jumpPresses = 0
    public init() {}

    var direction: Double { (right ? 1 : 0) - (left ? 1 : 0) }
}

public enum Physics {
    public static let gravity = 62.0
    public static let maxFall = 20.0
    public static let runSpeed = 7.5
    public static let groundAccel = 55.0
    public static let airAccel = 38.0
    public static let groundFriction = 45.0
    public static let airFriction = 12.0
    public static let jumpVelocity = 20.0        // a little over 3 tiles high
    public static let jumpCutVelocity = 7.0       // releasing early caps the rise
    public static let springVelocity = 27.0       // about 6 tiles high
    public static let stompBounce = 11.0
    public static let stompBounceHeld = 18.0
    public static let coyoteTime = 0.1
    public static let jumpBuffer = 0.12
    public static let hurtTime = 1.4
    public static let respawnDelay = 1.2
    public static let step = 1.0 / 120.0
}

public enum PlayerPose: Equatable { case idle, run, jump, fall, hurt, dead, cheer }

public struct Player {
    public static let width = 0.7
    public static let height = 0.9
    public static let maxHearts = 3

    public var position: Vec2
    public var velocity = Vec2(0, 0)
    public var facing: Double = 1
    public var onGround = false
    public var hearts = Player.maxHearts
    public var hurtTimer = 0.0
    public var deadTimer = 0.0
    public var isDead = false
    var coyote = 0.0
    var buffer = 0.0
    var jumping = false

    public var box: Box { Box(foot: position, width: Player.width, height: Player.height) }
    public var isInvulnerable: Bool { hurtTimer > 0 }
}

public struct Enemy: Identifiable {
    public let id: Int
    public let kind: EnemyKind
    public var position: Vec2
    public var velocity = Vec2(0, 0)
    public var alive = true
    public var awake = false
    let origin: Vec2
    var phase = 0.0

    public var size: (w: Double, h: Double) {
        switch kind {
        case .beetle: return (0.8, 0.6)
        case .spiker: return (0.8, 0.7)
        case .bat: return (0.8, 0.5)
        }
    }

    public var box: Box { Box(foot: position, width: size.w, height: size.h) }
    public var facing: Double { velocity.x < 0 ? -1 : 1 }
}

public enum GameEvent: Equatable {
    case jumped
    case landed
    case sprang
    case gemCollected(index: Int)
    case crateOpened(x: Int, y: Int)
    case enemyStomped(id: Int)
    case hurt
    case died
    case respawned
    case checkpoint(index: Int)
    case won
}

public struct LevelResult: Equatable {
    public let time: Double
    public let gems: Int
    public let totalGems: Int
    public let deaths: Int
    public let score: Int
    public let stars: Int
}

public final class World {
    public private(set) var level: Level
    public private(set) var player: Player
    public private(set) var enemies: [Enemy]
    public private(set) var gemTaken: [Bool]
    public private(set) var gems = 0
    public let totalGems: Int
    public private(set) var score = 0
    public private(set) var deaths = 0
    public private(set) var time = 0.0
    public private(set) var result: LevelResult?
    public private(set) var activeCheckpoint: Int?
    /// Everything that happened since the last `drainEvents()`; the renderer plays effects from it.
    public private(set) var events: [GameEvent] = []

    private var lastJumpPresses = 0
    private var accumulator = 0.0

    public init(level: Level) {
        self.level = level
        self.player = Player(position: level.start)
        self.enemies = level.enemies.enumerated().map { i, e in
            Enemy(id: i, kind: e.kind, position: e.position, origin: e.position)
        }
        self.gemTaken = Array(repeating: false, count: level.gems.count)
        self.totalGems = level.gems.count + level.crateCount
    }

    public convenience init(definition: LevelDefinition) throws {
        self.init(level: try Level(definition))
    }

    public var isFinished: Bool { result != nil }

    public var pose: PlayerPose {
        if result != nil { return .cheer }
        if player.isDead { return .dead }
        if player.hurtTimer > Physics.hurtTime - 0.35 { return .hurt }
        if !player.onGround { return player.velocity.y > 0 ? .jump : .fall }
        return abs(player.velocity.x) > 0.5 ? .run : .idle
    }

    public func drainEvents() -> [GameEvent] {
        defer { events.removeAll() }
        return events
    }

    /// Advance the game by real elapsed time, in fixed physics steps.
    public func update(dt: Double, input: Input) {
        guard result == nil else { return }
        accumulator += min(dt, 0.1)
        while accumulator >= Physics.step {
            accumulator -= Physics.step
            step(Physics.step, input)
            if result != nil { break }
        }
    }

    // MARK: - Simulation

    private func step(_ dt: Double, _ input: Input) {
        time += dt
        if player.isDead {
            player.deadTimer -= dt
            if player.deadTimer <= 0 { respawn() }
            return
        }
        updatePlayer(dt, input)
        for i in enemies.indices { updateEnemy(i, dt) }
        checkPickups()
        checkEnemies(input)
        checkHazards()

        if player.box.intersects(Box(foot: level.goal, width: 0.8, height: 3)) {
            win()
        }
    }

    private func updatePlayer(_ dt: Double, _ input: Input) {
        var p = player
        let dir = input.direction

        if dir != 0 && p.hurtTimer < Physics.hurtTime - 0.3 {
            p.facing = dir
            let accel = p.onGround ? Physics.groundAccel : Physics.airAccel
            p.velocity.x = approach(p.velocity.x, dir * Physics.runSpeed, accel * dt)
        } else {
            let friction = p.onGround ? Physics.groundFriction : Physics.airFriction
            p.velocity.x = approach(p.velocity.x, 0, friction * dt)
        }

        if input.jumpPresses != lastJumpPresses {
            lastJumpPresses = input.jumpPresses
            p.buffer = Physics.jumpBuffer
        }
        p.buffer = max(0, p.buffer - dt)
        p.coyote = p.onGround ? Physics.coyoteTime : max(0, p.coyote - dt)
        p.hurtTimer = max(0, p.hurtTimer - dt)

        if p.buffer > 0 && p.coyote > 0 {
            p.velocity.y = Physics.jumpVelocity
            p.buffer = 0
            p.coyote = 0
            p.onGround = false
            p.jumping = true
            events.append(.jumped)
        }
        if p.jumping && !input.jumpHeld && p.velocity.y > Physics.jumpCutVelocity {
            p.velocity.y = Physics.jumpCutVelocity
        }
        if p.velocity.y <= 0 { p.jumping = false }

        p.velocity.y = max(p.velocity.y - Physics.gravity * dt, -Physics.maxFall)

        // Horizontal move, then vertical, each resolved against the tiles.
        p.position.x += p.velocity.x * dt
        resolveX(&p.position, &p.velocity, width: Player.width, height: Player.height)

        let wasOnGround = p.onGround
        let previousBottom = p.position.y
        p.position.y += p.velocity.y * dt
        let hit = resolveY(&p.position, &p.velocity, width: Player.width, height: Player.height,
                           previousBottom: previousBottom)
        p.onGround = hit.landed
        if hit.landed && !wasOnGround { events.append(.landed) }
        // Walking into a spring from the side bounces too, not just landing on it.
        let footRow = Int(floor(p.position.y + 0.01))
        let walkedOntoSpring = p.velocity.y <= 0
            && level.tile(Int(floor(p.position.x)), footRow) == .spring
            && p.position.y - Double(footRow) < 0.6
        if walkedOntoSpring { p.position.y = Double(footRow + 1) }
        if hit.onSpring || walkedOntoSpring {
            p.velocity.y = Physics.springVelocity
            p.onGround = false
            p.jumping = false
            events.append(.sprang)
        }
        if let head = hit.headTile { bump(head.x, head.y) }

        if p.position.y < -2 { p.hearts = 0 }
        player = p
        if player.hearts <= 0 { die() }
    }

    private func updateEnemy(_ i: Int, _ dt: Double) {
        var e = enemies[i]
        guard e.alive else { return }
        // Enemies wait off-screen until the player gets near.
        if !e.awake {
            guard abs(e.position.x - player.position.x) < 13 else { return }
            e.awake = true
            e.velocity.x = e.kind == .bat ? 0 : -(e.kind == .spiker ? 1.6 : 2.0)
        }

        switch e.kind {
        case .bat:
            e.phase += dt * 1.3
            let newX = e.origin.x + 2.5 * sin(e.phase)
            e.velocity.x = (newX - e.position.x) / dt
            e.position = Vec2(newX, e.origin.y + 0.6 * sin(e.phase * 2))
        case .beetle, .spiker:
            let speed = abs(e.velocity.x)
            let (w, h) = e.size
            e.position.x += e.velocity.x * dt
            let before = e.velocity.x
            resolveX(&e.position, &e.velocity, width: w, height: h)
            if e.velocity.x == 0 { e.velocity.x = before > 0 ? -speed : speed }

            e.velocity.y = max(e.velocity.y - Physics.gravity * dt, -Physics.maxFall)
            let previousBottom = e.position.y
            e.position.y += e.velocity.y * dt
            let hit = resolveY(&e.position, &e.velocity, width: w, height: h, previousBottom: previousBottom)

            // Turn around at ledges and spikes instead of walking off.
            if hit.landed {
                let aheadX = e.position.x + (e.velocity.x > 0 ? w / 2 + 0.05 : -w / 2 - 0.05)
                let tx = Int(floor(aheadX)), ty = Int(floor(e.position.y - 0.1))
                let below = level.tile(tx, ty)
                if !below.isStandable || level.tile(tx, ty + 1) == .spike {
                    e.velocity.x = -e.velocity.x
                }
            }
            if e.position.y < -2 { e.alive = false }
        }
        enemies[i] = e
    }

    private func checkPickups() {
        let box = player.box
        for (i, gem) in level.gems.enumerated() where !gemTaken[i] {
            if box.intersects(Box(minX: gem.x - 0.3, minY: gem.y - 0.3, maxX: gem.x + 0.3, maxY: gem.y + 0.3)) {
                gemTaken[i] = true
                gems += 1
                score += 100
                events.append(.gemCollected(index: i))
            }
        }
        for (i, cp) in level.checkpoints.enumerated() where (activeCheckpoint ?? -1) < i {
            if box.intersects(Box(foot: cp, width: 0.8, height: 2)) {
                activeCheckpoint = i
                events.append(.checkpoint(index: i))
            }
        }
    }

    private func checkEnemies(_ input: Input) {
        let box = player.box
        for i in enemies.indices where enemies[i].alive {
            let e = enemies[i]
            guard box.intersects(e.box.inset(0.05)) else { continue }
            let stompable = e.kind != .spiker
            let fallingOnto = player.velocity.y < 0 && box.minY > e.position.y + e.size.h * 0.45
            if stompable && fallingOnto {
                enemies[i].alive = false
                player.velocity.y = input.jumpHeld ? Physics.stompBounceHeld : Physics.stompBounce
                player.position.y = max(player.position.y, e.box.maxY)
                score += 200
                events.append(.enemyStomped(id: e.id))
            } else {
                hurt(awayFrom: e.position.x)
            }
        }
    }

    private func checkHazards() {
        let box = player.box.inset(0.12)
        let x0 = Int(floor(box.minX)), x1 = Int(floor(box.maxX))
        let y0 = Int(floor(box.minY)), y1 = Int(floor(box.maxY))
        for y in y0...y1 {
            for x in x0...x1 where level.tile(x, y) == .spike {
                let spike = Box(minX: Double(x) + 0.1, minY: Double(y), maxX: Double(x) + 0.9, maxY: Double(y) + 0.5)
                if box.intersects(spike) {
                    hurt(awayFrom: Double(x) + 0.5)
                    if player.velocity.y < 9 { player.velocity.y = 12 }
                    return
                }
            }
        }
    }

    // MARK: - Collisions

    private func resolveX(_ pos: inout Vec2, _ vel: inout Vec2, width: Double, height: Double) {
        let eps = 0.001
        let box = Box(foot: pos, width: width, height: height)
        let y0 = Int(floor(box.minY + eps)), y1 = Int(floor(box.maxY - eps))
        if vel.x > 0 {
            let col = Int(floor(box.maxX))
            if (y0...y1).contains(where: { level.tile(col, $0).isSolid }) {
                pos.x = Double(col) - width / 2 - eps
                vel.x = 0
            }
        } else if vel.x < 0 {
            let col = Int(floor(box.minX))
            if (y0...y1).contains(where: { level.tile(col, $0).isSolid }) {
                pos.x = Double(col + 1) + width / 2 + eps
                vel.x = 0
            }
        }
    }

    private struct VerticalHit {
        var landed = false
        var onSpring = false
        var headTile: (x: Int, y: Int)?
    }

    private func resolveY(_ pos: inout Vec2, _ vel: inout Vec2, width: Double, height: Double,
                          previousBottom: Double) -> VerticalHit {
        let eps = 0.001
        var hit = VerticalHit()
        let box = Box(foot: pos, width: width, height: height)
        let x0 = Int(floor(box.minX + eps)), x1 = Int(floor(box.maxX - eps))
        if vel.y <= 0 {
            let row = Int(floor(box.minY))
            let top = Double(row + 1)
            var springs = 0, landed = false
            for x in x0...x1 {
                let t = level.tile(x, row)
                let oneWay = (t == .platform || t == .spring) && previousBottom >= top - eps
                if t.isSolid || oneWay {
                    landed = true
                    if t == .spring { springs += 1 }
                }
            }
            if landed {
                pos.y = top
                vel.y = 0
                hit.landed = true
                hit.onSpring = springs > 0
            }
        } else {
            let row = Int(floor(box.maxY))
            let solids = (x0...x1).filter { level.tile($0, row).isSolid }
            if !solids.isEmpty {
                pos.y = Double(row) - height - eps
                vel.y = 0
                // Bump the block under the middle of the head, or the nearest one.
                let center = Int(floor(pos.x))
                hit.headTile = (solids.contains(center) ? center : solids[0], row)
            }
        }
        return hit
    }

    private func bump(_ x: Int, _ y: Int) {
        guard level.tile(x, y) == .crate else { return }
        level.set(x, y, .usedCrate)
        gems += 1
        score += 100
        events.append(.crateOpened(x: x, y: y))
        // Knock out any enemy standing on the crate.
        for i in enemies.indices where enemies[i].alive && enemies[i].kind != .bat {
            let e = enemies[i]
            if abs(e.position.x - (Double(x) + 0.5)) < 0.9 && abs(e.position.y - Double(y + 1)) < 0.2 {
                enemies[i].alive = false
                score += 200
                events.append(.enemyStomped(id: e.id))
            }
        }
    }

    // MARK: - Damage, death, winning

    private func hurt(awayFrom x: Double) {
        guard !player.isInvulnerable, !player.isDead else { return }
        player.hearts -= 1
        player.hurtTimer = Physics.hurtTime
        player.velocity = Vec2(player.position.x < x ? -6 : 6, 9)
        player.onGround = false
        events.append(.hurt)
        if player.hearts <= 0 { die() }
    }

    private func die() {
        guard !player.isDead else { return }
        player.isDead = true
        player.hearts = 0
        player.deadTimer = Physics.respawnDelay
        player.velocity = Vec2(0, 0)
        deaths += 1
        events.append(.died)
    }

    private func respawn() {
        let spot = activeCheckpoint.map { level.checkpoints[$0] } ?? level.start
        player = Player(position: spot)
        player.hurtTimer = 1.0   // a moment of safety
        events.append(.respawned)
    }

    private func win() {
        let timeBonus = max(0, Int((level.definition.parTime - time) * 10)) * 10
        score += timeBonus + player.hearts * 500
        var stars = 1
        if gems == totalGems { stars += 1 }
        if time <= level.definition.parTime { stars += 1 }
        result = LevelResult(time: time, gems: gems, totalGems: totalGems, deaths: deaths,
                             score: score, stars: stars)
        player.velocity = Vec2(0, 0)
        events.append(.won)
    }
}

private func approach(_ value: Double, _ target: Double, _ delta: Double) -> Double {
    value < target ? min(value + delta, target) : max(value - delta, target)
}
