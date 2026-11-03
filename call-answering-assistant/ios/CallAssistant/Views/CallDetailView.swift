import SwiftUI

struct CallDetailView: View {
    let sid: String
    @Environment(CallStore.self) private var store
    @Environment(\.openURL) private var openURL
    @State private var call: Call?
    @State private var error: String?

    var body: some View {
        Group {
            if let call {
                content(for: call)
            } else if let error {
                ContentUnavailableView("Couldn't load call", systemImage: "exclamationmark.triangle",
                                       description: Text(error))
            } else {
                ProgressView()
            }
        }
        .navigationTitle(call?.displayName ?? "Call")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: sid) { await load() }
        .refreshable { await load() }
    }

    private func content(for call: Call) -> some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    if let reason = call.reason, !reason.isEmpty {
                        Text(reason).font(.title3.bold())
                    }
                    Text(call.summary ?? (call.isInProgress ? "The caller is still on the line." : ""))
                    HStack(spacing: 12) {
                        if let date = call.startDate {
                            Label(date.formatted(date: .abbreviated, time: .shortened), systemImage: "clock")
                        }
                        if let duration = call.duration {
                            Label(Duration.seconds(duration).formatted(.time(pattern: .minuteSecond)),
                                  systemImage: "timer")
                        }
                    }
                    .font(.caption).foregroundStyle(.secondary)
                }
                .padding(.vertical, 4)
            }

            Section("Caller") {
                LabeledContent("Caller ID", value: call.fromNumber.isEmpty ? "Unknown" : call.fromNumber)
                if let number = call.callbackNumber, !number.isEmpty, number != call.fromNumber {
                    LabeledContent("Call back on", value: number)
                }
                if let url = call.callBackURL {
                    Button { openURL(url) } label: {
                        Label("Call back \(call.numberToCall)", systemImage: "phone.fill")
                    }
                }
                if let digits = call.callBackURL?.absoluteString.replacingOccurrences(of: "tel:", with: ""),
                   let sms = URL(string: "sms:\(digits)") {
                    Button { openURL(sms) } label: { Label("Send a text", systemImage: "message.fill") }
                }
            }

            Section("Transcript") {
                ForEach(Array(call.transcript.enumerated()), id: \.offset) { _, turn in
                    TranscriptBubble(turn: turn)
                        .listRowSeparator(.hidden)
                }
            }
        }
    }

    private func load() async {
        do {
            let loaded = try await store.api.call(sid)
            call = loaded
            error = nil
            if !loaded.isInProgress { await store.setRead(loaded, true) }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

private struct TranscriptBubble: View {
    let turn: Turn

    var body: some View {
        HStack {
            if turn.isCaller { Spacer(minLength: 40) }
            VStack(alignment: turn.isCaller ? .trailing : .leading, spacing: 2) {
                Text(turn.isCaller ? "Caller" : "Assistant")
                    .font(.caption2).foregroundStyle(.secondary)
                Text(turn.text)
                    .padding(10)
                    .background(turn.isCaller ? Color.blue.opacity(0.15) : Color(.secondarySystemBackground),
                                in: RoundedRectangle(cornerRadius: 14))
            }
            if !turn.isCaller { Spacer(minLength: 40) }
        }
    }
}
