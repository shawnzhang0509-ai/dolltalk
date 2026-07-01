#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DollWorldwide 剧本编辑器 — 本地小程序，可视化插入场景和台词。

启动:
  python script_editor.py
  或双击 剧本编辑器.bat
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
DRAMAS_DIR = ROOT / "dramas"

POSITIONS = ("center", "left", "right")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config_lists() -> tuple[list[str], list[str], list[str]]:
    dolls = list(load_yaml(CONFIG_DIR / "dolls.yaml").keys())
    backgrounds = list(load_yaml(CONFIG_DIR / "backgrounds.yaml").keys())
    emo_cfg = load_yaml(CONFIG_DIR / "emotions.yaml")
    emotions = emo_cfg.get("emotions", ["happy", "sad", "waiting", "neutral"])
    return dolls or ["nova"], backgrounds or ["rainy_night"], emotions


def drama_to_yaml_text(drama: dict) -> str:
    lines = [
        f"title: {drama['title']}",
        f"doll: {drama['doll']}",
        "",
        "scenes:",
    ]
    for scene in drama.get("scenes", []):
        lines.append(f"  - title: {scene['title']}")
        lines.append(f"    background: {scene['background']}")
        lines.append("    beats:")
        for beat in scene.get("beats", []):
            sub = str(beat.get("subtitle", "")).replace('"', "'")
            parts = [
                f"start: {int(beat['start'])}",
                f"end: {int(beat['end'])}",
                f'subtitle: "{sub}"',
                f"position: {beat.get('position', 'center')}",
                f"scale: {round(float(beat.get('scale', 0.5)), 2)}",
            ]
            if beat.get("emotion"):
                parts.append(f"emotion: {beat['emotion']}")
            lines.append("      - { " + ", ".join(parts) + " }")
    return "\n".join(lines) + "\n"


def parse_drama(data: dict) -> dict:
    return {
        "title": str(data.get("title", "未命名剧集")),
        "doll": str(data.get("doll", "nova")),
        "scenes": [
            {
                "title": str(s.get("title", f"场景{i+1}")),
                "background": str(s.get("background", "rainy_night")),
                "beats": [
                    {
                        "start": int(b.get("start", 0)),
                        "end": int(b.get("end", 4)),
                        "subtitle": str(b.get("subtitle", "")),
                        "position": b.get("position", "center"),
                        "scale": float(b.get("scale", 0.5)),
                        **({"emotion": str(b["emotion"])} if b.get("emotion") else {}),
                    }
                    for b in s.get("beats", [])
                ],
            }
            for i, s in enumerate(data.get("scenes", []))
        ],
    }


class ScriptEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DollWorldwide 剧本编辑器")
        self.geometry("960x640")
        self.minsize(800, 520)

        self.dolls, self.backgrounds, self.emotions = load_config_lists()
        self.current_file: Path | None = None
        self.drama = self.new_drama()
        self.scene_index = 0
        self.beat_index = 0
        self._dirty = False
        self._loading = False

        self._build_ui()
        self._refresh_all()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def new_drama(self) -> dict:
        return {
            "title": "新剧集",
            "doll": self.dolls[0] if self.dolls else "nova",
            "scenes": [],
        }

    def _build_ui(self) -> None:
        # 顶部：剧集信息
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)

        ttk.Label(top, text="剧名").grid(row=0, column=0, sticky=tk.W, padx=(0, 4))
        self.title_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.title_var, width=30).grid(row=0, column=1, sticky=tk.W)
        self.title_var.trace_add("write", lambda *_: self._mark_dirty())

        ttk.Label(top, text="娃娃").grid(row=0, column=2, sticky=tk.W, padx=(16, 4))
        self.doll_var = tk.StringVar()
        ttk.Combobox(top, textvariable=self.doll_var, values=self.dolls, width=12, state="readonly").grid(
            row=0, column=3, sticky=tk.W
        )
        self.doll_var.trace_add("write", lambda *_: self._mark_dirty())

        btn_bar = ttk.Frame(top)
        btn_bar.grid(row=0, column=4, sticky=tk.E, padx=(24, 0))
        ttk.Button(btn_bar, text="新建", command=self._file_new).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="打开", command=self._file_open).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="保存", command=self._file_save).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="渲染", command=self._render).pack(side=tk.LEFT, padx=2)

        # 中间三栏
        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左：场景
        left = ttk.LabelFrame(body, text="场景", padding=6)
        body.add(left, weight=1)
        self.scene_list = tk.Listbox(left, height=12, exportselection=False)
        self.scene_list.pack(fill=tk.BOTH, expand=True)
        self.scene_list.bind("<<ListboxSelect>>", self._on_scene_select)
        sf = ttk.Frame(left)
        sf.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(sf, text="＋ 插入场景", command=self._insert_scene).pack(side=tk.LEFT, padx=2)
        ttk.Button(sf, text="删除", command=self._delete_scene).pack(side=tk.LEFT, padx=2)

        # 中：台词列表
        mid = ttk.LabelFrame(body, text="台词", padding=6)
        body.add(mid, weight=1)
        self.beat_list = tk.Listbox(mid, height=12, exportselection=False)
        self.beat_list.pack(fill=tk.BOTH, expand=True)
        self.beat_list.bind("<<ListboxSelect>>", self._on_beat_select)
        bf = ttk.Frame(mid)
        bf.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(bf, text="＋ 插入台词", command=self._insert_beat).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="删除", command=self._delete_beat).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="↑", width=3, command=lambda: self._move_beat(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="↓", width=3, command=lambda: self._move_beat(1)).pack(side=tk.LEFT, padx=2)

        # 右：台词编辑
        right = ttk.LabelFrame(body, text="编辑当前台词", padding=8)
        body.add(right, weight=2)

        self.start_var = tk.IntVar(value=0)
        self.end_var = tk.IntVar(value=4)
        self.subtitle_var = tk.StringVar()
        self.position_var = tk.StringVar(value="center")
        self.scale_var = tk.DoubleVar(value=0.5)
        self.emotion_var = tk.StringVar()

        row = 0
        ttk.Label(right, text="开始(秒)").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(right, from_=0, to=999, textvariable=self.start_var, width=8).grid(row=row, column=1, sticky=tk.W)
        ttk.Label(right, text="结束(秒)").grid(row=row, column=2, sticky=tk.W, padx=(12, 4))
        ttk.Spinbox(right, from_=0, to=999, textvariable=self.end_var, width=8).grid(row=row, column=3, sticky=tk.W)

        row += 1
        ttk.Label(right, text="台词").grid(row=row, column=0, sticky=tk.NW, pady=4)
        self.subtitle_text = tk.Text(right, height=4, width=40, wrap=tk.WORD)
        self.subtitle_text.grid(row=row, column=1, columnspan=3, sticky=tk.EW, pady=4)
        self.subtitle_text.bind("<KeyRelease>", lambda e: self._apply_beat_from_form())

        row += 1
        ttk.Label(right, text="位置").grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(right, textvariable=self.position_var, values=POSITIONS, state="readonly", width=10).grid(
            row=row, column=1, sticky=tk.W
        )
        ttk.Label(right, text="缩放").grid(row=row, column=2, sticky=tk.W, padx=(12, 4))
        ttk.Spinbox(right, from_=0.3, to=0.8, increment=0.02, textvariable=self.scale_var, width=8).grid(
            row=row, column=3, sticky=tk.W
        )

        row += 1
        ttk.Label(right, text="情绪").grid(row=row, column=0, sticky=tk.W, pady=4)
        emo_cb = ttk.Combobox(right, textvariable=self.emotion_var, values=[""] + self.emotions, width=12)
        emo_cb.grid(row=row, column=1, sticky=tk.W)
        ttk.Label(right, text="(平铺模式: assets/dolls/ 文件名含娃娃名即可)").grid(row=row, column=2, columnspan=2, sticky=tk.W)

        row += 1
        scene_box = ttk.LabelFrame(right, text="当前场景", padding=6)
        scene_box.grid(row=row, column=0, columnspan=4, sticky=tk.EW, pady=(12, 0))
        ttk.Label(scene_box, text="场景名").grid(row=0, column=0, sticky=tk.W)
        self.scene_title_var = tk.StringVar()
        ttk.Entry(scene_box, textvariable=self.scene_title_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=4)
        self.scene_title_var.trace_add("write", lambda *_: self._apply_scene_meta())

        ttk.Label(scene_box, text="背景").grid(row=1, column=0, sticky=tk.W, pady=(6, 0))
        self.scene_bg_var = tk.StringVar()
        ttk.Combobox(scene_box, textvariable=self.scene_bg_var, values=self.backgrounds, width=18).grid(
            row=1, column=1, sticky=tk.W, padx=4, pady=(6, 0)
        )
        self.scene_bg_var.trace_add("write", lambda *_: self._apply_scene_meta())

        ttk.Button(right, text="应用修改", command=self._apply_beat_from_form).grid(
            row=row + 1, column=0, columnspan=2, pady=(12, 0), sticky=tk.W
        )

        for v in (self.start_var, self.end_var, self.position_var, self.scale_var, self.emotion_var):
            v.trace_add("write", lambda *_: self._apply_beat_from_form())

        right.columnconfigure(1, weight=1)

        # 底部 YAML 预览
        bottom = ttk.LabelFrame(self, text="YAML 预览", padding=6)
        bottom.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.preview = tk.Text(bottom, height=8, wrap=tk.NONE, font=("Consolas", 10))
        self.preview.pack(fill=tk.BOTH, expand=True)
        self.preview.configure(state=tk.DISABLED)

        self.status = ttk.Label(self, text="就绪", anchor=tk.W, padding=(8, 4))
        self.status.pack(fill=tk.X)

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._sync_drama_meta()
        self._update_preview()

    def _sync_drama_meta(self) -> None:
        self.drama["title"] = self.title_var.get().strip() or "未命名剧集"
        self.drama["doll"] = self.doll_var.get().strip() or "nova"

    def _update_preview(self) -> None:
        self._sync_drama_meta()
        text = drama_to_yaml_text(self.drama)
        self.preview.configure(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        self.preview.insert("1.0", text)
        self.preview.configure(state=tk.DISABLED)

    def _refresh_all(self) -> None:
        self.title_var.set(self.drama["title"])
        self.doll_var.set(self.drama["doll"])
        self._refresh_scene_list()
        self._update_preview()
        self._set_status()

    def _set_status(self) -> None:
        n_scenes = len(self.drama.get("scenes", []))
        n_beats = sum(len(s.get("beats", [])) for s in self.drama.get("scenes", []))
        fname = self.current_file.name if self.current_file else "未保存"
        self.status.configure(text=f"{fname}  |  {n_scenes} 幕  {n_beats} 句")

    def _refresh_scene_list(self) -> None:
        self.scene_list.delete(0, tk.END)
        for i, s in enumerate(self.drama.get("scenes", [])):
            self.scene_list.insert(tk.END, f"{i+1}. {s['title']}  [{s['background']}]")
        if self.drama.get("scenes"):
            idx = min(self.scene_index, len(self.drama["scenes"]) - 1)
            self.scene_list.selection_clear(0, tk.END)
            self.scene_list.selection_set(idx)
            self.scene_list.activate(idx)
            self.scene_index = idx
            self._refresh_beat_list()
            self._load_scene_meta()
        else:
            self.beat_list.delete(0, tk.END)

    def _refresh_beat_list(self) -> None:
        self.beat_list.delete(0, tk.END)
        scenes = self.drama.get("scenes", [])
        if not scenes:
            return
        beats = scenes[self.scene_index].get("beats", [])
        for i, b in enumerate(beats):
            emo = f" [{b['emotion']}]" if b.get("emotion") else ""
            sub = b.get("subtitle", "")[:24]
            self.beat_list.insert(tk.END, f"{b['start']}-{b['end']}s  {sub}{emo}")
        if beats:
            idx = min(self.beat_index, len(beats) - 1)
            self.beat_list.selection_clear(0, tk.END)
            self.beat_list.selection_set(idx)
            self.beat_list.activate(idx)
            self.beat_index = idx
            self._load_beat_form()
        else:
            self._clear_beat_form()

    def _current_scene(self) -> dict | None:
        scenes = self.drama.get("scenes", [])
        if not scenes or self.scene_index >= len(scenes):
            return None
        return scenes[self.scene_index]

    def _on_scene_select(self, _event=None) -> None:
        sel = self.scene_list.curselection()
        if not sel:
            return
        self.scene_index = sel[0]
        self.beat_index = 0
        self._refresh_beat_list()
        self._load_scene_meta()

    def _on_beat_select(self, _event=None) -> None:
        sel = self.beat_list.curselection()
        if not sel:
            return
        self.beat_index = sel[0]
        self._load_beat_form()

    def _load_scene_meta(self) -> None:
        scene = self._current_scene()
        if not scene:
            return
        self._loading = True
        self.scene_title_var.set(scene.get("title", ""))
        self.scene_bg_var.set(scene.get("background", self.backgrounds[0]))
        self._loading = False

    def _apply_scene_meta(self) -> None:
        if self._loading:
            return
        scene = self._current_scene()
        if not scene:
            return
        scene["title"] = self.scene_title_var.get().strip() or "场景"
        scene["background"] = self.scene_bg_var.get().strip() or self.backgrounds[0]
        self._mark_dirty()
        self._refresh_scene_list()

    def _load_beat_form(self) -> None:
        scene = self._current_scene()
        if not scene:
            return
        beats = scene.get("beats", [])
        if self.beat_index >= len(beats):
            return
        b = beats[self.beat_index]
        self._loading = True
        self.start_var.set(b.get("start", 0))
        self.end_var.set(b.get("end", 4))
        self.subtitle_text.delete("1.0", tk.END)
        self.subtitle_text.insert("1.0", b.get("subtitle", ""))
        self.position_var.set(b.get("position", "center"))
        self.scale_var.set(b.get("scale", 0.5))
        self.emotion_var.set(b.get("emotion", ""))
        self._loading = False

    def _clear_beat_form(self) -> None:
        self.start_var.set(0)
        self.end_var.set(4)
        self.subtitle_text.delete("1.0", tk.END)
        self.position_var.set("center")
        self.scale_var.set(0.5)
        self.emotion_var.set("")

    def _apply_beat_from_form(self) -> None:
        if self._loading:
            return
        scene = self._current_scene()
        if not scene:
            return
        beats = scene.setdefault("beats", [])
        if self.beat_index >= len(beats):
            return
        try:
            beat = {
                "start": int(self.start_var.get()),
                "end": int(self.end_var.get()),
                "subtitle": self.subtitle_text.get("1.0", tk.END).strip(),
                "position": self.position_var.get() or "center",
                "scale": float(self.scale_var.get()),
            }
            emo = self.emotion_var.get().strip()
            if emo:
                beat["emotion"] = emo
            beats[self.beat_index] = beat
            self._mark_dirty()
            self._refresh_beat_list()
            self._set_status()
        except (tk.TclError, ValueError):
            pass

    def _next_beat_start(self) -> int:
        scene = self._current_scene()
        if not scene or not scene.get("beats"):
            return 0
        return int(scene["beats"][-1]["end"])

    def _insert_scene(self) -> None:
        n = len(self.drama.setdefault("scenes", [])) + 1
        self.drama["scenes"].append({
            "title": f"第{n}幕",
            "background": self.backgrounds[0],
            "beats": [],
        })
        self.scene_index = len(self.drama["scenes"]) - 1
        self.beat_index = 0
        self._mark_dirty()
        self._refresh_scene_list()
        self._set_status()

    def _delete_scene(self) -> None:
        if not self.drama.get("scenes"):
            return
        if not messagebox.askyesno("确认", "删除当前场景？"):
            return
        del self.drama["scenes"][self.scene_index]
        self.scene_index = max(0, self.scene_index - 1)
        self._mark_dirty()
        self._refresh_scene_list()
        self._set_status()

    def _insert_beat(self) -> None:
        if not self.drama.get("scenes"):
            self._insert_scene()
        scene = self._current_scene()
        assert scene is not None
        start = self._next_beat_start()
        beat = {
            "start": start,
            "end": start + 4,
            "subtitle": "",
            "position": "center",
            "scale": 0.5,
        }
        scene.setdefault("beats", []).append(beat)
        self.beat_index = len(scene["beats"]) - 1
        self._mark_dirty()
        self._refresh_beat_list()
        self._set_status()
        self.subtitle_text.focus_set()

    def _delete_beat(self) -> None:
        scene = self._current_scene()
        if not scene or not scene.get("beats"):
            return
        if not messagebox.askyesno("确认", "删除当前台词？"):
            return
        del scene["beats"][self.beat_index]
        self.beat_index = max(0, self.beat_index - 1)
        self._mark_dirty()
        self._refresh_beat_list()
        self._set_status()

    def _move_beat(self, delta: int) -> None:
        scene = self._current_scene()
        if not scene:
            return
        beats = scene.get("beats", [])
        i = self.beat_index
        j = i + delta
        if j < 0 or j >= len(beats):
            return
        beats[i], beats[j] = beats[j], beats[i]
        self.beat_index = j
        self._mark_dirty()
        self._refresh_beat_list()

    def _file_new(self) -> None:
        if self._dirty and not messagebox.askyesno("确认", "当前剧本未保存，新建？"):
            return
        self.drama = self.new_drama()
        self.current_file = None
        self.scene_index = 0
        self.beat_index = 0
        self._dirty = False
        self._refresh_all()

    def _file_open(self) -> None:
        path = filedialog.askopenfilename(
            initialdir=DRAMAS_DIR,
            title="打开剧本",
            filetypes=[("YAML", "*.yaml"), ("All", "*.*")],
        )
        if not path:
            return
        data = load_yaml(Path(path))
        self.drama = parse_drama(data)
        self.current_file = Path(path)
        self.scene_index = 0
        self.beat_index = 0
        self._dirty = False
        self._refresh_all()

    def _file_save(self) -> bool:
        self._apply_beat_from_form()
        self._sync_drama_meta()
        if not self.current_file:
            return self._file_save_as()
        DRAMAS_DIR.mkdir(parents=True, exist_ok=True)
        self.current_file.write_text(drama_to_yaml_text(self.drama), encoding="utf-8")
        self._dirty = False
        self._set_status()
        messagebox.showinfo("保存", f"已保存到\n{self.current_file}")
        return True

    def _file_save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            initialdir=DRAMAS_DIR,
            title="保存剧本",
            defaultextension=".yaml",
            filetypes=[("YAML", "*.yaml")],
        )
        if not path:
            return False
        self.current_file = Path(path)
        return self._file_save()

    def _render(self) -> None:
        if not self._file_save():
            return
        assert self.current_file is not None
        if messagebox.askyesno("渲染", "保存完成。现在生成场景帧？"):
            subprocess.Popen(
                [sys.executable, str(ROOT / "drama_builder.py"), str(self.current_file)],
                cwd=str(ROOT),
            )
            messagebox.showinfo("渲染", "已在后台开始渲染，请查看终端或 output_scenes 文件夹")

    def _on_close(self) -> None:
        if self._dirty:
            if messagebox.askyesno("退出", "剧本未保存，是否保存后退出？"):
                if not self._file_save():
                    return
        self.destroy()


def main() -> None:
    DRAMAS_DIR.mkdir(parents=True, exist_ok=True)
    app = ScriptEditor()
    app.mainloop()


if __name__ == "__main__":
    main()
