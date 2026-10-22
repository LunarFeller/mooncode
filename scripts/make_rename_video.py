#!/usr/bin/env python3
"""改名宣传短片：Kimi Code Mobile → Moon Code。白底，竖版 1080×1920 + 横版 1920×1080，60fps，无声。

用法：python3 scripts/make_rename_video.py <原始截图目录> [输出目录] [--fps 60]
原始截图目录与 make_screenshots.py 相同（用 iphone/ 下的 chat / devices / model）。默认输出到 marketing/video/。

分镜（秒，开场之后的时间都整体后移 OPEN - 0.5）：
  0.0–1.35 开场：整屏 Kimi 蓝 + 两只大白眼（App 自己的开场动效）弹出、眨眼，再平滑收缩成旧字标上方的
           小 bot（与 App 的 SplashFace → KimiFace 一样严丝合缝），之后一直在、隔一会儿眨眼
  0.5      旧字标「Kimi Code Mobile」
  0.6–0.85 bot 掏出一把砍刀举起来
  0.85–1.4 bot 跳到旧字标左端，横着刀从左冲到右，身后一道 Kimi 蓝刀光
  1.4–2.6  刀口先裂开一道细缝；上半截顺着刀口往右滑、越滑越快，悬空后往右下翻倒掉出画面；
           下半截晚一拍直接往下掉
  1.45–1.95 bot 收刀，跳回正上方
  2.2      「现已更名为」浮现
  2.6–3.05 Kimi 蓝小球从画面上方落下（与标题素材 make_header.py 同一颗）
  3.05     砸在「Moon」的第一个 o 上：「Moon Code」从撞击点向两边逐字弹出，小球弹回飞出画面；
           同时两个下角喷彩条（与 App 欢迎页的 ConfettiBurst 同一套物理）
  3.7–4.2  一句话「KimiCode 的远程控制客户端」
  4.8–6.0  字标上移缩小，bot 挪到字标左边并排（同 App 侧栏顶部），手机（对话界面）从下方 / 右侧滑入
  5.9–6.3  一句话下面弹出两枚麦穗徽章：「[App Store 图标] 软件开发工具 / #28」「[GitHub 图标] qkunio/mooncode / 100% 开源」
  6.3–7.2  App Store 风格的 App 卡片滑上来（图标 / 名称 / 副标题 / 获取）
  7.5–9.4  点「获取」：按下 → 下载圈走满 → 变成「打开」
  横版手机屏幕里轮播 3 个示例：对话 → 侧栏与设备 → 切换模型（屏幕内横向翻页）；竖版只放对话
  9.4–10.5 定格

App Store 图标直接读 macOS 自带 App Store.app 里的官方图标（AppIcon.icns），不用下载。
"""
import math
import random
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_header import KIMI, sf  # noqa: E402
from make_screenshots import PINGFANG, framed  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PF_MEDIUM, PF_REGULAR = 7, 3
# 白底浅色版：纸白底、近黑字（苹果官网用的 #1D1D1F）
PAPER = (255, 255, 255)
INK = (29, 29, 31)
GRAY = (142, 142, 147)
OPEN = 1.35  # 开场收缩结束
BLADE = 1.3  # 砍刀相对 bot 单位的放大
SHIFT = OPEN - 0.5  # 开场之后的分镜整体后移
DURATION = 10.5 + SHIFT
CONFETTI = [KIMI, (255, 204, 0), (255, 45, 85), (52, 199, 89), (175, 82, 222), (255, 149, 0), (50, 173, 230)]
CARD = (242, 242, 247)  # App Store 浅色模式卡片底（secondarySystemBackground）
CARD_BORDER = (229, 229, 234)
FILL = (227, 227, 232)  # 「获取」按钮底
SYSTEM_BLUE = (0, 122, 255)  # 浅色模式 systemBlue，App Store 按钮文字
PF_SEMIBOLD = 11
ICON = ROOT / "KimiCode/Assets.xcassets/AppIcon.appiconset/AppIcon-Light.png"
APP_STORE_ICON = "/System/Applications/App Store.app/Contents/Resources/AppIcon.icns"
# GitHub 标志：Octicons 的 mark-github（scripts/assets/github-mark.svg），用 Quick Look 栅格化后存成透明 PNG
GITHUB_MARK = Path(__file__).resolve().parent / "assets/github-mark.png"

# 两种画幅的版式：字标大小 / 位置（画面比例）、手机尺寸与终点、App 卡片（宽 / 中心 x / 顶 y / 缩放）
LAYOUTS = {
    "vertical": dict(
        size=(1080, 1920), old=112, word=170, word_end=124, tag=58,
        center=(0.5, 0.44), end=(0.5, 0.11), phone_w=600, phone_end=(0.5, 0.305), phone_from="bottom",
        card_w=920, card_at=(0.5, 0.655), u=1.0, scrim=0.5, carousel=False, now_style="tag", bot_u=6.4, bot_u_end=6.4,
    ),
    "landscape": dict(
        size=(1920, 1080), old=140, word=180, word_end=136, tag=52,
        center=(0.5, 0.5), end=(0.33, 0.295), phone_w=400, phone_end=(0.73, 0.14), phone_from="right",
        card_w=700, card_at=(0.33, 0.625), u=0.8, scrim=None, carousel=True, now_style="big", bot_u=5.6, bot_u_end=5.6,
    ),
}


