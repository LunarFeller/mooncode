import SwiftUI

@main
struct KimiCodeApp: App {
    @State private var model = AppModel()

    init() {
        PreviewStorage.purge()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
        }
    }
}
