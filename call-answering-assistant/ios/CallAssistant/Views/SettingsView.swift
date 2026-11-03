import SwiftUI

struct SettingsView: View {
    @Environment(CallStore.self) private var store
    @State private var serverURL = ""
    @State private var token = ""
    @State private var assistant = AssistantSettings(ownerName: "", greeting: "", instructions: "")
    @State private var status: String?
    @State private var busy = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("https://your-server.example.com", text: $serverURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField("Access token (APP_API_TOKEN)", text: $token)
                    Button("Connect") { Task { await connect() } }
                        .disabled(serverURL.isEmpty || token.isEmpty || busy)
                } header: {
                    Text("Server")
                } footer: {
                    Text("The backend that answers your forwarded calls. See the README for setup.")
                }

                Section {
                    TextField("Your name", text: $assistant.ownerName)
                    TextField("Custom greeting (optional)", text: $assistant.greeting, axis: .vertical)
                        .lineLimit(2...4)
                } header: {
                    Text("Assistant")
                } footer: {
                    Text("Leave the greeting empty to use: \"Hi, you've reached <name>'s assistant…\"")
                }

                Section {
                    TextField(
                        "e.g. I'm at work until 6pm. If it's the school, say it's urgent. "
                            + "Deliveries can be left at the front door.",
                        text: $assistant.instructions, axis: .vertical
                    )
                    .lineLimit(4...10)
                } header: {
                    Text("What the assistant should know")
                }

                Section {
                    Button("Save assistant settings") { Task { await saveAssistant() } }
                        .disabled(busy || !store.api.isConfigured)
                    if let status {
                        Text(status).font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("Settings")
            .task {
                serverURL = store.serverURL
                token = store.accessToken
                await loadAssistant()
            }
        }
    }

    private func connect() async {
        busy = true
        defer { busy = false }
        store.serverURL = serverURL.trimmingCharacters(in: .whitespaces)
        store.accessToken = token.trimmingCharacters(in: .whitespaces)
        do {
            _ = try await store.api.health()
            _ = try await store.api.calls()   // checks the token too
            status = "Connected."
            await store.registerPushToken()
            await loadAssistant()
            await store.refresh()
        } catch {
            status = error.localizedDescription
        }
    }

    private func loadAssistant() async {
        guard store.api.isConfigured else { return }
        if let loaded = try? await store.api.settings() { assistant = loaded }
    }

    private func saveAssistant() async {
        busy = true
        defer { busy = false }
        do {
            assistant = try await store.api.save(assistant)
            status = "Saved. New calls will use these settings."
        } catch {
            status = error.localizedDescription
        }
    }
}
