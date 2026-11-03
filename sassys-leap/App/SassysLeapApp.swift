import GameCore
import SwiftUI

@main
struct SassysLeapApp: App {
    @State private var progress = ProgressStore()
    @State private var playing: Int?

    var body: some Scene {
        WindowGroup {
            Group {
                if let index = playing {
                    GameView(levelIndex: index) { next in
                        playing = next
                    }
                    .id(index)
                } else {
                    MenuView { playing = $0 }
                }
            }
            .environment(progress)
            .persistentSystemOverlays(.hidden)
            .statusBarHidden()
            .preferredColorScheme(.dark)
        }
    }
}

struct LevelRecord: Codable, Equatable {
    var stars: Int
    var bestTime: Double
    var bestScore: Int
}

/// Stars and best times per level, kept on the device.
@Observable
final class ProgressStore {
    private(set) var records: [Int: LevelRecord] = [:]
    private let key = "levelRecords"

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode([Int: LevelRecord].self, from: data) {
            records = saved
        }
    }

    func isUnlocked(_ index: Int) -> Bool { index == 0 || records[index - 1] != nil }

    var totalStars: Int { records.values.map(\.stars).reduce(0, +) }

    func record(_ result: LevelResult, level index: Int) {
        var best = records[index] ?? LevelRecord(stars: 0, bestTime: .infinity, bestScore: 0)
        best.stars = max(best.stars, result.stars)
        best.bestTime = min(best.bestTime, result.time)
        best.bestScore = max(best.bestScore, result.score)
        records[index] = best
        if let data = try? JSONEncoder().encode(records) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}
