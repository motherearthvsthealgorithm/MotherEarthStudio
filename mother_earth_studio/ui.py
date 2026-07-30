import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .builder import build_episode, next_output_path
from .captions import generate_captions
from .paths import FOREST_DIR, MUSIC_DIR, NARRATION_DIR, OUTPUT_DIR, SCRIPTS_DIR, SUBTITLES_DIR, ensure_folders
from .settings import load_settings, save_settings
from .system_check import check_system


class StudioApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        ensure_folders()
        self.settings = load_settings()
        self.system = check_system()

        self.title("Mother Earth Studio 0.9.4")
        self.geometry("980x760")
        self.minsize(860, 680)

        self.video = tk.StringVar()
        self.narration = tk.StringVar()
        self.music = tk.StringVar()
        self.subtitles = tk.StringVar()
        self.episode_title = tk.StringVar()
        self.music_volume = tk.DoubleVar(value=self.settings.music_volume)
        self.burn_captions = tk.BooleanVar(value=self.settings.burn_captions_when_supported)
        self.status = tk.StringVar(value="Choose your story and media, then build a post-ready episode.")

        self._build_ui()
        self._show_system_status()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        style = ttk.Style(self)
        try:
            style.theme_use("aqua")
        except tk.TclError:
            pass
        style.configure("Section.TLabelframe", padding=12)
        style.configure("Section.TLabelframe.Label", font=("Helvetica Neue", 12, "bold"))
        style.configure("Build.TButton", font=("Helvetica Neue", 13, "bold"), padding=(16, 10))

        header = ttk.Frame(self, padding=(22, 14, 22, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="🌎 Mother Earth Studio", font=("Helvetica Neue", 24, "bold")).grid(row=0, column=0)
        ttk.Label(header, text="Story first. Technology supports the story.", font=("Helvetica Neue", 11)).grid(row=1, column=0)

        main = ttk.Frame(self, padding=(18, 8, 18, 12))
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(1, weight=1)

        episode = ttk.LabelFrame(main, text="Episode Story", style="Section.TLabelframe")
        episode.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        episode.columnconfigure(1, weight=1)
        ttk.Label(episode, text="Title", font=("Helvetica Neue", 11, "bold")).grid(row=0, column=0, sticky="nw", padx=(0, 10))
        ttk.Entry(episode, textvariable=self.episode_title, font=("Helvetica Neue", 12)).grid(row=0, column=1, sticky="ew")
        ttk.Label(episode, text="Approved script (optional)", font=("Helvetica Neue", 11, "bold")).grid(row=1, column=0, sticky="nw", padx=(0, 10), pady=(10, 0))
        script_area = ttk.Frame(episode)
        script_area.grid(row=1, column=1, sticky="ew", pady=(10, 0))
        script_area.columnconfigure(0, weight=1)
        self.script_text = tk.Text(script_area, height=7, wrap="word", font=("Helvetica Neue", 11), undo=True)
        self.script_text.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Button(script_area, text="Load Script", command=self.load_script).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(script_area, text="Save Script", command=self.save_script).grid(row=1, column=1, pady=(6, 0))
        ttk.Button(script_area, text="Clear", command=lambda: self.script_text.delete("1.0", "end")).grid(row=1, column=2, sticky="e", pady=(6, 0))

        media = ttk.LabelFrame(main, text="Media", style="Section.TLabelframe")
        media.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        media.columnconfigure(1, weight=1)
        self.file_labels: dict[str, ttk.Label] = {}
        self._media_row(media, 0, "video", "🌲", "Forest", self.video, FOREST_DIR, (("Video files", "*.mp4 *.mov *.m4v"),))
        self._media_row(media, 1, "narration", "🎙", "Narration", self.narration, NARRATION_DIR, (("Audio files", "*.mp3 *.wav *.m4a *.aac"),))
        self._media_row(media, 2, "music", "🎵", "Music", self.music, MUSIC_DIR, (("Audio files", "*.mp3 *.wav *.m4a *.aac"),), optional=True)
        self._media_row(media, 3, "subtitles", "💬", "Captions", self.subtitles, SUBTITLES_DIR, (("SubRip subtitles", "*.srt"),), optional=True)

        actions = ttk.Frame(media)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        actions.columnconfigure((0, 1, 2), weight=1)
        self.caption_button = ttk.Button(actions, text="Generate Captions", command=self.start_caption_generation)
        self.caption_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actions, text="Clear Music", command=lambda: self._clear("music", self.music, "Music cleared.")).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(actions, text="Clear Captions", command=lambda: self._clear("subtitles", self.subtitles, "Captions cleared.")).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        options = ttk.LabelFrame(main, text="Build", style="Section.TLabelframe")
        options.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        options.columnconfigure(0, weight=1)
        options.rowconfigure(8, weight=1)
        ttk.Label(options, text="Music volume", font=("Helvetica Neue", 11, "bold")).grid(row=0, column=0, sticky="w")
        vol = ttk.Frame(options)
        vol.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        vol.columnconfigure(0, weight=1)
        ttk.Scale(vol, from_=0, to=50, variable=self.music_volume, command=self._volume_changed).grid(row=0, column=0, sticky="ew")
        self.volume_label = ttk.Label(vol, text=f"{int(self.music_volume.get())}%", width=5, anchor="e")
        self.volume_label.grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(options, text="Burn captions into video when supported", variable=self.burn_captions).grid(row=2, column=0, sticky="w")
        ttk.Separator(options).grid(row=3, column=0, sticky="ew", pady=10)
        self.system_label = ttk.Label(options, justify="left", wraplength=300)
        self.system_label.grid(row=4, column=0, sticky="w")
        ttk.Label(options, text="Posting continuity: if subtitle burning is unavailable, Studio still creates a compatible MP4 and keeps the .srt beside it.", wraplength=300, justify="left").grid(row=5, column=0, sticky="w", pady=(10, 10))
        self.progress = ttk.Progressbar(options, mode="indeterminate")
        self.progress.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        self.build_button = ttk.Button(options, text="✨ Build Post-Ready Episode", command=self.start_build, style="Build.TButton")
        self.build_button.grid(row=7, column=0, sticky="ew")
        ttk.Label(options, textvariable=self.status, anchor="n", justify="left", wraplength=300).grid(row=8, column=0, sticky="nsew", pady=(12, 0))

        ttk.Label(self, text="Mother Earth Studio 0.9.4 • Caption Compatibility Release").grid(row=2, column=0, pady=(0, 8))

    def _media_row(self, parent, row, key, icon, name, variable, initial_dir, filetypes, optional=False):
        ttk.Label(parent, text=f"{icon}  {name}", font=("Helvetica Neue", 11, "bold")).grid(row=row, column=0, sticky="w", pady=8)
        label = ttk.Label(parent, text="None selected", anchor="w")
        label.grid(row=row, column=1, sticky="ew", padx=12, pady=8)
        self.file_labels[key] = label
        def choose():
            path = filedialog.askopenfilename(initialdir=str(initial_dir), title=f"Choose {name.lower()}", filetypes=list(filetypes) + [("All files", "*.*")])
            if path:
                variable.set(path)
                label.config(text=Path(path).name)
                self.status.set(f"{name} selected.")
        ttk.Button(parent, text="Choose", command=choose, width=10).grid(row=row, column=2, sticky="e", pady=8)

    def _clear(self, key, variable, message):
        variable.set("")
        self.file_labels[key].config(text="None selected")
        self.status.set(message)

    def _volume_changed(self, value):
        self.volume_label.config(text=f"{int(float(value))}%")

    def _show_system_status(self):
        ffmpeg_path = getattr(self.system, "ffmpeg_path", None)
        ffprobe_path = getattr(self.system, "ffprobe_path", None)
        ass_filter = getattr(self.system, "ass_filter", False)
        lines = [
            f"FFmpeg: {'ready' if self.system.ffmpeg else 'missing'}",
            f"  {ffmpeg_path or 'No executable found'}",
            f"FFprobe: {'ready' if self.system.ffprobe else 'missing'}",
            f"  {ffprobe_path or 'No executable found'}",
            f"Whisper: {'ready' if self.system.whisper else 'not installed'}",
            "Caption filters:",
            f"  drawtext: {'ready' if self.system.drawtext_filter else 'missing'}",
            f"  subtitles: {'ready' if self.system.subtitles_filter else 'missing'}",
            f"  ass: {'ready' if ass_filter else 'missing'}",
        ]
        self.system_label.config(text="\n".join(lines))

    def load_script(self):
        path = filedialog.askopenfilename(initialdir=str(SCRIPTS_DIR), filetypes=[("Text files", "*.txt *.md"), ("All files", "*.*")])
        if path:
            self.script_text.delete("1.0", "end")
            self.script_text.insert("1.0", Path(path).read_text(encoding="utf-8"))
            self.status.set(f"Loaded script: {Path(path).name}")

    def save_script(self):
        title = self.episode_title.get().strip() or "Untitled"
        path = filedialog.asksaveasfilename(initialdir=str(SCRIPTS_DIR), initialfile=f"{title}.txt", defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if path:
            Path(path).write_text(self.script_text.get("1.0", "end").strip(), encoding="utf-8")
            self.status.set(f"Saved script: {Path(path).name}")

    def _busy(self, active: bool):
        state = "disabled" if active else "normal"
        self.caption_button.config(state=state)
        self.build_button.config(state=state)
        if active:
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress["value"] = 0

    def start_caption_generation(self):
        if not self.narration.get():
            self.status.set("Choose narration before generating captions.")
            return
        narration = Path(self.narration.get())
        destination = SUBTITLES_DIR / f"{narration.stem}.srt"
        counter = 2
        while destination.exists():
            destination = SUBTITLES_DIR / f"{narration.stem}_{counter}.srt"
            counter += 1
        script = self.script_text.get("1.0", "end").strip()
        self._busy(True)
        self.status.set("Generating captions locally. The approved script controls the wording when provided...")
        threading.Thread(target=self._caption_worker, args=(narration, destination, script), daemon=True).start()

    def _caption_worker(self, narration, destination, script):
        try:
            language = generate_captions(narration, destination, script, self.settings.whisper_model)
        except Exception as exc:
            self.after(0, lambda exc=exc: self._finish_error(f"Caption generation failed:\n{exc}"))
            return
        def done():
            self._busy(False)
            self.subtitles.set(str(destination))
            self.file_labels["subtitles"].config(text=destination.name)
            mode = "approved script wording" if script else "Whisper wording"
            self.status.set(f"✅ Captions created with {mode}.\n{destination.name}\nLanguage: {language or 'unknown'}")
        self.after(0, done)

    def start_build(self):
        title = self.episode_title.get().strip()
        if not title or not self.video.get() or not self.narration.get():
            self.status.set("Episode title, forest video, and narration are required.")
            return
        self.settings.music_volume = int(self.music_volume.get())
        self.settings.burn_captions_when_supported = bool(self.burn_captions.get())
        save_settings(self.settings)
        number, output = next_output_path(OUTPUT_DIR, title)
        self._busy(True)
        self.status.set(f"Building Episode {number:03d}...")
        kwargs = dict(
            video=Path(self.video.get()), narration=Path(self.narration.get()), output=output,
            system=self.system, music=Path(self.music.get()) if self.music.get() else None,
            subtitles=Path(self.subtitles.get()) if self.subtitles.get() else None,
            music_volume=int(self.music_volume.get()), burn_captions=bool(self.burn_captions.get()),
        )
        threading.Thread(target=self._build_worker, args=(number, kwargs), daemon=True).start()

    def _build_worker(self, number, kwargs):
        try:
            result = build_episode(**kwargs)
        except Exception as exc:
            self.after(0, lambda exc=exc: self._finish_error(f"Episode build failed:\n{exc}"))
            return
        def done():
            self._busy(False)
            message = f"✅ Episode {number:03d} created\n{result.output.name}"
            if result.warning:
                message += f"\n\n{result.warning}"
            elif kwargs.get("subtitles") and result.captions_burned:
                message += f"\n\n✅ Captions visibly burned using {result.caption_renderer}."
            elif kwargs.get("subtitles"):
                message += "\n\n⚠️ MP4 created without burned captions."
            if result.log_path:
                message += f"\nBuild log: {result.log_path.name}"
            self.status.set(message)
            self._open_file(result.output)
        self.after(0, done)

    def _finish_error(self, message):
        self._busy(False)
        self.status.set(message)
        messagebox.showerror("Mother Earth Studio", message)

    def _open_file(self, path: Path):
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            elif os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            pass


def run() -> None:
    StudioApp().mainloop()
