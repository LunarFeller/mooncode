#!/usr/bin/env python3
"""App Store 产品页头图：静态 PNG + 循环动态 MP4。

用法：python3 scripts/make_header.py [输出目录] [--still-only] [--fps 60]
默认输出到 marketing/header/。

画面：纯色深底，「Moon」（蓝）「Code」（白）。一个 Kimi 蓝小球从画面上方落下，
砸在「Moon」的第一个 o 上：文字被压得下沉，离撞击点越远的字母下沉越少、越晚（果冻一样的波），
小球被弹回上方飞出画面，文字再抖几下回到原位，静止片刻后循环。

运动是按物理关系拼出来的解析曲线（自由落体 → 接触时一起压下 → 阻尼振荡），首尾无缝。
版式：顶部约 22% 会被状态栏和按钮盖住，小球只是从那里穿过；字标宽度控制在中间安全区内。
"""
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SF = "/System/Library/Fonts/SFNS.ttf"

SIZES = [(5244, 2950), (3840, 1646)]

BG = (0, 0, 0)
KIMI = (26, 136, 255)  # AccentColor 深色外观

PERIOD = 3.0  # 一个循环的秒数（视频就是一个循环，播放器循环播放）
T_FALL = 0.55  # 下落时长
T_CONTACT = 0.16  # 球压着文字一起下沉再弹起的时长
WOBBLE_FREQ = 3.2  # 回弹后抖动的频率（Hz）
WOBBLE_DECAY = 3.4  # 抖动衰减速率（1/s）
WAVE_SPEED = 6.0  # 下沉沿字标传播的速度（画面高度 / 秒）
IMPACT_LETTER = 1  # 砸在 "Moon" 的第几个字母上（第一个 o）


def sf(size, weight=900):
    f = ImageFont.truetype(SF, size)
    f.set_variation_by_axes([100, 96, 400, weight])
    return f


class Motion:
    """以画面高度为单位的运动曲线；y 向下为正。"""

    def __init__(self, fall_dist):
        self.fall_dist = fall_dist
        self.g = 2 * fall_dist / T_FALL ** 2
        self.v_imp = self.g * T_FALL
        # 接触期 s = A·sin(πτ/Tc)，起始速度与球的撞击速度连续
        self.depth = self.v_imp * T_CONTACT / math.pi
        self.omega = 2 * math.pi * WOBBLE_FREQ
        self.t_leave = T_FALL + T_CONTACT

    def sink(self, t):
        """撞击点处文字的下沉量（t 为循环内时间，可为负 = 尚未开始）。"""
        if t < T_FALL:
            return 0.0
        if t < self.t_leave:
            return self.depth * math.sin(math.pi * (t - T_FALL) / T_CONTACT)
        # 离开时 s=0、速度向上 = depth·π/Tc，之后阻尼振荡
        tau = t - self.t_leave
        v0 = self.depth * math.pi / T_CONTACT
        return -(v0 / self.omega) * math.exp(-WOBBLE_DECAY * tau) * math.sin(self.omega * tau)

    def ball(self, t):
        """球心相对接触位置的纵向偏移 + 速度。接触前后都是抛体，接触时跟着文字走。"""
        if t < T_FALL:
            dt = T_FALL - t
            return -(self.v_imp * dt - 0.5 * self.g * dt * dt), self.g * t
        if t < self.t_leave:
            return self.sink(t), 0.0
        tau = t - self.t_leave
        return -(self.v_imp * tau - 0.5 * self.g * tau * tau), -self.v_imp + self.g * tau


