import Foundation

// 这个独立命令行检查只运行体验模式。替代依赖 UIKit 的 AuthStore，绝不登录或访问真实设备。
// 编译时不包含 Core/AuthStore.swift；App 的实际 OAuth 流程不在这个检查的覆盖范围内。
@MainActor
final class AuthStore {
    var isSignedIn: Bool { false }
    var bearerToken: String? { nil }
    @discardableResult
    func refreshIfNeeded() async -> Bool { false }
    func signOut() {}
}

@main
struct ModelSelectionChecks {
    @MainActor
    static func main() async throws {
        let models = try JSONDecoder().decode(ModelList.self, from: Data("""
            {"items":[
              {"provider":"managed:kimi-code","model":"kimi-code/k3","display_name":"K3",
               "max_context_size":262144,"capabilities":["image_in"],
               "support_efforts":["low","high","max"],"default_effort":"low"},
              {"provider":"deepseek","model":"deepseek/flash","display_name":"DeepSeek Flash",
               "max_context_size":100000,"support_efforts":["off","high"],"default_effort":"high"},
              {"provider":"zhipuai","model":"zhipuai/glm","display_name":"GLM",
               "max_context_size":100000,"capabilities":["image_in"]},
              {"provider":"managed:kimi-code","model":"kimi-code/other","display_name":"Other",
               "max_context_size":100000},
              {"provider":"custom","model":"custom/plain","display_name":"GLM",
               "max_context_size":32000,"support_efforts":["off","low"],"default_effort":"invalid"}
            ]}
            """.utf8)).items
        let catalog = ModelCatalog(models: models)
        precondition(catalog.groups.map(\.id) == ["managed:kimi-code", "deepseek", "zhipuai", "custom"])
        precondition(catalog.groups[0].models.map(\.model) == ["kimi-code/k3", "kimi-code/other"])
        precondition(catalog.groups[0].name == "Kimi 订阅")
        precondition(catalog.groups(matching: "  DEEPSEEK  ", providerID: nil).flatMap(\.models).count == 1)
        precondition(catalog.groups(matching: "Kimi 订阅", providerID: nil).flatMap(\.models).count == 2)
        precondition(catalog.groups(matching: "glm", providerID: nil).map(\.id) == ["zhipuai", "custom"])
        precondition(catalog.groups(matching: "glm", providerID: "zhipuai").flatMap(\.models).count == 1)
        precondition(catalog.groups(matching: "missing", providerID: nil).isEmpty)
        precondition(catalog.groups(matching: "", providerID: "removed").isEmpty)
        precondition(ModelCatalog(models: []).groups.isEmpty)

        let reasoner = models[1]
        let plain = models[2]
        precondition(reasoner.resolvedEffort("off") == "off")
        precondition(reasoner.resolvedEffort("max") == "high")
        precondition(plain.resolvedEffort("high") == nil)
        precondition(models[4].resolvedEffort(nil) == "off")
        precondition(!reasoner.acceptsImages && plain.acceptsImages)

        let remembered = ComposerConfig(permission: .manual, modelID: reasoner.model, effort: "off")
        let restored = try JSONDecoder().decode(ComposerConfig.self, from: JSONEncoder().encode(remembered))
        precondition(ComposerConfig.initial(models: models, defaultModelID: models[0].model, remembered: restored) == remembered)
        let serverDefault = ComposerConfig.initial(models: models, defaultModelID: reasoner.model, remembered: nil)
        precondition(serverDefault.modelID == reasoner.model && serverDefault.effort == "high")
        let stale = ComposerConfig(permission: .manual, modelID: "removed/model", effort: "max")
        precondition(ComposerConfig.initial(models: models, defaultModelID: reasoner.model, remembered: stale) == serverDefault)
        let corrected = ComposerConfig.initial(
            models: models, defaultModelID: nil,
            remembered: .init(permission: .yolo, modelID: plain.model, effort: "high")
        )
        precondition(corrected.modelID == plain.model && corrected.effort == nil && corrected.permission == .yolo)
        precondition(ComposerConfig.initial(models: [reasoner], defaultModelID: "missing", remembered: nil).modelID == reasoner.model)
        precondition(ComposerConfig.initial(models: [], defaultModelID: reasoner.model, remembered: nil).modelID == nil)

        let prompt = PromptBody.make(text: "hello", images: [], files: [], config: remembered.patch)
        let wire = try JSONDecoder().decode(JSONValue.self, from: JSONEncoder().encode(prompt))
        precondition(wire["model"]?.stringValue == "deepseek/flash" && wire["thinking"]?.stringValue == "off")
        let plainPrompt = PromptBody.make(text: "hello", images: [], files: [], config: corrected.patch)
        let plainWire = try JSONDecoder().decode(JSONValue.self, from: JSONEncoder().encode(plainPrompt))
        precondition(plainWire["model"]?.stringValue == "zhipuai/glm" && plainWire["thinking"] == nil)

        // 运行实际 AppModel / ChatModel，检查目录没有再被过滤，以及选择、建会话和发任务的连接。
        let keys = ["kimi.composerConfig", "kimi.lastDeviceID"]
        let previous = keys.map { ($0, UserDefaults.standard.object(forKey: $0)) }
        for key in keys { UserDefaults.standard.removeObject(forKey: key) }
        defer {
            for (key, value) in previous {
                if let value { UserDefaults.standard.set(value, forKey: key) }
                else { UserDefaults.standard.removeObject(forKey: key) }
            }
        }
        let app = AppModel()
        app.startDemo()
        await app.bootstrap()
        defer { app.signOut() }
        precondition(app.models.contains { $0.provider == "demo-provider" }, "AppModel must retain third-party models")
        await app.refreshModels()
        precondition(ModelCatalog(models: app.models).groups.count == 2)
        let demoReasoner = app.models.first { $0.model == "demo-provider/reasoner" }!
        let demoPlain = app.models.first { $0.model == "demo-provider/chat" }!
        let workspace = app.workspaces.first!
        let draft = app.chat!
        await draft.setModel(demoReasoner, effort: "max")
        precondition(draft.config.effort == "high")
        app.newChat(in: workspace)
        let chat = app.chat!
        precondition(chat.config.modelID == demoReasoner.model, "A new chat must retain a third-party selection")
        await chat.send("model selection check")
        let sessionID = chat.sessionID!
        let status = try await app.client!.status(sessionID)
        precondition(status.model == demoReasoner.model && status.thinkingLevel == "high")
        await chat.abort()
        await chat.reload()
        await chat.setModel(demoPlain, effort: "high")
        precondition(chat.config.modelID == demoPlain.model && chat.config.effort == nil,
                     "Status from the previous model must not restore an unsupported thinking effort")
        await chat.send("plain model check")
        await chat.reload()
        let plainStatus = try await app.client!.status(sessionID)
        precondition(plainStatus.model == demoPlain.model && chat.config.effort == nil)
        await chat.abort()
        let previousConfig = chat.config
        let previousPreference = UserDefaults.standard.data(forKey: "kimi.composerConfig")
        try await app.client!.deleteSession(sessionID)
        await chat.setModel(demoReasoner, effort: "high")
        precondition(chat.errorMessage != nil && chat.config == previousConfig)
        precondition(UserDefaults.standard.data(forKey: "kimi.composerConfig") == previousPreference,
                     "A rejected model switch must not overwrite the remembered selection")
        app.newChat(in: workspace)
        let imageDraft = app.chat!
        imageDraft.attachments = [.image(jpeg: Data(), thumbnail: Data())]
        await imageDraft.setModel(demoReasoner, effort: "high")
        await imageDraft.send("keep my image")
        precondition(imageDraft.isDraft && imageDraft.optimisticPrompts.isEmpty)
        precondition(imageDraft.attachments.count == 1 && imageDraft.restoredDraft == "keep my image")
        precondition(imageDraft.errorMessage?.contains("不支持图片") == true)
        print("PASS: all providers, grouping/search, defaults/preferences, thinking capabilities, prompt encoding, demo sessions, failed-switch rollback and image validation")
    }
}
