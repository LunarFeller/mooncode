import SwiftUI
import ImageIO

/// 从当前会话的媒体接口加载，支持重开会话后的图片预览。
struct RemoteAttachmentImage: View {
    let attachment: AttachmentRef
    let number: Int
    let load: @MainActor (AttachmentRef) async throws -> Data
    @State private var data: Data?
    @State private var thumbnail: UIImage?
    @State private var failed = false
    @State private var attempt = 0
    @State private var showsPreview = false

    var body: some View {
        Button {
            if thumbnail != nil { showsPreview = true }
            else if failed { attempt += 1 }
        } label: {
            ZStack {
                Palette.fill
                if let thumbnail {
                    Image(uiImage: thumbnail).resizable().scaledToFit()
                } else if failed {
                    VStack(spacing: 6) {
                        Image(systemName: "photo.badge.exclamationmark")
                        Text("图片加载失败").font(.caption)
                        Text("点击重试").font(.caption)
                    }
                    .foregroundStyle(.secondary)
                } else {
                    ProgressView().accessibilityLabel("正在加载图片")
                }
            }
            .aspectRatio(1, contentMode: .fit)
            .clipShape(.rect(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(failed ? "重试图片 \(number)" : "预览图片 \(number)")
        .task(id: "\(attachment.id):\(attachment.source?.cacheKey ?? "none"):\(attempt)") {
            failed = false
            data = nil
            thumbnail = nil
            do {
                let bytes = try await load(attachment)
                try Task.checkCancellation()
                guard let image = AttachmentImageThumbnail.make(bytes) else {
                    failed = true
                    return
                }
                data = bytes
                thumbnail = image
            } catch {
                if !Task.isCancelled { failed = true }
            }
        }
        .sheet(isPresented: $showsPreview) {
            if let data { AttachmentImagePreview(data: data) }
        }
    }
}

/// 乐观发送和失败重试也展示图片，而不是只有一个附件数量标签。
struct LocalAttachmentPreviews: View {
    let attachments: [Attachment]
    @State private var selected: Preview?
    private struct Preview: Identifiable { let id: UUID; let data: Data }

    var body: some View {
        let images = attachments.compactMap { attachment -> (UUID, Data, Data)? in
            if case let .image(id, jpeg, thumbnail) = attachment { return (id, jpeg, thumbnail) }
            return nil
        }
        if !images.isEmpty {
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: images.count == 1 ? 1 : 2), spacing: 8) {
                ForEach(Array(images.enumerated()), id: \.element.0) { index, image in
                    Button { selected = Preview(id: image.0, data: image.1) } label: {
                        ZStack {
                            Palette.fill
                            if let thumbnail = UIImage(data: image.2) ?? AttachmentImageThumbnail.make(image.1) {
                                Image(uiImage: thumbnail).resizable().scaledToFit()
                            } else { Image(systemName: "photo").foregroundStyle(.secondary) }
                        }
                        .aspectRatio(1, contentMode: .fit)
                        .clipShape(.rect(cornerRadius: 12))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("预览待发送图片 \(index + 1)")
                }
            }
        }
        ForEach(attachments) { attachment in
            if case let .file(_, name, _, _) = attachment {
                Label(name, systemImage: "doc").font(.subheadline).foregroundStyle(.secondary)
            }
        }
        Color.clear.frame(height: 0)
            .sheet(item: $selected) { AttachmentImagePreview(data: $0.data) }
    }
}

private enum AttachmentImageThumbnail {
    static func make(_ data: Data) -> UIImage? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: 512,
                kCGImageSourceShouldCacheImmediately: true,
              ] as CFDictionary) else { return nil }
        return UIImage(cgImage: image)
    }
}

private struct AttachmentImagePreview: View {
    let data: Data
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if let image = UIImage(data: data) {
                    Image(uiImage: image).resizable().scaledToFit()
                } else { ContentUnavailableView("图片不可预览", systemImage: "photo") }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .padding()
            .navigationTitle("图片")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarTrailing) {
                Button("关闭") { dismiss() }.accessibilityLabel("关闭图片预览")
            } }
        }
    }
}
