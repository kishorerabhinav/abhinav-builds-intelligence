import SwiftUI
import UIKit

/// iOS doesn't let apps answer cellular calls, so the carrier forwards calls you
/// don't pick up to the assistant's Twilio number. iOS also blocks apps from
/// dialing * and # codes, so this screen builds the code for you to copy and dial.
struct ForwardingGuideView: View {
    @AppStorage("assistantNumber") private var assistantNumber = ""
    @State private var copied: String?

    private var number: String { assistantNumber.filter { $0.isNumber || $0 == "+" } }

    private struct Code: Identifiable {
        let id = UUID()
        let title: String
        let detail: String
        let code: String
    }

    private var gsmCodes: [Code] {
        [
            Code(title: "When I don't answer",
                 detail: "Rings you first for 20 seconds, then the assistant picks up.",
                 code: "**61*\(number)**20#"),
            Code(title: "When I decline or I'm busy",
                 detail: "Tap the red button to send a call to the assistant.",
                 code: "**67*\(number)#"),
            Code(title: "When my phone is off or has no signal",
                 detail: "Airplane mode, dead battery, no coverage.",
                 code: "**62*\(number)#"),
            Code(title: "Turn all forwarding off", detail: "Undo everything above.", code: "##002#"),
        ]
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    TextField("Assistant's Twilio number, e.g. +14155550123", text: $assistantNumber)
                        .keyboardType(.phonePad)
                } header: {
                    Text("1. Your assistant's number")
                } footer: {
                    Text("Include the country code. This is the Twilio number your server answers.")
                }

                if !number.isEmpty {
                    Section {
                        ForEach(gsmCodes) { item in
                            codeRow(item)
                        }
                    } header: {
                        Text("2. Dial a code in the Phone app")
                    } footer: {
                        Text("Works on most GSM carriers, including AT&T, T-Mobile, and most carriers "
                             + "outside the US. Copy a code, open Phone, paste it into the keypad, and "
                             + "press call. You'll get a confirmation on screen.")
                    }

                    Section {
                        codeRow(Code(title: "Busy and no-answer forwarding",
                                     detail: "Verizon conditional forwarding.",
                                     code: "*71\(number.replacingOccurrences(of: "+1", with: ""))"))
                        codeRow(Code(title: "Turn off", detail: "Verizon.", code: "*73"))
                    } header: {
                        Text("Verizon instead")
                    }
                }

                Section("3. Test it") {
                    Text("Call your iPhone from another phone and let it ring, or decline it. "
                         + "The assistant answers, and a summary appears in Calls a few seconds "
                         + "after the caller hangs up.")
                }

                Section("Good to know") {
                    Text("Your iPhone still rings first, so you never miss a call you want.")
                    Text("If Live Voicemail or Call Screening is on (Settings › Apps › Phone), "
                         + "iPhone may handle unknown callers itself before forwarding kicks in.")
                    Text("Forwarded minutes may count against your plan. Check with your carrier.")
                }
            }
            .navigationTitle("Set Up Forwarding")
            .overlay(alignment: .bottom) {
                if let copied {
                    Text("Copied \(copied)")
                        .font(.footnote.bold())
                        .padding(.horizontal, 14).padding(.vertical, 8)
                        .background(.thinMaterial, in: Capsule())
                        .padding(.bottom, 12)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
        }
    }

    private func codeRow(_ item: Code) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(item.title).font(.headline)
            Text(item.detail).font(.footnote).foregroundStyle(.secondary)
            HStack {
                Text(item.code).font(.body.monospaced()).textSelection(.enabled)
                Spacer()
                Button {
                    UIPasteboard.general.string = item.code
                    withAnimation { copied = item.code }
                    Task {
                        try? await Task.sleep(for: .seconds(2))
                        withAnimation { if copied == item.code { copied = nil } }
                    }
                } label: { Label("Copy", systemImage: "doc.on.doc") }
                    .buttonStyle(.bordered)
                    .labelStyle(.iconOnly)
            }
        }
        .padding(.vertical, 4)
    }
}
