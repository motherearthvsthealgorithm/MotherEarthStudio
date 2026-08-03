from __future__ import annotations

import re
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from .adaptive_typography import layout_overlay_text
from .story_highlights import (
    StoryHighlight,
    assess_highlight_confidence,
    load_highlights,
    quick_rewrite_text,
    save_highlights,
    suggest_highlights_from_srt,
)


def clamp_preview_time(value: float, maximum: float) -> float:
    return max(0.0, min(float(value), max(0.0, float(maximum))))


def preview_time_for_highlight(item: StoryHighlight) -> float:
    return max(0.0, item.start + max(0.0, item.end - item.start) / 2.0)


class StoryHighlightsEditor(tk.Toplevel):
    def __init__(
        self,
        parent,
        destination: Path,
        source_srt: Path | None = None,
        on_saved=None,
        preview_source: Path | None = None,
        ffmpeg_path: str = "ffmpeg",
    ):
        super().__init__(parent)
        self.destination = destination
        self.source_srt = source_srt
        self.on_saved = on_saved
        self.items: list[StoryHighlight] = []
        self.preview_source = Path(preview_source).expanduser() if preview_source else None
        self.ffmpeg_path = ffmpeg_path
        self.preview_duration = 0.0
        self.preview_job = None
        self.preview_generation = 0
        self.preview_photo = None
        self.preview_collapsed = False
        self.preview_temp = Path(tempfile.mkdtemp(prefix="mother_earth_preview_"))
        self.title("Story Highlights Editor v2.1 — Adaptive Typography Engine")
        self.geometry("1260x760")
        self.minsize(1040, 660)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self._bind_shortcuts()
        self._load()
        self._probe_preview_duration()

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self, padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Story Highlights", font=("Helvetica Neue", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="AI drafts. You direct. Review quickly without losing sight of the highlight list.",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.preview_toggle_text = tk.StringVar(value="Hide Preview")
        ttk.Button(
            header,
            textvariable=self.preview_toggle_text,
            command=self.toggle_preview,
            width=14,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(12, 0))

        self.content = ttk.Panedwindow(self, orient="horizontal")
        self.content.grid(row=1, column=0, sticky="nsew", padx=16)

        table_frame = ttk.Frame(self.content)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.content.add(table_frame, weight=5)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("confidence", "fit", "start", "end", "position", "text"),
            show="headings",
            selectmode="browse",
        )
        columns = [
            ("confidence", "Review", 78),
            ("fit", "Fit", 72),
            ("start", "Start", 68),
            ("end", "End", 68),
            ("position", "Position", 105),
            ("text", "Approved overlay text", 500),
        ]
        for col, label, width in columns:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="w", stretch=(col == "text"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self.update_preview())
        self.tree.bind("<Up>", self._keyboard_selection_changed, add="+")
        self.tree.bind("<Down>", self._keyboard_selection_changed, add="+")
        self.tree.tag_configure("review", background="#FFF2CC")
        self.tree.tag_configure("overflow", background="#FFD6D6")
        self.tree.tag_configure("tight", background="#FFF2CC")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        self.preview_pane = ttk.LabelFrame(self.content, text="Live Episode Preview", padding=10)
        self.preview_pane.columnconfigure(0, weight=1)
        self.preview_pane.rowconfigure(1, weight=1)
        self.content.add(self.preview_pane, weight=3)

        preview_toolbar = ttk.Frame(self.preview_pane)
        preview_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        preview_toolbar.columnconfigure(0, weight=1)
        ttk.Label(
            preview_toolbar,
            text="Select a highlight; the preview follows automatically.",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            preview_toolbar,
            text="Open Large Preview",
            command=self.open_large_preview,
        ).grid(row=0, column=1, sticky="e")

        self.preview_canvas = tk.Canvas(
            self.preview_pane,
            width=360,
            height=640,
            background="#171717",
            highlightthickness=0,
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda _e: self._draw_preview_overlay())
        self.preview_canvas.bind("<Double-1>", lambda _e: self.open_large_preview())

        scrub = ttk.Frame(self.preview_pane)
        scrub.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        scrub.columnconfigure(0, weight=1)
        self.preview_time = tk.DoubleVar(value=0.0)
        self.preview_scale = ttk.Scale(
            scrub,
            from_=0.0,
            to=60.0,
            variable=self.preview_time,
            command=self._preview_scale_changed,
        )
        self.preview_scale.grid(row=0, column=0, sticky="ew")
        self.preview_clock = tk.StringVar(value="0.00s")
        ttk.Label(scrub, textvariable=self.preview_clock, width=9, anchor="e").grid(row=0, column=1, padx=(8, 0))

        self.preview_meta = tk.StringVar(value="Select a highlight to preview it on the episode visual.")
        ttk.Label(self.preview_pane, textvariable=self.preview_meta, justify="center", wraplength=380).grid(row=3, column=0, pady=(6, 0))

        controls = ttk.Frame(self, padding=(16, 8, 16, 4))
        controls.grid(row=2, column=0, sticky="ew")
        buttons = [
            ("Suggest", self.suggest),
            ("Add", self.add),
            ("Edit", self.edit_selected),
            ("Delete", self.delete),
            ("Merge Previous", self.merge_previous),
            ("Split", self.split_selected),
            ("Quick Rewrite", self.quick_rewrite),
            ("Save Highlights", self.save),
        ]
        for i, (label, command) in enumerate(buttons):
            controls.columnconfigure(i, weight=1)
            ttk.Button(controls, text=label, command=command).grid(row=0, column=i, sticky="ew", padx=3)

        ttk.Label(
            self,
            text="Shortcuts: ↑/↓ review • Delete removes • Return edits • ⌘M merges • ⌘R rewrites • ⌘S saves",
            padding=(16, 5, 16, 14),
        ).grid(row=3, column=0, sticky="w")

    def toggle_preview(self):
        if self.preview_collapsed:
            self.content.add(self.preview_pane, weight=3)
            self.preview_toggle_text.set("Hide Preview")
            self.preview_collapsed = False
            self.update_preview()
        else:
            self.content.forget(self.preview_pane)
            self.preview_toggle_text.set("Show Preview")
            self.preview_collapsed = True

    def _keyboard_selection_changed(self, _event=None):
        self.after_idle(self.update_preview)

    def open_large_preview(self):
        idx = self.selected_index()
        if idx is None:
            messagebox.showinfo("Live Preview", "Select a highlight first.", parent=self)
            return
        win = tk.Toplevel(self)
        win.title("Large Episode Preview")
        win.geometry("560x760")
        win.transient(self)
        canvas = tk.Canvas(win, background="#171717", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=12, pady=12)

        def draw(_event=None):
            canvas.delete("all")
            width = max(480, canvas.winfo_width())
            height = max(700, canvas.winfo_height())
            if self.preview_photo:
                canvas.create_image(width / 2, height / 2, image=self.preview_photo, anchor="center")
            else:
                canvas.create_rectangle(0, 0, width, height, fill="#171717", outline="")
                canvas.create_text(width / 2, height / 2, text="Episode frame preview", fill="#A7A7A7", font=("Helvetica Neue", 16))
            item = self.items[idx]
            y_map = {"upper_center": 0.22, "middle_center": 0.50, "lower_center": 0.735}
            y = height * y_map.get(item.position, 0.735)
            wrap = max(320, int(width * 0.78))
            font_size = max(20, round(height / 27))
            canvas.create_text(width / 2 + 1, y + 2, text=layout.text, width=wrap, justify="center", fill="#161616", font=("Helvetica Neue", font_size, "bold"), anchor="center")
            canvas.create_text(width / 2, y, text=layout.text, width=wrap, justify="center", fill="#F4F0E8", font=("Helvetica Neue", font_size, "bold"), anchor="center")

        canvas.bind("<Configure>", draw)
        self.after(50, draw)
    def _bind_shortcuts(self):
        self.bind("<Delete>", lambda _e: self.delete())
        self.bind("<BackSpace>", lambda _e: self.delete())
        self.bind("<Return>", lambda _e: self.edit_selected())
        self.bind("<Command-m>", lambda _e: self.merge_previous())
        self.bind("<Command-r>", lambda _e: self.quick_rewrite())
        self.bind("<Command-s>", lambda _e: self.save())

    def _load(self):
        if self.destination.exists():
            try:
                self.items = load_highlights(self.destination)
            except Exception as exc:
                messagebox.showwarning("Story Highlights", str(exc), parent=self)
        elif self.source_srt and self.source_srt.exists():
            self.items = suggest_highlights_from_srt(self.source_srt)
        self._reassess_all()
        self.refresh()

    def _reassess_all(self):
        for item in self.items:
            item.confidence, item.review_reason = assess_highlight_confidence(item.text, item.start, item.end)

    def refresh(self, select_index: int | None = None):
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self.items):
            review = item.confidence < 0.70
            badge = "⚠ Review" if review else f"{round(item.confidence * 100)}%"
            layout = layout_overlay_text(item.text)
            fit_badge = {"good": "✓ Fits", "tight": "⚠ Tight", "overflow": "✕ Won't fit"}[layout.fit_status]
            tags = []
            if layout.fit_status == "overflow":
                tags.append("overflow")
            elif layout.fit_status == "tight" or review:
                tags.append("tight")
            self.tree.insert(
                "", "end", iid=str(i),
                values=(badge, fit_badge, f"{item.start:.2f}", f"{item.end:.2f}", item.position, item.text),
                tags=tuple(tags),
            )
        if select_index is not None and self.items:
            select_index = max(0, min(select_index, len(self.items) - 1))
            self.tree.selection_set(str(select_index))
            self.tree.focus(str(select_index))
            self.tree.see(str(select_index))
        self.update_preview()

    def selected_index(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def update_preview(self):
        idx = self.selected_index()
        if idx is None or idx >= len(self.items):
            self.preview_meta.set("Select a highlight to preview it on the episode visual.")
            self._draw_preview_overlay()
            return
        item = self.items[idx]
        reason = item.review_reason or "No obvious fragment warning"
        self.preview_meta.set(
            f"{item.start:.2f}s–{item.end:.2f}s • {item.position} • "
            f"confidence {round(item.confidence * 100)}%\n{reason}"
        )
        midpoint = preview_time_for_highlight(item)
        self.preview_time.set(midpoint)
        self.preview_clock.set(f"{midpoint:.2f}s")
        self._schedule_preview_frame(midpoint)
        self._draw_preview_overlay()

    def _close(self):
        try:
            for child in self.preview_temp.glob("*"):
                child.unlink(missing_ok=True)
            self.preview_temp.rmdir()
        except OSError:
            pass
        self.destroy()

    def _probe_preview_duration(self):
        if not self.preview_source or not self.preview_source.exists():
            self.preview_meta.set("No episode visual is available. Add a visual to enable live preview.")
            return
        def work():
            duration = 0.0
            try:
                result = subprocess.run(
                    [self.ffmpeg_path.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries",
                     "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(self.preview_source)],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    duration = float((result.stdout or "0").strip())
            except Exception:
                duration = 0.0
            if duration <= 0.0 and self.items:
                duration = max(item.end for item in self.items)
            self.after(0, lambda: self._set_preview_duration(duration))
        threading.Thread(target=work, daemon=True).start()

    def _set_preview_duration(self, duration: float):
        self.preview_duration = max(0.0, duration)
        self.preview_scale.configure(to=max(1.0, self.preview_duration))
        self._schedule_preview_frame(self.preview_time.get())

    def _preview_scale_changed(self, raw_value):
        value = clamp_preview_time(float(raw_value), self.preview_duration or float(raw_value))
        self.preview_clock.set(f"{value:.2f}s")
        if self.preview_job is not None:
            self.after_cancel(self.preview_job)
        self.preview_job = self.after(140, lambda: self._schedule_preview_frame(value))

    def _schedule_preview_frame(self, timestamp: float):
        if not self.preview_source or not self.preview_source.exists():
            self._draw_preview_overlay()
            return
        self.preview_generation += 1
        generation = self.preview_generation
        timestamp = clamp_preview_time(timestamp, self.preview_duration or timestamp)
        destination = self.preview_temp / f"frame_{generation}.png"

        def work():
            command = [
                self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{timestamp:.3f}", "-i", str(self.preview_source),
                "-frames:v", "1",
                "-vf", "scale=360:640:force_original_aspect_ratio=increase,crop=360:640",
                str(destination),
            ]
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=20)
                if result.returncode == 0 and destination.exists():
                    self.after(0, lambda: self._install_preview_frame(destination, generation))
            except Exception:
                return
        threading.Thread(target=work, daemon=True).start()

    def _install_preview_frame(self, path: Path, generation: int):
        if generation != self.preview_generation or not path.exists():
            return
        try:
            self.preview_photo = tk.PhotoImage(file=str(path))
        except tk.TclError:
            self.preview_photo = None
        self.preview_collapsed = False
        self._draw_preview_overlay()

    def _draw_preview_overlay(self):
        if not hasattr(self, "preview_canvas"):
            return
        canvas = self.preview_canvas
        canvas.delete("all")
        width = max(320, canvas.winfo_width())
        height = max(500, canvas.winfo_height())
        if self.preview_photo:
            canvas.create_image(width / 2, height / 2, image=self.preview_photo, anchor="center")
        else:
            canvas.create_rectangle(0, 0, width, height, fill="#171717", outline="")
            canvas.create_text(width / 2, height / 2, text="Episode frame preview", fill="#A7A7A7", font=("Helvetica Neue", 16))

        idx = self.selected_index()
        if idx is None or idx >= len(self.items):
            return
        item = self.items[idx]
        y_map = {"upper_center": 0.22, "middle_center": 0.50, "lower_center": 0.735}
        y = height * y_map.get(item.position, 0.735)
        # Match the renderer's warm ivory, safe margins, two-line wrapping, and subtle shadow.
        layout = layout_overlay_text(item.text)
        wrap = max(220, int(width * 0.80))
        font_size = max(14, round(height / layout.font_divisor))
        canvas.create_text(
            width / 2 + 1, y + 2, text=layout.text, width=wrap, justify="center",
            fill="#161616", font=("Helvetica Neue", font_size, "bold"), anchor="center",
        )
        canvas.create_text(
            width / 2, y, text=layout.text, width=wrap, justify="center",
            fill="#F4F0E8", font=("Helvetica Neue", font_size, "bold"), anchor="center",
        )

    def suggest(self):
        if not self.source_srt or not self.source_srt.exists():
            messagebox.showwarning("Story Highlights", "Choose or generate an SRT caption file first.", parent=self)
            return
        if self.items and not messagebox.askyesno("Replace highlights?", "Replace the current list with new suggestions?", parent=self):
            return
        self.items = suggest_highlights_from_srt(self.source_srt)
        self.refresh(0)

    def _dialog(self, item: StoryHighlight | None = None):
        win = tk.Toplevel(self)
        win.title("Edit Story Highlight")
        win.transient(self)
        win.grab_set()
        win.columnconfigure(1, weight=1)
        text = tk.StringVar(value=item.text if item else "")
        start = tk.StringVar(value=f"{item.start:.2f}" if item else "0.00")
        end = tk.StringVar(value=f"{item.end:.2f}" if item else "4.00")
        pos = tk.StringVar(value=item.position if item else "lower_center")
        fade = tk.StringVar(value=f"{item.fade_duration:.2f}" if item else "0.28")
        fields = [("Text", text), ("Start (seconds)", start), ("End (seconds)", end), ("Fade (seconds)", fade)]
        for row, (label, var) in enumerate(fields):
            ttk.Label(win, text=label, padding=8).grid(row=row, column=0, sticky="w")
            ttk.Entry(win, textvariable=var, width=62).grid(row=row, column=1, sticky="ew", padx=8, pady=5)
        ttk.Label(win, text="Position", padding=8).grid(row=4, column=0, sticky="w")
        ttk.Combobox(
            win, textvariable=pos,
            values=("upper_center", "middle_center", "lower_center"),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", padx=8, pady=5)
        result = []

        def ok():
            try:
                candidate = StoryHighlight(
                    text.get(), float(start.get()), float(end.get()), pos.get(), float(fade.get())
                ).normalized()
            except ValueError:
                messagebox.showerror("Invalid timing", "Start, end, and fade must be numbers.", parent=win)
                return
            if not candidate.text:
                messagebox.showerror("Missing text", "Overlay text cannot be empty.", parent=win)
                return
            candidate.confidence, candidate.review_reason = assess_highlight_confidence(
                candidate.text, candidate.start, candidate.end
            )
            result.append(candidate)
            win.destroy()

        ttk.Button(win, text="Save", command=ok).grid(row=5, column=1, sticky="e", padx=8, pady=12)
        self.wait_window(win)
        return result[0] if result else None

    def add(self):
        item = self._dialog()
        if item:
            self.items.append(item)
            self.items.sort(key=lambda x: x.start)
            self.refresh(self.items.index(item))

    def edit_selected(self):
        idx = self.selected_index()
        if idx is None:
            return
        item = self._dialog(self.items[idx])
        if item:
            self.items[idx] = item
            self.items.sort(key=lambda x: x.start)
            self.refresh(self.items.index(item))

    def delete(self):
        idx = self.selected_index()
        if idx is None:
            return
        self.items.pop(idx)
        self.refresh(min(idx, len(self.items) - 1) if self.items else None)

    def merge_previous(self):
        idx = self.selected_index()
        if idx is None or idx == 0:
            messagebox.showinfo("Merge", "Select a highlight that has a previous highlight.", parent=self)
            return
        previous = self.items[idx - 1]
        current = self.items[idx]
        joined = f"{previous.text.rstrip(' .…')}… {current.text.lstrip()}"
        merged = StoryHighlight(
            text=joined,
            start=previous.start,
            end=current.end,
            position=previous.position,
            fade_duration=max(previous.fade_duration, current.fade_duration),
        ).normalized()
        merged.confidence, merged.review_reason = assess_highlight_confidence(merged.text, merged.start, merged.end)
        self.items[idx - 1:idx + 1] = [merged]
        self.refresh(idx - 1)

    def split_selected(self):
        idx = self.selected_index()
        if idx is None:
            return
        item = self.items[idx]
        default = max(1, len(item.text) // 2)
        split_at = simpledialog.askinteger(
            "Split Highlight",
            "Character position to split at (choose a space near the middle):",
            initialvalue=default,
            minvalue=1,
            maxvalue=max(1, len(item.text) - 1),
            parent=self,
        )
        if split_at is None:
            return
        left = item.text[:split_at].strip()
        right = item.text[split_at:].strip()
        if not left or not right:
            messagebox.showwarning("Split Highlight", "The split must leave text on both sides.", parent=self)
            return
        duration = item.end - item.start
        ratio = len(left) / max(1, len(left) + len(right))
        midpoint = item.start + duration * ratio
        first = StoryHighlight(left, item.start, midpoint, item.position, item.fade_duration).normalized()
        second = StoryHighlight(right, midpoint + 0.12, item.end, item.position, item.fade_duration).normalized()
        for candidate in (first, second):
            candidate.confidence, candidate.review_reason = assess_highlight_confidence(
                candidate.text, candidate.start, candidate.end
            )
        self.items[idx:idx + 1] = [first, second]
        self.refresh(idx)

    def quick_rewrite(self):
        idx = self.selected_index()
        if idx is None:
            return
        item = self.items[idx]
        rewritten = quick_rewrite_text(item.text)
        candidate = simpledialog.askstring(
            "Quick Rewrite",
            "Edit the cleaned suggestion:",
            initialvalue=rewritten,
            parent=self,
        )
        if candidate is None or not candidate.strip():
            return
        item.text = candidate.strip()
        item.confidence, item.review_reason = assess_highlight_confidence(item.text, item.start, item.end)
        self.refresh(idx)

    def save(self):
        self._reassess_all()
        save_highlights(self.destination, self.items, str(self.source_srt or ""))
        if self.on_saved:
            self.on_saved(self.destination)
        low_confidence = sum(1 for item in self.items if item.confidence < 0.70)
        note = f"\n\n{low_confidence} highlight(s) are still flagged for review." if low_confidence else ""
        messagebox.showinfo(
            "Story Highlights",
            f"Saved {len(self.items)} approved highlights.{note}",
            parent=self,
        )
        self.destroy()
