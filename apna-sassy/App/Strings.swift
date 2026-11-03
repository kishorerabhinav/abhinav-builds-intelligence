import Foundation

/// Every word the player sees, in Angika as spoken around Munger, Bihar.
/// Change the game's wording here.
enum Say {
    static let title = "अपना सैसी"

    // Level list
    static func best(seconds: Double, score: Int) -> String {
        "सबसें बढ़िया \(String(format: "%.1f", seconds)) सेकेंड · \(score) अंक"
    }
    static let notPlayed = "अभी तांय नै खेललौ"
    static let locked = "पहिलकोॅ लेवल पार करोॅ"

    // In the level
    static func seconds(_ s: Int) -> String { "\(s) सेकेंड" }
    static let paused = "तनी दम धरोॅ"
    static let resume = "आगू चलोॅ"
    static let restart = "फेरू सें"
    static let levels = "लेवल"
    static let replay = "फेरू खेलोॅ"
    static let next = "अगलका"

    // Results
    static let levelDone = "की बात छै! लेवल पार होय गेलै!"
    static let homeAtLast = "अपना सैसी घोॅर पहुँची गेलै!"
    static func summary(seconds: Double, gems: Int, total: Int, score: Int) -> String {
        "\(String(format: "%.1f", seconds)) सेकेंड · हीरा \(gems)/\(total) · \(score) अंक"
    }
    static func starRules(par: Int) -> String {
        "तारा मिलतौं: पार करला पर · सब हीरा बटोरला पर · \(par) सेकेंड सें पहिनें"
    }

    // Controls (VoiceOver)
    static let left = "बायाँ"
    static let right = "दायाँ"
    static let jump = "कूदोॅ"
}
