import Foundation

/// Every word the player sees, in Hindi with a Bihari (Bhojpuri) flavour.
/// Change the game's wording here.
enum Say {
    static let title = "अपना सैसी"

    // Level list
    static func best(seconds: Double, score: Int) -> String {
        "सबसे बढ़िया \(String(format: "%.1f", seconds)) सेकंड · \(score) अंक"
    }
    static let notPlayed = "अभी खेलल नइखीं"
    static let locked = "पहिले वाला लेवल पार करीं"

    // In the level
    static func seconds(_ s: Int) -> String { "\(s) सेकंड" }
    static let paused = "तनी सुस्ता लीं"
    static let resume = "चलीं आगे"
    static let restart = "फेर से"
    static let levels = "लेवल"
    static let replay = "फेर खेलीं"
    static let next = "अगिला"

    // Results
    static let levelDone = "का बात बा! लेवल पार!"
    static let homeAtLast = "अपना सैसी घरे पहुँच गइली!"
    static func summary(seconds: Double, gems: Int, total: Int, score: Int) -> String {
        "\(String(format: "%.1f", seconds)) सेकंड · हीरा \(gems)/\(total) · \(score) अंक"
    }
    static func starRules(par: Int) -> String {
        "तारा मिली: पार करे पर · सब हीरा बटोरे पर · \(par) सेकंड से पहिले"
    }

    // Controls (VoiceOver)
    static let left = "बाएँ"
    static let right = "दाएँ"
    static let jump = "कूदीं"
}
