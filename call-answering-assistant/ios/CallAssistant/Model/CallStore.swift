import Foundation
import Observation
import UIKit
import UserNotifications

@MainActor
@Observable
final class CallStore {
    static let shared = CallStore()

    var calls: [Call] = []
    var isLoading = false
    var errorMessage: String?
    /// Set when the user taps a notification, so the list can open that call.
    var callToOpen: String?

    var serverURL: String {
        didSet { UserDefaults.standard.set(serverURL, forKey: "serverURL") }
    }
    var accessToken: String {
        didSet { Keychain.write(accessToken, for: "accessToken") }
    }
    private var pushToken: String?

    var api: APIClient { APIClient(baseURL: serverURL, token: accessToken) }
    var unreadCount: Int { calls.filter { !$0.isRead && !$0.isInProgress }.count }

    private init() {
        serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? ""
        accessToken = Keychain.read("accessToken")
    }

    func refresh() async {
        guard api.isConfigured else { errorMessage = APIError.notConfigured.errorDescription; return }
        isLoading = true
        defer { isLoading = false }
        do {
            calls = try await api.calls()
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
        updateBadge()
    }

    func setRead(_ call: Call, _ read: Bool) async {
        guard let index = calls.firstIndex(where: { $0.sid == call.sid }), calls[index].isRead != read else { return }
        calls[index].isRead = read
        updateBadge()
        do { try await api.markRead(call.sid, read) } catch { errorMessage = error.localizedDescription }
    }

    func delete(_ call: Call) async {
        calls.removeAll { $0.sid == call.sid }
        updateBadge()
        do { try await api.delete(call.sid) } catch { errorMessage = error.localizedDescription }
    }

    // MARK: - Push notifications

    func didReceivePushToken(_ token: String) {
        pushToken = token
        Task { await registerPushToken() }
    }

    /// Called at launch and again whenever the server settings change.
    func registerPushToken() async {
        guard let pushToken, api.isConfigured else { return }
        try? await api.registerDevice(token: pushToken)
    }

    private func updateBadge() {
        UNUserNotificationCenter.current().setBadgeCount(unreadCount)
    }
}
