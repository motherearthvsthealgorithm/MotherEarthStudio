import tkinter as tk
from tkinter import filedialog

def choose_video():
    filename = filedialog.askopenfilename(
        title="Choose a forest video",
        filetypes=[
            ("Video files", "*.mp4 *.mov *.m4v"),
            ("All files", "*.*"),
        ],
    )

    if filename:
        selected_video.set(filename)
        status_label.config(text="Video selected.")

app = tk.Tk()
app.title("Mother Earth Studio")
app.geometry("700x520")

selected_video = tk.StringVar()

title_label = tk.Label(
    app,
    text="Mother Earth Studio",
    font=("Helvetica Neue", 24),
)
title_label.pack(pady=(30, 5))

tagline_label = tk.Label(
    app,
    text="I'm here to ask different questions.",
    font=("Helvetica Neue", 13),
)
tagline_label.pack(pady=(0, 25))

choose_button = tk.Button(
    app,
    text="Choose Forest Video",
    command=choose_video,
    width=24,
    height=2,
)
choose_button.pack()

video_label = tk.Label(
    app,
    textvariable=selected_video,
    wraplength=520,
)
video_label.pack(pady=20)

status_label = tk.Label(
    app,
    text="Choose a video to begin.",
)
status_label.pack()

app.mainloop()