def app_store_icon(size):
    """macOS 自带的 App Store 图标；icns 带一圈留白，按不透明区域裁掉再缩放。"""
    icon = Image.open(APP_STORE_ICON).convert("RGBA")
    icon = icon.crop(icon.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox())
    return icon.resize((size, size), Image.LANCZOS)


def laurel(u, height, color=(29, 29, 31)):
    """半边麦穗（左侧）：一条细弧形枝，从下往上长，两侧交替细长叶子，越往上越小。3 倍超采样。"""
    ss = 3
    R = height * 0.5 * ss
    W = round(R * 0.95)
    H = round(height * ss)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = color + (255,)
    cx, cy = R * 1.05, H / 2  # 弧心：枝在弧心左侧
    n = 9
    t0, t1 = math.radians(128), math.radians(236)  # 左下 → 左上（y 向下的坐标系）
    stem = []
    for k in range(41):
        th = t0 + (t1 - t0) * k / 40
        stem.append((cx + R * math.cos(th), cy + R * math.sin(th)))
    d.line(stem, fill=col, width=max(1, round(1.4 * u * ss)), joint="curve")

    def leaf(x, y, dx, dy, length, width):
        nx, ny = -dy, dx
        pts = []
        for k in range(17):
            t = k / 16
            off = width / 2 * math.sin(math.pi * t) ** 0.9
            pts.append((x + dx * length * t + nx * off, y + dy * length * t + ny * off))
        for k in range(16, -1, -1):
            t = k / 16
            off = width / 2 * math.sin(math.pi * t) ** 0.9
            pts.append((x + dx * length * t - nx * off, y + dy * length * t - ny * off))
        d.polygon(pts, fill=col)

    for i in range(n):
        th = t0 + (t1 - t0) * (i + 0.5) / n
        x, y = cx + R * math.cos(th), cy + R * math.sin(th)
        tx, ty = -math.sin(th), math.cos(th)  # 沿枝往上
        ox, oy = math.cos(th), math.sin(th)  # 向外
        k = 1 - 0.4 * i / (n - 1)
        L, Wd = 15 * u * ss * k, 5.2 * u * ss * k
        for side, a, scale in ((1, 42, 1.0), (-1, 36, 0.78)):
            ar = math.radians(a)
            dx = tx * math.cos(ar) + ox * math.sin(ar) * side
            dy = ty * math.cos(ar) + oy * math.sin(ar) * side
            leaf(x, y, dx, dy, L * scale, Wd * scale)
    # 顶端一片顺着枝
    x, y = stem[-1]
    leaf(x, y, -math.sin(t1), math.cos(t1), 11 * u * ss, 4 * u * ss)
    return img.resize((W // ss, H // ss), Image.LANCZOS)


def github_mark(size):
    return Image.open(GITHUB_MARK).convert("RGBA").resize((size, size), Image.LANCZOS)


def make_badge(big, small, icon, u, big_size=50, big_cjk=""):
    """App Store 榜单 / 奖项样式的徽章：左右细麦穗，中间上一行小字（可带图标）、下一行大字，整体垂直居中。
    big_cjk：大字后面接的中文（如「100%」后的「 开源」），SF 没有中文字形，用同字号的苹方 Semibold 接上。"""
    big_font = sf(round(big_size * u), 700)
    cjk_font = ImageFont.truetype(PINGFANG, round(big_size * u * 0.9), index=PF_SEMIBOLD)
    small_font = ImageFont.truetype(PINGFANG, round(28 * u), index=PF_MEDIUM)
    bw = big_font.getlength(big) + (cjk_font.getlength(big_cjk) if big_cjk else 0)
    sw = small_font.getlength(small) + (icon.width + 7 * u if icon else 0)
    text_w = max(bw, sw)
    height = round(128 * u)
    branch = laurel(u, height)
    gap = round(6 * u)
    w = round(branch.width * 2 + gap * 2 + text_w)
    img = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    img.alpha_composite(branch, (0, 0))
    img.alpha_composite(branch.transpose(Image.FLIP_LEFT_RIGHT), (w - branch.width, 0))
    d = ImageDraw.Draw(img)
    cx = w / 2
    # 小字一行 + 大字一行，整块在徽章里垂直居中
    sh = small_font.size * 1.25
    bh = big_font.getbbox(big, anchor="ls")
    big_h = bh[3] - bh[1]
    block = sh + 6 * u + big_h
    top = (height - block) / 2
    sy = top + sh / 2
    x0 = cx - sw / 2
    if icon:
        img.alpha_composite(icon, (round(x0), round(sy - icon.height / 2)))
        x0 += icon.width + 7 * u
    d.text((x0, sy), small, font=small_font, fill=(99, 99, 102, 255), anchor="lm")
    base = top + sh + 6 * u - bh[1]
    bx = cx - bw / 2
    d.text((bx, base), big, font=big_font, fill=INK + (255,), anchor="ls")
    if big_cjk:
        d.text((bx + big_font.getlength(big), base), big_cjk, font=cjk_font, fill=INK + (255,), anchor="ls")
    return img


def squircle_icon(path, size):
    """App 图标按 iOS 的圆角（约 22.37%）裁好。"""
    ss = 4
    icon = Image.open(path).convert("RGBA").resize((size * ss, size * ss), Image.LANCZOS)
    mask = Image.new("L", icon.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, icon.width - 1, icon.height - 1), round(size * ss * 0.2237), fill=255)
    icon.putalpha(mask)
    return icon.resize((size, size), Image.LANCZOS)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def phase(t, start, end):
    return clamp((t - start) / (end - start))


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=1.9):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, x):
    return a + (b - a) * x


