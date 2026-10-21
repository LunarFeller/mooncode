import SwiftUI
import UIKit

// 正文原地选择：长按选中一个词，拖两端手柄自由调整范围。
//
// iOS 上 SwiftUI `Text` 的 `.textSelection(.enabled)` 长按只能拷贝整段，选不了一部分，所以正文改用
// 不可编辑的 UITextView。连续的段落 / 标题 / 列表排进同一个 UITextView，可以跨段连着选；
// 代码块、表格、引用、分隔线各自独立，选区到它们就停（代码块有复制按钮，表格长按拷贝）。

/// 可选中的富文本。内容没变不重排，尺寸按宽度缓存。
struct SelectableText: UIViewRepresentable {
    let content: RichText
    /// 宽度贴着文字（用户气泡）；否则占满给的宽度。
    var hugsWidth = false
    /// 最多显示几行，超出省略；0 = 不限。
    var lineLimit = 0

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> SelectableTextView {
        let view = SelectableTextView(usingTextLayoutManager: true)
        view.isEditable = false
        view.isSelectable = true
        view.isScrollEnabled = false
        view.backgroundColor = .clear
        view.textContainerInset = .zero
        view.textContainer.lineFragmentPadding = 0
        view.dataDetectorTypes = []
        view.linkTextAttributes = [.foregroundColor: Palette.uiKimi]
        view.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)

        // UITextView 会吞掉单击，对话页「点一下收起键盘」在正文上就不灵了，自己补一个。
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.tapped(_:)))
        tap.cancelsTouchesInView = false
        tap.delegate = context.coordinator
        view.addGestureRecognizer(tap)
        return view
    }

    func updateUIView(_ view: SelectableTextView, context: Context) {
        let coordinator = context.coordinator
        let key = Coordinator.Key(content: content, dynamicTypeSize: context.environment.dynamicTypeSize)
        if coordinator.key != key {
            coordinator.key = key
            coordinator.sizes = [:]
            let selection = view.selectedRange
            view.attributedText = content.attributedString()
            // 流式输出只往后追加：正在选的范围还在就留着。
            if selection.length > 0, NSMaxRange(selection) <= view.attributedText.length {
                view.selectedRange = selection
            }
        }
        if view.textContainer.maximumNumberOfLines != lineLimit {
            view.textContainer.maximumNumberOfLines = lineLimit
            view.textContainer.lineBreakMode = lineLimit > 0 ? .byTruncatingTail : .byWordWrapping
            coordinator.sizes = [:]
        }
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView: SelectableTextView, context: Context) -> CGSize? {
        // 没给宽度（问理想尺寸）时按一行排开，和 `Text` 一样。
        let width = proposal.width.flatMap { $0.isFinite && $0 > 0 ? $0 : nil } ?? 10_000
        let hug = hugsWidth || proposal.width == nil
        let key = Coordinator.SizeKey(width: width, hug: hug)
        if let size = context.coordinator.sizes[key] { return size }

        var measureWidth = width
        if hug {
            let used = uiView.attributedText.boundingRect(
                with: CGSize(width: width, height: .greatestFiniteMagnitude),
                options: [.usesLineFragmentOrigin, .usesFontLeading],
                context: nil
            ).width
            // 多留 1pt：TextKit 2 和 boundingRect 的小数差一点就会多折一行。
            measureWidth = min(width, ceil(used) + 1)
        }
        let fitted = uiView.sizeThatFits(CGSize(width: measureWidth, height: .greatestFiniteMagnitude))
        let size = CGSize(width: measureWidth, height: ceil(fitted.height))
        context.coordinator.sizes[key] = size
        return size
    }

    @MainActor
    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        struct Key: Equatable {
            let content: RichText
            let dynamicTypeSize: DynamicTypeSize
        }

        struct SizeKey: Hashable {
            let width: CGFloat
            let hug: Bool
        }

        var key: Key?
        var sizes: [SizeKey: CGSize] = [:]
        /// 按下时有没有选区：有的话这一下是用来取消选择的，不算单击。
        private var hadSelection = false
        private var touchDownAt = Date.distantPast

        @objc func tapped(_ recognizer: UITapGestureRecognizer) {
            // 长按选字抬手时单击识别器也会触发：按得久、或抬手时已经选上了，都不算单击。
            guard !hadSelection, Date.now.timeIntervalSince(touchDownAt) < 0.35,
                  let view = recognizer.view as? UITextView, view.selectedRange.length == 0
            else { return }
            // 点在链接上交给 UITextView 打开。
            let point = recognizer.location(in: view)
            if let position = view.closestPosition(to: point) {
                let offset = view.offset(from: view.beginningOfDocument, to: position)
                if offset < view.attributedText.length,
                   view.attributedText.attribute(.link, at: offset, effectiveRange: nil) != nil {
                    return
                }
            }
            // 和点对话页空白处一样：收起键盘。
            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
            hadSelection = ((gestureRecognizer.view as? UITextView)?.selectedRange.length ?? 0) > 0
            touchDownAt = .now
            return true
        }

        func gestureRecognizer(
            _ gestureRecognizer: UIGestureRecognizer,
            shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
        ) -> Bool {
            true
        }

        /// 等 UITextView 自己的双击（选词）失败了再算单击，免得双击选词时先触发单击。
        func gestureRecognizer(
            _ gestureRecognizer: UIGestureRecognizer,
            shouldRequireFailureOf otherGestureRecognizer: UIGestureRecognizer
        ) -> Bool {
            otherGestureRecognizer.view === gestureRecognizer.view
                && ((otherGestureRecognizer as? UITapGestureRecognizer)?.numberOfTapsRequired ?? 0) > 1
        }
    }
}

