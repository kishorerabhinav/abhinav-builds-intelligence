# Pip's Leap

An original side-scrolling platformer for iPhone (iOS 17 and later, built for iOS 27). You play
Pip, a little sprout trying to get home across four worlds. Run, jump, stomp critters, pop crates
for gems, and bounce off springs.

All the characters, levels and pixel art are original. Every sprite and tile is drawn in code at
launch, so the app has no image files.

## Playing

- **Left thumb:** ◀ ▶ to run. **Right thumb:** jump. Hold jump to go higher, tap it for a hop.
- Land on **beetles** and **bats** to knock them out. Don't land on the purple **spikers**; jump
  over them.
- Hit **crates** from below to get a gem. **Springs** launch you about six tiles high.
- You have three hearts. Spikes and critters cost one; falling in a pit costs them all. You come
  back at the last **checkpoint flag** you touched.
- Reach the **leaf banner** to finish. Stars: one for finishing, one for every gem, one for
  beating the par time.
- A game controller or keyboard also works: arrows or WASD, plus Space or the A button.

| # | World | What's new |
|---|---|---|
| 1 | Sunny Meadow | Running, jumping, crates, beetles, a spring |
| 2 | Echo Cavern | Low ceilings, spike pits, spikers |
| 3 | Cloud Steps | Floating islands, one-way platforms, springs |
| 4 | Twilight Keep | Everything at once |

## Install on your iPhone

You need a Mac with Xcode.

```bash
brew install xcodegen
cd pips-leap
xcodegen generate
open PipsLeap.xcodeproj
```

In Xcode, pick your team under **Signing & Capabilities** (a free Apple ID works), change the
bundle ID from `com.example.PipsLeap` to something unique, plug in your iPhone, and press Run.
The first time, approve the developer on the phone in Settings › General › VPN & Device
Management.

## How it's built

| Folder | What it is |
|---|---|
| `Sources/GameCore/` | The game itself in plain Swift: physics, collisions, enemies, scoring, and the level maps. No UI code. |
| `App/` | The iPhone app: a SpriteKit scene that draws the game, SwiftUI menus, HUD and touch controls, and saved progress |
| `Tests/GameCoreTests/` | Physics and rules tests, plus a bot that plays every level |

Levels are ASCII maps in `Sources/GameCore/Levels.swift`. The legend is in `Level.swift`: `#`
ground, `C` crate, `=` platform, `^` spikes, `S` spring, `*` gem, `e`/`b`/`s` enemies, `K`
checkpoint, `P` start, `G` goal. To add a level, add a `LevelDefinition` to `Levels.all`.

The engine runs at a fixed 120 steps a second. Movement has coyote time and jump buffering, so
jumps feel fair on a touch screen.

## Tests

```bash
cd pips-leap && swift test
```

Besides unit tests for jumping, walls, crates, stomping, spikes, springs, platforms and
checkpoints, a test bot holds right and jumps at walls, gaps, spikes and enemies. It must finish
all four levels without dying, which proves every level can be beaten with the real physics.
