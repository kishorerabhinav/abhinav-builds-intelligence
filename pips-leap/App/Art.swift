import SpriteKit
import UIKit
import GameCore

extension UIColor {
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(red: CGFloat((hex >> 16) & 0xff) / 255,
                  green: CGFloat((hex >> 8) & 0xff) / 255,
                  blue: CGFloat(hex & 0xff) / 255, alpha: alpha)
    }
}

/// Colours for one world. Tiles are drawn from these at launch, so no image assets are needed.
struct Palette {
    let skyTop: UIColor
    let skyBottom: UIColor
    let hills: UIColor
    let grass: UIColor
    let grassDark: UIColor
    let dirt: UIColor
    let dirtDark: UIColor
    let brick: UIColor
    let brickDark: UIColor

    static func of(_ theme: Theme) -> Palette {
        switch theme {
        case .meadow:
            return Palette(skyTop: .init(hex: 0x6ec6ff), skyBottom: .init(hex: 0xc9ecff), hills: .init(hex: 0x8fd18a),
                           grass: .init(hex: 0x5bbf4a), grassDark: .init(hex: 0x3e9a35), dirt: .init(hex: 0xb07443),
                           dirtDark: .init(hex: 0x86532c), brick: .init(hex: 0xd0703f), brickDark: .init(hex: 0x8e4424))
        case .cavern:
            return Palette(skyTop: .init(hex: 0x14121f), skyBottom: .init(hex: 0x2b2740), hills: .init(hex: 0x231f35),
                           grass: .init(hex: 0x4f9a77), grassDark: .init(hex: 0x346b52), dirt: .init(hex: 0x5c5574),
                           dirtDark: .init(hex: 0x403a55), brick: .init(hex: 0x7a6aa0), brickDark: .init(hex: 0x4a3f68))
        case .sky:
            return Palette(skyTop: .init(hex: 0x8ab8ff), skyBottom: .init(hex: 0xffe3f1), hills: .init(hex: 0xffffff, alpha: 0.7),
                           grass: .init(hex: 0xffffff), grassDark: .init(hex: 0xd7e8fb), dirt: .init(hex: 0xe8f1fb),
                           dirtDark: .init(hex: 0xbfd5ee), brick: .init(hex: 0xf2b8d0), brickDark: .init(hex: 0xc9849f))
        case .dusk:
            return Palette(skyTop: .init(hex: 0x3a2a63), skyBottom: .init(hex: 0xf3a06f), hills: .init(hex: 0x52386e),
                           grass: .init(hex: 0x739a52), grassDark: .init(hex: 0x4f733a), dirt: .init(hex: 0x7c4b5c),
                           dirtDark: .init(hex: 0x58303f), brick: .init(hex: 0x95506a), brickDark: .init(hex: 0x5e2c40))
        }
    }
}

enum Art {
    // MARK: - Pip, the hero (an original sprout character)

    private static let pipPalette: [Character: UIColor] = [
        "k": .init(hex: 0x1d2b22), "g": .init(hex: 0x62c95c), "l": .init(hex: 0xa6ec86),
        "f": .init(hex: 0x2f9e44), "w": .white, "e": .init(hex: 0x111111),
        "p": .init(hex: 0xff9fb0), "o": .init(hex: 0xf08c3a),
    ]

    private static let pipBody = [
        "......ff....",
        ".....fllf...",
        "......f.....",
        "...kkkkkk...",
        "..kgllgggk..",
        ".kggwegwegk.",
        ".kpggggggpk.",
        ".kgggkkgggk.",
        ".kggggggggk.",
        "..kggggggk..",
        "...kkkkkk...",
    ]

    static let pipIdle = sprite(pipBody + ["...oo..oo..."], pipPalette)
    static let pipRun = [
        sprite(pipBody + ["..oo....oo.."], pipPalette),
        sprite(pipBody + ["....oooo...."], pipPalette),
    ]
    static let pipJump = sprite(Array(pipBody.dropLast()) + ["..kkkkkkkk..", "..o......o.."], pipPalette)

    // MARK: - Enemies (face left by default)

    private static let critterPalette: [Character: UIColor] = [
        "k": .init(hex: 0x1b1420), "r": .init(hex: 0xd9483b), "R": .init(hex: 0xa83228),
        "p": .init(hex: 0x8e5bd6), "P": .init(hex: 0x6a3fb0), "b": .init(hex: 0x5a4a8c),
        "w": .white, "e": .init(hex: 0x111111), "s": .init(hex: 0xe6e9ef),
    ]

