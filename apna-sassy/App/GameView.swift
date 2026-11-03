import GameCore
import SpriteKit
import SwiftUI
import UIKit

/// Values the HUD shows. The scene only writes them when they change.
@MainActor
@Observable
final class GameModel {
    let levelIndex: Int
    let scene: GameScene
    var hearts = Player.maxHearts
    var gems = 0
    var seconds = 0
    var result: LevelResult?
    var paused = false

    @ObservationIgnored private let haptics = UIImpactFeedbackGenerator(style: .medium)
    @ObservationIgnored private let notify = UINotificationFeedbackGenerator()

    var totalGems: Int { scene.world.totalGems }

    init(levelIndex: Int) {
        self.levelIndex = levelIndex
        let world = try! World(definition: Levels.all[levelIndex])   // levels are checked by the GameCore tests
        scene = GameScene(world: world)
        scene.onTick = { [weak self] world in self?.tick(world) }
        scene.onEvent = { [weak self] event in self?.feedback(event) }
    }

    private func tick(_ world: World) {
        if hearts != world.player.hearts { hearts = world.player.hearts }
        if gems != world.gems { gems = world.gems }
        let s = Int(world.time)
        if seconds != s { seconds = s }
        if result == nil, let r = world.result { result = r }
    }

    private func feedback(_ event: GameEvent) {
        switch event {
        case .enemyStomped, .crateOpened, .sprang: haptics.impactOccurred(intensity: 0.7)
        case .hurt: notify.notificationOccurred(.warning)
        case .died: notify.notificationOccurred(.error)
        case .won: notify.notificationOccurred(.success)
        default: break
        }
    }

    func setPaused(_ value: Bool) {
        paused = value
        scene.isPaused = value
        if !value { scene.resetClock() }
    }
}

struct GameView: View {
    /// Called with the level to play next, or nil to go back to the menu.
    let onExit: (Int?) -> Void
    @State private var model: GameModel
    @Environment(ProgressStore.self) private var progress
    @Environment(\.scenePhase) private var scenePhase

    init(levelIndex: Int, onExit: @escaping (Int?) -> Void) {
        self.onExit = onExit
        _model = State(initialValue: GameModel(levelIndex: levelIndex))
    }

    var body: some View {
        ZStack {
            SpriteView(scene: model.scene, preferredFramesPerSecond: 120, options: [.ignoresSiblingOrder])
                .ignoresSafeArea()

            VStack {
                hud
                Spacer()
                if model.result == nil {
                    TouchControls(scene: model.scene)
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)

            if model.paused { pauseMenu }
            if let result = model.result { resultCard(result) }
        }
        .onChange(of: model.result) { _, result in
            if let result { progress.record(result, level: model.levelIndex) }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active && model.result == nil { model.setPaused(true) }
        }
    }

    // MARK: - HUD

    private var hud: some View {
        HStack(spacing: 14) {
            Button { model.setPaused(true) } label: {
                Image(systemName: "pause.fill").font(.title3.bold())
                    .frame(width: 44, height: 44)
                    .background(.black.opacity(0.3), in: Circle())
            }
            HStack(spacing: 3) {
                ForEach(0..<Player.maxHearts, id: \.self) { i in
                    Image(systemName: i < model.hearts ? "heart.fill" : "heart")
                        .foregroundStyle(.red)
                }
            }
            pill {
                Image(uiImage: UIImage(cgImage: Art.gem.cgImage())).interpolation(.none)
                    .resizable().frame(width: 18, height: 18)
                Text("\(model.gems)/\(model.totalGems)")
            }
            Spacer()
            pill {
                Image(systemName: "timer")
                Text(Say.seconds(model.seconds))
            }
            Text(Levels.all[model.levelIndex].name)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(.white.opacity(0.85))
        }
        .font(.headline.monospacedDigit())
        .foregroundStyle(.white)
    }

    private func pill<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        HStack(spacing: 6, content: content)
            .padding(.horizontal, 12).padding(.vertical, 6)
            .background(.black.opacity(0.3), in: Capsule())
    }

