import os
import subprocess
import tkinter as tk
from tkinter import filedialog


def choose_video():
    filename = filedialog.askopenfilename(
        initialdir="Assets/Forest",
        title="Choose a forest video",
        filetypes=[
            ("Video files", "*.mp4 *.mov *.m4v"),
            ("All files", "*.*"),
        ],
    )

    if filename:
        selected_video.set(filename)
        status_label.config(text="Video selected.")


def choose_voiceover():
    filename = filedialog.askopenfilename(
        initialdir="Assets/Narration",
        title="Choose a narration recording",
        filetypes=[
            ("Audio files", "*.mp3 *.wav *.m4a *.aac"),
            ("All files", "*.*"),
        ],
    )

    if filename:
        selected_voiceover.set(filename)
        status_label.config(text="Narration selected.")


def build_episode():
    video = selected_video.get()
    voice = selected_voiceover.get()

    if not video:
        status_label.config(text="Please choose a forest video.")
        return

    if not voice:
        status_label.config(text="Please choose a narration recording.")
        return

    os.makedirs("Output", exist_ok=True)

    episode = 1
    while True:
        output = f"Output/Episode_{episode:03d}.mp4"
        if not os.path.exists(output):
            break
        episode += 1

    status_label.config(text="Building episode...")
    app.update_idletasks()

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", video,
                "-i", voice,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                output,
            ],
            check=True,
        )
    except FileNotFoundError:
        status_label.config(text="FFmpeg was not found.")
        return
    except subprocess.CalledProcessError:
        status_label.config(text="Episode build failed. Check the terminal.")
        return

    status_label.config(text=f"✅ Created {os.path.basename(output)}")


app = tk.Tk()
app.title("Mother Earth Studio")
app.geometry("700x520")

selected_video = tk.StringVar()
selected_voiceover = tk.StringVar()

title_label = tk.Label(
    app,
    text="🌎 Mother Earth Studio",
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

voiceover_button = tk.Button(
    app,
    text="Choose Narration",
    command=choose_voiceover,
    width=24,
    height=2,
)
voiceover_button.pack(pady=(15, 0))

voiceover_label = tk.Label(
    app,
    textvariable=selected_voiceover,
    wraplength=520,
)
voiceover_label.pack(pady=10)

build_button = tk.Button(
    app,
    text="✨ Build Episode",
    command=build_episode,
    width=24,
    height=2,
)
build_button.pack(pady=(20, 0))

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
