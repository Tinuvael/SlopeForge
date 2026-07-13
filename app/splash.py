import tkinter as tk
from pathlib import Path
import sys
from app.config import APP_NAME, APP_VERSION

def resource_path(relative_path: str) -> Path:
    """
    Works both in normal Python run and PyInstaller onefile build.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    return Path(__file__).resolve().parent.parent / relative_path


def show_splash(duration_ms: int = 1200, fade_ms: int = 500):
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.configure(bg="white")

    width = 512
    height = 512

    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()

    x = int((screen_width - width) / 2)
    y = int((screen_height - height) / 2)

    splash.geometry(f"{width}x{height}+{x}+{y}")
    splash.attributes("-alpha", 1.0)

    icon_path = resource_path("assets/icons/stopeforge_icon_512x512.png")

    try:
        icon_image = tk.PhotoImage(file=str(icon_path))
        label = tk.Label(splash, image=icon_image, bg="white")
        label.image = icon_image
        label.pack(expand=True)
    except Exception:
        label = tk.Label(
            splash,
            text="StopeForge",
            font=("Segoe UI", 30, "bold"),
            bg="white",
            fg="black",
        )
        label.pack(expand=True)

    version_label = tk.Label(
        splash,
        text=f"version {APP_VERSION}",
        font=("Segoe UI", 9),
        bg="black",
        fg="#FFFFFF",
    )
    version_label.place(
        x=5, 
        y=height - 0,
        anchor="sw"
    )

    app_name_label = tk.Label(
        splash,
        text=APP_NAME,
        font=("Segoe UI", 10, "bold"),
        bg="black",
        fg="#FFFAFA",
        anchor="e",
        justify="right",
    )

    app_name_label.place(
        x=width - 0,
        y=height - 20,
        anchor="se",
    )

    copyright_label = tk.Label(
        splash,
        text="© 2026 Емшанов Евгений. All rights reserved.",
        font=("Segoe UI", 8),
        bg="black",
        fg="#FFFFFF",
        anchor="e",
        justify="right",
    )

    copyright_label.place(
        x=width - 0,
        y=height - 0,
        anchor="se",
    )


    def fade_out(step: int = 0):
        steps = 20
        alpha = max(0.0, 1.0 - step / steps)
        splash.attributes("-alpha", alpha)

        if step < steps:
            splash.after(int(fade_ms / steps), lambda: fade_out(step + 1))
        else:
            splash.destroy()

    splash.after(duration_ms, fade_out)
    splash.mainloop()

