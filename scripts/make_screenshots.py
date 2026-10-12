#!/usr/bin/env python3
"""App Store 宣传图：把模拟器原始截图套上设备边框，配蓝底大标题。

用法：python3 scripts/make_screenshots.py <原始截图目录> <输出目录>
原始截图用体验模式在模拟器里拍（xcrun simctl io <udid> screenshot xxx.png），文件名见下方 SHOTS。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PINGFANG = (
    "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/"
    "3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc"
)
SC_SEMIBOLD, SC_REGULAR = 11, 3

KIMI_TOP = (40, 146, 255)
KIMI_BOTTOM = (10, 92, 230)

# (原始截图文件名, 主标题, 副标题)
SHOTS = {
    "iphone": [
        ("chat.png", "随时随地 指挥 Agent", "思考、工具调用、执行结果实时同步"),
        ("devices.png", "多台电脑 一手掌握", "侧栏切换设备，项目与会话井井有条"),
        ("model.png", "多款模型 随心切换", "K3 等 Kimi 官方模型，思考强度按需选"),
        ("usage.png", "上下文与用量 一目了然", "剩余额度随时查看，心里有数"),
        ("welcome.png", "一行 kimi rc 即可接入", "登录 Kimi 账号，选台电脑就开工"),
    ],
}
SHOTS["ipad"] = SHOTS["iphone"]

# 画布尺寸（App Store Connect 要求）、设备屏幕在画布里的宽度、屏幕圆角（按原始截图像素）、标题字号
DEVICES = {
    "iphone": dict(canvas=(1284, 2778), screen_w=940, corner=168, bezel=26, title=107, sub=51),
    "ipad": dict(canvas=(2064, 2752), screen_w=1500, corner=72, bezel=40, title=132, sub=64),
}


def font(size, index):
    return ImageFont.truetype(PINGFANG, size, index=index)


def gradient(size):
    w, h = size
    top, bottom = KIMI_TOP, KIMI_BOTTOM
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / (h - 1)
        col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    bg = col.resize((w, h))
    # 顶部一团柔光，别让大色块太平
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse((-w * 0.3, -h * 0.25, w * 1.3, h * 0.35), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.15))
    bg.paste(Image.new("RGB", (w, h), (255, 255, 255)), (0, 0), glow)
    return bg


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


def framed(shot, screen_w, corner, bezel):
    scale = screen_w / shot.width
    screen = shot.convert("RGB").resize((screen_w, round(shot.height * scale)), Image.LANCZOS)
    r = round(corner * scale)
    w, h = screen.width + bezel * 2, screen.height + bezel * 2
    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle((0, 0, w - 1, h - 1), r + bezel, fill=(18, 18, 20, 255))
    # 边框外沿一圈细高光，像金属中框
    ImageDraw.Draw(frame).rounded_rectangle(
        (1, 1, w - 2, h - 2), r + bezel - 1, outline=(90, 90, 96, 255), width=3
    )
    frame.paste(screen, (bezel, bezel), rounded_mask(screen.size, r))
    return frame


def compose(kind, raw_dir, out_dir):
    spec = DEVICES[kind]
    cw, ch = spec["canvas"]
    title_font = font(spec["title"], SC_SEMIBOLD)
    sub_font = font(spec["sub"], SC_REGULAR)
    for i, (name, title, subtitle) in enumerate(SHOTS[kind], 1):
        canvas = gradient((cw, ch)).convert("RGBA")
        draw = ImageDraw.Draw(canvas)
        title_y = round(ch * 0.075)
        draw.text((cw / 2, title_y), title, font=title_font, fill="white", anchor="mt")
        sub_y = title_y + title_font.size + round(ch * 0.018)
        draw.text((cw / 2, sub_y), subtitle, font=sub_font, fill=(255, 255, 255, 215), anchor="mt")

        device = framed(Image.open(raw_dir / name), spec["screen_w"], spec["corner"], spec["bezel"])
        x = (cw - device.width) // 2
        y = sub_y + sub_font.size + round(ch * 0.04)
        # 阴影
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (x, y + 30, x + device.width, y + device.height + 30), 180, fill=(0, 30, 90, 110)
        )
        canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(50)))
        canvas.alpha_composite(device, (x, y))

        out = out_dir / f"{kind}-{i}.png"
        canvas.convert("RGB").save(out)
        print(out, canvas.size, "device bottom", y + device.height)


def main():
    raw_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind in DEVICES:
        if (raw_dir / kind).is_dir():
            compose(kind, raw_dir / kind, out_dir)


if __name__ == "__main__":
    main()
