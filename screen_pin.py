
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Screen Pin 2.5

功能：
1. F8 全局快捷键截图
2. 鼠标框选区域
3. 多张截图独立悬浮
4. Header 任意空白区域拖动图片
5. Header 按钮根据窗口宽度自动显示/隐藏
6. 置顶 / 取消置顶
7. 红色画笔（单按钮开关）
8. 橡皮擦
9. 撤销
10. 图片边缘横向/纵向拉伸
11. 图片区域拖动移动
12. 右下角等比例缩放
12. 截图和涂鸦完成后自动复制最新图片到 Windows 剪贴板
13. 自动保存到本地目录
14. 独立关闭贴图
"""

import os
import ctypes
from pathlib import Path
from datetime import datetime
from io import BytesIO

import tkinter as tk
from tkinter import filedialog, messagebox

import mss
from PIL import Image, ImageTk, ImageDraw, ImageChops


# =========================================================
# DPI 设置
# =========================================================

def enable_dpi_awareness():

    if os.name != "nt":
        return

    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(
            ctypes.c_void_p(-4)
        )
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


enable_dpi_awareness()


# =========================================================
# 全局配置
# =========================================================

APP_NAME = "Screen Pin 2.5"

SAVE_DIR = Path.home() / "Pictures" / "ScreenPin"

BRUSH_WIDTH = 3
ERASER_WIDTH = 20

MIN_WIDTH = 120
MIN_HEIGHT = 80
EDGE_RESIZE_MARGIN = 7

TOOLBAR_HEIGHT = 28
RESIZE_HEIGHT = 10

# 紧凑 Header 参数
HEADER_PADX = 1
HEADER_BG = "#20242C"
BUTTON_BG = "#303744"
BUTTON_HOVER_BG = "#414B5B"
BUTTON_ACTIVE_BG = "#8B3D43"
BUTTON_FG = "#E8EDF5"
CLOSE_BG = "#71383D"
CLOSE_HOVER_BG = "#A9444B"
CLOSE_BUTTON_WIDTH = 25


# =========================================================
# 绘图工具
# =========================================================

def draw_stroke(draw, points, color, width):

    if not points:
        return

    if len(points) == 1:

        x, y = points[0]

        draw.ellipse(
            (
                x - width / 2,
                y - width / 2,
                x + width / 2,
                y + width / 2
            ),
            fill=color
        )

    else:

        draw.line(
            points,
            fill=color,
            width=width,
            joint="curve"
        )


# =========================================================
# 主程序
# =========================================================

class ScreenPinApp:

    def __init__(self):

        self.root = tk.Tk()
        self.root.withdraw()

        self.root.title(APP_NAME)

        self.pins = []
        self.selecting = False

        SAVE_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.start_hotkey_listener()

    # =====================================================
    # 全局快捷键
    # =====================================================

    def start_hotkey_listener(self):

        if os.name == "nt":
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            comctl32 = ctypes.windll.comctl32
            hwnd = self.root.winfo_id()
            hotkey_id = 1
            wm_hotkey = 0x0312
            mod_norepeat = 0x4000
            vk_f8 = 0x77

            result_type = ctypes.c_ssize_t
            subclass_proc = ctypes.WINFUNCTYPE(
                result_type, wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t
            )
            comctl32.SetWindowSubclass.argtypes = (
                wintypes.HWND, subclass_proc, ctypes.c_size_t, ctypes.c_size_t
            )
            comctl32.RemoveWindowSubclass.argtypes = (
                wintypes.HWND, subclass_proc, ctypes.c_size_t
            )
            comctl32.DefSubclassProc.argtypes = (
                wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
            )
            comctl32.DefSubclassProc.restype = result_type
            user32.RegisterHotKey.argtypes = (
                wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT
            )
            user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)

            @subclass_proc
            def on_window_message(window, message, wparam, lparam, subclass_id, data):
                if message == wm_hotkey and wparam == hotkey_id:
                    self.root.after_idle(self.start_selection)
                    return 0
                return comctl32.DefSubclassProc(window, message, wparam, lparam)

            if not comctl32.SetWindowSubclass(hwnd, on_window_message, hotkey_id, 0):
                raise RuntimeError("无法初始化 F8 截图快捷键。")

            def stop():
                user32.UnregisterHotKey(hwnd, hotkey_id)
                comctl32.RemoveWindowSubclass(hwnd, on_window_message, hotkey_id)

            if not user32.RegisterHotKey(hwnd, hotkey_id, mod_norepeat, vk_f8):
                stop()
                raise RuntimeError("无法注册 F8 截图快捷键，可能已被其他程序占用。")

            self.stop_hotkey_listener = stop
            return

        from Xlib import X, XK, display, error

        connection = display.Display()
        desktop = connection.screen().root
        keycode = connection.keysym_to_keycode(XK.XK_F8)
        lock_keys = {
            XK.string_to_keysym(name)
            for name in ("Caps_Lock", "Num_Lock", "Scroll_Lock")
        }
        modifiers = {0}
        for index, keycodes in enumerate(connection.get_modifier_mapping()):
            if any(connection.keycode_to_keysym(code, 0) in lock_keys for code in keycodes if code):
                modifiers |= {mask | (1 << index) for mask in modifiers}

        grab_error = error.CatchError(error.BadAccess)
        for mask in modifiers:
            desktop.grab_key(keycode, mask, False, X.GrabModeAsync, X.GrabModeAsync,
                             onerror=grab_error)
        connection.sync()
        if grab_error.get_error():
            connection.close()
            raise RuntimeError("无法注册 F8 截图快捷键，可能已被其他程序占用。")

        # An application can already own an active keyboard grab (for example
        # while displaying a menu). XRecord still observes F8 in that case.
        from pynput import keyboard

        modifier_keys = {
            keyboard.Key.alt, keyboard.Key.alt_gr, keyboard.Key.ctrl,
            keyboard.Key.shift, keyboard.Key.cmd,
        }
        held_modifiers = set()
        f8_pressed = False

        def on_press(key):
            nonlocal f8_pressed
            canonical = listener.canonical(key)
            if canonical in modifier_keys:
                held_modifiers.add(key)
            elif key == keyboard.Key.f8 and not f8_pressed:
                f8_pressed = True
                if not held_modifiers:
                    self.root.after(0, self.start_selection)

        def on_release(key):
            nonlocal f8_pressed
            held_modifiers.discard(key)
            if key == keyboard.Key.f8:
                f8_pressed = False

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()

        def drain_grab_events(file, mask):
            while connection.pending_events():
                connection.next_event()

        self.root.createfilehandler(connection.fileno(), tk.READABLE, drain_grab_events)

        def stop():
            listener.stop()
            self.root.deletefilehandler(connection.fileno())
            connection.close()

        self.stop_hotkey_listener = stop

    # =====================================================
    # 区域截图
    # =====================================================

    def start_selection(self):

        if self.selecting:
            return

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                screenshot = sct.grab(monitor)
                self.selection_image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        except Exception as e:
            messagebox.showerror("截图失败", str(e))
            return

        self.selecting = True
        self.selection_origin = monitor["left"], monitor["top"]
        width, height = self.selection_image.size

        self.selector = tk.Toplevel(self.root)
        self.selector.overrideredirect(True)

        # A leading "+" makes negative offsets absolute virtual-desktop coordinates.
        left, top = self.selection_origin
        self.selector.geometry(f"{width}x{height}+{left}+{top}")

        self.selector.attributes("-topmost", True)

        self.selector.configure(bg="black")

        self.canvas = tk.Canvas(
            self.selector,
            bg="black",
            highlightthickness=0,
            cursor="cross"
        )

        self.canvas.pack(fill="both", expand=True)

        self.selection_preview = ImageTk.PhotoImage(self.selection_image)
        self.canvas.create_image(0, 0, anchor="nw", image=self.selection_preview)

        self.canvas.create_text(
            25,
            25,
            anchor="nw",
            text="F8 截图 | 鼠标左键框选 | ESC 取消",
            fill="white",
            font=("Microsoft YaHei", 13)
        )

        self.selection_rect = None

        self.start_x = 0
        self.start_y = 0

        self.canvas.bind(
            "<ButtonPress-1>",
            self.on_mouse_down
        )

        self.canvas.bind(
            "<B1-Motion>",
            self.on_mouse_move
        )

        self.canvas.bind(
            "<ButtonRelease-1>",
            self.on_mouse_up
        )

        self.selector.bind(
            "<Escape>",
            self.cancel_selection
        )

        self.selector.focus_force()

    def on_mouse_down(self, event):

        self.start_x = event.x_root
        self.start_y = event.y_root

        self.selection_rect = self.canvas.create_rectangle(
            event.x,
            event.y,
            event.x,
            event.y,
            outline="#00FF66",
            width=2
        )

    def on_mouse_move(self, event):

        if self.selection_rect is None:
            return

        self.canvas.coords(
            self.selection_rect,
            self.start_x - self.selector.winfo_rootx(),
            self.start_y - self.selector.winfo_rooty(),
            event.x,
            event.y
        )

    def on_mouse_up(self, event):

        left, top = self.selection_origin
        image = self.selection_image
        x1 = max(0, min(self.start_x, event.x_root) - left)
        y1 = max(0, min(self.start_y, event.y_root) - top)
        x2 = min(image.width, max(self.start_x, event.x_root) - left)
        y2 = min(image.height, max(self.start_y, event.y_root) - top)

        self.cancel_selection()

        if x2 - x1 < 5 or y2 - y1 < 5:
            return

        try:
            self.create_pin(image.crop((x1, y1, x2, y2)), left + x1, top + y1)
        except Exception as e:
            messagebox.showerror("截图失败", str(e))

    def cancel_selection(self, event=None):

        if self.selecting:

            self.selector.destroy()

            self.selecting = False
            self.selection_rect = None
            self.selection_preview = None
            self.selection_image = None

    # =====================================================
    # 自动保存路径
    # =====================================================

    def get_auto_save_path(self):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        return SAVE_DIR / f"ScreenPin_{timestamp}.png"

    # =====================================================
    # 创建贴图
    # =====================================================

    def create_pin(self, image, x, y):

        pin = ScreenPin(
            self,
            image,
            x,
            y
        )

        self.pins.append(pin)

        # 新截图完成后，自动把最新截图复制到系统剪贴板
        pin.copy_to_clipboard()

    def run(self):

        try:
            self.root.mainloop()
        finally:
            self.stop_hotkey_listener()


# =========================================================
# 独立截图窗口
# =========================================================

class ScreenPin:

    def __init__(self, app, image, x, y):

        self.app = app

        self.original_image = image.convert("RGB").copy()

        self.width = image.width
        self.height = image.height

        self.display_width = image.width
        self.display_height = image.height

        self.x = x
        self.y = y

        self.current_tool = "move"
        self.current_color = "#FF0000"

        self.brush_width = BRUSH_WIDTH
        self.eraser_width = ERASER_WIDTH

        self.strokes = []
        self.current_stroke = None

        self.is_topmost = True

        self.drag_offset_x = 0
        self.drag_offset_y = 0

        self.resizing = False
        self.edge_resize_mode = None
        self.edge_resize_start_x = 0
        self.edge_resize_start_y = 0
        self.edge_resize_start_width = self.display_width
        self.edge_resize_start_height = self.display_height
        self.edge_resize_start_window_x = x
        self.edge_resize_start_window_y = y
        self.image_dragging = False

        self.auto_save_path = app.get_auto_save_path()

        self.window = tk.Toplevel(app.root)

        self.window.overrideredirect(True)

        self.window.attributes("-topmost", True)

        self.window.configure(bg=HEADER_BG)

        self.window.geometry(
            f"{self.display_width}x"
            f"{self.display_height + TOOLBAR_HEIGHT + RESIZE_HEIGHT}"
            f"+{x}+{y}"
        )

        self.create_interface()

        self.render_image()

        self.auto_save()

    # =====================================================
    # Header 界面（紧凑图标工具栏）
    # =====================================================

    def create_interface(self):

        self.toolbar = tk.Frame(
            self.window,
            bg=HEADER_BG,
            height=TOOLBAR_HEIGHT
        )
        self.toolbar.pack(side="top", fill="x")
        self.toolbar.pack_propagate(False)

        self.header_buttons = {}

        # 左侧拖动手柄：保留很小的占用宽度
        self.drag_handle = tk.Label(
            self.toolbar,
            text="⠿",
            fg="#AAB4C3",
            bg=HEADER_BG,
            font=("Segoe UI Symbol", 11),
            cursor="fleur",
            padx=4
        )
        self.drag_handle.pack(side="left")

        # Header 空白区域可拖动；按钮自身不绑定拖动事件
        self.toolbar.bind("<ButtonPress-1>", self.start_drag)
        self.toolbar.bind("<B1-Motion>", self.move_window)
        self.drag_handle.bind("<ButtonPress-1>", self.start_drag)
        self.drag_handle.bind("<B1-Motion>", self.move_window)

        # 置顶
        self.top_button = self.create_header_button(
            "top", "⌖", self.toggle_topmost, tooltip="置顶/取消置顶"
        )

        # 单一画笔按钮：默认红色，再次点击退出涂鸦
        self.pen_button = self.create_header_button(
            "pen", "✎", self.toggle_pen, tooltip="红色画笔"
        )

        # 橡皮擦
        self.eraser_button = self.create_header_button(
            "eraser", "▱", self.use_eraser, tooltip="橡皮擦"
        )

        # 撤销
        self.undo_button = self.create_header_button(
            "undo", "↶", self.undo, tooltip="撤销"
        )

        # 关闭按钮始终显示
        self.close_button = tk.Button(
            self.toolbar,
            text="×",
            command=self.destroy,
            bg=CLOSE_BG,
            fg="#FFFFFF",
            activebackground=CLOSE_HOVER_BG,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            highlightthickness=0,
            width=2,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
            padx=0,
            pady=0
        )
        self.close_button.pack(side="right", padx=(1, 3), pady=2)
        self.close_button.bind(
            "<Enter>", lambda _e: self.close_button.configure(
                bg=CLOSE_HOVER_BG
            )
        )
        self.close_button.bind(
            "<Leave>", lambda _e: self.close_button.configure(
                bg=CLOSE_BG
            )
        )

        self.window.bind("<Configure>", self.on_window_configure)

        # 图片区域
        self.canvas = tk.Canvas(
            self.window,
            width=self.display_width,
            height=self.display_height,
            highlightthickness=0,
            bg="white"
        )
        self.canvas.pack(fill="both", expand=True)
        # 图片区域：默认模式下任意位置可拖动；边缘可独立拉伸
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", self.on_canvas_leave)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)

        # 底部缩放区域
        self.resize_bar = tk.Frame(
            self.window,
            height=RESIZE_HEIGHT,
            bg=HEADER_BG
        )
        self.resize_bar.pack(side="bottom", fill="x")

        self.resize_handle = tk.Label(
            self.resize_bar,
            text="◢",
            bg=HEADER_BG,
            fg="#8FA3BD",
            cursor="sizing",
            font=("Segoe UI Symbol", 8),
            padx=3
        )
        self.resize_handle.pack(side="right")
        self.resize_handle.bind("<ButtonPress-1>", self.start_resize)
        self.resize_handle.bind("<B1-Motion>", self.do_resize)
        self.resize_handle.bind("<ButtonRelease-1>", self.end_resize)

        self.update_header_buttons()
        self.refresh_header_button_style("top")
        self.refresh_header_button_style("pen")
        self.refresh_header_button_style("eraser")

    # =====================================================
    # 创建紧凑图标按钮
    # =====================================================

    def create_header_button(
        self,
        key,
        text,
        command,
        tooltip=""
    ):

        button = tk.Button(
            self.toolbar,
            text=text,
            command=command,
            bg=BUTTON_BG,
            fg=BUTTON_FG,
            activebackground=BUTTON_HOVER_BG,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI Symbol", 10),
            width=2,
            height=1,
            padx=0,
            pady=0,
            cursor="hand2"
        )

        button.bind(
            "<Enter>",
            lambda _e, w=button: w.configure(
                bg=BUTTON_HOVER_BG
            )
        )
        button.bind(
            "<Leave>",
            lambda _e, k=key: self.refresh_header_button_style(k)
        )

        self.header_buttons[key] = button
        return button

    def refresh_header_button_style(self, key):

        button = self.header_buttons.get(key)
        if button is None:
            return

        active = (
            (key == "pen" and self.current_tool == "pen")
            or (key == "eraser" and self.current_tool == "eraser")
            or (key == "top" and self.is_topmost)
        )

        button.configure(
            bg=BUTTON_ACTIVE_BG if active else BUTTON_BG,
            fg="#FFFFFF" if active else BUTTON_FG
        )

    # =====================================================
    # Header 自适应按钮显示
    # =====================================================

    def update_header_buttons(self):

        if not self.window.winfo_exists():
            return

        width = self.window.winfo_width()

        # 左侧手柄、右侧关闭按钮和必要留白
        reserved_width = 48
        available = max(0, width - reserved_width)

        # 依次显示；空间不足时优先隐藏撤销等次要按钮
        button_specs = [
            ("top", 25),
            ("pen", 25),
            ("eraser", 25),
            ("undo", 25)
        ]

        used_width = 0

        for key, required_width in button_specs:

            widget = self.header_buttons[key]

            if available - used_width >= required_width:

                if not widget.winfo_manager():
                    widget.pack(
                        side="left",
                        padx=HEADER_PADX,
                        pady=2
                    )

                used_width += required_width + HEADER_PADX * 2

            else:

                if widget.winfo_manager():
                    widget.pack_forget()

    # =====================================================
    # 窗口尺寸变化
    # =====================================================

    def on_window_configure(self, event):

        if event.widget != self.window:
            return

        if not hasattr(self, "header_buttons"):
            return

        self.update_header_buttons()

    # =====================================================
    # Header 整体拖动
    # =====================================================

    def start_drag(self, event):

        self.drag_offset_x = (
            event.x_root - self.window.winfo_x()
        )

        self.drag_offset_y = (
            event.y_root - self.window.winfo_y()
        )

    def move_window(self, event):

        new_x = (
            event.x_root - self.drag_offset_x
        )

        new_y = (
            event.y_root - self.drag_offset_y
        )

        self.window.geometry(
            f"+{new_x}+{new_y}"
        )

    # =====================================================
    # 画笔 / 橡皮擦
    # =====================================================

    def toggle_pen(self):

        if self.current_tool == "pen":
            self.current_tool = "move"
            self.canvas.configure(cursor="arrow")
        else:
            self.current_tool = "pen"
            self.current_color = "#FF0000"
            self.canvas.configure(cursor="pencil")

        self.refresh_header_button_style("pen")
        self.refresh_header_button_style("eraser")

    def use_pen(self, color="#FF0000"):

        self.current_tool = "pen"
        self.current_color = color
        self.canvas.configure(cursor="pencil")

        self.refresh_header_button_style("pen")
        self.refresh_header_button_style("eraser")

    def use_eraser(self):

        self.current_tool = "eraser"
        self.canvas.configure(cursor="dot")

        self.refresh_header_button_style("pen")
        self.refresh_header_button_style("eraser")

    # =====================================================
    # 置顶
    # =====================================================

    def toggle_topmost(self):

        self.is_topmost = not self.is_topmost

        self.window.attributes(
            "-topmost",
            self.is_topmost
        )

        self.refresh_header_button_style("top")

    # =====================================================
    # 图片坐标转换（支持非等比例拉伸）
    # =====================================================

    def get_scale_x(self):

        return self.display_width / self.original_image.width

    def get_scale_y(self):

        return self.display_height / self.original_image.height

    def get_scale(self):

        # 兼容画笔宽度等需要单一比例的场景
        return (self.get_scale_x() + self.get_scale_y()) / 2

    def to_original_point(self, x, y):

        return (
            x / self.get_scale_x(),
            y / self.get_scale_y()
        )

    def to_display_point(self, x, y):

        return (
            x * self.get_scale_x(),
            y * self.get_scale_y()
        )

    # =====================================================
    # 图片区域鼠标操作：边缘拉伸 / 图片拖动 / 涂鸦
    # =====================================================

    def get_edge_resize_mode(self, x, y):

        margin = EDGE_RESIZE_MARGIN
        width = self.display_width
        height = self.display_height

        # 边缘优先级高于内部拖动/绘图
        if x <= margin:
            return "left"
        if x >= width - margin:
            return "right"
        if y <= margin:
            return "top"
        if y >= height - margin:
            return "bottom"

        return None

    def on_canvas_motion(self, event):

        mode = self.get_edge_resize_mode(event.x, event.y)

        if mode in ("left", "right"):
            self.canvas.configure(cursor="sb_h_double_arrow")
        elif mode in ("top", "bottom"):
            self.canvas.configure(cursor="sb_v_double_arrow")
        elif self.current_tool == "pen":
            self.canvas.configure(cursor="pencil")
        elif self.current_tool == "eraser":
            self.canvas.configure(cursor="dot")
        else:
            self.canvas.configure(cursor="fleur")

    def on_canvas_leave(self, event=None):

        if self.current_tool == "pen":
            self.canvas.configure(cursor="pencil")
        elif self.current_tool == "eraser":
            self.canvas.configure(cursor="dot")
        else:
            self.canvas.configure(cursor="arrow")

    def on_canvas_press(self, event):

        self.edge_resize_mode = self.get_edge_resize_mode(
            event.x, event.y
        )

        if self.edge_resize_mode:
            self.edge_resize_start_x = event.x_root
            self.edge_resize_start_y = event.y_root
            self.edge_resize_start_width = self.display_width
            self.edge_resize_start_height = self.display_height
            self.edge_resize_start_window_x = self.window.winfo_x()
            self.edge_resize_start_window_y = self.window.winfo_y()
            self.image_dragging = False
            self.current_stroke = None
            return

        if self.current_tool in ("pen", "eraser"):
            self.on_draw_start(event)
            return

        # 默认移动模式：图片内部任意位置均可拖动整张贴图
        self.image_dragging = True
        self.drag_offset_x = event.x_root - self.window.winfo_x()
        self.drag_offset_y = event.y_root - self.window.winfo_y()

    def on_canvas_drag(self, event):

        if self.edge_resize_mode:
            dx = event.x_root - self.edge_resize_start_x
            dy = event.y_root - self.edge_resize_start_y

            new_width = self.edge_resize_start_width
            new_height = self.edge_resize_start_height
            new_x = self.edge_resize_start_window_x
            new_y = self.edge_resize_start_window_y

            if self.edge_resize_mode == "right":
                new_width = max(MIN_WIDTH, self.edge_resize_start_width + dx)
            elif self.edge_resize_mode == "left":
                raw_width = self.edge_resize_start_width - dx
                new_width = max(MIN_WIDTH, raw_width)
                new_x = (
                    self.edge_resize_start_window_x
                    + self.edge_resize_start_width - new_width
                )
            elif self.edge_resize_mode == "bottom":
                new_height = max(MIN_HEIGHT, self.edge_resize_start_height + dy)
            elif self.edge_resize_mode == "top":
                raw_height = self.edge_resize_start_height - dy
                new_height = max(MIN_HEIGHT, raw_height)
                new_y = (
                    self.edge_resize_start_window_y
                    + self.edge_resize_start_height - new_height
                )

            self.display_width = int(new_width)
            self.display_height = int(new_height)
            self.window.geometry(
                f"{self.display_width}x"
                f"{self.display_height + TOOLBAR_HEIGHT + RESIZE_HEIGHT}"
                f"+{int(new_x)}+{int(new_y)}"
            )
            self.render_image()
            return

        if self.image_dragging:
            new_x = event.x_root - self.drag_offset_x
            new_y = event.y_root - self.drag_offset_y
            self.window.geometry(f"+{new_x}+{new_y}")
            return

        if self.current_stroke is not None:
            self.on_draw_move(event)

    def on_canvas_release(self, event):

        if self.edge_resize_mode:
            self.edge_resize_mode = None
            self.auto_save()
            self.on_canvas_motion(event)
            return

        if self.image_dragging:
            self.image_dragging = False
            return

        if self.current_stroke is not None:
            self.on_draw_end(event)

    # =====================================================
    # 涂鸦开始
    # =====================================================

    def on_draw_start(self, event):

        if self.current_tool not in ("pen", "eraser"):
            return

        point = self.to_original_point(event.x, event.y)

        self.current_stroke = {
            "tool": self.current_tool,
            "color": self.current_color,
            "width": (
                self.brush_width if self.current_tool == "pen"
                else self.eraser_width
            ) / self.get_scale(),
            "points": [point]
        }

    # =====================================================
    # 涂鸦过程
    # =====================================================

    def on_draw_move(self, event):

        if self.current_stroke is None:
            return

        point = self.to_original_point(event.x, event.y)
        self.current_stroke["points"].append(point)

        display_points = []
        for px, py in self.current_stroke["points"]:
            dx, dy = self.to_display_point(px, py)
            display_points.extend([dx, dy])

        if len(display_points) >= 4:
            if self.current_stroke["tool"] == "pen":
                color = self.current_stroke["color"]
            else:
                color = "#FFFFFF"

            self.canvas.delete("preview")
            self.canvas.create_line(
                *display_points,
                fill=color,
                width=(
                    self.brush_width
                    if self.current_stroke["tool"] == "pen"
                    else self.eraser_width
                ),
                capstyle=tk.ROUND,
                smooth=True,
                tags="preview"
            )

    # =====================================================
    # 涂鸦完成
    # =====================================================

    def on_draw_end(self, event):

        if self.current_stroke is None:
            return

        self.strokes.append(
            self.current_stroke
        )

        self.current_stroke = None

        self.render_image()

        self.auto_save()
        self.copy_to_clipboard()

    # =====================================================
    # 创建涂鸦图层
    # =====================================================

    def create_annotation_layer(self):

        layer = Image.new(
            "RGBA",
            self.original_image.size,
            (0, 0, 0, 0)
        )

        for stroke in self.strokes:

            points = stroke["points"]

            if stroke["tool"] == "pen":

                draw = ImageDraw.Draw(layer)

                draw_stroke(
                    draw,
                    points,
                    stroke["color"],
                    max(1, round(stroke["width"]))
                )

            elif stroke["tool"] == "eraser":

                mask = Image.new(
                    "L",
                    layer.size,
                    0
                )

                draw = ImageDraw.Draw(mask)

                draw_stroke(
                    draw,
                    points,
                    255,
                    max(1, round(stroke["width"]))
                )

                old_alpha = layer.getchannel("A")

                new_alpha = ImageChops.subtract(
                    old_alpha,
                    mask
                )

                layer.putalpha(new_alpha)

        return layer

    # =====================================================
    # 获取最终图片
    # =====================================================

    def get_final_image(self):

        base = self.original_image.convert("RGBA")

        layer = self.create_annotation_layer()

        return Image.alpha_composite(
            base,
            layer
        ).convert("RGB")

    # =====================================================
    # 刷新图片
    # =====================================================

    def render_image(self):

        final_image = self.get_final_image()

        display_image = final_image.resize(
            (
                self.display_width,
                self.display_height
            ),
            Image.Resampling.LANCZOS
        )

        self.photo = ImageTk.PhotoImage(
            display_image
        )

        self.canvas.configure(
            width=self.display_width,
            height=self.display_height
        )

        self.canvas.delete("all")

        self.canvas.create_image(
            0,
            0,
            anchor="nw",
            image=self.photo
        )

    # =====================================================
    # 撤销
    # =====================================================

    def undo(self):

        if not self.strokes:
            return

        self.strokes.pop()

        self.render_image()

        self.auto_save()
        self.copy_to_clipboard()

    # =====================================================
    # 缩放
    # =====================================================

    def start_resize(self, event):

        self.resizing = True

        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root

        self.resize_start_width = self.display_width
        self.resize_start_height = self.display_height
        self.resize_start_ratio = (
            self.resize_start_width / self.resize_start_height
        )

    def do_resize(self, event):

        if not self.resizing:
            return

        dx = event.x_root - self.resize_start_x

        dy = event.y_root - self.resize_start_y

        ratio = self.resize_start_ratio

        if abs(dx) >= abs(dy * ratio):

            new_width = self.resize_start_width + dx

        else:

            new_width = (
                self.resize_start_height + dy
            ) * ratio

        new_width = max(
            MIN_WIDTH,
            round(new_width)
        )

        new_height = max(
            MIN_HEIGHT,
            round(new_width / ratio)
        )

        self.display_width = new_width
        self.display_height = new_height

        self.window.geometry(
            f"{new_width}x"
            f"{new_height + TOOLBAR_HEIGHT + RESIZE_HEIGHT}"
            f"+{self.window.winfo_x()}+{self.window.winfo_y()}"
        )

        self.render_image()

    def end_resize(self, event=None):

        if self.resizing:
            self.resizing = False
            self.auto_save()

    # =====================================================
    # 自动保存
    # =====================================================

    def auto_save(self):

        try:

            self.auto_save_path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            self.get_final_image().save(
                self.auto_save_path,
                format="PNG"
            )

        except Exception as e:

            print(
                f"[自动保存失败] {e}"
            )

    # =====================================================
    # 自动复制最新图片到 Windows 剪贴板
    # =====================================================

    def copy_to_clipboard(self):

        """
        将当前最终图片（原始截图分辨率，包含所有涂鸦）写入
        Windows 剪贴板，格式为 CF_DIB，可直接粘贴到 Office、
        微信、画图等支持图片粘贴的软件。

        不依赖 pywin32，使用 Windows 原生 User32 / Kernel32 API。
        """

        if os.name != "nt":
            print("[剪贴板] 当前自动图片剪贴板功能仅支持 Windows")
            return False

        h_global = None
        clipboard_opened = False
        kernel32 = None
        user32 = None

        try:
            import ctypes
            from ctypes import wintypes

            image = self.get_final_image().convert("RGB")

            bmp_buffer = BytesIO()
            image.save(bmp_buffer, format="BMP")
            bmp_bytes = bmp_buffer.getvalue()

            # CF_DIB 需要 DIB 数据，不包含 BMP 文件头的前 14 字节
            dib_bytes = bmp_bytes[14:]

            if not dib_bytes:
                raise RuntimeError("生成剪贴板图像数据失败")

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            user32 = ctypes.WinDLL("user32", use_last_error=True)

            kernel32.GlobalAlloc.argtypes = [
                wintypes.UINT,
                ctypes.c_size_t
            ]
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = ctypes.c_void_p

            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalFree.restype = wintypes.HGLOBAL

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL

            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype = wintypes.BOOL

            user32.SetClipboardData.argtypes = [
                wintypes.UINT,
                wintypes.HANDLE
            ]
            user32.SetClipboardData.restype = wintypes.HANDLE

            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL

            GMEM_MOVEABLE = 0x0002
            CF_DIB = 8

            h_global = kernel32.GlobalAlloc(
                GMEM_MOVEABLE,
                len(dib_bytes)
            )
            if not h_global:
                raise ctypes.WinError(ctypes.get_last_error())

            locked_ptr = kernel32.GlobalLock(h_global)
            if not locked_ptr:
                raise ctypes.WinError(ctypes.get_last_error())

            ctypes.memmove(
                locked_ptr,
                dib_bytes,
                len(dib_bytes)
            )
            kernel32.GlobalUnlock(h_global)

            if not user32.OpenClipboard(None):
                raise ctypes.WinError(ctypes.get_last_error())

            clipboard_opened = True

            if not user32.EmptyClipboard():
                raise ctypes.WinError(ctypes.get_last_error())

            result = user32.SetClipboardData(CF_DIB, h_global)
            if not result:
                raise ctypes.WinError(ctypes.get_last_error())

            # SetClipboardData 成功后，内存句柄所有权交给系统
            h_global = None

            print(
                f"[剪贴板已更新] {image.width} x {image.height}"
            )
            return True

        except Exception as e:
            print(f"[剪贴板复制失败] {e}")
            return False

        finally:
            try:
                if clipboard_opened and user32 is not None:
                    user32.CloseClipboard()
            except Exception:
                pass

            # SetClipboardData 成功时句柄已交给系统，不再释放；
            # 只有写入失败、系统尚未接管时才释放内存。
            if h_global and kernel32 is not None:
                try:
                    kernel32.GlobalFree(h_global)
                except Exception:
                    pass

    # =====================================================
    # 手动保存
    # =====================================================

    def save_image(self):

        file_path = filedialog.asksaveasfilename(
            title="保存截图",
            defaultextension=".png",
            initialfile="ScreenPin.png",
            filetypes=[
                ("PNG 图片", "*.png"),
                ("JPEG 图片", "*.jpg"),
                ("BMP 图片", "*.bmp")
            ]
        )

        if not file_path:
            return

        try:

            image = self.get_final_image()

            ext = Path(file_path).suffix.lower()

            if ext in (".jpg", ".jpeg"):

                image.save(
                    file_path,
                    format="JPEG",
                    quality=95
                )

            elif ext == ".bmp":

                image.save(
                    file_path,
                    format="BMP"
                )

            else:

                image.save(
                    file_path,
                    format="PNG"
                )

            print(
                f"[保存成功] {file_path}"
            )

        except Exception as e:

            messagebox.showerror(
                "保存失败",
                str(e)
            )

    # =====================================================
    # 关闭贴图
    # =====================================================

    def destroy(self):

        try:

            self.auto_save()

            self.window.destroy()

            if self in self.app.pins:

                self.app.pins.remove(self)

        except Exception as e:

            print(
                f"[关闭贴图失败] {e}"
            )


# =========================================================
# 程序入口
# =========================================================

if __name__ == "__main__":

    print("=" * 55)
    print("Screen Pin 2.5")
    print("=" * 55)

    print("快捷键：F8")

    print(f"自动保存目录：{SAVE_DIR}")

    print("紧凑 Header：图标工具栏，取消透明度调节")

    print("图片内部拖动移动，图片四边可独立横向/纵向拉伸")
    print("截图和涂鸦完成后，自动复制最新图片到 Windows 剪贴板")
    print("Header 已移除保存按钮，保留置顶、画笔、橡皮擦、撤销和关闭")
    print("Header 按钮根据图片宽度自动显示/隐藏")

    print("=" * 55)

    app = ScreenPinApp()

    try:

        app.run()

    except KeyboardInterrupt:

        pass
