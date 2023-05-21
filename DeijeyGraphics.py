import tkinter as tk
import ctypes


def recording_dot():
    tk.Canvas.create_circle = monkey_patched_create_circle

    root = tk.Tk()
    user32 = ctypes.windll.user32
    screensize = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)

    root.resizable(False, False)
    root.overrideredirect(True)
    root.geometry(f'30x30+{screensize[0] - 40}+{screensize[1] // 10}')
    root.wm_attributes("-topmost", True)
    root.wm_attributes("-alpha", 0.6)
    root.wm_attributes("-transparentcolor", "white")

    canvas = tk.Canvas(root, width=30, height=30, borderwidth=0, highlightthickness=0, bg='white')
    canvas.grid()
    canvas.create_circle(15, 15, 15, fill="red", outline="#DDD")

    return root


def visible(tkinter_object, visibility_request):
    if visibility_request:
        tkinter_object.wm_attributes("-alpha", 0.6)
    else:
        tkinter_object.wm_attributes("-alpha", 0)


def monkey_patched_create_circle(self, x, y, r, **kwargs):
    return self.create_oval(x - r, y - r, x + r, y + r, **kwargs)


