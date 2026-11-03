# Apna Sassy — context for Claude Code

This file carries over everything done so far in an earlier cloud session, so work can continue
on the owner's Windows PC. Claude Code reads it automatically when started in this folder.

## What this is

**Apna Sassy (अपना सैसी)** is an original side-scrolling platformer for iPhone (iOS 17+, the owner
runs iOS 27.2). The hero is **Apna Sassy**, the owner's real Saint Bernard: brown and white coat,
dark ears, white blaze, black/blue harness, fluffy tail. She runs, jumps, stomps critters, opens
crates for gems and bounces on springs across four levels named after places around Munger, Bihar.

- The game must stay **original**. The owner once asked for it to look exactly like Super Mario;
  that was declined (it would be a copy of Nintendo's game). Don't reintroduce Mario characters,
  levels, art, music, HUD or title-screen look. Genre conventions are fine.
- All on-screen text is in **Angika as spoken around Munger** (Devanagari), e.g.
  "की बात छै! लेवल पार होय गेलै!", "तनी दम धरोॅ", "अपना सैसी घोॅर पहुँची गेलै!".
  Every string is in `App/Strings.swift` (iOS) and the `SAY` object in `web/template.html` (web).
  The owner should confirm wording; Angika varies by village.

## Layout

| Path | What |
|---|---|
| `Sources/GameCore/` | Game rules in plain Swift: physics (fixed 120 Hz, coyote time, jump buffer), collisions, enemies, scoring, stars. `Levels.swift` holds the ASCII level maps (legend in `Level.swift`). |
| `App/` | iOS app: SpriteKit renderer (`GameScene.swift`), SwiftUI menu/HUD/touch controls (`MenuView.swift`, `GameView.swift`), pixel art drawn in code (`Art.swift`), strings (`Strings.swift`), app entry + saved progress (`ApnaSassyApp.swift`), app icon (`Assets.xcassets`). |
| `Tests/GameCoreTests/` | 13 tests, including a bot that must finish all 4 levels without dying. Run `swift test`. |
| `project.yml` | XcodeGen spec (`xcodegen generate` → `ApnaSassy.xcodeproj`). Bundle ID is still the placeholder `com.example.ApnaSassy`. |
| `web/` | Browser version: same rules/levels/art/text ported to JS. `python web/build.py` regenerates `web/index.html` from the Swift sources. Published privately at https://claude.ai/artifact/KLqxjz6frnyC7fmHCjBaTF |
| `docs/` | `app-icon.png` (1024², made from a photo of Sassy cut out onto the meadow sky), sprite preview. |
| `../.github/workflows/apna-sassy-ios.yml` | GitHub Actions on `macos-15`: runs tests, generates the project, builds an **unsigned** `.ipa`, uploads it as artifact `ApnaSassy-unsigned-ipa`. |

Levels (in order): गंगा किनारोॅ (meadow), खड़गपुर के गुफा (cavern), बादलोॅ के सीढ़ी (sky),
मुंगेर किला (dusk). Enemies: beetle and bat (stompable), spiker (never stomp).

## Status

- Engine tests pass (Linux and macOS CI). The iOS app **compiles** on GitHub's Mac runner and
  produces `ApnaSassy-unsigned.ipa` (~2 MB, display name अपना सैसी, icon included, landscape only).
- The app has **never been run on a real iPhone yet**.
- Work lives on branch `claude/sprout-platformer` (not merged to `main`).

## Where we are: installing on the owner's iPhone from Windows

The owner has no Mac and a free Apple ID, so the plan is **Sideloadly** on Windows:

1. Install iTunes and iCloud — the web versions from Apple, not Microsoft Store ones
   (`winget install --id Apple.iTunes -e`; iCloud from the link on sideloadly.io).
2. Install Sideloadly (`winget search sideloadly`, else download `https://sideloadly.io/SideloadlySetup64.exe`).
3. Get the `.ipa`: from the earlier chat, or from the latest successful run of the
   "Apna Sassy iOS build" workflow on GitHub (Actions tab → run → Artifacts).
4. Plug in the iPhone, tap Trust, drag the `.ipa` into Sideloadly, sign in with the Apple ID
   (the owner types the password; never ask for it), Start.
5. On the iPhone: Settings › Privacy & Security › Developer Mode on; Settings › General ›
   VPN & Device Management › trust the Apple ID. Free-account installs expire after 7 days.

Sideloadly has no CLI; the signing step is in its window. Help the owner through errors from
there.

## Possible next steps (only when asked)

- With a paid Apple Developer account: real bundle ID, signing + TestFlight upload in CI.
- Sounds (the owner may record Angika voice lines), dog-treat collectibles, more levels.
