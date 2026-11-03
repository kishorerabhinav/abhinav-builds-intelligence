import Foundation

enum APIError: LocalizedError {
    case notConfigured
    case badURL
    case http(Int, String)

    var errorDescription: String? {
        switch self {
        case .notConfigured: return "Add your server address and access token in Settings."
        case .badURL: return "The server address isn't a valid URL."
        case .http(401, _): return "The server rejected the access token."
        case .http(let code, let body): return "Server error \(code). \(body)"
        }
    }
}

/// Talks to the call-answering backend's /api endpoints.
struct APIClient {
    let baseURL: String
    let token: String

    var isConfigured: Bool { !baseURL.isEmpty && !token.isEmpty }

    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    func health() async throws -> Bool {
        struct Health: Decodable { let ok: Bool }
        let data = try await send("GET", "/api/health")
        return try Self.decoder.decode(Health.self, from: data).ok
    }

    func calls() async throws -> [Call] {
        try Self.decoder.decode([Call].self, from: try await send("GET", "/api/calls"))
    }

    func call(_ sid: String) async throws -> Call {
        try Self.decoder.decode(Call.self, from: try await send("GET", "/api/calls/\(sid)"))
    }

    func markRead(_ sid: String, _ read: Bool) async throws {
        _ = try await send("PATCH", "/api/calls/\(sid)", body: ["is_read": read])
    }

    func delete(_ sid: String) async throws {
        _ = try await send("DELETE", "/api/calls/\(sid)")
    }

    func settings() async throws -> AssistantSettings {
        try Self.decoder.decode(AssistantSettings.self, from: try await send("GET", "/api/settings"))
    }

    func save(_ settings: AssistantSettings) async throws -> AssistantSettings {
        let data = try await send("PUT", "/api/settings", json: try Self.encoder.encode(settings))
        return try Self.decoder.decode(AssistantSettings.self, from: data)
    }

    func registerDevice(token deviceToken: String) async throws {
        _ = try await send("POST", "/api/devices", body: ["token": deviceToken])
    }

    // MARK: - Plumbing

    private func send(_ method: String, _ path: String, body: [String: Any]? = nil) async throws -> Data {
        let json = try body.map { try JSONSerialization.data(withJSONObject: $0) }
        return try await send(method, path, json: json)
    }

    private func send(_ method: String, _ path: String, json: Data?) async throws -> Data {
        guard isConfigured else { throw APIError.notConfigured }
        let trimmed = baseURL.trimmingCharacters(in: CharacterSet(charactersIn: "/ "))
        guard let url = URL(string: trimmed + path), url.scheme == "https" || url.host == "localhost" else {
            throw APIError.badURL
        }
        var request = URLRequest(url: url, timeoutInterval: 20)
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let json {
            request.httpBody = json
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        let (data, response) = try await URLSession.shared.data(for: request)
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard (200..<300).contains(code) else {
            throw APIError.http(code, String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }
}
