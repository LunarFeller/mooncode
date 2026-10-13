#!/usr/bin/env python3
"""App Store「搜索结果」素材（横版 3840×2560）：左边字标 + 一句话，右边三台手机。

用法：python3 scripts/make_search_banner.py <原始截图目录> [输出目录]
原始截图目录与 make_screenshots.py 相同（用其中 iphone/ 下的 chat / devices / usage）。
默认输出到 marketing/search/。

版式：与宣传截图同一套淡 Kimi 蓝纯色底。左侧白色 bot + 「Moon Code」+ 中文一句话 + `kimi rc` 胶囊；
右侧三台手机，中间那台在前、两侧稍小靠后，底部出血。搜索结果卡片底部会叠 App 名和按钮，
文字都放在上方 3/4 里。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_screenshots import KIMI, PINGFANG, framed  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SF = "/System/Library/Fonts/SFNS.ttf"
SF_MONO = "/System/Library/Fonts/SFNSMono.ttf"
PF_MEDIUM = 7  # PingFang SC Medium

SIZE = (3840, 2560)
WHITE = (255, 255, 255)
# 字标里 bot 的眼睛、胶囊文字用的深一点的蓝（与底色同色系）
INK = (23, 131, 255)


def sf(size, weight):
    f = ImageFont.truetype(SF, size)
    f.set_variation_by_axes([100, 96, 400, weight])
    return f


def bot(unit):
    """KimiFace 的几何（24×16 单位、眼睛 3×4.5、间距 6、偏移 (2.7, -2.8)），白底蓝眼。"""
    ss = 4
    u = unit * ss
    w, h = round(24 * u), round(16 * u)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), round(2.3 * u), fill=WHITE)
    cx, cy = w / 2 + 2.7 * u, h / 2 - 2.8 * u
    for side in (-1, 1):
        ex = cx + 4.5 * u * side
        d.rectangle((ex - 1.5 * u, cy - 2.25 * u, ex + 1.5 * u, cy + 2.25 * u), fill=INK)
    return img.resize((w // ss, h // ss), Image.LANCZOS)


def shadow_for(canvas_size, box, radius, offset, blur, alpha):
    layer = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rounded_rectangle((x0, y0 + offset, x1, y1 + offset), radius, fill=(0, 30, 90, alpha))
    return layer.filter(ImageFilter.GaussianBlur(blur))


def place_phone(canvas, shot, cx, top, screen_w, alpha):
    device = framed(shot, screen_w, corner=168, bezel=round(screen_w * 0.028))
    x = round(cx - device.width / 2)
    canvas.alpha_composite(
        shadow_for(canvas.size, (x, top, x + device.width, top + device.height), 160, 40, 70, alpha)
    )
    canvas.alpha_composite(device, (x, top))


def main():
    raw = Path(sys.argv[1]) / "iphone"
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "marketing/search"
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = SIZE
    canvas = Image.new("RGBA", SIZE, KIMI + (255,))

    # 右侧三台手机：两侧先画（稍小、靠下），中间在前
    place_phone(canvas, Image.open(raw / "devices.png"), cx=2160, top=760, screen_w=820, alpha=90)
    place_phone(canvas, Image.open(raw / "usage.png"), cx=3390, top=760, screen_w=820, alpha=90)
    place_phone(canvas, Image.open(raw / "chat.png"), cx=2775, top=430, screen_w=980, alpha=130)

    # 左侧文字块：bot → 字标 → 一句话 → kimi rc 胶囊，整体在上 3/4 里垂直居中
    draw = ImageDraw.Draw(canvas)
    left = 280
    mark = bot(unit=10)
    word = sf(220, 760)
    tagline = ImageFont.truetype(PINGFANG, 92, index=PF_MEDIUM)
    mono = ImageFont.truetype(SF_MONO, 76)
    mono.set_variation_by_axes([500])

    gap1, gap2, gap3 = 90, 70, 110
    word_h = word.getbbox("Moon Code", anchor="ls")
    pill_h = 150
    block = mark.height + gap1 + (word_h[3] - word_h[1]) + gap2 + 92 + gap3 + pill_h
    y = round((h * 0.78 - block) / 2)

    canvas.alpha_composite(mark, (left, y))
    y += mark.height + gap1 - word_h[1]
    draw.text((left - 8, y), "Moon Code", font=word, fill=WHITE, anchor="ls")
    y += word_h[3] + gap2
    draw.text((left, y), "KimiCode 的远程控制客户端", font=tagline, fill=WHITE, anchor="lt")
    y += 92 + gap3

    label = "$ kimi rc"
    tw = draw.textlength(label, font=mono)
    # 半透明白胶囊要单独一层再叠上去（直接在画布上画，alpha 会把底色替换掉而不是混合）
    layer = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((left, y, left + tw + 110, y + pill_h), pill_h / 2, fill=(255, 255, 255, 56))
    canvas.alpha_composite(layer)
    ImageDraw.Draw(canvas).text((left + 55, y + pill_h / 2), label, font=mono, fill=WHITE, anchor="lm")

    out = out_dir / f"search-{w}x{h}.png"
    canvas.convert("RGB").save(out, optimize=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