final class SelectableTextView: UITextView {
    /// 正在选字的那一个。有选区时侧栏的横滑手势让路，不抢拖手柄的手指（见 `MainView`）。
    private(set) static weak var selecting: SelectableTextView?

    static var isSelecting: Bool {
        guard let view = selecting else { return false }
        return view.isFirstResponder && view.selectedRange.length > 0
    }

    override func becomeFirstResponder() -> Bool {
        let became = super.becomeFirstResponder()
        if became { Self.selecting = self }
        return became
    }

    /// 不在选的时候（不是第一响应者）把选区清掉：选完点别处，高亮跟着消失。
    override func resignFirstResponder() -> Bool {
        let resigned = super.resignFirstResponder()
        if resigned {
            if selectedRange.length > 0 { selectedRange = NSRange(location: 0, length: 0) }
            if Self.selecting === self { Self.selecting = nil }
        }
        return resigned
    }
}

/// 长按弹系统的编辑菜单（和选中文字时那条小菜单一样），只有「拷贝」。给不进连续选区的整块内容用（表格）。
///
/// 不用 `.contextMenu`：iOS 26 的上下文菜单只有一项时是一大条，还要把整块抬起来，太重了。
struct CopyMenuGesture: UIGestureRecognizerRepresentable {
    let text: @MainActor () -> String
    var onMenuShown: @MainActor (Bool) -> Void = { _ in }

    func makeCoordinator(converter: CoordinateSpaceConverter) -> Coordinator { Coordinator() }

    func makeUIGestureRecognizer(context: Context) -> UILongPressGestureRecognizer {
        let recognizer = UILongPressGestureRecognizer()
        recognizer.minimumPressDuration = 0.4
        return recognizer
    }

    func handleUIGestureRecognizerAction(_ recognizer: UILongPressGestureRecognizer, context: Context) {
        guard recognizer.state == .began, let view = recognizer.view else { return }
        let coordinator = context.coordinator
        coordinator.text = text
        coordinator.onMenuShown = onMenuShown
        coordinator.present(in: view, at: recognizer.location(in: view))
    }

    @MainActor
    final class Coordinator: NSObject, @preconcurrency UIEditMenuInteractionDelegate {
        var text: @MainActor () -> String = { "" }
        var onMenuShown: @MainActor (Bool) -> Void = { _ in }
        private lazy var interaction = UIEditMenuInteraction(delegate: self)

        func present(in view: UIView, at point: CGPoint) {
            // 手势挂在 SwiftUI 的宿主视图上，菜单也挂过去，弹出位置就是手指按的地方。
            if interaction.view !== view {
                interaction.view?.removeInteraction(interaction)
                view.addInteraction(interaction)
            }
            let configuration = UIEditMenuConfiguration(identifier: nil, sourcePoint: point)
            // 默认会落到手指下面；和选中文字一样放上面，放不下系统会自己挪。
            configuration.preferredArrowDirection = .down
            interaction.presentEditMenu(with: configuration)
        }

