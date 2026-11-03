import GameCore
import SpriteKit
import SwiftUI

struct MenuView: View {
    let onPlay: (Int) -> Void
    @Environment(ProgressStore.self) private var progress

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.43, green: 0.78, blue: 1), Color(red: 0.79, green: 0.93, blue: 1)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            HStack(spacing: 32) {
                VStack(spacing: 14) {
                    Image(uiImage: UIImage(cgImage: Art.sassyIdle.cgImage()))
                        .interpolation(.none)
                        .resizable()
                        .frame(width: 126, height: 91)
                    Text("Apna Sassy")
                        .font(.system(size: 44, weight: .black, design: .rounded))
                        .foregroundStyle(.white)
                        .shadow(color: .black.opacity(0.35), radius: 0, x: 3, y: 3)
                    Label("\(progress.totalStars) / \(Levels.all.count * 3)", systemImage: "star.fill")
                        .font(.headline)
                        .foregroundStyle(.yellow)
                        .padding(.horizontal, 12).padding(.vertical, 6)
                        .background(.black.opacity(0.25), in: Capsule())
                }

                ScrollView {
                    VStack(spacing: 10) {
                        ForEach(Array(Levels.all.enumerated()), id: \.offset) { index, level in
                            LevelButton(index: index, level: level, record: progress.records[index],
                                        unlocked: progress.isUnlocked(index)) { onPlay(index) }
                        }
                    }
                    .padding(.vertical, 20)
                }
                .frame(maxWidth: 340)
                .scrollIndicators(.hidden)
            }
            .padding(.horizontal, 24)
        }
    }
}

private struct LevelButton: View {
    let index: Int
    let level: LevelDefinition
    let record: LevelRecord?
    let unlocked: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Text("\(index + 1)")
                    .font(.title2.weight(.black))
                    .frame(width: 40, height: 40)
                    .background(.white.opacity(0.25), in: RoundedRectangle(cornerRadius: 10))
                VStack(alignment: .leading, spacing: 2) {
                    Text(level.name).font(.headline)
                    if let record {
                        Text("Best \(String(format: "%.1f", record.bestTime))s · \(record.bestScore) pts")
                            .font(.caption).opacity(0.85)
                    } else {
                        Text(unlocked ? "Not played yet" : "Finish the level before")
                            .font(.caption).opacity(0.85)
                    }
                }
                Spacer()
                if unlocked {
                    HStack(spacing: 2) {
                        ForEach(0..<3, id: \.self) { star in
                            Image(systemName: star < (record?.stars ?? 0) ? "star.fill" : "star")
                                .foregroundStyle(.yellow)
                        }
                    }
                } else {
                    Image(systemName: "lock.fill")
                }
            }
            .foregroundStyle(.white)
            .padding(12)
            .background(themeColor.opacity(unlocked ? 1 : 0.45), in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
        .disabled(!unlocked)
    }

    private var themeColor: Color {
        switch level.theme {
        case .meadow: return Color(red: 0.24, green: 0.6, blue: 0.21)
        case .cavern: return Color(red: 0.33, green: 0.29, blue: 0.47)
        case .sky: return Color(red: 0.45, green: 0.62, blue: 0.95)
        case .dusk: return Color(red: 0.55, green: 0.27, blue: 0.39)
        }
    }
}
