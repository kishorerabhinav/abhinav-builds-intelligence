import XCTest
@testable import GameCore

final class GameCoreTests: XCTestCase {
    private func world(_ map: String) throws -> World {
        try World(definition: LevelDefinition(name: "Test", theme: .meadow, parTime: 30, map: map))
    }

    private func run(_ w: World, seconds: Double, _ input: (World) -> Input) {
        var t = 0.0
        while t < seconds && !w.isFinished {
            w.update(dt: 1.0 / 60.0, input: input(w))
            t += 1.0 / 60.0
        }
    }

    func testParsingFlipsRowsAndFindsEntities() throws {
        let level = try Level(LevelDefinition(name: "T", theme: .meadow, parTime: 1, map: """
        ..*..
        P.e.G
        #####
        """))
        XCTAssertEqual(level.width, 5)
        XCTAssertEqual(level.height, 3)
        XCTAssertEqual(level.tile(0, 0), .ground)
        XCTAssertEqual(level.start, Vec2(0.5, 1))
        XCTAssertEqual(level.goal, Vec2(4.5, 1))
        XCTAssertEqual(level.gems.count, 1)
        XCTAssertEqual(level.enemies.first?.kind, .beetle)
        XCTAssertEqual(level.tile(-1, 1), .ground, "left edge is a wall")
        XCTAssertEqual(level.tile(2, -1), .empty, "below the map is a pit")
    }

    func testMissingStartIsAnError() {
        XCTAssertThrowsError(try Level(LevelDefinition(name: "T", theme: .meadow, parTime: 1, map: "..G\n###")))
    }

    func testJumpReachesAboutThreeTiles() throws {
        let w = try world("""
        ..........
        ..........
        ..........
        ..........
        ..........
        ..........
        P........G
        ##########
        """)
        run(w, seconds: 0.2) { _ in Input() }
        XCTAssertTrue(w.player.onGround)
        var input = Input()
        input.jumpHeld = true
        input.jumpPresses = 1
        var peak = 0.0
        run(w, seconds: 1.2) { w in peak = max(peak, w.player.position.y); return input }
        XCTAssertEqual(peak - 1, 3.0, accuracy: 0.2)
        XCTAssertTrue(w.player.onGround)
    }

    func testShortTapJumpsLower() throws {
        let w = try world("""
        ..........
        ..........
        ..........
        ..........
        P........G
        ##########
        """)
        run(w, seconds: 0.2) { _ in Input() }
        var input = Input()
        input.jumpPresses = 1     // pressed and released between frames
        var peak = 0.0
        run(w, seconds: 1.0) { w in peak = max(peak, w.player.position.y); return input }
        XCTAssertGreaterThan(peak - 1, 0.3)
        XCTAssertLessThan(peak - 1, 1.5)
    }

    func testWallsStopThePlayer() throws {
        let w = try world("""
        ....#....
        P...#...G
        #########
        """)
        var input = Input()
        input.right = true
        run(w, seconds: 2) { _ in input }
        XCTAssertLessThanOrEqual(w.player.box.maxX, 4.0)
        XCTAssertFalse(w.isFinished)
    }

    func testHeadbuttingACrateGivesAGemOnce() throws {
        let w = try world("""
        .....
        .C...
        .....
        .P..G
        #####
        """)
        XCTAssertEqual(w.totalGems, 1)
        run(w, seconds: 0.2) { _ in Input() }
        var input = Input()
        input.jumpHeld = true
        input.jumpPresses = 1
        run(w, seconds: 1) { _ in input }
        input.jumpPresses = 2
        run(w, seconds: 1) { _ in input }
        XCTAssertEqual(w.gems, 1)
        XCTAssertEqual(w.level.tile(1, 3), .usedCrate)
    }

    func testStompingABeetle() throws {
        let w = try world("""
        ..........
        ..........
        ..........
        ...P.....G
        ...e......
        ##########
        """)
        // The player starts right above the beetle and falls onto it.
        var stomped = false
        run(w, seconds: 0.5) { w in
            if w.drainEvents().contains(where: { if case .enemyStomped = $0 { return true }; return false }) {
                stomped = true
            }
            return Input()
        }
        XCTAssertTrue(stomped)
        XCTAssertEqual(w.player.hearts, Player.maxHearts)
        XCTAssertFalse(w.enemies[0].alive)
    }

