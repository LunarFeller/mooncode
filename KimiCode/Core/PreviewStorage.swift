import Foundation

/// 文件预览 / 下载落地的沙盒临时目录：`tmp/MoonCodePreview/<uuid>/<文件名>`，每个文件独占一个子目录，删的时候整个子目录一起删。
enum PreviewStorage {
    private static var root: URL {
        FileManager.default.temporaryDirectory.appending(path: "MoonCodePreview", directoryHint: .isDirectory)
    }

    /// 给一个文件准备落地位置（子目录已建好，文件本身还不存在）。
    static func makeDestination(for path: String) throws -> URL {
        let directory = root.appending(path: UUID().uuidString, directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let name = (path as NSString).lastPathComponent
        return directory.appending(path: name.isEmpty ? "Preview" : name)
    }

    /// 删掉 `makeDestination` 给出的文件连同它的子目录。
    static func remove(_ file: URL) {
        try? FileManager.default.removeItem(at: file.deletingLastPathComponent())
    }

    /// 启动时清掉上次没来得及删的（被杀进程时 `onDisappear` 不会走）。
    static func purge() {
        try? FileManager.default.removeItem(at: root)
    }
}