        func editMenuInteraction(
            _ interaction: UIEditMenuInteraction,
            menuFor configuration: UIEditMenuConfiguration,
            suggestedActions: [UIMenuElement]
        ) -> UIMenu? {
            UIMenu(children: [
                UIAction(title: "拷贝") { [weak self] _ in
                    guard let self else { return }
                    UIPasteboard.general.string = self.text()
                },
            ])
        }

        /// 让菜单避开手指那一块，停在上方（只给一个点的话会盖在手指和字上）。
        func editMenuInteraction(
            _ interaction: UIEditMenuInteraction,
            targetRectFor configuration: UIEditMenuConfiguration
        ) -> CGRect {
            CGRect(x: configuration.sourcePoint.x - 1, y: configuration.sourcePoint.y - 24, width: 2, height: 48)
        }

        func editMenuInteraction(
            _ interaction: UIEditMenuInteraction,
            willPresentMenuFor configuration: UIEditMenuConfiguration,
            animator: any UIEditMenuInteractionAnimating
        ) {
            onMenuShown(true)
        }

        func editMenuInteraction(
            _ interaction: UIEditMenuInteraction,
            willDismissMenuFor configuration: UIEditMenuConfiguration,
            animator: any UIEditMenuInteractionAnimating
        ) {
            onMenuShown(false)
        }
    }
}

// MARK: - 富文本

/// 交给 `SelectableText` 排的内容。Equatable：内容不变就不重排。
enum RichText: Equatable {
    /// 连续的 Markdown 块（段落 / 标题 / 列表）。
    case markdown([MarkdownBlock], tone: TextTone)
    case plain(String, tone: TextTone, lineSpacing: CGFloat)

    func attributedString() -> NSAttributedString {
        switch self {
        case let .markdown(blocks, tone):
            let result = NSMutableAttributedString()
            for block in blocks {
                guard let segment = Self.markdown(block, tone: tone) else { continue }
                if result.length > 0 {
                    // 换行符跟着上一块的样式，段间距才算在上一块上。
                    let attributes = result.attributes(at: result.length - 1, effectiveRange: nil)
                    result.append(NSAttributedString(string: "\n", attributes: attributes))
                }
                result.append(segment)
            }
            Self.trimTrailingSpacing(result)
            return result
        case let .plain(text, tone, lineSpacing):
            let result = NSMutableAttributedString(
                string: text,
                attributes: [.font: tone.font, .foregroundColor: tone.color]
            )
            Self.applyParagraphs(result, lineSpacing: lineSpacing, spacingAfter: 0)
            return result
        }
    }

    /// 和 `MarkdownText` 里各块的 SwiftUI 样式对应：字号、行距、块间距 8。
    private static func markdown(_ block: MarkdownBlock, tone: TextTone) -> NSAttributedString? {
        let body = tone.font
        switch block {
        case let .paragraph(text):
            let result = inline(text, font: body, color: tone.color)
            applyParagraphs(result, lineSpacing: 4, spacingAfter: 8)
            return result
        case let .heading(level, text):
            let font = level <= 1 ? semibold(.title3) : level == 2 ? .preferredFont(forTextStyle: .headline) : semibold(.subheadline)
            let result = inline(text, font: font, color: tone.color)
            applyParagraphs(result, lineSpacing: 0, spacingBefore: 4, spacingAfter: 8)
            return result
        case let .list(items, ordered):
            let result = NSMutableAttributedString()
            let widest = ordered ? "\(items.count)." : "•"
            let markerWidth = ceil((widest as NSString).size(withAttributes: [.font: body]).width) + 6
            for (index, item) in items.enumerated() {
                let line = NSMutableAttributedString(
                    string: (ordered ? "\(index + 1)." : "•") + "\t",
                    attributes: [.font: body, .foregroundColor: UIColor.secondaryLabel]
                )
                line.append(inline(item.text, font: body, color: tone.color))
                let indent = CGFloat(item.indent) * 16
                applyParagraphs(
                    line, lineSpacing: 4,
                    spacingAfter: index == items.count - 1 ? 8 : 4,
                    firstLineIndent: indent, headIndent: indent + markerWidth
                )
                if index < items.count - 1 {
                    line.append(NSAttributedString(string: "\n", attributes: line.attributes(at: line.length - 1, effectiveRange: nil)))
                }
                result.append(line)
            }
            return result
        case .quote, .code, .table, .rule:
            // 这几种在 `MarkdownText` 里单独排，不进连续的选区。
            return nil
        }
    }

