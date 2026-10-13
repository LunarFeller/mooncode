import SwiftUI

/// 选择暂存在面板内，只有点完成才写入会话；下滑关闭即放弃修改。
struct ModelSelectionPanel: View {
    let models: [ModelInfo]
    let confirm: (ModelInfo, String?) -> Void
    var onHeight: ((CGFloat) -> Void)?

    @State private var selectedID: String?
    @State private var selectedEffort: String?
    @State private var listHeight: CGFloat = 0

    init(
        models: [ModelInfo],
        config: ComposerConfig,
        confirm: @escaping (ModelInfo, String?) -> Void,
        onHeight: ((CGFloat) -> Void)? = nil
    ) {
        self.models = models
        self.confirm = confirm
        self.onHeight = onHeight
        _selectedID = State(initialValue: config.modelID)
        _selectedEffort = State(initialValue: config.effort)
    }

    private var selectedModel: ModelInfo? {
        models.first { $0.model == selectedID }
    }

    /// 按 provider 分组，组的顺序沿用列表顺序（Kimi 订阅组已排在最前）。
    private var groups: [(label: String, models: [ModelInfo])] {
        var result: [(label: String, models: [ModelInfo])] = []
        for model in models {
            if let index = result.firstIndex(where: { $0.label == model.providerLabel }) {
                result[index].models.append(model)
            } else {
                result.append((model.providerLabel, [model]))
            }
        }
        return result
    }

    /// 模型多了（第三方 provider）列表会很长：超过这个高度就在面板里滚动。
    private static let maxListHeight: CGFloat = 440

    var body: some View {
        VStack(spacing: 20) {
            Text("模型")
                .font(.headline)
                .padding(.top, 28)

            ScrollViewReader { proxy in
                ScrollView {
                    modelList
                        .padding(.horizontal, 24)
                        .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { listHeight = $0 }
                }
                .scrollBounceBehavior(.basedOnSize)
                .frame(height: min(listHeight, Self.maxListHeight))
                .onAppear {
                    guard let selectedID else { return }
                    proxy.scrollTo(selectedID, anchor: .center)
                }
            }

            if let model = selectedModel, model.thinkingOptions.count > 1 {
                thinkingMenu(for: model)
                    .padding(.horizontal, 24)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Button {
                guard let model = selectedModel else { return }
                confirm(model, model.normalizedThinking(selectedEffort))
            } label: {
                Text("完成")
                    .font(.body.weight(.semibold))
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .foregroundStyle(.white)
                    .background(Palette.kimi, in: .capsule)
            }
            .buttonStyle(.plain)
            .opacity(selectedModel == nil ? 0.4 : 1)
            .disabled(selectedModel == nil)
            .padding(.horizontal, 24)
            .padding(.bottom, 16)
        }
        // 面板高度按内容算（交给外面设 detent），不留大片空白。
        .fixedSize(horizontal: false, vertical: true)
        .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { onHeight?($0) }
        .background(Color(.systemBackground))
    }

    @ViewBuilder
    private var modelList: some View {
        if models.isEmpty {
            Text("暂无可用模型")
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity)
        } else {
            let groups = groups
            VStack(alignment: .leading, spacing: 16) {
                ForEach(groups, id: \.label) { group in
                    VStack(alignment: .leading, spacing: 8) {
                        // 只有 Kimi 订阅一组时不显示组名，和以前一样。
                        if groups.count > 1 {
                            Text(group.label)
                                .font(.footnote.weight(.medium))
                                .foregroundStyle(.secondary)
                                .padding(.leading, 20)
                        }
                        VStack(spacing: 0) {
                            ForEach(group.models) { model in
                                if model.id != group.models.first?.id {
                                    Divider().padding(.horizontal, 20)
                                }
                                choiceRow(model.name, selected: selectedID == model.model) {
                                    selectedID = model.model
                                    selectedEffort = model.normalizedThinking(selectedEffort)
                                }
                                .id(model.model)
                            }
                        }
                        .background(Color(.secondarySystemBackground), in: .rect(cornerRadius: 24))
                    }
                }
            }
        }
    }

    /// 固定在模型列表下方，点击整行弹出原生单选菜单。有强度时选强度，没强度时只有开 / 关。
    private func thinkingMenu(for model: ModelInfo) -> some View {
        let title = model.efforts.isEmpty ? "思考" : "思考强度"
        let current = model.normalizedThinking(selectedEffort)
        return Menu {
            Picker(title, selection: Binding(
                get: { current },
                set: { selectedEffort = $0 }
            )) {
                ForEach(model.thinkingOptions, id: \.self) { option in
                    Text(option.thinkingOptionLabel).tag(option)
                }
            }
            .pickerStyle(.inline)
        } label: {
            HStack(spacing: 12) {
                Text(title)
                    .foregroundStyle(.primary)
                Spacer(minLength: 12)
                Text(current.thinkingOptionLabel)
                    .foregroundStyle(.secondary)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
            }
            .font(.body.weight(.medium))
            .padding(.horizontal, 20)
            .frame(minHeight: 52)
            .background(Color(.secondarySystemBackground), in: .capsule)
            .contentShape(.capsule)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
        .accessibilityValue(current.thinkingOptionLabel)
    }

    private func choiceRow(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title)
                    .font(.body.weight(.medium))
                Spacer(minLength: 12)
                Image(systemName: "checkmark")
                    .font(.body.weight(.semibold))
                    .opacity(selected ? 1 : 0)
            }
            .foregroundStyle(.primary)
            .padding(.horizontal, 20)
            .frame(minHeight: 56)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}