    static let beetle = [
        sprite(["....kkkkk...", "..kkrrrrrkk.", ".kwkrrRrrrrk", "kweerrrRrrrk",
                "kkkkrrrrRrrk", ".kkkkkkkkkk.", "..k.k..k.k..", ".k...k...k.."], critterPalette),
        sprite(["....kkkkk...", "..kkrrrrrkk.", ".kwkrrRrrrrk", "kweerrrRrrrk",
                "kkkkrrrrRrrk", ".kkkkkkkkkk.", "...k.k..k.k.", "..k...k...k."], critterPalette),
    ]

    static let spiker = [
        sprite(["...s...s....", "..ksk.ksk...", ".kpppppppk..", "kweppppppppk",
                "kwepppPppppk", "kppppPppPppk", ".kkkkkkkkkk.", "..k.k..k.k.."], critterPalette),
        sprite(["...s...s....", "..ksk.ksk...", ".kpppppppk..", "kweppppppppk",
                "kwepppPppppk", "kppppPppPppk", ".kkkkkkkkkk.", "...k.k..k.k."], critterPalette),
    ]

    static let bat = [
        sprite(["k..........k", "kk...kk...kk", "kbk.kbbk.kbk", "kbbkbbbbkbbk",
                ".kbbwbbwbbk.", "..kbebbebk..", "...kbbbbk...", "....k..k...."], critterPalette),
        sprite(["............", ".....kk.....", "....kbbk....", ".kkkbbbbkkk.",
                "kbbbwbbwbbbk", "kbbkebbekbbk", "kk.kbbbbk.kk", "k...k..k...k"], critterPalette),
    ]

    // MARK: - Pickups and props

    static let gem = draw(8, 8) { c in
        let shape: [(Int, Int, Int)] = [(3, 0, 2), (2, 1, 4), (1, 2, 6), (0, 3, 8), (0, 4, 8), (1, 5, 6), (2, 6, 4), (3, 7, 2)]
        for (x, y, w) in shape { fill(c, x, y, w, 1, .init(hex: 0x2fd6c8)) }
        fill(c, 2, 2, 2, 2, .init(hex: 0xb8fff6))
        fill(c, 4, 4, 3, 2, .init(hex: 0x16a39a))
    }

    static func goal() -> SKTexture {
        draw(16, 48) { c in
            fill(c, 7, 4, 2, 44, .init(hex: 0xe8e2d0))
            fill(c, 9, 4, 1, 44, .init(hex: 0xb6ad94))
            fill(c, 5, 44, 6, 4, .init(hex: 0x6b5b45))
            fill(c, 6, 0, 4, 4, .init(hex: 0xffd447))
            // A big leaf banner: Pip's home.
            let leaf = UIColor(hex: 0x3fbf55), vein = UIColor(hex: 0x23843a)
            for row in 0..<12 {
                let w = row < 6 ? row + 2 : 13 - row
                fill(c, 10, 5 + row, min(w, 6), 1, leaf)
            }
            fill(c, 10, 10, 5, 1, vein)
        }
    }

    static func checkpoint(active: Bool) -> SKTexture {
        draw(16, 32) { c in
            fill(c, 7, 6, 2, 26, .init(hex: 0x9a8f7a))
            fill(c, 5, 29, 6, 3, .init(hex: 0x5e5244))
            let flag = active ? UIColor(hex: 0x5bdc6a) : UIColor(hex: 0xb0b0b0)
            fill(c, 9, 6, 6, 5, flag)
            fill(c, 9, 11, 4, 2, flag)
            fill(c, 6, 3, 4, 3, active ? .init(hex: 0xffe680) : .init(hex: 0x808080))
        }
    }

    // MARK: - Tiles (16x16, drawn from the world palette)

    struct TileSet {
        let groundTop, groundFill, brick, crate, usedCrate, platform, spike, spring: SKTexture
    }