def text_layer(size, draw_fn):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer


def with_alpha(layer, alpha):
    if alpha >= 1:
        return layer
    a = layer.getchannel("A").point(lambda v: round(v * alpha))
    layer = layer.copy()
    layer.putalpha(a)
    return layer


class Scene:
    def __init__(self, spec, shots):
        self.spec = spec
        self.w, self.h = spec["size"]
        w, h = self.w, self.h

        # 旧字标：白「Kimi Code 」+ 蓝「Mobile」（旧版 App 里的样子）
        self.old_font = sf(spec["old"], 860)
        self.old_a, self.old_b = "Kimi Code ", "Mobile"
        self.old_width = self.old_font.getlength(self.old_a + self.old_b)
        rng = random.Random(7)
        ocx, ocy = spec["center"][0] * w, spec["center"][1] * h
        self.old_x0 = ocx - self.old_width / 2
        self.old_base = ocy + spec["old"] * 0.36
        # 整条旧字标画成一张贴图，刀口在 x-height 中间，砍完按刀口切成上下两半
        pad = spec["old"]
        base_in = spec["old"] * 1.2 + pad / 2
        old = Image.new("RGBA", (round(self.old_width + pad * 2), round(spec["old"] * 1.6 + pad)), (0, 0, 0, 0))
        od = ImageDraw.Draw(old)
        od.text((pad, base_in), self.old_a, font=self.old_font, fill=INK + (255,), anchor="ls")
        od.text((pad + self.old_font.getlength(self.old_a), base_in), self.old_b, font=self.old_font, fill=KIMI + (255,), anchor="ls")
        cut = round(base_in - spec["old"] * 0.33)
        self.old_img = old
        self.old_top = old.crop((0, 0, old.width, cut))
        self.old_bottom = old.crop((0, cut, old.width, old.height))
        self.old_origin = (self.old_x0 - pad, self.old_base - base_in)
        self.cut_y = self.old_base - spec["old"] * 0.33

        # 彩条：与 App 的 ConfettiBurst 同一套参数，按画面高度缩放（App 里是 874pt 高的屏幕）
        k = h / 874
        self.confetti = []
        for i in range(64):
            side = i % 2
            angle = math.radians(rng.uniform(6, 42))
            speed = rng.uniform(2400, 3400) * k
            inward = 1 if side == 0 else -1
            self.confetti.append(dict(
                side=side, vx=inward * math.sin(angle) * speed, vy=-math.cos(angle) * speed,
                w=rng.uniform(9, 13) * k, h=rng.uniform(20, 30) * k, color=rng.choice(CONFETTI),
                spin=rng.uniform(-9, 9), rot=rng.uniform(0, 2 * math.pi), flip=rng.uniform(6, 14),
                wobble=rng.uniform(6, 16) * k, phase=rng.uniform(0, 2 * math.pi), delay=rng.uniform(0, 0.12),
            ))
        self.k = k

        # 新字标：逐字弹出用的字母贴图，按最终位置排好
        self.word_font = sf(spec["word"], 860)
        word = "Moon Code"
        self.word_width = self.word_font.getlength(word)
        cx, cy = spec["center"][0] * w, spec["center"][1] * h
        self.word_x0 = cx - self.word_width / 2
        self.baseline = cy + spec["word"] * 0.36
        self.letters = []
        for i, c in enumerate(word):
            if c == " ":
                continue
            x = self.word_x0 + self.word_font.getlength(word[:i])
            cw = self.word_font.getlength(c)
            pad = spec["word"]
            spr = Image.new("RGBA", (round(cw + pad * 2), round(spec["word"] * 1.6 + pad)), (0, 0, 0, 0))
            base_in = spec["word"] * 1.2 + pad / 2
            ImageDraw.Draw(spr).text((pad, base_in), c, font=self.word_font,
                                     fill=(KIMI if i < 4 else INK) + (255,), anchor="ls")
            self.letters.append(dict(x=x, w=cw, spr=spr, ox=pad, oy=base_in))
        impact = self.letters[1]  # 第一个 o
        self.impact_x = impact["x"] + impact["w"] / 2
        top = self.baseline + self.word_font.getbbox("o", anchor="ls")[1]
        self.r = spec["word"] * 0.2
        self.contact_y = top - self.r

        self.tag_font = ImageFont.truetype(PINGFANG, spec["tag"], index=PF_MEDIUM)
        new_top = self.baseline + self.word_font.getbbox("M", anchor="ls")[1]
        if spec["now_style"] == "tag":
            # 竖版：与副标题完全同一个样式。间距按整行可见边缘量，让「现已更名为 ↔ Moon Code」和
            # 「Moon Code ↔ 副标题」肉眼看起来一样（Code 的 d 比 M 高，中文比 K 高，单个字母量会偏）
            self.now_font = self.tag_font
            word_box = self.word_font.getbbox("Moon Code", anchor="ls")
            tag_box = self.tag_font.getbbox("KimiCode 的远程控制客户端", anchor="lt")
            gap_below = (self.baseline + spec["tag"] * 1.25 + tag_box[1]) - (self.baseline + word_box[3])
            now_box = self.now_font.getbbox("现已更名为", anchor="ls")
            self.now_base = (self.baseline + word_box[1]) - gap_below - now_box[3]
            self.now_color = INK
        else:
            # 横版：旧字标字号的 2/3，半粗
            self.now_font = ImageFont.truetype(PINGFANG, round(spec["old"] * 2 / 3), index=PF_SEMIBOLD)
            self.now_base = new_top - spec["word"] * 0.3
            self.now_color = INK

        # bot 贴着下方文字：按字形顶边算，留很小的缝
        u0 = spec["bot_u"]
        gap = 2.5 * u0
        old_top = self.old_base + self.old_font.getbbox("K", anchor="ls")[1]
        now_top = self.now_base + self.now_font.getbbox("现", anchor="ls")[1]
        self.bot_y_old = old_top - gap - 8 * u0  # 旧字标上方
        self.bot_y_now = now_top - gap * 2.5 - 8 * u0  # 「现已更名为」上方：字小，留宽一点
        self.bot_y_new = new_top - gap - 8 * u0  # 新字标上方

        # App Store 卡片
        u = spec["u"]
        self.u = u
        self.card_size = (spec["card_w"], round(200 * u))
        self.icon = squircle_icon(ICON, round(144 * u))
        self.name_font = ImageFont.truetype(PINGFANG, round(46 * u), index=PF_SEMIBOLD)
        self.sub_font = ImageFont.truetype(PINGFANG, round(31 * u), index=PF_REGULAR)
        self.btn_font = ImageFont.truetype(PINGFANG, round(32 * u), index=PF_SEMIBOLD)
        self.cap_font = ImageFont.truetype(PINGFANG, round(34 * u), index=PF_REGULAR)
        self.badges = [
            make_badge("#28", "软件开发工具", app_store_icon(round(31 * u)), u),
            make_badge("100%", "qkunio/mooncode", github_mark(round(29 * u)), u, big_cjk=" 开源"),
        ]

        # 手机：每个示例先缩到屏幕宽度，静止时用现成的带边框贴图，翻页时现拼屏幕再套边框
        sw = spec["phone_w"]
        self.bezel = round(sw * 0.028)
        names = ["chat", "devices", "model"] if spec["carousel"] else ["chat"]
        self.screens = [shots[n].convert("RGB").resize((sw, round(shots[n].height * sw / shots[n].width)), Image.LANCZOS)
                        for n in names]
        self.phones = [framed(sc, sw, corner=168 * sw / shots["chat"].width, bezel=self.bezel) for sc in self.screens]
        self.phone = self.phones[0]

    # MARK: 各段

    def draw_old(self, canvas, t):
        if t < 0 or t > 2.7:
            return
        ox, oy = self.old_origin
        cut_y = self.cut_y
        if t < 1.4:
            canvas.alpha_composite(self.old_img, (round(ox), round(oy)))
        else:
            g = self.h * 2.4  # 重力（像素 / 秒²）
            old = self.spec["old"]
            # 刀过之后先裂开一道细缝（上下各让开一点），像被切开
            gap = old * 0.035 * ease_out(phase(t, 1.4, 1.5))
            # 上半截：沿刀口往右滑，匀加速；滑出约 0.6 个字高后失去支撑，开始下坠并往右翻
            ts = max(0.0, t - 1.5)
            slide_a = old * 6.0
            dx_top = 0.5 * slide_a * ts * ts
            tf = max(0.0, t - 1.78)
            dy_top = -gap + 0.5 * g * tf * tf
            ang_top = -min(38.0, 70 * tf * tf + 30 * tf)  # PIL 逆时针为正：负 = 顺时针往右翻
            # 下半截：晚一拍直接往下掉，轻微往左歪
            tb = max(0.0, t - 1.9)
            dy_bot = gap + 0.5 * g * tb * tb
            ang_bot = min(12.0, 22 * tb)
            a = 1 - phase(t, 2.35, 2.65)
            if a > 0:
                for part, (dx, dy, ang, y0) in (
                    (self.old_bottom, (-old * 0.2 * tb, dy_bot, ang_bot, cut_y)),
                    (self.old_top, (dx_top, dy_top, ang_top, oy)),
                ):
                    img = part.rotate(ang, resample=Image.BICUBIC, expand=True) if abs(ang) > 0.1 else part
                    px = ox + dx - (img.width - part.width) / 2
                    py = y0 + dy - (img.height - part.height) / 2
                    canvas.alpha_composite(with_alpha(img, a), (round(px), round(py)))
        # 刀光：bot 冲过去时在身后拉出来，砍完淡掉
        x_from = self.old_x0 - self.spec["old"] * 0.4
        bx, _, bu = self.bot_at(t)
        x_to = bx + (11 + 23.5 * BLADE) * bu if t < 1.4 else self.old_x0 + self.old_width + self.spec["old"] * 0.4
        glow = 1 - phase(t, 1.45, 1.75)
        if t >= 1.1 and glow > 0 and x_to > x_from:
            th = max(10, round(self.spec["old"] * 0.16))
            layer = text_layer(canvas.size, lambda d: d.polygon(
                [(x_from, cut_y), (x_to, cut_y - th / 2), (x_to, cut_y + th / 2)], fill=KIMI + (255,)))
            canvas.alpha_composite(with_alpha(layer, glow))

    def blade_angle(self, t):
        """砍刀相对水平的角度（度，负 = 往上举），没拿出来时返回 None。"""
        if t < 0.6 or t > 1.75:
            return None
        if t < 0.85:
            return -70
        if t < 1.1:
            return lerp(-70, -10, ease_in_out(phase(t, 0.85, 1.1)))
        if t < 1.4:
            return lerp(-10, 8, phase(t, 1.1, 1.4))
        return lerp(8, -40, ease_out(phase(t, 1.4, 1.6)))

    def draw_blade(self, canvas, t):
        """bot 右手的砍刀：深色刀柄 + 浅灰宽刃 + 刀背一道深线。以手（bot 右侧中下）为轴转。"""
        ang = self.blade_angle(t)
        if ang is None:
            return
        cx, cy, u = self.bot_at(t)
        scale = ease_out_back(phase(t, 0.6, 0.78)) * (1 - ease_in_out(phase(t, 1.55, 1.75)))
        if scale <= 0.01:
            return
        px, py = cx + 11 * u, cy + 3 * u  # 握刀点
        r = math.radians(ang)
        ca, sa = math.cos(r), math.sin(r)

        def pts(shape):
            k = u * scale * BLADE
            return [(px + (x * ca - y * sa) * k, py + (x * sa + y * ca) * k) for x, y in shape]

        handle = [(-1.5, -0.9), (4.5, -0.9), (4.5, 0.9), (-1.5, 0.9)]
        guard = [(4.2, -1.8), (5.4, -1.8), (5.4, 1.8), (4.2, 1.8)]
        blade = [(5.4, -1.3), (19, -2.2), (23.5, -1.0), (22.5, 2.6), (5.4, 1.7)]
        spine = [(5.4, -1.3), (19, -2.2), (19.2, -1.4), (5.4, -0.6)]
        polys = [(pts(blade), (214, 219, 226)), (pts(spine), (160, 167, 178)), (pts(handle), INK), (pts(guard), (72, 72, 74))]
        xs = [x for poly, _ in polys for x, _ in poly]
        ys = [y for poly, _ in polys for _, y in poly]
        bx0, by0 = math.floor(min(xs)) - 2, math.floor(min(ys)) - 2
        lw, lh = math.ceil(max(xs)) - bx0 + 2, math.ceil(max(ys)) - by0 + 2
        ss = 3
        layer = Image.new("RGBA", (lw * ss, lh * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for poly, col in polys:
            d.polygon([((x - bx0) * ss, (y - by0) * ss) for x, y in poly], fill=col + (255,))
        canvas.alpha_composite(layer.resize((lw, lh), Image.LANCZOS), (bx0, by0))

    def draw_opening(self, canvas, t):
        """开场：整屏 Kimi 蓝的大脸，眼睛弹出、眨一下，再平滑收缩成旧字标上方的小 bot（同 App 的 SplashFace）。"""
        if t >= OPEN:
            return
        w, h = self.w, self.h
        c = ease_in_out(phase(t, 0.85, OPEN))
        bx, by, bu = self.bot_at(OPEN - SHIFT)
        x0, x1 = lerp(0, bx - 12 * bu, c), lerp(w, bx + 12 * bu, c)
        y0, y1 = lerp(0, by - 8 * bu, c), lerp(h, by + 8 * bu, c)
        u = lerp(min(w, h) / 402 * 15, bu, c)
        pop = ease_out_back(phase(t, 0.12, 0.38))
        blink = 0.12 if 0.58 <= t < 0.68 else 1
        self.draw_face(canvas, (x0, y0, x1, y1), 2.3 * bu * c, u, pop * blink)

    def draw_confetti(self, canvas, t):
        t0 = 3.1
        t = t - t0
        life = 4.0
        if t <= 0 or t >= life:
            return
        d = ImageDraw.Draw(canvas)
        kd, g = 3.0, 900 * self.k
        for P in self.confetti:
            tt = t - P["delay"]
            if tt <= 0:
                continue
            decay = (1 - math.exp(-kd * tt)) / kd
            x = P["side"] * self.w + P["vx"] * decay + math.sin(tt * 4 + P["phase"]) * P["wobble"] * min(tt, 1)
            y = self.h + P["vy"] * decay + g / kd * (tt - decay)
            fade = clamp((life - P["delay"] - tt) / 0.6)
            if fade <= 0:
                continue
            ang = P["rot"] + P["spin"] * tt
            sx = max(0.08, abs(math.cos(P["flip"] * tt + P["phase"])))
            hw, hh = P["w"] / 2 * sx, P["h"] / 2
            ca, sa = math.cos(ang), math.sin(ang)
            pts = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            col = tuple(round(255 - (255 - c) * fade) for c in P["color"])  # 白底上淡出 = 往白混
            d.polygon(pts, fill=col)

    def draw_now(self, canvas, t):
        a = ease_out(phase(t, 2.2, 2.6)) * (1 - ease_in_out(phase(t, 3.2, 3.6)))
        if a <= 0:
            return
        cx = self.spec["center"][0] * self.w
        layer = text_layer(canvas.size, lambda d: d.text((cx, self.now_base + (1 - a) * 20), "现已更名为",
                                                          font=self.now_font, fill=self.now_color + (255,), anchor="ms"))
        canvas.alpha_composite(with_alpha(layer, a))

    def ball(self, canvas, t):
        t_fall, t_hit, t_out = 2.6, 3.05, 3.6
        if not (t_fall <= t <= t_out):
            return
        start_y = -self.r * 2
        if t <= t_hit:
            x = (t - t_fall) / (t_hit - t_fall)
            cy = lerp(start_y, self.contact_y, x * x)  # 自由落体
            sy = 1 + 0.12 * x
        else:
            x = (t - t_hit) / (t_out - t_hit)
            cy = lerp(self.contact_y, start_y - self.h * 0.1, 1 - (1 - x) ** 2)  # 弹回减速
            sy = 1 - 0.25 * math.exp(-x * 14) + 0.08 * x
        rx, ry = self.r / math.sqrt(sy), self.r * sy
        ss = 4
        img = Image.new("RGBA", (round(rx * 2 * ss) + 4, round(ry * 2 * ss) + 4), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse((2, 2, img.width - 2, img.height - 2), fill=KIMI + (255,))
        img = img.resize((max(1, img.width // ss), max(1, img.height // ss)), Image.LANCZOS)
        canvas.alpha_composite(img, (round(self.impact_x - img.width / 2), round(cy + self.r - img.height)))

    def end_group(self):
        """终点：bot + 间距 + 字标作为一组，以 end 点居中。返回 (字标中心 x, bot 中心 x)。"""
        f = sf(self.spec["word_end"], 860)
        width = f.getlength("Moon Code")
        bw = 24 * self.spec["bot_u_end"]
        gap = self.spec["word_end"] * 0.22
        gx = self.spec["end"][0] * self.w
        left = gx - (bw + gap + width) / 2
        return left + bw + gap + width / 2, left + bw / 2

    def word_layout(self, t):
        """字标的字号 / 中心点：先在画面中间，4.8s 起移到终点（给左边的 bot 让出位置）。"""
        m = ease_in_out(phase(t, 4.8, 5.8))
        size = lerp(self.spec["word"], self.spec["word_end"], m)
        cx = lerp(self.spec["center"][0] * self.w, self.end_group()[0], m)
        cy = lerp(self.spec["center"][1], self.spec["end"][1], m) * self.h
        return size, cx, cy, m

    def bot_at(self, t):
        """小 bot 的中心与单位尺寸：先在旧字标正上方；砍旧名时跳到左端、横冲到右端、再跳回；
        4.8s 起挪到新字标左边并排。"""
        u0 = self.spec["bot_u"]
        sx = self.spec["center"][0] * self.w
        # 平时贴在下方文字上：旧字标 →（「现已更名为」出来时往上让一让）→ 新字标
        sy = self.bot_y_old
        if t >= 2.0:
            up = ease_in_out(phase(t, 2.0, 2.3))
            down = ease_in_out(phase(t, 3.4, 3.75))
            sy = lerp(lerp(self.bot_y_old, self.bot_y_now, up), self.bot_y_new, down)
        dash_y = self.cut_y - 3 * u0  # 握刀点比 bot 中心低 3 个单位：刀刃正好压在刀口上
        # bot 从字标左端压着第一个字母起跑，刀尖领先；冲到刀尖越过最后一个字母为止（bot 不出画面）
        lx = self.old_x0 + 4 * u0
        rx = self.old_x0 + self.old_width - 34 * u0
        hop = self.spec["old"] * 0.9

        def jump(a, b, x):  # 抛物线跳
            e = ease_in_out(x)
            return lerp(a[0], b[0], e), lerp(a[1], b[1], e) - hop * 4 * x * (1 - x)

        if 0.85 <= t < 1.1:
            x, y = jump((sx, sy), (lx, dash_y), phase(t, 0.85, 1.1))
            return x, y, u0
        if 1.1 <= t < 1.5:
            return lerp(lx, rx, ease_in_out(phase(t, 1.1, 1.4))), dash_y, u0
        if 1.5 <= t < 1.95:
            x, y = jump((rx, dash_y), (sx, sy), phase(t, 1.5, 1.95))
            return x, y, u0
        m = ease_in_out(phase(t, 4.8, 5.8))
        ex = self.end_group()[1]
        ey = self.spec["end"][1] * self.h  # 与字标中线对齐
        return lerp(sx, ex, m), lerp(sy, ey, m), lerp(u0, self.spec["bot_u_end"], m)

    def draw_face(self, canvas, rect, radius, u, eye_scale=1.0):
        """bot 的脸：圆角矩形 + 两只眼（KimiFace 几何：眼 3×4.5、间距 6、偏移 (2.7, -2.8)）。"""
        x0, y0, x1, y1 = rect
        ss = 3
        pad = 4
        bx0, by0 = math.floor(x0) - pad, math.floor(y0) - pad
        lw, lh = math.ceil(x1) - bx0 + pad, math.ceil(y1) - by0 + pad
        if lw <= 0 or lh <= 0:
            return
        layer = Image.new("RGBA", (lw * ss, lh * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle(((x0 - bx0) * ss, (y0 - by0) * ss, (x1 - bx0) * ss, (y1 - by0) * ss), radius * ss,
                            fill=KIMI + (255,))
        cx, cy = (x0 + x1) / 2 - bx0, (y0 + y1) / 2 - by0
        for side in (-1, 1):
            ex, ey = cx + (2.7 + 4.5 * side) * u, cy - 2.8 * u
            ew, eh = 1.5 * u * min(eye_scale, 1.2), 2.25 * u * eye_scale
            if ew > 0 and eh > 0:
                d.rectangle(((ex - ew) * ss, (ey - eh) * ss, (ex + ew) * ss, (ey + eh) * ss), fill=(255, 255, 255, 255))
        canvas.alpha_composite(layer.resize((lw, lh), Image.LANCZOS), (bx0, by0))

    def draw_bot(self, canvas, t):
        """开场收缩完之后一直在的小 bot；2.4s 一个周期，末尾眨一下眼（同 App 的 KimiFace）。"""
        if t < OPEN - SHIFT:
            return
        cx, cy, u = self.bot_at(t)
        cyc = (t % 2.4) / 2.4
        blink = 0.15 if 0.9 < cyc < 0.96 else 1
        self.draw_face(canvas, (cx - 12 * u, cy - 8 * u, cx + 12 * u, cy + 8 * u), 2.3 * u, u, blink)

    def draw_word(self, canvas, t):
        t_hit = 3.05
        if t < t_hit:
            return
        if t < 3.9:
            # 从撞击点向两边逐字弹出（离得越远越晚、弹得越轻）
            span = self.word_width
            for L in self.letters:
                c = L["x"] + L["w"] / 2
                delay = abs(c - self.impact_x) / span * 0.32
                x = phase(t, t_hit + delay, t_hit + delay + 0.42)
                if x <= 0:
                    continue
                s = max(0.01, ease_out_back(x))
                spr = L["spr"]
                if abs(s - 1) > 0.003:
                    spr = spr.resize((max(1, round(spr.width * s)), max(1, round(spr.height * s))), Image.BICUBIC)
                oy = L["oy"] * s
                # 以字母底部中心为锚点缩放
                ax = L["x"] + L["w"] / 2 - (L["ox"] + L["w"] / 2) * s
                canvas.alpha_composite(spr, (round(ax), round(self.baseline - oy)))
            return
        size, cx, cy, _ = self.word_layout(t)
        f = sf(round(size), 860)
        width = f.getlength("Moon Code")
        x0 = cx - width / 2
        base = cy + size * 0.36
        d = ImageDraw.Draw(canvas)
        d.text((x0, base), "Moon", font=f, fill=KIMI + (255,), anchor="ls")
        d.text((x0 + f.getlength("Moon"), base), " Code", font=f, fill=INK + (255,), anchor="ls")

    def draw_tagline(self, canvas, t):
        a = ease_out(phase(t, 3.7, 4.2))
        if a <= 0:
            return
        size, _, cy, m = self.word_layout(t)
        cx = lerp(self.spec["center"][0], self.spec["end"][0], m) * self.w  # 跟整组（bot + 字标）居中
        y = cy + size * 0.36 + self.spec["tag"] * 1.25 + (1 - a) * 24
        canvas.alpha_composite(with_alpha(text_layer(canvas.size, lambda d: d.text(
            (cx, y), "KimiCode 的远程控制客户端", font=self.tag_font, fill=INK + (255,), anchor="mt")), a))

    def button(self, t):
        """卡片右侧的按钮：获取 →（按下）→ 下载圈 → 打开。返回贴图。"""
        u, ss = self.u, 4
        bw, bh = round(132 * u), round(58 * u)
        img = Image.new("RGBA", (bw * ss, bh * ss), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        t_press, t_load, t_done = 7.5, 7.8, 9.05
        if t < t_load:
            press = phase(t, t_press, t_press + 0.12) * (1 - phase(t, t_press + 0.12, t_load))
            s = 1 - 0.1 * ease_in_out(press)
            w2, h2 = bw * ss * s, bh * ss * s
            x0, y0 = (bw * ss - w2) / 2, (bh * ss - h2) / 2
            d.rounded_rectangle((x0, y0, x0 + w2, y0 + h2), h2 / 2, fill=FILL + (255,))
            label = "获取"
        elif t < t_done:
            # 下载圈：灰色底环 + 蓝色进度 + 中间小方块（停止）
            p = ease_in_out(phase(t, t_load + 0.15, t_done - 0.1))
            r = bh * ss * 0.46
            cx, cy = bw * ss / 2, bh * ss / 2
            lw = round(5 * u * ss)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=FILL + (255,), width=lw)
            if p > 0:
                d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * p, fill=SYSTEM_BLUE + (255,), width=lw)
            q = r * 0.32
            d.rounded_rectangle((cx - q, cy - q, cx + q, cy + q), q * 0.25, fill=SYSTEM_BLUE + (255,))
            label = None
        else:
            s = clamp(ease_out_back(phase(t, t_done, t_done + 0.3)), 0, 1.2)
            w2, h2 = bw * ss * s, bh * ss * s
            x0, y0 = (bw * ss - w2) / 2, (bh * ss - h2) / 2
            d.rounded_rectangle((x0, y0, x0 + w2, y0 + h2), max(1, h2 / 2), fill=FILL + (255,))
            label = "打开" if s > 0.5 else None
        img = img.resize((bw, bh), Image.LANCZOS)
        if label:
            ImageDraw.Draw(img).text((bw / 2, bh / 2), label, font=self.btn_font, fill=SYSTEM_BLUE + (255,), anchor="mm")
        return img

    def draw_card(self, canvas, t):
        a = ease_out(phase(t, 6.3, 6.9))
        if a <= 0:
            return
        u = self.u
        cx_frac, top_frac = self.spec["card_at"]
        final_y = top_frac * self.h
        if self.spec["scrim"]:
            # 竖版：卡片从屏幕下方滑上来；渐白层是卡片的「影子」，上沿和卡片保持同样距离，一起往上推
            p = ease_out(phase(t, 6.3, 7.0))
            y = lerp(self.h + 10, final_y, p)
            lead = final_y - self.spec["scrim"] * self.h  # 渐白上沿在卡片上方多远
            top = round(y - lead)
            fade_h = round((self.h - self.spec["scrim"] * self.h) * 0.38)
            if top < self.h:
                col = Image.new("L", (1, self.h - top))
                for i in range(col.height):
                    col.putpixel((0, i), round(255 * ease_in_out(clamp(i / fade_h))))
                scrim = Image.new("RGBA", (self.w, self.h - top), PAPER + (255,))
                scrim.putalpha(col.resize((self.w, col.height)))
                canvas.alpha_composite(scrim, (0, top))
            card_alpha = 1.0
        else:
            y = final_y + (1 - a) * 80 * u
            card_alpha = a
        cw, ch = self.card_size
        card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        d = ImageDraw.Draw(card)
        d.rounded_rectangle((0, 0, cw - 1, ch - 1), round(40 * u), fill=CARD + (255,), outline=CARD_BORDER + (255,), width=2)
        pad = round(28 * u)
        card.alpha_composite(self.icon, (pad, (ch - self.icon.height) // 2))
        tx = pad * 2 + self.icon.width
        d.text((tx, ch / 2 - 8 * u), "Moon Code", font=self.name_font, fill=INK + (255,), anchor="ls")
        d.text((tx, ch / 2 + 12 * u), "KimiCode远程控制客户端", font=self.sub_font, fill=GRAY + (255,), anchor="lt")
        btn = self.button(t)
        card.alpha_composite(btn, (cw - pad - btn.width, (ch - btn.height) // 2))

        x = round(cx_frac * self.w - cw / 2)
        canvas.alpha_composite(with_alpha(card, card_alpha), (x, round(y)))



    def phone_image(self, t):
        """轮播：对话 → 侧栏与设备 → 切换模型，屏幕内横向翻页。"""
        if len(self.phones) == 1:
            return self.phone
        turns = [(7.3, 7.75), (8.9, 9.35)]
        idx = 0
        for i, (a, b) in enumerate(turns):
            if t >= b:
                idx = i + 1
            elif t > a:
                p = ease_in_out(phase(t, a, b))
                A, B = self.screens[i], self.screens[i + 1]
                sw = A.width
                screen = Image.new("RGB", A.size, PAPER)
                screen.paste(A, (round(-p * sw), 0))
                screen.paste(B, (round(sw * (1 - p)), 0))
                return framed(screen, sw, corner=168 * sw / 1206, bezel=self.bezel)
        return self.phones[idx]

    def draw_badges(self, canvas, t):
        """一句话下面两枚徽章并排，依次弹出。"""
        if t < 5.9:
            return
        u = self.u
        size, _, cy, m = self.word_layout(t)
        gx = lerp(self.spec["center"][0], self.spec["end"][0], m) * self.w
        top = cy + size * 0.36 + self.spec["tag"] * 1.25 + self.spec["tag"] * 1.2 + 34 * u
        gap = 36 * u
        total = sum(b.width for b in self.badges) + gap
        x = gx - total / 2
        for i, b in enumerate(self.badges):
            p = phase(t, 5.9 + i * 0.15, 6.3 + i * 0.15)
            if p > 0:
                s = max(0.01, ease_out_back(p))
                img = b if abs(s - 1) < 0.003 else b.resize((max(1, round(b.width * s)), max(1, round(b.height * s))), Image.BICUBIC)
                canvas.alpha_composite(with_alpha(img, clamp(p * 2.5)),
                                       (round(x + (b.width - img.width) / 2), round(top + (b.height - img.height) / 2)))
            x += b.width + gap

    def draw_phone(self, canvas, t):
        x = ease_out(phase(t, 5.0, 6.0))
        if x <= 0:
            return
        phone = self.phone_image(t)
        ex, ey = self.spec["phone_end"]
        fx = round(ex * self.w - self.phone.width / 2)
        fy = round(ey * self.h)
        if self.spec["phone_from"] == "bottom":
            px, py = fx, round(lerp(self.h + 40, fy, x))
        else:
            px, py = round(lerp(self.w + 40, fx, x)), fy
        canvas.alpha_composite(with_alpha(phone, clamp(x * 1.6)), (px, py))

    def frame(self, t):
        canvas = Image.new("RGBA", (self.w, self.h), PAPER + (255,))
        tt = t - SHIFT  # 开场之后的分镜时间
        self.draw_old(canvas, tt)
        self.draw_now(canvas, tt)
        self.draw_phone(canvas, tt)
        self.draw_confetti(canvas, tt)
        self.draw_word(canvas, tt)
        self.draw_tagline(canvas, tt)
        self.draw_badges(canvas, tt)
        self.draw_card(canvas, tt)
        self.ball(canvas, tt)
        self.draw_bot(canvas, tt)
        self.draw_blade(canvas, tt)
        self.draw_opening(canvas, t)
        return canvas.convert("RGB")


def main():
    args = sys.argv[1:]
    fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 60
    positional = [a for a in args if not a.startswith("--") and a != str(fps)]
    raw = Path(positional[0]) / "iphone"
    out_dir = Path(positional[1]) if len(positional) > 1 else ROOT / "marketing/video"
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = {n: Image.open(raw / f"{n}.png") for n in ("chat", "devices", "model")}

    for name, spec in LAYOUTS.items():
        scene = Scene(spec, shots)
        w, h = spec["size"]
        out = out_dir / f"rename-{name}-{w}x{h}.mp4"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "17",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(out),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(round(DURATION * fps)):
            proc.stdin.write(scene.frame(i / fps).tobytes())
        proc.stdin.close()
        proc.wait()
        # 封面：定格那一帧
        scene.frame(DURATION - 0.1).save(out_dir / f"rename-{name}-{w}x{h}.png", optimize=True)
        print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
