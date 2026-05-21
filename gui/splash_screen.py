import tkinter as tk
from PIL import Image, ImageTk
import os

def run_splash(next_function=None):

    # ----------------------------------------------------------
    # PATH CONFIG
    # ----------------------------------------------------------
    BASE_PATH = os.path.join(os.path.dirname(__file__), "assets")

    FRAMES = [
        os.path.join(BASE_PATH, "Frame 1.png"),
        os.path.join(BASE_PATH, "Frame 2.png"),
        os.path.join(BASE_PATH, "Frame 3.png"),
        os.path.join(BASE_PATH, "Frame 4.png"),
        os.path.join(BASE_PATH, "Frame 5.png")
    ]

    WIDTH = 900
    HEIGHT = 600
    FRAME_DURATION = 700      # 0.7 sec per frame
    LAST_FRAME_HOLD = 900   # 10 sec for last frame

    # ----------------------------------------------------------
    # SPLASH WINDOW
    # ----------------------------------------------------------
    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg="black")

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = (screen_w - WIDTH) // 2
    y = (screen_h - HEIGHT) // 2
    root.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")

    label = tk.Label(root, bg="black")
    label.pack(expand=True)

    # Start fully transparent for popup animation
    root.attributes("-alpha", 0.0)

    # ----------------------------------------------------------
    # FADE-IN POPUP ANIMATION
    # ----------------------------------------------------------
    def fade_in(alpha=0.0):
        if alpha < 1.0:
            alpha += 0.05
            root.attributes("-alpha", alpha)
            root.after(30, lambda: fade_in(alpha))

    # ----------------------------------------------------------
    # LOAD IMAGES
    # ----------------------------------------------------------
    loaded = []
    for frame in FRAMES:
        img = Image.open(frame).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        loaded.append(ImageTk.PhotoImage(img))

    index = 0

    # ----------------------------------------------------------
    # ANIMATION LOGIC
    # ----------------------------------------------------------
    def animate():
        nonlocal index
        label.config(image=loaded[index])
        index += 1

        if index < len(loaded):
            # show frames 1–4 normally
            root.after(FRAME_DURATION, animate)
        else:
            # hold last frame 10 sec
            root.after(LAST_FRAME_HOLD, close_splash)

    def close_splash():
        root.destroy()
        if next_function:
            next_function()

    # START BOTH ANIMATIONS
    fade_in()
    animate()

    root.mainloop()
