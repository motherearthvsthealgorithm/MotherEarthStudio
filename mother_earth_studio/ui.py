import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .builder import build_episode, next_output_path
from .brand_identity import BrandIdentity, generate_cover
from .timeline_build import prepare_visual_source
from .captions import generate_captions
from .story_highlights_editor import StoryHighlightsEditor
from .project import (
    DEFAULT_PROJECTS_ROOT,
    EpisodeProject,
    InvalidProjectError,
    ProjectAlreadyExistsError,
    ProjectError,
    create_project,
    load_project,
)
from .recent_projects import (
    forget_missing_projects,
    remember_project,
)
from .paths import FOREST_DIR, MUSIC_DIR, NARRATION_DIR, OUTPUT_DIR, SCRIPTS_DIR, SUBTITLES_DIR, ensure_folders
from .settings import load_settings, save_settings
from .system_check import check_system
from .visual_timeline import (
    VisualTimelineItem,
    deserialize_visual_timeline,
    detect_visual_kind,
    remove_visual_item,
    reorder_visual_items,
    serialize_visual_timeline,
)


class StudioApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        ensure_folders()
        self.settings = load_settings()
        self.system = check_system()
        self.current_project: EpisodeProject | None = None
        self._loading_project = False
        self._autosave_job = None
        self.recent_project_paths: list[Path] = []
        self.recent_project_choice = tk.StringVar()
        self.visual_items: list[VisualTimelineItem] = []

        self.title("Mother Earth Studio 0.11.3")
        self.geometry("1040x780")
        self.minsize(760, 600)

        self.video = tk.StringVar()
        self.narration = tk.StringVar()
        self.music = tk.StringVar()
        self.subtitles = tk.StringVar()
        self.episode_title = tk.StringVar()
        self.cover_headline = tk.StringVar()
        self.cover_source = tk.StringVar()
        self.music_volume = tk.DoubleVar(value=self.settings.music_volume)
        self.burn_captions = tk.BooleanVar(value=self.settings.burn_captions_when_supported)
        self.story_first = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Choose your story and media, then build a post-ready episode.")

        self._build_ui()
        self._show_system_status()

        self.episode_title.trace_add(
            "write",
            self._schedule_project_autosave,
        )
        self.cover_headline.trace_add(
            "write",
            self._schedule_project_autosave,
        )

        self.script_text.bind(
            "<<Modified>>",
            self._on_script_modified,
        )

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._load_startup_project)

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

        scroll_container = ttk.Frame(self)
        scroll_container.grid(row=1, column=0, sticky="nsew")
        scroll_container.columnconfigure(0, weight=1)
        scroll_container.rowconfigure(0, weight=1)

        self.scroll_canvas = tk.Canvas(scroll_container, highlightthickness=0, borderwidth=0)
        self.scroll_canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=self.scroll_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)

        main = ttk.Frame(self.scroll_canvas, padding=(18, 8, 18, 18))
        self.scroll_window = self.scroll_canvas.create_window((0, 0), window=main, anchor="nw")

        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)

        main.bind("<Configure>", self._update_scroll_region)
        self.scroll_canvas.bind("<Configure>", self._resize_scroll_content)
        self.scroll_canvas.bind("<Enter>", self._enable_mousewheel)
        self.scroll_canvas.bind("<Leave>", self._disable_mousewheel)

        project_bar = ttk.LabelFrame(
            main,
            text="Project",
            style="Section.TLabelframe",
        )
        project_bar.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(0, 10),
        )
        project_bar.columnconfigure(2, weight=1)

        ttk.Button(
            project_bar,
            text="＋ New Project",
            command=self.new_project,
        ).grid(row=0, column=0, padx=(0, 6))

        ttk.Button(
            project_bar,
            text="Open Project",
            command=self.open_project,
        ).grid(row=0, column=1, padx=(0, 12))

        self.recent_project_menu = ttk.Combobox(
            project_bar,
            textvariable=self.recent_project_choice,
            state="readonly",
        )
        self.recent_project_menu.grid(
            row=0,
            column=2,
            sticky="ew",
        )

        ttk.Button(
            project_bar,
            text="Open Recent",
            command=self.open_recent_project,
        ).grid(row=0, column=3, padx=(8, 0))

        self.project_location_label = ttk.Label(
            project_bar,
            text="No project open",
            anchor="w",
        )
        self.project_location_label.grid(
            row=1,
            column=0,
            columnspan=4,
            sticky="ew",
            pady=(8, 0),
        )

        episode = ttk.LabelFrame(main, text="Episode Story", style="Section.TLabelframe")
        episode.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
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
        media.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        media.columnconfigure(1, weight=1)
        self.file_labels: dict[str, ttk.Label] = {}

        timeline = ttk.LabelFrame(
            media,
            text="Visual Timeline",
            padding=8,
        )
        timeline.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=(0, 10),
        )
        timeline.columnconfigure(0, weight=1)
        timeline.rowconfigure(1, weight=1)

        add_controls = ttk.Frame(timeline)
        add_controls.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        add_controls.columnconfigure((0, 1), weight=1)

        ttk.Button(
            add_controls,
            text="＋ Add Photos",
            command=self.add_timeline_photos,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ttk.Button(
            add_controls,
            text="＋ Add Videos",
            command=self.add_timeline_videos,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        list_area = ttk.Frame(timeline)
        list_area.grid(row=1, column=0, sticky="nsew")
        list_area.columnconfigure(0, weight=1)
        list_area.rowconfigure(0, weight=1)

        self.timeline_list = tk.Listbox(
            list_area,
            height=7,
            exportselection=False,
            activestyle="dotbox",
        )
        self.timeline_list.grid(row=0, column=0, sticky="nsew")

        timeline_scrollbar = ttk.Scrollbar(
            list_area,
            orient="vertical",
            command=self.timeline_list.yview,
        )
        timeline_scrollbar.grid(row=0, column=1, sticky="ns")
        self.timeline_list.configure(
            yscrollcommand=timeline_scrollbar.set,
        )

        timeline_controls = ttk.Frame(timeline)
        timeline_controls.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        timeline_controls.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(
            timeline_controls,
            text="↑ Move Up",
            command=lambda: self.move_timeline_item(-1),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ttk.Button(
            timeline_controls,
            text="↓ Move Down",
            command=lambda: self.move_timeline_item(1),
        ).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Button(
            timeline_controls,
            text="Remove",
            command=self.remove_selected_timeline_item,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self._media_row(media, 1, "narration", "🎙", "Narration", self.narration, NARRATION_DIR, (("Audio files", "*.mp3 *.wav *.m4a *.aac"),))
        self._media_row(media, 2, "music", "🎵", "Music", self.music, MUSIC_DIR, (("Audio files", "*.mp3 *.wav *.m4a *.aac"),), optional=True)
        self._media_row(media, 3, "subtitles", "💬", "Story Overlays", self.subtitles, SUBTITLES_DIR, (("Story highlights (primary) or SRT fallback", "*.json *.srt"),), optional=True)

        actions = ttk.Frame(media)
        actions.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        actions.columnconfigure((0, 1, 2, 3, 4), weight=1)
        self.caption_button = ttk.Button(actions, text="Generate Transcript", command=self.start_caption_generation)
        self.caption_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actions, text="Story Highlights", command=self.open_story_highlights).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(actions, text="Review Overlay Source", command=self.review_captions).grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(actions, text="Clear Music", command=lambda: self._clear("music", self.music, "Music cleared.")).grid(row=0, column=3, sticky="ew", padx=4)
        ttk.Button(actions, text="Clear Text", command=lambda: self._clear("subtitles", self.subtitles, "Story overlays cleared.")).grid(row=0, column=4, sticky="ew", padx=(4, 0))

        branding = ttk.LabelFrame(
            main,
            text="Brand Identity & Cover",
            style="Section.TLabelframe",
        )
        branding.grid(
            row=3,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(10, 0),
        )
        branding.columnconfigure(1, weight=1)
        ttk.Label(
            branding,
            text="Opening",
            font=("Helvetica Neue", 11, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(
            branding,
            text="Mother Earth vs. The Algorithm — I'm here to ask different questions.",
            wraplength=700,
            justify="left",
        ).grid(row=0, column=1, columnspan=2, sticky="w")
        ttk.Label(
            branding,
            text="Cover headline",
            font=("Helvetica Neue", 11, "bold"),
        ).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(8, 0))
        ttk.Entry(
            branding,
            textvariable=self.cover_headline,
        ).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ttk.Button(
            branding,
            text="Use Selected Visual",
            command=self.use_selected_visual_for_cover,
        ).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        self.cover_source_label = ttk.Label(
            branding,
            text="Cover source: first timeline visual",
            anchor="w",
        )
        self.cover_source_label.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(6, 0),
        )

        options = ttk.LabelFrame(main, text="Build", style="Section.TLabelframe")
        options.grid(row=2, column=1, sticky="nsew", padx=(6, 0))
        options.columnconfigure(0, weight=1)
        options.rowconfigure(8, weight=1)
        ttk.Label(options, text="Music volume", font=("Helvetica Neue", 11, "bold")).grid(row=0, column=0, sticky="w")
        vol = ttk.Frame(options)
        vol.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        vol.columnconfigure(0, weight=1)
        ttk.Scale(vol, from_=0, to=50, variable=self.music_volume, command=self._volume_changed).grid(row=0, column=0, sticky="ew")
        self.volume_label = ttk.Label(vol, text=f"{int(self.music_volume.get())}%", width=5, anchor="e")
        self.volume_label.grid(row=0, column=1, padx=(8, 0))
        ttk.Checkbutton(options, text="Use story-first highlights", variable=self.story_first).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(options, text="Burn captions into video when supported", variable=self.burn_captions).grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Separator(options).grid(row=4, column=0, sticky="ew", pady=10)
        self.system_label = ttk.Label(options, justify="left", wraplength=300)
        self.system_label.grid(row=5, column=0, sticky="w")
        ttk.Label(options, text="Posting continuity: if subtitle burning is unavailable, Studio still creates a compatible MP4 and keeps the .srt beside it.", wraplength=300, justify="left").grid(row=6, column=0, sticky="w", pady=(10, 10))
        self.progress = ttk.Progressbar(options, mode="indeterminate")
        self.progress.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        self.build_button = ttk.Button(options, text="✨ Build Post-Ready Episode", command=self.start_build, style="Build.TButton")
        self.build_button.grid(row=8, column=0, sticky="ew")
        ttk.Label(options, textvariable=self.status, anchor="n", justify="left", wraplength=300).grid(row=9, column=0, sticky="nsew", pady=(12, 0))

        ttk.Label(
            self,
            text="Mother Earth Studio 0.11.3 • Editor Workflow Polish",
        ).grid(row=4, column=0, pady=(4, 8))

    def _update_scroll_region(self, _event=None) -> None:
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def _resize_scroll_content(self, event) -> None:
        self.scroll_canvas.itemconfigure(self.scroll_window, width=event.width)

    def _enable_mousewheel(self, _event=None) -> None:
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _disable_mousewheel(self, _event=None) -> None:
        self.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event) -> None:
        if event.delta == 0:
            return
        direction = -1 if event.delta > 0 else 1
        self.scroll_canvas.yview_scroll(direction, "units")


    def _refresh_recent_projects(self) -> None:
        self.recent_project_paths = forget_missing_projects()

        display_values = [
            f"{path.name} — {path.parent}"
            for path in self.recent_project_paths
        ]

        self.recent_project_menu["values"] = display_values

        if display_values:
            self.recent_project_choice.set(display_values[0])
        else:
            self.recent_project_choice.set("")

    def _load_startup_project(self) -> None:
        self._refresh_recent_projects()

        if not self.recent_project_paths:
            self.status.set(
                "Create a new project or open an existing project."
            )
            return

        try:
            self._activate_project(
                load_project(self.recent_project_paths[0])
            )
        except ProjectError as exc:
            self.status.set(
                f"Could not reopen the last project: {exc}"
            )

    def new_project(self) -> None:
        title = simpledialog.askstring(
            "New Project",
            "What is this episode or project called?",
            parent=self,
        )

        if title is None:
            return

        title = title.strip()

        if not title:
            messagebox.showwarning(
                "Project title required",
                "Enter a project title before continuing.",
                parent=self,
            )
            return

        try:
            project = create_project(
                title,
                DEFAULT_PROJECTS_ROOT,
            )
        except ProjectAlreadyExistsError:
            existing_path = (
                DEFAULT_PROJECTS_ROOT
                / self._project_slug(title)
            )

            open_existing = messagebox.askyesno(
                "Project already exists",
                "A project with this name already exists. "
                "Open it instead?",
                parent=self,
            )

            if not open_existing:
                return

            try:
                project = load_project(existing_path)
            except ProjectError as exc:
                messagebox.showerror(
                    "Could not open project",
                    str(exc),
                    parent=self,
                )
                return
        except ProjectError as exc:
            messagebox.showerror(
                "Could not create project",
                str(exc),
                parent=self,
            )
            return

        self._activate_project(project)

    def _project_slug(self, title: str) -> str:
        import re

        value = title.strip().lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        return value.strip("-") or "untitled-episode"

    def open_project(self) -> None:
        selected = filedialog.askdirectory(
            initialdir=str(DEFAULT_PROJECTS_ROOT),
            title="Open Mother Earth Studio Project",
        )

        if not selected:
            return

        try:
            project = load_project(Path(selected))
        except InvalidProjectError as exc:
            messagebox.showerror(
                "Not a Studio project",
                str(exc),
                parent=self,
            )
            return
        except ProjectError as exc:
            messagebox.showerror(
                "Could not open project",
                str(exc),
                parent=self,
            )
            return

        self._activate_project(project)

    def open_recent_project(self) -> None:
        selection = self.recent_project_menu.current()

        if selection < 0:
            return

        try:
            project_path = self.recent_project_paths[selection]
            project = load_project(project_path)
        except (IndexError, ProjectError) as exc:
            messagebox.showerror(
                "Could not open recent project",
                str(exc),
                parent=self,
            )
            self._refresh_recent_projects()
            return

        self._activate_project(project)

    def _activate_project(
        self,
        project: EpisodeProject,
    ) -> None:
        if self.current_project is not None:
            self._save_current_project()

        self._loading_project = True
        self.current_project = project

        try:
            self.episode_title.set(project.title)
            branding = project.metadata.get("branding", {})
            self.cover_headline.set(
                str(branding.get("cover_headline") or project.title)
            )
            stored_cover_source = branding.get("cover_source")
            if stored_cover_source:
                try:
                    resolved_cover = project.resolve(
                        str(stored_cover_source)
                    )
                    self.cover_source.set(str(resolved_cover))
                except ProjectError:
                    self.cover_source.set("")
            else:
                self.cover_source.set("")
            self._refresh_cover_source_label()

            script_path = project.file_path("script")
            script_contents = ""

            if script_path and script_path.exists():
                script_contents = script_path.read_text(
                    encoding="utf-8"
                )

                heading = f"# {project.title}\n\n"

                if script_contents.startswith(heading):
                    script_contents = script_contents[len(heading):]

            self.script_text.delete("1.0", "end")
            self.script_text.insert("1.0", script_contents)
            self.script_text.edit_modified(False)

            for key, variable in (
                ("narration", self.narration),
                ("music", self.music),
                ("captions", self.subtitles),
            ):
                project_path = project.file_path(key)

                if project_path and project_path.exists():
                    variable.set(str(project_path))

                    label_key = (
                        "subtitles"
                        if key == "captions"
                        else key
                    )

                    if label_key in self.file_labels:
                        self.file_labels[label_key].config(
                            text=project_path.name
                        )
                else:
                    variable.set("")

                    label_key = (
                        "subtitles"
                        if key == "captions"
                        else key
                    )

                    if label_key in self.file_labels:
                        self.file_labels[label_key].config(
                            text="None selected"
                        )

            self._load_project_timeline(project)

            remember_project(project.root)
            self._refresh_recent_projects()

            self.project_location_label.config(
                text=str(project.root)
            )

            self.title(
                f"Mother Earth Studio 0.11.3 — {project.title}"
            )

            self.status.set(
                f"Project opened: {project.title}"
            )
        finally:
            self._loading_project = False

    def _on_script_modified(self, _event=None) -> None:
        if self._loading_project:
            self.script_text.edit_modified(False)
            return

        if self.script_text.edit_modified():
            self.script_text.edit_modified(False)
            self._schedule_project_autosave()

    def _schedule_project_autosave(self, *_args) -> None:
        if self._loading_project:
            return

        if self.current_project is None:
            return

        if self._autosave_job is not None:
            self.after_cancel(self._autosave_job)

        self._autosave_job = self.after(
            700,
            self._save_current_project,
        )

    def _save_current_project(self) -> None:
        self._autosave_job = None

        project = self.current_project

        if project is None or self._loading_project:
            return

        try:
            title = self.episode_title.get().strip()

            if title:
                project.metadata["title"] = title

            script_path = project.file_path("script")

            if script_path is None:
                script_path = project.root / "script" / "script.md"
                project.metadata["files"]["script"] = (
                    "script/script.md"
                )

            script_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            script_body = self.script_text.get(
                "1.0",
                "end-1c",
            ).rstrip()

            document = f"# {project.title}\n\n"

            if script_body:
                document += script_body + "\n"

            script_path.write_text(
                document,
                encoding="utf-8",
            )

            project.metadata["visual_timeline"] = (
                self._serialize_timeline_for_project(project)
            )
            branding = project.metadata.setdefault("branding", {})
            cover_source = None
            if self.cover_source.get():
                cover_source = project.relative_path(
                    Path(self.cover_source.get())
                )
            branding.update(
                {
                    "enabled": True,
                    "title": "Mother Earth vs. The Algorithm",
                    "tagline": "I'm here to ask different questions.",
                    "intro_duration": 3.5,
                    "cover_headline": (
                        self.cover_headline.get().strip() or title
                    ),
                    "cover_source": cover_source,
                }
            )

            project.save()

            self.project_location_label.config(
                text=f"{project.root} • Saved"
            )
        except (OSError, ProjectError) as exc:
            self.status.set(
                f"Project auto-save failed: {exc}"
            )

    def _store_media_in_project(
        self,
        key: str,
        selected_path: Path,
    ) -> Path:
        project = self.current_project

        if project is None:
            return selected_path

        destination_folder = (
            project.root / "captions"
            if key == "subtitles"
            else project.root / "assets"
        )

        destination_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        destination = (
            destination_folder / selected_path.name
        )

        if selected_path.resolve() != destination.resolve():
            import shutil
            shutil.copy2(selected_path, destination)

        metadata_key = (
            "captions"
            if key == "subtitles"
            else key
        )

        project.set_file(metadata_key, destination)

        return destination

    def _serialize_timeline_for_project(
        self,
        project: EpisodeProject,
    ) -> list[dict]:
        records = serialize_visual_timeline(self.visual_items)

        for record in records:
            path = Path(str(record["path"]))

            try:
                record["path"] = project.relative_path(path)
            except ProjectError:
                record["path"] = str(path)

        return records

    def _load_project_timeline(
        self,
        project: EpisodeProject,
    ) -> None:
        records = project.metadata.get("visual_timeline", [])

        if not isinstance(records, list):
            records = []

        resolved_records: list[dict] = []

        for record in records:
            if not isinstance(record, dict):
                continue

            resolved = dict(record)
            stored_path = Path(str(resolved.get("path", "")))

            if stored_path and not stored_path.is_absolute():
                try:
                    resolved["path"] = str(
                        project.resolve(stored_path.as_posix())
                    )
                except ProjectError:
                    continue

            resolved_records.append(resolved)

        try:
            self.visual_items = deserialize_visual_timeline(
                resolved_records
            )
        except (TypeError, ValueError):
            self.visual_items = []

        if not self.visual_items:
            legacy_video = project.file_path("video")

            if legacy_video and legacy_video.exists():
                self.visual_items = [
                    VisualTimelineItem(
                        path=str(legacy_video),
                        kind="video",
                        order=0,
                        loop=True,
                    )
                ]

        self._refresh_timeline_list()
        self._sync_legacy_video_source()

    def _store_visual_asset(
        self,
        selected_path: Path,
    ) -> Path:
        project = self.current_project

        if project is None:
            return selected_path.resolve()

        destination_folder = project.root / "assets"
        destination_folder.mkdir(parents=True, exist_ok=True)
        destination = destination_folder / selected_path.name

        if (
            destination.exists()
            and selected_path.resolve() != destination.resolve()
        ):
            counter = 2

            while destination.exists():
                destination = (
                    destination_folder
                    / f"{selected_path.stem}-{counter}{selected_path.suffix}"
                )
                counter += 1

        if selected_path.resolve() != destination.resolve():
            import shutil
            shutil.copy2(selected_path, destination)

        return destination.resolve()

    def _add_timeline_paths(
        self,
        selected_paths,
    ) -> None:
        if not selected_paths:
            return

        added = 0

        for selected in selected_paths:
            source = Path(selected)

            try:
                stored = self._store_visual_asset(source)
                kind = detect_visual_kind(stored)
            except (OSError, ProjectError, ValueError) as exc:
                messagebox.showerror(
                    "Could not add visual asset",
                    str(exc),
                    parent=self,
                )
                continue

            self.visual_items.append(
                VisualTimelineItem(
                    path=str(stored),
                    kind=kind,
                    order=len(self.visual_items),
                )
            )
            added += 1

        if not added:
            return

        self._refresh_timeline_list()
        self._sync_legacy_video_source()
        self._schedule_project_autosave()
        self.status.set(
            f"Added {added} visual asset"
            f"{'s' if added != 1 else ''} to the timeline."
        )

    def add_timeline_photos(self) -> None:
        selected = filedialog.askopenfilenames(
            initialdir=str(FOREST_DIR),
            title="Add photos to the visual timeline",
            filetypes=[
                (
                    "Image files",
                    "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff",
                ),
                ("All files", "*.*"),
            ],
        )
        self._add_timeline_paths(selected)

    def add_timeline_videos(self) -> None:
        selected = filedialog.askopenfilenames(
            initialdir=str(FOREST_DIR),
            title="Add videos to the visual timeline",
            filetypes=[
                ("Video files", "*.mp4 *.mov *.m4v"),
                ("All files", "*.*"),
            ],
        )
        self._add_timeline_paths(selected)

    def _selected_timeline_index(self) -> int | None:
        selection = self.timeline_list.curselection()

        if not selection:
            self.status.set(
                "Select a visual timeline item first."
            )
            return None

        return int(selection[0])

    def move_timeline_item(self, direction: int) -> None:
        source_index = self._selected_timeline_index()

        if source_index is None:
            return

        destination_index = source_index + direction

        if not 0 <= destination_index < len(self.visual_items):
            return

        self.visual_items = reorder_visual_items(
            self.visual_items,
            source_index,
            destination_index,
        )
        self._refresh_timeline_list(destination_index)
        self._sync_legacy_video_source()
        self._schedule_project_autosave()

    def remove_selected_timeline_item(self) -> None:
        selected_index = self._selected_timeline_index()

        if selected_index is None:
            return

        self.visual_items = remove_visual_item(
            self.visual_items,
            selected_index,
        )

        next_index = min(
            selected_index,
            len(self.visual_items) - 1,
        )

        self._refresh_timeline_list(
            next_index if next_index >= 0 else None
        )
        self._sync_legacy_video_source()
        self._schedule_project_autosave()
        self.status.set("Visual asset removed from the timeline.")

    def _refresh_timeline_list(
        self,
        selected_index: int | None = None,
    ) -> None:
        self.timeline_list.delete(0, "end")

        for index, item in enumerate(self.visual_items, start=1):
            icon = "PHOTO" if item.kind == "image" else "VIDEO"
            self.timeline_list.insert(
                "end",
                f"{index}. [{icon}] {Path(item.path).name}",
            )

        if (
            selected_index is not None
            and 0 <= selected_index < len(self.visual_items)
        ):
            self.timeline_list.selection_set(selected_index)
            self.timeline_list.activate(selected_index)
            self.timeline_list.see(selected_index)

        self._refresh_build_readiness()

    def _sync_legacy_video_source(self) -> None:
        first_video = next(
            (
                Path(item.path)
                for item in self.visual_items
                if item.kind == "video"
            ),
            None,
        )

        self.video.set(str(first_video) if first_video else "")

        if self.current_project is not None:
            if first_video and first_video.exists():
                self.current_project.set_file(
                    "video",
                    first_video,
                )
            else:
                self.current_project.set_file(
                    "video",
                    None,
                )

    def _refresh_cover_source_label(self) -> None:
        if self.cover_source.get():
            name = Path(self.cover_source.get()).name
            self.cover_source_label.config(
                text=f"Cover source: {name}"
            )
        else:
            self.cover_source_label.config(
                text="Cover source: first timeline visual"
            )

    def use_selected_visual_for_cover(self) -> None:
        selected_index = self._selected_timeline_index()
        if selected_index is None:
            return
        selected = Path(self.visual_items[selected_index].path)
        self.cover_source.set(str(selected))
        self._refresh_cover_source_label()
        self._schedule_project_autosave()
        self.status.set(
            f"Cover source selected: {selected.name}"
        )

    def _cover_source_path(self, visual_items) -> Path | None:
        if self.cover_source.get():
            candidate = Path(self.cover_source.get())
            if candidate.exists():
                return candidate
        if visual_items:
            candidate = Path(visual_items[0].path)
            if candidate.exists():
                return candidate
        return None

    def _on_close(self) -> None:
        if self.current_project is not None:
            self._save_current_project()

        self.destroy()

    def _media_row(self, parent, row, key, icon, name, variable, initial_dir, filetypes, optional=False):
        ttk.Label(parent, text=f"{icon}  {name}", font=("Helvetica Neue", 11, "bold")).grid(row=row, column=0, sticky="w", pady=8)
        label = ttk.Label(parent, text="None selected", anchor="w")
        label.grid(row=row, column=1, sticky="ew", padx=12, pady=8)
        self.file_labels[key] = label
        def choose():
            path = filedialog.askopenfilename(initialdir=str(initial_dir), title=f"Choose {name.lower()}", filetypes=list(filetypes) + [("All files", "*.*")])
            if path:
                selected_path = Path(path)

                try:
                    stored_path = self._store_media_in_project(
                        key,
                        selected_path,
                    )
                except (OSError, ProjectError) as exc:
                    messagebox.showerror(
                        "Could not add media",
                        str(exc),
                        parent=self,
                    )
                    return

                variable.set(str(stored_path))
                label.config(text=stored_path.name)
                self.status.set(f"{name} selected.")
        self._refresh_build_readiness()
        ttk.Button(parent, text="Choose", command=choose, width=10).grid(row=row, column=2, sticky="e", pady=8)

    def _clear(self, key, variable, message):
        variable.set("")
        self.file_labels[key].config(text="None selected")

        if self.current_project is not None:
            metadata_key = (
                "captions"
                if key == "subtitles"
                else key
            )
            self.current_project.set_file(
                metadata_key,
                None,
            )

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
        threading.Thread(target=self._caption_worker, args=(narration, destination, script, bool(self.story_first.get())), daemon=True).start()

    def _caption_worker(self, narration, destination, script, story_first):
        try:
            language = generate_captions(narration, destination, script, self.settings.whisper_model, story_first=story_first)
        except Exception as exc:
            self.after(0, lambda exc=exc: self._finish_error(f"Caption generation failed:\n{exc}"))
            return
        def done():
            self._busy(False)
            self.subtitles.set(str(destination))
            self.file_labels["subtitles"].config(text=destination.name)
            mode = "story-first highlights" if story_first else ("approved script wording" if script else "Whisper wording")
            self.status.set(f"✅ Captions created with {mode}.\n{destination.name}\nLanguage: {language or 'unknown'}")
        self.after(0, done)

    def _build_readiness_summary(self) -> str:
        visual_count = len(self.visual_items)
        photo_count = sum(
            item.kind == "image"
            for item in self.visual_items
        )
        video_count = sum(
            item.kind == "video"
            for item in self.visual_items
        )

        missing: list[str] = []
        if not self.episode_title.get().strip():
            missing.append("title")
        if not visual_count:
            missing.append("visuals")
        if not self.narration.get():
            missing.append("narration")

        if missing:
            heading = "Not ready: add " + ", ".join(missing)
        elif photo_count == visual_count:
            heading = "Ready to build a photo reel"
        elif video_count == 1 and visual_count == 1:
            heading = "Ready to build a video episode"
        else:
            heading = "Timeline needs attention before building"

        if photo_count == visual_count and visual_count:
            timeline = f"{photo_count} photo"
            timeline += "s" if photo_count != 1 else ""
        elif video_count == visual_count and visual_count:
            timeline = f"{video_count} video"
            timeline += "s" if video_count != 1 else ""
        elif visual_count:
            timeline = (
                f"{photo_count} photos + {video_count} videos"
            )
        else:
            timeline = "empty"

        narration = (
            Path(self.narration.get()).name
            if self.narration.get()
            else "not selected"
        )
        music = (
            Path(self.music.get()).name
            if self.music.get()
            else "none"
        )
        captions = (
            Path(self.subtitles.get()).name
            if self.subtitles.get()
            else "none"
        )

        return (
            f"{heading}\n"
            f"Timeline: {timeline}\n"
            f"Narration: {narration}\n"
            f"Music: {music}\n"
            f"Story overlays: {captions}"
        )

    def _refresh_build_readiness(self) -> None:
        self.status.set(self._build_readiness_summary())

    def open_story_highlights(self):
        current = Path(self.subtitles.get()) if self.subtitles.get() else None
        source_srt = current if current and current.suffix.lower() == ".srt" else None
        if source_srt is None and self.current_project:
            candidates = sorted((self.current_project.root / "captions").glob("*.srt"), key=lambda p: p.stat().st_mtime, reverse=True)
            source_srt = candidates[0] if candidates else None
        if self.current_project:
            destination = self.current_project.root / "captions" / "story_highlights.json"
        else:
            destination = SUBTITLES_DIR / "story_highlights.json"
        def saved(path):
            self.subtitles.set(str(path))
            self.file_labels["subtitles"].config(text=path.name)
            if self.current_project:
                self.current_project.set_file("captions", path)
            self.status.set("✅ Story highlights approved. Build will render only this editorial overlay track.")
        preview_source = Path(self.video.get()) if self.video.get() else None
        if preview_source is None and self.visual_items:
            preview_source = Path(self.visual_items[0].path)
        StoryHighlightsEditor(
            self,
            destination,
            source_srt=source_srt,
            on_saved=saved,
            preview_source=preview_source,
            ffmpeg_path=self.system.ffmpeg_path or "ffmpeg",
        )

    def review_captions(self):
        if not self.subtitles.get():
            message = (
                "Generate or choose captions before reviewing them."
            )
            self.status.set(message)
            messagebox.showwarning(
                "Mother Earth Studio",
                message,
                parent=self,
            )
            return

        caption_path = Path(self.subtitles.get())

        if caption_path.suffix.lower() == ".json":
            self.open_story_highlights()
            return

        if self._open_file(caption_path):
            self.status.set(
                "Caption file opened for review. "
                "Save your edits before building."
            )
            return

        if self._reveal_file(caption_path):
            message = (
                "No default application is assigned to .srt files. "
                "Mother Earth Studio revealed the caption file in "
                "Finder instead."
            )
            self.status.set(message)
            messagebox.showinfo(
                "Caption file revealed",
                message,
                parent=self,
            )
            return

        message = (
            "Mother Earth Studio could not open or reveal the "
            f"selected caption file:\n{caption_path}"
        )
        self.status.set(message)
        messagebox.showerror(
            "Could not access captions",
            message,
            parent=self,
        )

    def start_build(self):
        title = self.episode_title.get().strip()
        if not title or not self.narration.get():
            self.status.set(
                "Episode title and narration are required."
            )
            return

        if not self.visual_items:
            self.status.set(
                "Add at least one photo or video to the visual timeline."
            )
            return

        self.settings.music_volume = int(self.music_volume.get())
        self.settings.burn_captions_when_supported = bool(self.burn_captions.get())
        save_settings(self.settings)
        number, output = next_output_path(OUTPUT_DIR, title)
        self._busy(True)
        self.status.set(f"Building Episode {number:03d}...")
        kwargs = dict(
            narration=Path(self.narration.get()),
            output=output,
            system=self.system,
            music=Path(self.music.get()) if self.music.get() else None,
            subtitles=Path(self.subtitles.get()) if self.subtitles.get() else None,
            music_volume=int(self.music_volume.get()),
            burn_captions=bool(self.burn_captions.get()),
        )
        visual_items = list(self.visual_items)
        identity = BrandIdentity()
        cover_headline = (
            self.cover_headline.get().strip() or title
        )
        cover_source = self._cover_source_path(visual_items)
        cache_dir = (
            self.current_project.root / "assets" / ".generated"
            if self.current_project is not None
            else OUTPUT_DIR / ".generated"
        )
        threading.Thread(
            target=self._build_worker,
            args=(number, visual_items, cache_dir, identity, cover_headline, cover_source, kwargs),
            daemon=True,
        ).start()

    def _build_worker(
        self,
        number,
        visual_items,
        cache_dir,
        identity,
        cover_headline,
        cover_source,
        kwargs,
    ):
        try:
            prepared = prepare_visual_source(
                visual_items,
                kwargs["narration"],
                cache_dir,
                ffmpeg_path=(
                    getattr(self.system, "ffmpeg_path", None)
                    or "ffmpeg"
                ),
            )
            build_kwargs = dict(kwargs)
            build_kwargs["video"] = prepared.path
            build_kwargs["brand_identity"] = identity
            result = build_episode(**build_kwargs)
            cover_output = None
            if cover_source is not None:
                cover_dir = (
                    self.current_project.root / "covers"
                    if self.current_project is not None
                    else OUTPUT_DIR / "covers"
                )
                cover_output = cover_dir / (
                    f"{result.output.stem}-cover.png"
                )
                generate_cover(
                    cover_source,
                    cover_output,
                    cover_headline,
                    identity,
                    ffmpeg_path=(
                        getattr(self.system, "ffmpeg_path", None)
                        or "ffmpeg"
                    ),
                )
                if self.current_project is not None:
                    branding = self.current_project.metadata.setdefault(
                        "branding",
                        {},
                    )
                    branding["cover_output"] = (
                        self.current_project.relative_path(cover_output)
                    )
                    self.current_project.save()
        except Exception as exc:
            self.after(0, lambda exc=exc: self._finish_error(f"Episode build failed:\n{exc}"))
            return
        def done():
            self._busy(False)
            message = f"✅ Episode {number:03d} created\n{result.output.name}"
            if prepared.generated:
                message += (
                    f"\n\nPhoto reel created from "
                    f"{prepared.image_count} images."
                )
            if result.warning:
                message += f"\n\n{result.warning}"
            elif kwargs.get("subtitles") and result.captions_burned:
                message += f"\n\n✅ Captions visibly burned using {result.caption_renderer}."
            elif kwargs.get("subtitles"):
                message += "\n\n⚠️ MP4 created without burned captions."
            if cover_output is not None:
                message += (
                    f"\n\nCover created: {cover_output.name}"
                )
            if result.log_path:
                message += f"\nBuild log: {result.log_path.name}"
            self.status.set(message)
            self._open_file(result.output)
        self.after(0, done)

    def _finish_error(self, message):
        self._busy(False)
        self.status.set(message)
        messagebox.showerror("Mother Earth Studio", message)

    def _open_file(self, path: Path) -> bool:
        path = Path(path)

        if not path.exists():
            return False

        try:
            if sys.platform == "darwin":
                completed = subprocess.run(
                    ["open", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                return completed.returncode == 0

            if os.name == "nt":
                os.startfile(path)
                return True

            completed = subprocess.run(
                ["xdg-open", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
            return completed.returncode == 0
        except Exception:
            return False

    def _reveal_file(self, path: Path) -> bool:
        path = Path(path)

        if not path.exists():
            return False

        try:
            if sys.platform == "darwin":
                completed = subprocess.run(
                    ["open", "-R", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                return completed.returncode == 0

            return self._open_file(path.parent)
        except Exception:
            return False


def run() -> None:
    StudioApp().mainloop()