    static func tiles(_ p: Palette) -> TileSet {
        let speckles = [(3, 7), (11, 9), (6, 12), (13, 14), (1, 14), (9, 5)]
        let groundFill = draw(16, 16) { c in
            fill(c, 0, 0, 16, 16, p.dirt)
            for (x, y) in speckles { fill(c, x, y, 2, 1, p.dirtDark) }
        }
        let groundTop = draw(16, 16) { c in
            fill(c, 0, 0, 16, 16, p.dirt)
            for (x, y) in speckles where y > 6 { fill(c, x, y, 2, 1, p.dirtDark) }
            fill(c, 0, 0, 16, 4, p.grass)
            for x in stride(from: 0, to: 16, by: 3) { fill(c, x, 4, 2, 1 + (x % 2), p.grassDark) }
            fill(c, 0, 0, 16, 1, p.grass.withAlphaComponent(0.6))
        }
        let brick = draw(16, 16) { c in
            fill(c, 0, 0, 16, 16, p.brick)
            fill(c, 0, 7, 16, 1, p.brickDark); fill(c, 0, 15, 16, 1, p.brickDark)
            fill(c, 0, 0, 1, 7, p.brickDark); fill(c, 8, 8, 1, 7, p.brickDark)
            fill(c, 2, 1, 4, 1, .init(white: 1, alpha: 0.25)); fill(c, 10, 9, 4, 1, .init(white: 1, alpha: 0.25))
        }
        let wood = UIColor(hex: 0xd99a4e), woodDark = UIColor(hex: 0x8a5a2b)
        func crateArt(used: Bool) -> SKTexture {
            draw(16, 16) { c in
                fill(c, 0, 0, 16, 16, used ? woodDark : wood)
                fill(c, 0, 0, 16, 1, .init(hex: 0x4a2f15)); fill(c, 0, 15, 16, 1, .init(hex: 0x4a2f15))
                fill(c, 0, 0, 1, 16, .init(hex: 0x4a2f15)); fill(c, 15, 0, 1, 16, .init(hex: 0x4a2f15))
                fill(c, 2, 2, 12, 1, woodDark); fill(c, 2, 13, 12, 1, woodDark)
                if !used {
                    fill(c, 7, 4, 2, 1, .init(hex: 0x2fd6c8)); fill(c, 6, 5, 4, 1, .init(hex: 0x2fd6c8))
                    fill(c, 5, 6, 6, 2, .init(hex: 0x2fd6c8)); fill(c, 6, 8, 4, 1, .init(hex: 0x2fd6c8))
                    fill(c, 7, 9, 2, 1, .init(hex: 0x2fd6c8)); fill(c, 6, 6, 2, 1, .init(hex: 0xb8fff6))
                }
            }
        }
        let platform = draw(16, 16) { c in
            fill(c, 0, 0, 16, 4, wood)
            fill(c, 0, 4, 16, 1, woodDark)
            fill(c, 3, 5, 2, 2, woodDark); fill(c, 11, 5, 2, 2, woodDark)
        }
        let spike = draw(16, 16) { c in
            for (i, base) in [0, 8].enumerated() {
                for row in 0..<8 {
                    let w = (row + 1)
                    fill(c, base + 4 - w / 2, 8 + row, max(w, 1), 1, i == 0 ? .init(hex: 0xd7dce4) : .init(hex: 0xc3c9d3))
                }
                fill(c, base + 3, 8, 1, 2, .white)
            }
        }
        let spring = draw(16, 16) { c in
            fill(c, 1, 6, 14, 3, .init(hex: 0xe24b4b))
            fill(c, 1, 6, 14, 1, .init(hex: 0xff8a8a))
            for y in stride(from: 9, to: 14, by: 2) { fill(c, 4, y, 8, 1, .init(hex: 0x9aa3ad)) }
            fill(c, 2, 14, 12, 2, .init(hex: 0x5b6470))
        }
        return TileSet(groundTop: groundTop, groundFill: groundFill, brick: brick,
                       crate: crateArt(used: false), usedCrate: crateArt(used: true),
                       platform: platform, spike: spike, spring: spring)
    }

    // MARK: - Helpers

    static func sprite(_ rows: [String], _ palette: [Character: UIColor]) -> SKTexture {
        let width = rows.map(\.count).max() ?? 0
        return draw(width, rows.count) { c in
            for (y, row) in rows.enumerated() {
                for (x, ch) in row.enumerated() {
                    if let color = palette[ch] { fill(c, x, y, 1, 1, color) }
                }
            }
        }
    }

    static func draw(_ w: Int, _ h: Int, _ body: (CGContext) -> Void) -> SKTexture {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let image = UIGraphicsImageRenderer(size: CGSize(width: w, height: h), format: format).image { ctx in
            body(ctx.cgContext)
        }
        let texture = SKTexture(image: image)
        texture.filteringMode = .nearest
        return texture
    }

    private static func fill(_ c: CGContext, _ x: Int, _ y: Int, _ w: Int, _ h: Int, _ color: UIColor) {
        c.setFillColor(color.cgColor)
        c.fill(CGRect(x: x, y: y, width: w, height: h))
    }
}
