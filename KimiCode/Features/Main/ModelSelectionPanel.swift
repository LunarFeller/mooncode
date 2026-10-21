import SwiftUI

/// 点模型或思考强度立刻写入会话（自动保存），左上角 ✕ 或下滑关闭；右上角 ⚙︎ 管理模型供应商。
struct ModelSelectionPanel: View {
    let models: [ModelInfo]
    let apply: (ModelInfo, String?) -> Void
    var onHeight: ((CGFloat) -> Void)?
    /// 有它才显示 ⚙︎：读写电脑上的供应商配置。
    var client: (any KapServicing)?
    /// 供应商改完后重拉模型列表。
    var onProvidersChanged: () async -> Void = {}

    @Environment(\.dismiss) private var dismiss
    @State private var showsSettings = false

    @State private var selectedID: String?
    @State private var selectedEffort: String?
    @State private var listHeight: CGFloat = 0

    init(
        models: [ModelInfo],
        config: ComposerConfig,
        apply: @escaping (ModelInfo, String?) -> Void,
        onHeight: ((CGFloat) -> Void)? = nil,
        client: (any KapServicing)? = nil,
        onProvidersChanged: @escaping () async -> Void = {}
    ) {
        self.models = models
        self.apply = apply
        self.onHeight = onHeight
        self.client = client
        self.onProvidersChanged = onProvidersChanged
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
            ZStack {
                Text("模型")
                    .font(.headline)
                HStack {
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark")
                            .font(.body.weight(.medium))
                            .frame(width: 32, height: 32)
                    }
                    .buttonStyle(.glass)
                    .buttonBorderShape(.circle)
                    .accessibilityLabel("关闭")
                    Spacer()
                    if client != nil {
                        Button(action: { showsSettings = true }) {
                            Image(systemName: "gearshape")
                                .font(.body.weight(.medium))
                                .frame(width: 32, height: 32)
                        }
                        .buttonStyle(.glass)
                        .buttonBorderShape(.circle)
                        .accessibilityLabel("管理模型供应商")
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 20)

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

        }
        .padding(.bottom, 28)
        // 面板高度按内容算（交给外面设 detent），不留大片空白。
        .fixedSize(horizontal: false, vertical: true)
        .onGeometryChange(for: CGFloat.self) { $0.size.height } action: { onHeight?($0) }
        .background(Color(.systemGroupedBackground))
        .sheet(isPresented: $showsSettings) {
            if let client {
                ProviderSettingsSheet(client: client, onChange: onProvidersChanged)
                    .presentationDetents([.large])
            }
        }
    }

    /// 自动保存：每次改动直接写入会话。
    private func applySelection() {
        guard let model = selectedModel else { return }
        apply(model, model.normalizedThinking(selectedEffort))
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
                                    guard selectedID != model.model else { return }
                                    selectedID = model.model
                                    selectedEffort = model.normalizedThinking(selectedEffort)
                                    applySelection()
                                }
                                .id(model.model)
                            }
                        }
                        .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: 24))
                    }
                }
            }
        }
    }

    /// 固定在模型列表下方的分段控件，从左到右低 → 高，点一下即生效。
    /// 不用弹出菜单：iOS 26 的菜单会从整行胶囊「变形」出来、盖住模型列表，观感很怪。
    private func thinkingMenu(for model: ModelInfo) -> some View {
        let title = model.efforts.isEmpty ? "思考" : "思考强度"
        let current = model.normalizedThinking(selectedEffort)
        return VStack(alignment: .leading, spacing: 12) {
            Text(title)
                .font(.body.weight(.medium))
            Picker(title, selection: Binding(
                get: { current },
                set: {
                    selectedEffort = $0
                    applySelection()
                }
            )) {
                ForEach(model.thinkingOptions, id: \.self) { option in
                    Text(option.thinkingOptionLabel).tag(option)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 16)
        .background(Color(.secondarySystemGroupedBackground), in: .rect(cornerRadius: 24))
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