    /// 行内 Markdown（粗体 / 斜体 / 行内代码 / 删除线 / 链接），对应 `MarkdownText.inline`。
    private static func inline(_ text: String, font: UIFont, color: UIColor) -> NSMutableAttributedString {
        let parsed = (try? AttributedString(
            markdown: text,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace, failurePolicy: .returnPartiallyParsedIfPossible)
        )) ?? AttributedString(text)
        let code = UIFont.monospacedSystemFont(ofSize: UIFont.preferredFont(forTextStyle: .callout).pointSize, weight: .regular)
        let result = NSMutableAttributedString()
        for run in parsed.runs {
            let intent = run.inlinePresentationIntent ?? []
            var attributes: [NSAttributedString.Key: Any] = [.font: font, .foregroundColor: color]
            if intent.contains(.code) {
                attributes[.font] = code
                attributes[.foregroundColor] = Palette.uiKimi
                attributes[.backgroundColor] = Palette.uiFill
            } else {
                var traits: UIFontDescriptor.SymbolicTraits = []
                if intent.contains(.stronglyEmphasized) { traits.insert(.traitBold) }
                if intent.contains(.emphasized) { traits.insert(.traitItalic) }
                if !traits.isEmpty,
                   let descriptor = font.fontDescriptor.withSymbolicTraits(font.fontDescriptor.symbolicTraits.union(traits)) {
                    attributes[.font] = UIFont(descriptor: descriptor, size: 0)
                }
            }
            if intent.contains(.strikethrough) {
                attributes[.strikethroughStyle] = NSUnderlineStyle.single.rawValue
            }
            if let link = run.link {
                attributes[.link] = link
            }
            result.append(NSAttributedString(string: String(parsed[run.range].characters), attributes: attributes))
        }
        return result
    }

    private static func semibold(_ style: UIFont.TextStyle) -> UIFont {
        .systemFont(ofSize: UIFont.preferredFont(forTextStyle: style).pointSize, weight: .semibold)
    }

    /// 按段落设样式：段前 / 段后距只加在这一块的第一段 / 最后一段，块内的换行只有行距。
    private static func applyParagraphs(
        _ text: NSMutableAttributedString,
        lineSpacing: CGFloat,
        spacingBefore: CGFloat = 0,
        spacingAfter: CGFloat,
        firstLineIndent: CGFloat = 0,
        headIndent: CGFloat = 0
    ) {
        let ranges = paragraphRanges(text)
        for (index, range) in ranges.enumerated() {
            let style = NSMutableParagraphStyle()
            style.lineSpacing = lineSpacing
            style.paragraphSpacingBefore = index == 0 ? spacingBefore : 0
            style.paragraphSpacing = index == ranges.count - 1 ? spacingAfter : 0
            style.firstLineHeadIndent = index == 0 ? firstLineIndent : headIndent
            style.headIndent = headIndent
            if headIndent > firstLineIndent {
                style.tabStops = [NSTextTab(textAlignment: .natural, location: headIndent)]
                style.defaultTabInterval = headIndent
            }
            text.addAttribute(.paragraphStyle, value: style, range: range)
        }
    }

    /// 最后一段不要段后距，否则底下多出一截空白。
    private static func trimTrailingSpacing(_ text: NSMutableAttributedString) {
        guard let last = paragraphRanges(text).last,
              let style = text.attribute(.paragraphStyle, at: last.location, effectiveRange: nil) as? NSParagraphStyle,
              let trimmed = style.mutableCopy() as? NSMutableParagraphStyle
        else { return }
        trimmed.paragraphSpacing = 0
        text.addAttribute(.paragraphStyle, value: trimmed, range: last)
    }

    private static func paragraphRanges(_ text: NSAttributedString) -> [NSRange] {
        let string = text.string as NSString
        var ranges: [NSRange] = []
        string.enumerateSubstrings(
            in: NSRange(location: 0, length: string.length),
            options: [.byParagraphs, .substringNotRequired]
        ) { _, _, enclosing, _ in
            ranges.append(enclosing)
        }
        return ranges
    }
}

/// 基础字号 + 颜色（对应 SwiftUI 的 `.font` / `.foregroundStyle`，UIKit 里读不到环境，得显式给）。
struct TextTone: Equatable {
    var textStyle: UIFont.TextStyle = .body
    var secondary = false

    static let body = TextTone()

    var font: UIFont { .preferredFont(forTextStyle: textStyle) }
    var color: UIColor { secondary ? .secondaryLabel : .label }
}
