import SwiftUI

struct ContentView: View {
    @Environment(CallStore.self) private var store

    var body: some View {
        TabView {
            CallListView()
                .tabItem { Label("Calls", systemImage: "phone.bubble") }
                .badge(store.unreadCount)
            ForwardingGuideView()
                .tabItem { Label("Set Up", systemImage: "arrow.turn.up.right") }
            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
