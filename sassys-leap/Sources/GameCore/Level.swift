import Foundation

/// Positions are in tile units with y pointing up; row 0 is the bottom of the level.
public struct Vec2: Equatable {
    public var x: Double
    public var y: Double
    public init(_ x: Double, _ y: Double) { self.x = x; self.y = y }
}

public struct Box: Equatable {
    public var minX, minY, maxX, maxY: Double

    /// A box whose bottom edge is centred on `foot`.
    public init(foot: Vec2, width: Double, height: Double) {
        minX = foot.x - width / 2; maxX = foot.x + width / 2
        minY = foot.y; maxY = foot.y + height
    }

    public init(minX: Double, minY: Double, maxX: Double, maxY: Double) {
        self.minX = minX; self.minY = minY; self.maxX = maxX; self.maxY = maxY
    }

    public func intersects(_ o: Box) -> Bool {
        minX < o.maxX && maxX > o.minX && minY < o.maxY && maxY > o.minY
    }

    public func inset(_ d: Double) -> Box {
        Box(minX: minX + d, minY: minY + d, maxX: maxX - d, maxY: maxY - d)
    }
}

public enum Tile: Equatable {
    case empty, ground, brick, crate, usedCrate, platform, spike, spring

    /// Blocks movement from every side.
    public var isSolid: Bool {
        switch self {
        case .ground, .brick, .crate, .usedCrate: return true
        default: return false
        }
    }

    /// Can be stood on (solid tiles plus one-way platforms and springs).
    public var isStandable: Bool { isSolid || self == .platform || self == .spring }
}

public enum Theme: String, CaseIterable {
    case meadow, cavern, sky, dusk
}

public enum EnemyKind: Equatable {
    /// Walks back and forth, turns at walls and ledges. Can be stomped.
    case beetle
    /// Flies in a loop around where it starts. Can be stomped.
    case bat
    /// Walks like a beetle but its back is spiky: never stomp it.
    case spiker
}

public struct LevelDefinition {
    public let name: String
    public let theme: Theme
    /// Seconds; finishing faster than this earns the third star.
    public let parTime: Double
    /// Top row first. Legend:
    /// `#` ground  `B` brick  `C` gem crate (hit from below)  `=` one-way platform
    /// `^` spikes  `S` spring  `P` start  `G` goal  `*` gem  `K` checkpoint
    /// `e` beetle  `b` bat  `s` spiker  `.` or space: empty
    public let rows: [String]

    public init(name: String, theme: Theme, parTime: Double, map: String) {
        self.name = name
        self.theme = theme
        self.parTime = parTime
        self.rows = map.split(separator: "\n", omittingEmptySubsequences: true).map(String.init)
    }
}

public enum LevelError: Error, Equatable {
    case missingStart, missingGoal, empty
}

public struct Level {
    public let definition: LevelDefinition
    public let width: Int
    public let height: Int
    public private(set) var tiles: [Tile]
    public let start: Vec2
    public let goal: Vec2
    public let checkpoints: [Vec2]
    public let gems: [Vec2]
    public let enemies: [(kind: EnemyKind, position: Vec2)]

    public init(_ def: LevelDefinition) throws {
        guard !def.rows.isEmpty else { throw LevelError.empty }
        let height = def.rows.count
        let width = def.rows.map(\.count).max() ?? 0
        var tiles = [Tile](repeating: .empty, count: width * height)
        var start: Vec2?, goal: Vec2?
        var checkpoints: [Vec2] = [], gems: [Vec2] = []
        var enemies: [(EnemyKind, Vec2)] = []

        for (rowIndex, row) in def.rows.enumerated() {
            let y = height - 1 - rowIndex
            for (x, ch) in row.enumerated() {
                let foot = Vec2(Double(x) + 0.5, Double(y))
                var tile = Tile.empty
                switch ch {
                case "#": tile = .ground
                case "B": tile = .brick
                case "C": tile = .crate
                case "=": tile = .platform
                case "^": tile = .spike
                case "S": tile = .spring
                case "P": start = foot
                case "G": goal = foot
                case "K": checkpoints.append(foot)
                case "*": gems.append(Vec2(foot.x, foot.y + 0.5))
                case "e": enemies.append((.beetle, foot))
                case "b": enemies.append((.bat, Vec2(foot.x, foot.y + 0.2)))
                case "s": enemies.append((.spiker, foot))
                default: break
                }
                tiles[y * width + x] = tile
            }
        }
        guard let start else { throw LevelError.missingStart }
        guard let goal else { throw LevelError.missingGoal }

        self.definition = def
        self.width = width
        self.height = height
        self.tiles = tiles
        self.start = start
        self.goal = goal
        self.checkpoints = checkpoints.sorted { $0.x < $1.x }
        self.gems = gems
        self.enemies = enemies
    }

    /// Outside the map: walls on the left and right, open sky above, a pit below.
    public func tile(_ x: Int, _ y: Int) -> Tile {
        if x < 0 || x >= width { return y >= 0 ? .ground : .empty }
        if y < 0 || y >= height { return .empty }
        return tiles[y * width + x]
    }

    mutating func set(_ x: Int, _ y: Int, _ tile: Tile) {
        guard x >= 0, x < width, y >= 0, y < height else { return }
        tiles[y * width + x] = tile
    }

    public var crateCount: Int { tiles.filter { $0 == .crate }.count }
}
