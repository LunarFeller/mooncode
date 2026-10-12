import SwiftUI

/// 彩条喷射：从屏幕左下、右下两个角往斜上方喷出彩色纸条，减速、翻飞、飘落、淡出。
/// 一次性的：出现即开始，`duration` 之后画面上就空了（由调用方移除）。
struct ConfettiBurst: View {
    static let duration: TimeInterval = 4

    /// 粒子只在第一次出现时生成；父视图每次重绘都不会重新随机。
    @State private var pieces = Piece.burst()
    @State private var clock = Clock()

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let t = clock.elapsed(at: timeline.date)
                guard t < Self.duration else { return }
                for piece in pieces {
                    piece.draw(in: &context, size: size, t: t)
                }
            }
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

/// 从第一次真正画出来的那一帧开始计时：视图创建到首帧之间若有卡顿，彩条也是从喷口喷出来，而不是凭空出现在半空。
private final class Clock {
    private var start: Date?

    func elapsed(at date: Date) -> TimeInterval {
        if start == nil { start = date }
        return date.timeIntervalSince(start!)
    }
}

private struct Piece {
    /// 喷口：0 = 左下角，1 = 右下角
    let side: CGFloat
    let vx: CGFloat
    let vy: CGFloat
    let width: CGFloat
    let height: CGFloat
    let color: Color
    let spin: Double
    let rotation: Double
    let flip: Double
    let wobble: Double
    let phase: Double
    let delay: Double

    private static let palette: [Color] = [Palette.kimi, .yellow, .pink, .green, .purple, .orange, .cyan]
    /// 空气阻力（1/s）与重力（pt/s²）：终速 g/k ≈ 300pt/s，纸条慢慢飘落而不是砸下去。
    private static let drag: Double = 3
    private static let gravity: Double = 900

    static func burst() -> [Piece] {
        (0..<64).map { i in
            let side: CGFloat = i % 2 == 0 ? 0 : 1
            // 与竖直方向夹 6°–42°，朝屏幕中间喷；初速最高能冲到屏幕顶上（升高 ≈ 初速 / 阻力）
            let angle = Double.random(in: 6...42) * .pi / 180
            let speed = Double.random(in: 2400...3400)
            let inward: Double = side == 0 ? 1 : -1
            return Piece(
                side: side,
                vx: inward * sin(angle) * speed,
                vy: -cos(angle) * speed,
                width: .random(in: 9...13),
                height: .random(in: 20...30),
                color: palette.randomElement()!,
                spin: .random(in: -9...9),
                rotation: .random(in: 0...(2 * .pi)),
                flip: .random(in: 6...14),
                wobble: .random(in: 6...16),
                phase: .random(in: 0...(2 * .pi)),
                delay: .random(in: 0...0.12)
            )
        }
    }

    func draw(in context: inout GraphicsContext, size: CGSize, t: Double) {
        let t = t - delay
        guard t > 0 else { return }
        let k = Self.drag
        let decay = (1 - exp(-k * t)) / k
        let x = side * size.width + vx * decay + sin(t * 4 + phase) * wobble * min(t, 1)
        let y = size.height + vy * decay + Self.gravity / k * (t - decay)
        let fade = min(1, max(0, (ConfettiBurst.duration - delay - t) / 0.6))
        guard fade > 0 else { return }

        var ctx = context
        ctx.opacity = fade
        ctx.translateBy(x: x, y: y)
        ctx.rotate(by: .radians(rotation + spin * t))
        // 绕自身长轴翻转：横向缩放随时间正余弦变化，看起来像纸条在翻面
        ctx.scaleBy(x: max(0.08, abs(cos(flip * t + phase))), y: 1)
        ctx.fill(Path(CGRect(x: -width / 2, y: -height / 2, width: width, height: height)), with: .color(color))
    }
}
