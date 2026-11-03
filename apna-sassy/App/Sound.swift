import AVFoundation
import GameCore

/// Small synth effects, and Sassy's lines read by iOS's Hindi female voice (the closest to
/// Angika a phone has). Matches `sound` in web/template.html.
@MainActor
final class Sound {
    static let shared = Sound()

    private let engine = AVAudioEngine()
    private let players = (0..<6).map { _ in AVAudioPlayerNode() }
    private var nextPlayer = 0
    private let format = AVAudioFormat(standardFormatWithSampleRate: 44_100, channels: 1)!
    private var clips: [String: AVAudioPCMBuffer] = [:]
    private let speech = AVSpeechSynthesizer()
    private lazy var voice: AVSpeechSynthesisVoice? = {
        let hindi = AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("hi") }
        return hindi.first { $0.gender == .female } ?? hindi.first ?? AVSpeechSynthesisVoice(language: "hi-IN")
    }()

    private enum Wave { case square, triangle, sine, saw }
    private struct Note { var from: Double, to: Double, length: Double, wave: Wave, volume: Float, at: Double = 0 }

    private init() {
        // .playback: heard even with the silent switch on; mixes with music already playing.
        try? AVAudioSession.sharedInstance().setCategory(.playback, options: [.mixWithOthers])
        try? AVAudioSession.sharedInstance().setActive(true)
        for p in players {
            engine.attach(p)
            engine.connect(p, to: engine.mainMixerNode, format: format)
        }
        let arp: ([Double], Double) -> [Note] = { freqs, step in
            freqs.enumerated().map { Note(from: $1, to: $1, length: step * 1.6, wave: .triangle, volume: 0.14, at: Double($0) * step) }
        }
        clips = [
            "jump": render([Note(from: 380, to: 760, length: 0.12, wave: .square, volume: 0.08)]),
            "spring": render([Note(from: 300, to: 1200, length: 0.25, wave: .sine, volume: 0.16)]),
            "gem": render(arp([988, 1319], 0.06)),
            "crate": render([Note(from: 220, to: 160, length: 0.09, wave: .square, volume: 0.1)] + arp([1319], 0.06)),
            "stomp": render([Note(from: 520, to: 110, length: 0.14, wave: .square, volume: 0.12)]),
            "checkpoint": render(arp([523, 659, 784], 0.09)),
            "hurt": render([Note(from: 320, to: 110, length: 0.28, wave: .saw, volume: 0.1)]),
            "died": render([Note(from: 420, to: 70, length: 0.7, wave: .saw, volume: 0.1)]),
            "won": render(arp([523, 659, 784, 1047], 0.12)),
        ]
        try? engine.start()
    }

    private func render(_ notes: [Note]) -> AVAudioPCMBuffer {
        let rate = format.sampleRate
        let total = notes.map { $0.at + $0.length }.max() ?? 0
        let frames = AVAudioFrameCount(total * rate) + 1
        let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames)!
        buffer.frameLength = frames
        let out = buffer.floatChannelData![0]
        for n in notes {
            var phase = 0.0
            let start = Int(n.at * rate), count = Int(n.length * rate)
            for i in 0..<count where start + i < Int(frames) {
                let k = Double(i) / Double(count)
                phase += n.from * pow(n.to / n.from, k) / rate          // exponential sweep, like Web Audio
                let p = phase - floor(phase)
                let s: Double
                switch n.wave {
                case .square: s = p < 0.5 ? 1 : -1
                case .triangle: s = 1 - 4 * abs(p - 0.5)
                case .sine: s = sin(2 * .pi * p)
                case .saw: s = 2 * p - 1
                }
                out[start + i] += Float(s) * n.volume * Float(pow(0.001, k))   // fade to silence
            }
        }
        return buffer
    }

    private func play(_ name: String) {
        guard let clip = clips[name] else { return }
        if !engine.isRunning { try? engine.start() }
        let p = players[nextPlayer]
        nextPlayer = (nextPlayer + 1) % players.count
        p.stop()
        p.scheduleBuffer(clip)
        p.play()
    }

    func say(_ text: String) {
        speech.stopSpeaking(at: .immediate)
        let u = AVSpeechUtterance(string: text)
        u.voice = voice
        u.pitchMultiplier = 1.2
        speech.speak(u)
    }

    func play(_ event: GameEvent, lastLevel: Bool) {
        switch event {
        case .jumped: play("jump")
        case .sprang: play("spring")
        case .gemCollected: play("gem")
        case .crateOpened: play("crate")
        case .enemyStomped: play("stomp")
        case .checkpoint: play("checkpoint"); say(Say.Voice.checkpoint)
        case .hurt: play("hurt"); say(Say.Voice.hurt)
        case .died: play("died"); say(Say.Voice.died)
        case .won: play("won"); say(lastLevel ? Say.homeAtLast : Say.levelDone)
        case .landed, .respawned: break
        }
    }
}