    func testLandingOnASpikerHurts() throws {
        let w = try world("""
        ..........
        ..........
        ...P.....G
        ...s......
        ##########
        """)
        run(w, seconds: 0.4) { _ in Input() }
        XCTAssertEqual(w.player.hearts, Player.maxHearts - 1)
        XCTAssertTrue(w.enemies[0].alive)
    }

    func testFallingInAPitRespawnsAtCheckpoint() throws {
        let w = try world("""
        ...........
        P..K......G
        #####..####
        """)
        var input = Input()
        input.right = true
        var died = false
        run(w, seconds: 1.5) { w in
            if w.drainEvents().contains(.died) { died = true; input.right = false }
            return input
        }
        XCTAssertTrue(died)
        XCTAssertEqual(w.deaths, 1)
        run(w, seconds: 2) { _ in Input() }
        XCTAssertEqual(w.player.position.x, 3.5, accuracy: 0.01)
        XCTAssertEqual(w.player.hearts, Player.maxHearts)
    }

    func testSpringLaunchesHigh() throws {
        let w = try world("""
        ...
        ...
        ...
        ...
        ...
        ...
        ...
        .P.
        ...
        .SG
        ###
        """)
        var peak = 0.0
        run(w, seconds: 1.5) { w in peak = max(peak, w.player.position.y); return Input() }
        XCTAssertGreaterThan(peak, 7.5)
    }

    func testOneWayPlatformCanBeJumpedThrough() throws {
        let w = try world("""
        ......
        ......
        .===..
        ......
        .P...G
        ######
        """)
        run(w, seconds: 0.2) { _ in Input() }
        var input = Input()
        input.jumpHeld = true
        input.jumpPresses = 1
        run(w, seconds: 1.5) { _ in input }
        XCTAssertEqual(w.player.position.y, 4, accuracy: 0.01, "landed on top of the platform")
    }

    func testAllLevelsParse() throws {
        XCTAssertEqual(Levels.all.count, 4)
        for def in Levels.all {
            let level = try Level(def)
            XCTAssertEqual(level.height, 12, def.name)
            XCTAssertTrue(level.tile(Int(level.start.x), Int(level.start.y) - 1).isStandable, def.name)
        }
    }

    /// A simple bot holds right and jumps at walls, gaps, spikes and enemies.
    /// If it can finish every level, the levels are beatable with the real physics.
    func testBotCanFinishEveryLevel() throws {
        for def in Levels.all {
            let w = try World(definition: def)
            var input = Input()
            input.right = true
            var seconds = 0.0
            while !w.isFinished && seconds < 120 {
                input.jumpHeld = !w.player.onGround || shouldJump(w)
                if w.player.onGround && shouldJump(w) { input.jumpPresses += 1 }
                w.update(dt: 1.0 / 60.0, input: input)
                seconds += 1.0 / 60.0
                for event in w.drainEvents() where event == .hurt || event == .died {
                    print("\(def.name): \(event) at x=\(Int(w.player.position.x)) y=\(Int(w.player.position.y))")
                }
            }
            XCTAssertTrue(w.isFinished, "\(def.name): bot stuck at x=\(w.player.position.x), y=\(w.player.position.y)")
            XCTAssertEqual(w.deaths, 0, "\(def.name): bot died")
            if let r = w.result {
                print("\(def.name): \(String(format: "%.1f", r.time))s, gems \(r.gems)/\(r.totalGems), hearts \(w.player.hearts)")
            }
        }
    }
}

func shouldJump(_ w: World) -> Bool {
    let p = w.player
    let level = w.level
    let foot = Int(floor(p.position.y + 0.01))
    let front = p.position.x + Player.width / 2
    for dx in [0.3, 0.9] {
        let tx = Int(floor(front + dx))
        if level.tile(tx, foot).isSolid || level.tile(tx, foot + 1).isSolid { return true }
        if level.tile(tx, foot) == .spike { return true }
    }
    // Spikes ahead, or a gap with no ground a few tiles below: jump from the edge.
    let edgeX = Int(floor(front + 0.25))
    if level.tile(edgeX, foot) == .spike { return true }
    let groundBelow = (foot - 4..<foot).contains { y in
        level.tile(edgeX, y).isStandable && level.tile(edgeX, y + 1) != .spike
    }
    if !groundBelow { return true }
    for e in w.enemies where e.alive {
        let dx = e.position.x - p.position.x
        if dx > 0 && dx < 2.4 && abs(e.position.y - p.position.y) < 1.5 { return true }
    }
    return false
}