class Scene:
    def __init__(self, w, h):
        self.w, self.h = w, h
        b, a = "Moon", "Code"  # b：会动的蓝字在前；a：静止的白字在后
        size = round(h * 0.2)
        f = sf(size)
        while f.getlength(a + b) > h * 1.15:
            size -= 4
            f = sf(size)
        self.font = f
        self.size = size
        x0 = w / 2 - f.getlength(a + b) / 2
        self.baseline = h * 0.64
        self.prefix = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(self.prefix).text((x0 + f.getlength(b), self.baseline), a, font=f, fill=(255, 255, 255, 255), anchor="ls")

        # "Moon" 拆成单个字母，从左边起排，保留字距
        xm = x0
        self.letters = []
        pad = size
        for i, c in enumerate(b):
            lx = xm + f.getlength(b[:i])
            cw = f.getlength(c)
            spr = Image.new("RGBA", (round(cw + pad * 2), round(size * 1.6 + pad)), (0, 0, 0, 0))
            base_in_spr = size * 1.2 + pad / 2
            ImageDraw.Draw(spr).text((pad, base_in_spr), c, font=f, fill=KIMI + (255,), anchor="ls")
            self.letters.append(dict(x=lx, w=cw, spr=spr, ox=pad, oy=base_in_spr))

        imp = self.letters[IMPACT_LETTER]
        self.impact_x = imp["x"] + imp["w"] / 2
        top = self.baseline + f.getbbox(b[IMPACT_LETTER], anchor="ls")[1]
        self.r = h * 0.05
        self.contact_y = top - self.r  # 球心接触时的位置
        start_y = -self.r * 1.6  # 从画面外落下
        self.motion = Motion((self.contact_y - start_y) / h)

    def frame(self, t):
        w, h = self.w, self.h
        m = self.motion
        t %= PERIOD
        img = Image.new("RGBA", (w, h), BG + (255,))
        img.alpha_composite(self.prefix)

        span = self.letters[-1]["x"] + self.letters[-1]["w"] - self.letters[0]["x"]
        for L in self.letters:
            cx = L["x"] + L["w"] / 2
            dist = (cx - self.impact_x) / h
            delay = abs(dist) / WAVE_SPEED
            falloff = 1 - 0.3 * min(1, abs(cx - self.impact_x) / span)
            s = m.sink(t - delay) * falloff * h
            # 离撞击点的字母朝撞击点微微倾斜，像被往下拽
            angle = math.degrees(math.atan2(s, abs(cx - self.impact_x) + h * 0.15)) * (1 if dist > 0 else -1) * 0.25
            spr = L["spr"]
            if abs(angle) > 0.05 and dist != 0:
                spr = spr.rotate(angle, resample=Image.BICUBIC, center=(L["ox"] + L["w"] / 2, L["oy"]))
            img.alpha_composite(spr, (round(L["x"] - L["ox"]), round(self.baseline - L["oy"] + s)))

        dy, v = m.ball(t)
        cy = self.contact_y + dy * h
        if t < m.t_leave + T_FALL and cy + self.r * 2 > 0:  # 弹出画面后不再落回
            # 挤压与拉伸：飞行中沿速度方向拉长，接触时压扁（底部贴着文字）
            if T_FALL <= t < m.t_leave:
                k = math.sin(math.pi * (t - T_FALL) / T_CONTACT)
                sy = 1 - 0.22 * k
            else:
                sy = 1 + 0.07 * min(1, abs(v) / m.v_imp)
            sx = 1 / math.sqrt(sy)
            rx, ry = self.r * sx, self.r * sy
            bottom = cy + self.r
            ss = 4  # 超采样画圆，边缘更顺
            box = (round((rx + self.r * 0.14) * 2 * ss) + 8, round((ry + self.r * 0.14) * 2 * ss) + 8)
            ball = Image.new("RGBA", box, (0, 0, 0, 0))
            # 一圈底色描边：与同色的「Moon」贴在一起时也分得清
            ring = round(self.r * 0.14 * ss)
            ImageDraw.Draw(ball).ellipse((4, 4, box[0] - 4, box[1] - 4), fill=KIMI + (255,), outline=BG + (255,), width=ring)
            ball = ball.resize((max(1, box[0] // ss), max(1, box[1] // ss)), Image.LANCZOS)
            img.alpha_composite(ball, (round(self.impact_x - ball.width / 2), round(bottom + self.r * 0.14 - ball.height)))
        return img.convert("RGB")


def main():
    args = sys.argv[1:]
    fps = int(args[args.index("--fps") + 1]) if "--fps" in args else 60
    positional = [a for a in args if not a.startswith("--") and a != str(fps)]
    out_dir = Path(positional[0]) if positional else ROOT / "marketing/header"
    out_dir.mkdir(parents=True, exist_ok=True)

    for w, h in SIZES:
        scene = Scene(w, h)
        name = f"header-{w}x{h}"
        # 静态图：球刚要砸下的瞬间
        scene.frame(T_FALL - 0.12).save(out_dir / f"{name}.png", optimize=True)
        print("wrote", out_dir / f"{name}.png", flush=True)
        if "--still-only" in args:
            continue
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
            "-c:v", "libx264", "-profile:v", "high", "-level", "6.1", "-preset", "slow", "-crf", "16",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
            str(out_dir / f"{name}.mp4"),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(round(PERIOD * fps)):
            proc.stdin.write(scene.frame(i / fps).tobytes())
        proc.stdin.close()
        proc.wait()
        print("wrote", out_dir / f"{name}.mp4", flush=True)


if __name__ == "__main__":
    main()
