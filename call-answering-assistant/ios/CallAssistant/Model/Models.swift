import Foundation

struct Turn: Codable, Hashable {
    let role: String   // "assistant" or "caller"
    let text: String

    var isCaller: Bool { role == "caller" }
}

struct Call: Codable, Identifiable, Hashable {
    let sid: String
    let fromNumber: String
    let toNumber: String
    let startedAt: String
    let endedAt: String?
    let status: String
    let transcript: [Turn]
    let callerName: String?
    let callbackNumber: String?
    let reason: String?
    let urgency: String?
    let summary: String?
    var isRead: Bool

    var id: String { sid }

    var displayName: String {
        if let name = callerName, !name.isEmpty { return name }
        return fromNumber.isEmpty ? "Unknown caller" : fromNumber
    }

    var numberToCall: String {
        if let number = callbackNumber, !number.isEmpty { return number }
        return fromNumber
    }

    var startDate: Date? { Call.parseDate(startedAt) }

    var duration: TimeInterval? {
        guard let start = startDate, let end = endedAt.flatMap(Call.parseDate) else { return nil }
        return end.timeIntervalSince(start)
    }

    var isInProgress: Bool { status == "in_progress" || status == "summarizing" }
    var isUrgent: Bool { urgency == "urgent" }
    var isSpam: Bool { urgency == "spam" }

    var callBackURL: URL? {
        let digits = numberToCall.filter { $0.isNumber || $0 == "+" }
        return digits.isEmpty ? nil : URL(string: "tel:\(digits)")
    }

    private static func parseDate(_ value: String) -> Date? {
        ISO8601DateFormatter().date(from: value)
    }
}

struct AssistantSettings: Codable, Equatable {
    var ownerName: String
    var greeting: String
    var instructions: String
}
