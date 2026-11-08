# -*- coding: utf-8 -*-
"""调色台 —— 纯 tkinter 实现的取色 / 调色小工具。

左边是色相-饱和度色轮，右边是七条渐变滑条
（色相 / 饱和度 / 明度 / 红 / 绿 / 蓝 / 不透明度），
每条滑条右边都有数字框，可以直接输入精确值。
实时输出 HEX、RGB、RGBA 三种编码，一键复制。

运行：python 调色台_ai.py
依赖：仅 Python 标准库（tkinter）
"""

import ctypes
import math
import random
import tkinter as tk
from pathlib import Path

# ---------------------------------------------------------------- 主题

BG = "#121318"          # 窗口底色
CARD = "#1b1c23"        # 卡片底色
CARD_HI = "#262835"     # 输入框 / 按钮底色
LINE = "#343748"        # 描边
TEXT = "#e9eaf2"
MUTED = "#8b90a3"
ACCENT = "#5b8cff"
CHECK_A = "#3a3d4e"     # 棋盘格亮格
CHECK_B = "#23252f"     # 棋盘格暗格

FONT_UI = "Microsoft YaHei UI"
FONT_MONO = "Consolas"

# 系统缩放系数，在 main() 里按屏幕 DPI 覆盖（高分屏下 1 逻辑像素 != 1 物理像素）
SCALE = 1.0


def px(value):
    """把设计稿上的逻辑像素换算成当前屏幕的物理像素。"""
    return int(round(value * SCALE))


def font(size, weight="normal", family=FONT_UI):
    """字号用负数表示像素，这样不受 tk 的磅值缩放影响。"""
    return (family, -px(size), weight)


# ---------------------------------------------------------------- 颜色换算

def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value


def hsv_to_rgb(hue, sat, val):
    """HSV(色相 0-360, 饱和度 0-1, 明度 0-1) -> RGB 三元组(0-255 整数)"""
    hue = hue % 360.0
    h = hue / 60.0
    sector = int(h)
    f = h - sector
    p = val * (1.0 - sat)
    q = val * (1.0 - sat * f)
    t = val * (1.0 - sat * (1.0 - f))
    if sector == 0:
        r, g, b = val, t, p
    elif sector == 1:
        r, g, b = q, val, p
    elif sector == 2:
        r, g, b = p, val, t
    elif sector == 3:
        r, g, b = p, q, val
    elif sector == 4:
        r, g, b = t, p, val
    else:
        r, g, b = val, p, q
    return (int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5))


def rgb_to_hsv(red, green, blue):
    """RGB(0-255) -> (色相 0-360, 饱和度 0-1, 明度 0-1)"""
    r, g, b = red / 255.0, green / 255.0, blue / 255.0
    high = max(r, g, b)
    low = min(r, g, b)
    delta = high - low
    if delta == 0:
        hue = 0.0
    elif high == r:
        hue = (60.0 * ((g - b) / delta) + 360.0) % 360.0
    elif high == g:
        hue = 60.0 * ((b - r) / delta) + 120.0
    else:
        hue = 60.0 * ((r - g) / delta) + 240.0
    sat = 0.0 if high == 0 else delta / high
    return hue, sat, high


def hx(rgb):
    """RGB 三元组 -> '#rrggbb' 字符串。"""
    r, g, b = (int(clamp(v, 0, 255) + 0.5) for v in rgb)
    return "#%02x%02x%02x" % (r, g, b)


def to_hex(rgb, alpha=None):
    """RGB -> 大写 HEX；给了 alpha 就输出 8 位 HEX（含透明度）。"""
    text = "#%02X%02X%02X" % tuple(int(clamp(v, 0, 255) + 0.5) for v in rgb)
    if alpha is not None:
        text += "%02X" % int(round(clamp(alpha, 0.0, 1.0) * 255))
    return text


