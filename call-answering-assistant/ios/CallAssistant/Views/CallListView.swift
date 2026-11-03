import SwiftUI

struct CallListView: View {
    @Environment(CallStore.self) private var store
    @State private var path: [String] = []
    @State private var showSpam = false

    private var visibleCalls: [Call] {
        store.calls.filter { showSpam || !$0.isSpam }
    }

    var body: some View {
        NavigationStack(path: $path) {
            List {
                if let error = store.errorMessage {
                    Label(error, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                        .font(.footnote)
                }
                ForEach(visibleCalls) { call in
                    NavigationLink(value: call.sid) { CallRow(call: call) }
                        .swipeActions(edge: .trailing) {
                            Button(role: .destructive) {
                                Task { await store.delete(call) }
                            } label: { Label("Delete", systemImage: "trash") }
                        }
                        .swipeActions(edge: .leading) {
                            Button {
                                Task { await store.setRead(call, !call.isRead) }
                            } label: {
                                Label(call.isRead ? "Unread" : "Read",
                                      systemImage: call.isRead ? "envelope.badge" : "envelope.open")
                            }
                            .tint(.blue)
                        }
                }
            }
            .overlay {
                if visibleCalls.isEmpty && store.errorMessage == nil {
                    ContentUnavailableView(
                        "No calls yet",
                        systemImage: "phone.arrow.down.left",
                        description: Text("Calls your assistant answers will show up here.")
                    )
                }
            }
            .navigationTitle("Calls")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Toggle("Show spam", isOn: $showSpam)
                    } label: { Image(systemName: "line.3.horizontal.decrease.circle") }
                }
            }
            .navigationDestination(for: String.self) { sid in
                CallDetailView(sid: sid)
            }
            .refreshable { await store.refresh() }
            .task { await store.refresh() }
            .onChange(of: store.callToOpen) { _, sid in
                guard let sid else { return }
                path = [sid]
                store.callToOpen = nil
            }
        }
    }
}

private struct CallRow: View {
    let call: Call

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Circle()
                .fill(call.isRead ? Color.clear : Color.blue)
                .frame(width: 9, height: 9)
                .padding(.top, 6)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(call.displayName).font(.headline).lineLimit(1)
                    if call.isUrgent {
                        Text("URGENT")
                            .font(.caption2.bold())
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(.red, in: Capsule())
                            .foregroundStyle(.white)
                    }
                    Spacer()
                    if let date = call.startDate {
                        Text(date, format: .relative(presentation: .named))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                if call.isInProgress {
                    Label(call.status == "summarizing" ? "Summarizing…" : "On the line now",
                          systemImage: "waveform")
                        .font(.subheadline).foregroundStyle(.green)
                } else {
                    if let reason = call.reason, !reason.isEmpty {
                        Text(reason).font(.subheadline.weight(.medium))
                    }
                    Text(call.summary ?? "")
                        .font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
                }
            }
        }
        .padding(.vertical, 2)
    }
}
