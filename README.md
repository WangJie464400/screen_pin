# Screen Pin 2.5

Screen Pin 是一款区域截图和桌面贴图工具。按下全局快捷键 **F8** 时，程序先保存当前屏幕画面，再显示框选窗口。已经展开的下拉框、右键菜单和屏幕上可见的贴图都会保留在这帧画面中。

## 安装与启动

需要 Python 3 和带 Tkinter 的图形桌面。可以运行 `python -m tkinter` 检查 Tkinter 是否可用，正常时会打开一个测试窗口。

先获取源码：

```bash
git clone https://github.com/WangJie464400/screen_pin.git
cd screen_pin
```

**Windows（PowerShell）**

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install mss Pillow
.\.venv\Scripts\python.exe screen_pin.py
```

**Linux（X11）**

以下系统包安装命令适用于 Debian 和 Ubuntu。请在 X11 桌面会话中运行。

```bash
sudo apt install python3-tk python3-venv
python3 -m venv .venv
.venv/bin/python -m pip install mss Pillow pynput python-xlib
.venv/bin/python screen_pin.py
```

程序启动后在后台等待快捷键。若启动时提示无法注册 **F8**，请检查是否已有 Screen Pin 实例或其他程序占用了该键。当前的 Linux 快捷键实现依赖 X11，原生 Wayland 和 macOS 不在支持范围内。

## 截图与贴图

1. 展开要截取的菜单或下拉框，按 **F8** 冻结画面。
2. 按住鼠标左键拖动框选，松开后生成独立的置顶贴图。按 **Esc** 可取消本次框选。
3. 再按 **F8** 可继续截图。每张贴图都可以独立移动、编辑和关闭。

| 操作 | 用法 |
| --- | --- |
| 移动贴图 | 拖动顶部手柄或工具栏空白处。默认移动模式下也可拖动图片内部。 |
| 调整大小 | 拖动图片左右边缘调整宽度，拖动上下边缘调整高度，拖动右下角手柄等比例缩放。 |
| 切换置顶 | 点击 **⌖**。 |
| 涂鸦 | 点击 **✎** 使用红色画笔，再点一次回到移动模式。 |
| 擦除涂鸦 | 点击 **▱** 后在标注上拖动。 |
| 撤销 | 点击 **↶** 撤销最近一次画笔或擦除操作。 |
| 关闭贴图 | 点击 **×**。 |

贴图太窄时，工具栏会隐藏空间不足的按钮。拉宽贴图即可重新显示这些按钮。

## 保存与剪贴板

- 截图自动保存到用户主目录下的 `Pictures/ScreenPin/`，文件名格式为 `ScreenPin_YYYYMMDD_HHMMSS_ffffff.png`。
- 标注或撤销会更新同一张贴图对应的 PNG。保存的图片包含标注，并保持原始截图分辨率。拖动边缘或缩放手柄只调整贴图的显示大小。
- Windows 在生成贴图、完成一笔画笔或擦除操作以及撤销后，会将最新图片复制到剪贴板，可直接粘贴到支持图片的应用中。Linux 可从保存目录打开 PNG。