    // MARK: - Overlays

    private var pauseMenu: some View {
        overlayCard {
            Text(Say.paused).font(.largeTitle.weight(.black))
            HStack(spacing: 12) {
                cardButton(Say.resume, "play.fill") { model.setPaused(false) }
                cardButton(Say.restart, "arrow.counterclockwise") { restart() }
                cardButton(Say.levels, "square.grid.2x2.fill") { onExit(nil) }
            }
        }
    }

    private func resultCard(_ r: LevelResult) -> some View {
        let isLast = model.levelIndex + 1 >= Levels.all.count
        return overlayCard {
            Text(isLast ? Say.homeAtLast : Say.levelDone).font(.largeTitle.weight(.black))
            HStack(spacing: 6) {
                ForEach(0..<3, id: \.self) { i in
                    Image(systemName: i < r.stars ? "star.fill" : "star")
                        .font(.system(size: 36)).foregroundStyle(.yellow)
                }
            }
            Text(Say.summary(seconds: r.time, gems: r.gems, total: r.totalGems, score: r.score))
                .font(.headline.monospacedDigit())
            Text(Say.starRules(par: Int(Levels.all[model.levelIndex].parTime)))
                .font(.caption).opacity(0.75)
            HStack(spacing: 12) {
                cardButton(Say.replay, "arrow.counterclockwise") { restart() }
                cardButton(Say.levels, "square.grid.2x2.fill") { onExit(nil) }
                if !isLast {
                    cardButton(Say.next, "arrow.right") { onExit(model.levelIndex + 1) }
                }
            }
        }
    }

    private func restart() {
        model.setPaused(false)
        model = GameModel(levelIndex: model.levelIndex)
    }

    private func overlayCard<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        ZStack {
            Color.black.opacity(0.45).ignoresSafeArea()
            VStack(spacing: 16, content: content)
                .foregroundStyle(.white)
                .padding(28)
                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 24))
        }
    }

    private func cardButton(_ title: String, _ icon: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(title, systemImage: icon)
                .font(.headline)
                .padding(.horizontal, 18).padding(.vertical, 12)
                .background(.white.opacity(0.2), in: Capsule())
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Touch controls

/// Left/right on the left thumb, jump on the right thumb. Each button tracks its own touch,
/// so you can run and jump at the same time.
struct TouchControls: View {
    let scene: GameScene

    var body: some View {
        HStack(alignment: .bottom) {
            HStack(spacing: 14) {
                HoldButton(icon: "arrowtriangle.left.fill") { scene.touchInput.left = $0 }
                HoldButton(icon: "arrowtriangle.right.fill") { scene.touchInput.right = $0 }
            }
            Spacer()
            HoldButton(icon: "arrow.up", size: 96) { down in
                if down { scene.touchInput.jumpPresses += 1 }
                scene.touchInput.jumpHeld = down
            }
        }
    }
}

struct HoldButton: View {
    let icon: String
    var size: CGFloat = 80
    let onChange: (Bool) -> Void
    @State private var down = false

    var body: some View {
        Image(systemName: icon)
            .font(.system(size: size * 0.38, weight: .black))
            .foregroundStyle(.white.opacity(down ? 1 : 0.85))
            .frame(width: size, height: size)
            .background(.black.opacity(down ? 0.45 : 0.25), in: Circle())
            .overlay(Circle().stroke(.white.opacity(0.35), lineWidth: 2))
            .scaleEffect(down ? 0.92 : 1)
            .contentShape(Circle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        if !down { down = true; onChange(true) }
                    }
                    .onEnded { _ in
                        down = false
                        onChange(false)
                    }
            )
            .accessibilityLabel(icon.contains("left") ? Say.left : icon.contains("right") ? Say.right : Say.jump)
    }
}