def hex_to_rgb(text):
    """'#3f8cff' -> (63, 140, 255)"""
    text = text.strip().lstrip("#")
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def mix(color_a, color_b, ratio):
    """两色线性混合，ratio=0 得 color_a，ratio=1 得 color_b。"""
    return tuple(a + (b - a) * ratio for a, b in zip(color_a, color_b))


def alpha_text(alpha):
    """0.85 -> '0.85'，1.0 -> '1'，0.5 -> '0.5'"""
    text = ("%.2f" % alpha).rstrip("0").rstrip(".")
    return text or "0"


# ---------------------------------------------------------------- 色轮

def build_wheel_photo(size, background, radius):
    """逐像素画一张色相环：角度=色相，半径=饱和度，明度固定 100%。"""
    image = tk.PhotoImage(width=size, height=size)
    center = (size - 1) / 2.0
    reach = radius * radius
    backdrop = hex_to_rgb(background)
    rows = []
    for y in range(size):
        dy = y - center
        dy2 = dy * dy
        line = []
        for x in range(size):
            dx = x - center
            dist2 = dx * dx + dy2
            if dist2 > reach + radius * 2 + 4:
                line.append(background)
                continue
            dist = math.sqrt(dist2)
            hue = math.degrees(math.atan2(dy, dx)) % 360.0
            red, green, blue = hsv_to_rgb(hue, min(dist / radius, 1.0), 1.0)
            # 边缘一像素内和底色混合，避免锯齿
            cover = radius + 0.5 - dist
            if cover < 1.0:
                ratio = clamp(cover, 0.0, 1.0)
                red, green, blue = mix(backdrop, (red, green, blue), ratio)
            line.append(hx((red, green, blue)))
        rows.append("{" + " ".join(line) + "}")
    image.put(" ".join(rows))
    return image


class ColorWheel(tk.Canvas):
    """色轮：按住拖动即可同时改变色相和饱和度。"""

    def __init__(self, master, size, on_pick):
        super().__init__(master, width=size, height=size, bg=CARD,
                         highlightthickness=0, bd=0, cursor="crosshair")
        self.on_pick = on_pick
        self.center = (size - 1) / 2.0
        self.radius = size / 2.0 - px(5)

        self._photo = build_wheel_photo(size, CARD, self.radius)
        self.create_image(0, 0, image=self._photo, anchor="nw")

        self._ring = self.create_oval(0, 0, 0, 0, outline="#ffffff", width=px(2), state="hidden")
        self._dot = self.create_oval(0, 0, 0, 0, outline="#000000", width=0, state="hidden")

        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)

    def _on_pointer(self, event):
        dx = event.x - self.center
        dy = event.y - self.center
        dist = math.hypot(dx, dy)
        hue = math.degrees(math.atan2(dy, dx)) % 360.0
        sat = clamp(dist / self.radius, 0.0, 1.0)
        self.on_pick(hue, sat)

    def set_marker(self, hue, sat, rgb):
        """把选中点画到色轮上，并用当前颜色填充。"""
        angle = math.radians(hue)
        dist = clamp(sat, 0.0, 1.0) * self.radius
        x = self.center + math.cos(angle) * dist
        y = self.center + math.sin(angle) * dist

        outer = px(9)
        self.coords(self._ring, x - outer, y - outer, x + outer, y + outer)
        inner = px(6)
        self.coords(self._dot, x - inner, y - inner, x + inner, y + inner)
        self.itemconfig(self._dot, fill=hx(rgb))
        self.itemconfig(self._ring, state="normal")
        self.itemconfig(self._dot, state="normal")


# ---------------------------------------------------------------- 预览

class ColorPreview(tk.Canvas):
    """棋盘格背景 + 半透明色块，直观看出透明度效果。"""

    def __init__(self, master, width, height, tile=14):
        self.tile = max(2, px(tile))
        self.cols = max(1, width // self.tile)
        self.rows = max(1, height // self.tile)
        super().__init__(master, width=self.cols * self.tile, height=self.rows * self.tile,
                         bg=CARD, highlightthickness=0, bd=0)
        self._image = None
        self._item = self.create_image(0, 0, anchor="nw")
        self.create_rectangle(0, 0, self.cols * self.tile - 1, self.rows * self.tile - 1,
                              outline=LINE, width=px(1))

    def set_color(self, rgb, alpha):
        light = hex_to_rgb(CHECK_A)
        dark = hex_to_rgb(CHECK_B)
        alpha = clamp(alpha, 0.0, 1.0)
        rows = []
        for row in range(self.rows):
            line = []
            for col in range(self.cols):
                base = light if (row + col) % 2 == 0 else dark
                line.append(hx(mix(base, rgb, alpha)))
            rows.append("{" + " ".join(line) + "}")

        image = tk.PhotoImage(master=self, width=self.cols, height=self.rows)
        image.put(" ".join(rows))
        image = image.zoom(self.tile, self.tile)
        self._image = image
        self.itemconfig(self._item, image=self._image)


# ---------------------------------------------------------------- 滑条

class GradientSlider(tk.Frame):
    """一条带渐变色轨道的滑条，右边配一个可以打字进去的数字框。"""

    def __init__(self, master, title, minimum, maximum, value,
                 on_change, gradient, number_format, width):
        super().__init__(master, bg=CARD)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.current = float(value)
        self.on_change = on_change
        self.gradient = gradient
        self.number_format = number_format

        self.track_width = px(width)
        self.track_height = px(10)
        self.track_top = px(8)
        self.knob_y = px(13)
        self.knob_radius = px(7)
        self.padding = px(9)
        self._image = None

        self.label = tk.Label(self, text=title, bg=CARD, fg=MUTED,
                              font=font(12), anchor="w")
        self.label.grid(row=0, column=0, sticky="w", padx=(0, px(8)))

        self.canvas = tk.Canvas(self, width=self.track_width, height=px(26), bg=CARD,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.grid(row=0, column=1, sticky="w")

        self.entry = tk.Entry(self, width=5, justify="center", bg=CARD_HI, fg=TEXT,
                              insertbackground=TEXT, font=font(12, family=FONT_MONO),
                              relief="flat", bd=0,
                              highlightthickness=px(1),
                              highlightbackground=LINE, highlightcolor=ACCENT)
        self.entry.grid(row=0, column=2, sticky="e", padx=(px(10), 0))

        self.grid_columnconfigure(0, minsize=px(46))
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(0, weight=1)      # 行高富余时内容保持垂直居中

        self._knob = self.canvas.create_oval(0, 0, 0, 0, fill="#ffffff",
                                             outline="#0e0f15", width=px(2))

        self.refresh_gradient()
        self._move_knob()
        self._show_in_entry()

        for event, handler in (("<Button-1>", self._on_press),
                               ("<B1-Motion>", self._on_drag),
                               ("<MouseWheel>", self._on_wheel)):
            self.canvas.bind(event, handler)
        self.entry.bind("<Return>", self._commit)
        self.entry.bind("<KP_Enter>", self._commit)
        self.entry.bind("<FocusOut>", self._commit)

    # ---- 外观 ----

    def refresh_gradient(self):
        """按当前颜色重画轨道渐变。轨道的颜色依赖主窗口的状态。"""
        width = self.track_width
        half = max(2, width // 2)
        cells = []
        for index in range(half):
            ratio = index / (half - 1)
            cells.append(hx(self.gradient(ratio)))
        image = tk.PhotoImage(master=self.canvas, width=half, height=1)
        image.put("{" + " ".join(cells) + "}")
        image = image.zoom(2, self.track_height)
        self._image = image
        if not self._track_item_exists():
            self._track_item = self.canvas.create_image(
                0, self.track_top, image=image, anchor="nw")
        else:
            self.canvas.itemconfig(self._track_item, image=image)
        self.canvas.tag_lower(self._track_item)
        self.canvas.tag_raise(self._knob)

    def _track_item_exists(self):
        try:
            return bool(self.canvas.itemconfigure(self._track_item))
        except (AttributeError, tk.TclError):
            return False

    def _move_knob(self):
        span = self.maximum - self.minimum
        ratio = 0.0 if span == 0 else (self.current - self.minimum) / span
        x = self.padding + ratio * (self.track_width - 2 * self.padding)
        r = self.knob_radius
        self.canvas.coords(self._knob, x - r, self.knob_y - r, x + r, self.knob_y + r)

    def _show_in_entry(self):
        try:
            focused = self.focus_get() is self.entry
        except (tk.TclError, KeyError):
            focused = False
        if focused:
            return
        self.entry.delete(0, "end")
        self.entry.insert(0, self.number_format.format(self.current))

    # ---- 数值 ----

    def set_value(self, value, notify=False):
        self.current = clamp(float(value), self.minimum, self.maximum)
        self._move_knob()
        self._show_in_entry()
        if notify and self.on_change is not None:
            self.on_change(self.current)

    def _value_from_x(self, x):
        span = self.maximum - self.minimum
        usable = max(1, self.track_width - 2 * self.padding)
        ratio = clamp((x - self.padding) / usable, 0.0, 1.0)
        return self.minimum + ratio * span

    # ---- 交互 ----

    def _on_press(self, event):
        self.set_value(self._value_from_x(event.x), notify=True)

    def _on_drag(self, event):
        self.set_value(self._value_from_x(event.x), notify=True)

    def _on_wheel(self, event):
        step = (self.maximum - self.minimum) / 100.0
        delta = step if event.delta > 0 else -step
        self.set_value(self.current + delta, notify=True)
        return "break"

    def _commit(self, event=None):
        text = self.entry.get().strip()
        for symbol in ("%", "°", " ", ","):
            text = text.replace(symbol, "")
        try:
            value = float(text)
        except ValueError:
            self._show_in_entry()
            return "break"
        self.set_value(value, notify=True)
        return "break"


# ---------------------------------------------------------------- 色板

class PaletteStrip(tk.Canvas):
    """一排常用颜色，点一下就套用。"""

    def __init__(self, master, colors, on_pick, columns=9, swatch=30, gap=6):
        size = px(swatch)
        space = px(gap)
        rows = math.ceil(len(colors) / columns)
        width = columns * size + (columns - 1) * space
        height = rows * size + (rows - 1) * space
        super().__init__(master, width=width, height=height, bg=CARD,
                         highlightthickness=0, bd=0)
        for index, color in enumerate(colors):
            row, col = divmod(index, columns)
            x0 = col * (size + space)
            y0 = row * (size + space)
            item = self.create_rectangle(x0, y0, x0 + size, y0 + size,
                                         fill=color, outline="", width=0)
            self.tag_bind(item, "<Button-1>", lambda e, c=color: on_pick(c))
            self.tag_bind(item, "<Enter>",
                          lambda e, i=item: self.itemconfig(i, outline="#ffffff", width=px(2)))
            self.tag_bind(item, "<Leave>",
                          lambda e, i=item: self.itemconfig(i, outline="", width=0))


PRESETS = [
    "#F25F5C", "#F08A5D", "#F6C453", "#8AC926", "#4CB944",
    "#2EC4B6", "#4CC9F0", "#4361EE", "#6C63FF",
    "#9B5DE5", "#E056A0", "#FF6B6B", "#FFFFFF", "#C9CDD8",
    "#8A8F9E", "#4A4F5C", "#23262F", "#000000",
]


# ---------------------------------------------------------------- 主界面

def flat_button(master, text, command, accent=False):
    background = ACCENT if accent else CARD_HI
    hover = "#7ba3ff" if accent else "#33374a"
    button = tk.Button(master, text=text, command=command, font=font(12),
                       bg=background, fg="#ffffff" if accent else TEXT,
                       activebackground=hover, activeforeground="#ffffff",
                       relief="flat", bd=0, highlightthickness=0,
                       padx=px(14), pady=px(5), cursor="hand2")
    button.bind("<Enter>", lambda e: button.configure(bg=hover))
    button.bind("<Leave>", lambda e: button.configure(bg=background))
    return button


class ColorStudio:
    """主窗口：状态只存 HSV + alpha，RGB 由它实时算出来。"""

    def __init__(self, root):
        self.root = root
        self.hue = 216.0
        self.sat = 0.85
        self.val = 1.0
        self.alpha = 0.85
        self._build()
        self.refresh()

    # ---- 布局 ----

    def _section(self, master, text):
        return tk.Label(master, text=text, bg=CARD, fg=MUTED, font=font(11))

    def _build(self):
        self.root.configure(bg=BG)
        self.root.title("调色台 · Color Studio")
        self.root.resizable(False, False)

        body = tk.Frame(self.root, bg=BG)
        body.pack(padx=px(18), pady=px(18))

        left = tk.Frame(body, bg=CARD, width=px(380), height=px(600))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        right = tk.Frame(body, bg=CARD, width=px(640), height=px(600))
        right.pack(side="left", fill="y", padx=(px(16), 0))
        right.pack_propagate(False)

        self._build_left(left)
        self._build_right(right)

    def _build_left(self, card):
        panel = tk.Frame(card, bg=CARD)
        panel.pack(fill="both", expand=True, padx=px(20), pady=px(16))

        self._section(panel, "调色盘").pack(anchor="w")

        self.wheel = ColorWheel(panel, px(300), self._on_wheel)
        self.wheel.pack(pady=(px(8), px(6)))

        self.hex_var = tk.StringVar()
        self.rgba_var = tk.StringVar()
        self.hex8_var = tk.StringVar()

        tk.Label(panel, textvariable=self.hex_var, bg=CARD, fg=TEXT,
                 font=font(26, "bold", FONT_MONO)).pack(anchor="w")
        tk.Label(panel, textvariable=self.rgba_var, bg=CARD, fg=MUTED,
                 font=font(11, family=FONT_MONO)).pack(anchor="w", pady=(px(2), 0))
        tk.Label(panel, textvariable=self.hex8_var, bg=CARD, fg=MUTED,
                 font=font(11, family=FONT_MONO)).pack(anchor="w")

        buttons = tk.Frame(panel, bg=CARD)
        buttons.pack(fill="x", pady=(px(12), 0))
        self.hex_button = flat_button(buttons, "复制 HEX", self._copy_hex)
        self.hex_button.pack(side="left")
        self.rgba_button = flat_button(buttons, "复制 RGBA", self._copy_rgba)
        self.rgba_button.pack(side="left", padx=(px(8), 0))

        self._section(panel, "常用色").pack(anchor="w", pady=(px(16), px(8)))
        PaletteStrip(panel, PRESETS, self._on_preset).pack(anchor="w")

    def _build_right(self, card):
        panel = tk.Frame(card, bg=CARD)
        panel.pack(fill="both", expand=True, padx=px(22), pady=px(16))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        head = tk.Frame(panel, bg=CARD)
        head.grid(row=0, column=0, sticky="ew")
        self._section(head, "预览").pack(side="left")
        tk.Label(head, text="拖动色轮取色，滑条右侧可直接输入数值",
                 bg=CARD, fg=MUTED, font=font(11)).pack(side="right")

        self.preview = ColorPreview(panel, px(588), px(130))
        self.preview.grid(row=1, column=0, sticky="w", pady=(px(10), px(16)))

        sliders = tk.Frame(panel, bg=CARD)
        sliders.grid(row=2, column=0, sticky="nsew")
        sliders.grid_columnconfigure(0, weight=1)
        for row in range(7):
            sliders.grid_rowconfigure(row, weight=1)

        def current_rgb():
            return hsv_to_rgb(self.hue, self.sat, self.val)

        self.sl_hue = GradientSlider(
            sliders, "色相", 0, 360, self.hue, self._on_hue,
            lambda t: hsv_to_rgb(t * 360.0, 1.0, 1.0), "{:.0f}°", 460)
        self.sl_sat = GradientSlider(
            sliders, "饱和", 0, 100, self.sat * 100, self._on_sat,
            lambda t: hsv_to_rgb(self.hue, t, max(self.val, 0.18)), "{:.0f}%", 460)
        self.sl_val = GradientSlider(
            sliders, "明度", 0, 100, self.val * 100, self._on_val,
            lambda t: hsv_to_rgb(self.hue, self.sat, t), "{:.0f}%", 460)
        self.sl_red = GradientSlider(
            sliders, "红色", 0, 255, 0, self._on_red,
            lambda t: (t * 255.0, current_rgb()[1], current_rgb()[2]), "{:.0f}", 460)
        self.sl_green = GradientSlider(
            sliders, "绿色", 0, 255, 0, self._on_green,
            lambda t: (current_rgb()[0], t * 255.0, current_rgb()[2]), "{:.0f}", 460)
        self.sl_blue = GradientSlider(
            sliders, "蓝色", 0, 255, 0, self._on_blue,
            lambda t: (current_rgb()[0], current_rgb()[1], t * 255.0), "{:.0f}", 460)
        self.sl_alpha = GradientSlider(
            sliders, "不透明", 0, 100, self.alpha * 100, self._on_alpha,
            lambda t: mix(hex_to_rgb(CARD), current_rgb(), t), "{:.0f}%", 460)

        for index, slider in enumerate((self.sl_hue, self.sl_sat, self.sl_val,
                                        self.sl_red, self.sl_green, self.sl_blue,
                                        self.sl_alpha)):
            slider.grid(row=index, column=0, sticky="ew")

        bottom = tk.Frame(panel, bg=CARD)
        bottom.grid(row=3, column=0, sticky="ew", pady=(px(12), 0))
        flat_button(bottom, "随机颜色", self._randomize).pack(side="left")
        flat_button(bottom, "恢复默认", self._reset).pack(side="left", padx=(px(8), 0))
        tk.Label(bottom, text="点数字框可修改 · 滚轮微调滑条",
                 bg=CARD, fg=MUTED, font=font(11)).pack(side="right")

    # ---- 状态同步 ----

    def _rgb(self):
        return hsv_to_rgb(self.hue, self.sat, self.val)

    def refresh(self, skip=None):
        red, green, blue = self._rgb()

        if skip != "hue":
            self.sl_hue.set_value(self.hue)
        if skip != "sat":
            self.sl_sat.set_value(self.sat * 100)
        if skip != "val":
            self.sl_val.set_value(self.val * 100)
        if skip != "red":
            self.sl_red.set_value(red)
        if skip != "green":
            self.sl_green.set_value(green)
        if skip != "blue":
            self.sl_blue.set_value(blue)
        if skip != "alpha":
            self.sl_alpha.set_value(self.alpha * 100)

        self.wheel.set_marker(self.hue, self.sat, (red, green, blue))
        self.preview.set_color((red, green, blue), self.alpha)

        self.hex_var.set(to_hex((red, green, blue)))
        self.rgba_var.set("rgba(%d, %d, %d, %s)" % (red, green, blue, alpha_text(self.alpha)))
        self.hex8_var.set("8 位 HEX  " + to_hex((red, green, blue), self.alpha))

        for slider in (self.sl_sat, self.sl_val, self.sl_red,
                       self.sl_green, self.sl_blue, self.sl_alpha):
            slider.refresh_gradient()

    def _apply_rgb(self, red, green, blue, skip=None):
        hue, sat, val = rgb_to_hsv(red, green, blue)
        if sat <= 0.001:          # 灰色没有色相，沿用上一次的
            hue = self.hue
        if val <= 0.001:          # 黑色没有饱和度，沿用上一次的
            sat = self.sat
        self.hue, self.sat, self.val = hue, sat, val
        self.refresh(skip=skip)

    # ---- 回调 ----

    def _on_wheel(self, hue, sat):
        self.hue, self.sat = hue, sat
        self.refresh()

    def _on_hue(self, value):
        self.hue = value % 360.0
        self.refresh(skip="hue")

    def _on_sat(self, value):
        self.sat = clamp(value / 100.0, 0.0, 1.0)
        self.refresh(skip="sat")

    def _on_val(self, value):
        self.val = clamp(value / 100.0, 0.0, 1.0)
        self.refresh(skip="val")

    def _on_red(self, value):
        _, green, blue = self._rgb()
        self._apply_rgb(value, green, blue, skip="red")

    def _on_green(self, value):
        red, _, blue = self._rgb()
        self._apply_rgb(red, value, blue, skip="green")

    def _on_blue(self, value):
        red, green, _ = self._rgb()
        self._apply_rgb(red, green, value, skip="blue")

    def _on_alpha(self, value):
        self.alpha = clamp(value / 100.0, 0.0, 1.0)
        self.refresh(skip="alpha")

    def _on_preset(self, color_text):
        red, green, blue = hex_to_rgb(color_text)
        self._apply_rgb(red, green, blue)

    def _randomize(self):
        self.hue = random.uniform(0.0, 360.0)
        self.sat = random.uniform(0.45, 1.0)
        self.val = random.uniform(0.75, 1.0)
        self.refresh()

    def _reset(self):
        self.hue, self.sat, self.val, self.alpha = 216.0, 0.85, 1.0, 0.85
        self.refresh()

    # ---- 输出 ----

    def _copy(self, text, button, original):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        button.configure(text="已复制")
        self.root.after(1000, lambda: button.configure(text=original))

    def _copy_hex(self):
        red, green, blue = self._rgb()
        self._copy(to_hex((red, green, blue)), self.hex_button, "复制 HEX")

    def _copy_rgba(self):
        red, green, blue = self._rgb()
        self._copy("rgba(%d, %d, %d, %s)" % (red, green, blue, alpha_text(self.alpha)),
                   self.rgba_button, "复制 RGBA")


def enable_dark_title_bar(root):
    """把 Windows 自带的标题栏改成深色，和窗口内容配色一致。"""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        enabled = ctypes.c_int(1)
        for attribute in (20, 19):          # Win11 用 20，旧版本用 19
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled))
            if result == 0:
                break
    except Exception:
        pass


def apply_window_icon(root):
    """同目录下有图标 PNG 就用作窗口和任务栏图标，没有就跳过。"""
    try:
        icon_file = Path(__file__).with_name("调色台_ai_icon.png")
        if icon_file.exists():
            root.iconphoto(True, tk.PhotoImage(file=str(icon_file)))
    except Exception:
        pass


def main():
    global SCALE
    try:  # 让窗口在高分屏上按物理像素渲染，文字才清晰
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    SCALE = max(1.0, root.winfo_fpixels("1i") / 96.0)

    apply_window_icon(root)
    ColorStudio(root)
    enable_dark_title_bar(root)

    root.update_idletasks()
    width = root.winfo_reqwidth()
    height = root.winfo_reqheight()
    x = (root.winfo_screenwidth() - width) // 2
    y = max(0, (root.winfo_screenheight() - height) // 2 - px(30))
    root.geometry("+%d+%d" % (x, y))

    root.attributes("-topmost", True)
    root.after(300, lambda: root.attributes("-topmost", False))
    root.mainloop()


if __name__ == "__main__":
    main()
