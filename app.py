# -*- coding: utf-8 -*-
"""角色卡创作清单 — 本地角色创作清单。

一个不依赖网络与账号的 Windows 桌面程序：
项目 -> 世界观 / 角色 -> 可勾选、可增删改的条目。
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import sys
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import store
from paths import app_dir, resource_path
from theme import Palette, Theme
from tutorials import TUTORIAL_GROUPS, open_tutorial
from views import Workspace
from widgets import (
    Card,
    ConfirmDialog,
    FlatButton,
    InfoDialog,
    InputDialog,
    Pill,
    ProgressBar,
    ScrollFrame,
    bind_click_tree,
    divider,
    install_wheel_scrolling,
)

APP_TITLE = "角色卡创作清单"
APP_VERSION = "1.2.2"
APP_AUTHOR = "Liangel"
# 发布后把网址填进来，欢迎页会自动变成可点的链接；留空则显示“待补充”。
APP_LINK_LEINAP = "https://discord.com/channels/1134557553011998840/1567466831843819651"
APP_LINK_GITHUB = "https://github.com/anqi213/jueseka-checklist"


# ---------------------------------------------------------------------------
# 启动辅助
# ---------------------------------------------------------------------------

def setup_logging() -> None:
    try:
        folder = store.data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(folder / "app.log"),
            level=logging.INFO,
            encoding="utf-8",
            format="%(asctime)s %(levelname)s %(message)s",
        )
    except OSError:
        logging.basicConfig(level=logging.INFO)


def acquire_single_instance() -> Any | None:
    """Windows 命名互斥体，避免两个实例同时写同一个数据文件。"""
    if os.name != "nt":
        return True
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\JuesekaChecklist"
        )
        if not handle:
            return True
        if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.user32.MessageBoxW(
                0,
                "角色卡创作清单已经在运行。\n\n请切换到已经打开的窗口。",
                APP_TITLE,
                0x00000040,
            )
            return None
        return handle
    except Exception:  # noqa: BLE001
        return True


# ---------------------------------------------------------------------------
# 欢迎页
# ---------------------------------------------------------------------------

class WelcomeView(tk.Frame):
    def __init__(self, master: tk.Misc, app: "App", theme: Theme):
        super().__init__(master, bg=Palette.BG)
        self.app = app
        self.theme = theme
        self._build()

    def _build(self) -> None:
        self._build_credits()

        center = tk.Frame(self, bg=Palette.BG)
        center.place(relx=0.5, rely=0.46, anchor="center")

        self._welcome_icon = tk.PhotoImage(file=str(resource_path("assets/brand_66.png")))
        mark_frame = tk.Frame(center, bg=Palette.GOLD, padx=2, pady=2)
        mark_frame.pack(pady=(0, 22))
        mark = tk.Label(mark_frame, image=self._welcome_icon, bg=Palette.BG,
                        bd=0, highlightthickness=0)
        mark.pack()

        FlatButton(center, "＋ 新建第一个项目", self.app.new_project,
                   variant="primary", font=self.theme.body_lg,
                   padx=22, pady=9).pack()

        features = tk.Frame(self, bg=Palette.BG)
        features.place(relx=0.5, rely=0.86, anchor="center")
        items = [
            ("清单", "逐条勾选完成"),
            ("可扩展", "条目自由增删改"),
            ("离线", "本地自动保存"),
        ]
        for i, (title, desc) in enumerate(items):
            card = Card(features, bg=Palette.CARD, padding=12)
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            features.grid_columnconfigure(i, weight=1, uniform="feature")
            tk.Label(card.body, text=title, bg=Palette.CARD, fg=Palette.ACCENT,
                     font=self.theme.label, anchor="w").pack(anchor="w")
            tk.Label(card.body, text=desc, bg=Palette.CARD, fg=Palette.MUTED,
                     font=self.theme.tiny, anchor="w").pack(anchor="w", pady=(2, 0))

    def _build_credits(self) -> None:
        """欢迎页上方的作者与链接。链接留空时显示“待补充”，填上就能点。"""
        box = tk.Frame(self, bg=Palette.BG)
        box.place(relx=0.5, rely=0.075, anchor="n")
        font = self.theme.font(12)
        rows = [
            ("作者", APP_AUTHOR, None),
            ("类脑", "类脑社区（Discord）", APP_LINK_LEINAP),
            ("GitHub", "github.com/anqi213/jueseka-checklist", APP_LINK_GITHUB),
        ]
        for index, (label, text, url) in enumerate(rows):
            tk.Label(box, text=f"{label}：", bg=Palette.BG, fg=Palette.MUTED,
                     font=font, anchor="e").grid(row=index, column=0, sticky="e",
                                                 padx=(0, 4), pady=2)
            if url:
                link = tk.Label(box, text=text, bg=Palette.BG, fg=Palette.ACCENT,
                                font=font, anchor="w", cursor="hand2",
                                underline=True)
                link.grid(row=index, column=1, sticky="w", pady=2)
                link.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))
                link.bind("<Enter>",
                          lambda _e, w=link: w.configure(fg=Palette.ACCENT_DARK))
                link.bind("<Leave>",
                          lambda _e, w=link: w.configure(fg=Palette.ACCENT))
            else:
                tk.Label(box, text=text or "待补充", bg=Palette.BG,
                         fg=Palette.INK_SOFT if text else Palette.FAINT,
                         font=font, anchor="w").grid(row=index, column=1,
                                                     sticky="w", pady=2)


# ---------------------------------------------------------------------------
# 主程序
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.theme = Theme(root)
        self.data, self.load_warning = store.load_data()
        self.current_project_id: str | None = None
        self.workspace: Workspace | None = None
        self._save_job: str | None = None
        self._closing = False
        self.project_rows: dict[str, dict[str, Any]] = {}

        self._configure_root()
        install_wheel_scrolling(self.root)
        self._build_layout()
        self._build_menu()
        self._bind_shortcuts()
        self._restore_session()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.report_callback_exception = self._report_exception
        if self.load_warning:
            self.root.after(350, lambda: self.show_info("数据提示", self.load_warning))
        self.root.after(700, self._startup_backup)

    # ------------------------------------------------------------------
    # 窗口与布局
    # ------------------------------------------------------------------
    def _configure_root(self) -> None:
        self.root.title(APP_TITLE)
        self.root.configure(bg=Palette.BG)
        self.root.minsize(1120, 700)
        width = min(1380, max(1120, self.root.winfo_screenwidth() - 120))
        height = min(830, max(700, self.root.winfo_screenheight() - 90))
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2 - 12)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        icon = resource_path("assets/app.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

    def _build_layout(self) -> None:
        self.sidebar = tk.Frame(self.root, bg=Palette.SIDEBAR, width=262)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()

        self.main = tk.Frame(self.root, bg=Palette.BG)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(0, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self.workspace_host = tk.Frame(self.main, bg=Palette.BG)
        self.workspace_host.grid(row=0, column=0, sticky="nsew")

        self.statusbar = tk.Frame(self.root, bg=Palette.SURFACE, height=30)
        self.statusbar.grid(row=1, column=1, sticky="ew")
        self.statusbar.grid_propagate(False)
        tk.Frame(self.statusbar, bg=Palette.BORDER, height=1).pack(fill="x", side="top")
        inner = tk.Frame(self.statusbar, bg=Palette.SURFACE, padx=18, pady=0)
        inner.pack(fill="both", expand=True)
        self.save_label = tk.Label(inner, text="准备就绪", bg=Palette.SURFACE,
                                   fg=Palette.MUTED, font=self.theme.tiny)
        self.save_label.pack(side="left")
        self.context_label = tk.Label(inner, text="", bg=Palette.SURFACE,
                                      fg=Palette.FAINT, font=self.theme.tiny)
        self.context_label.pack(side="left", padx=(16, 0))
        self.data_link = tk.Label(inner, text="本地数据  ·  打开数据文件夹",
                                  bg=Palette.SURFACE, fg=Palette.MUTED,
                                  font=self.theme.tiny, cursor="hand2")
        self.data_link.pack(side="right")
        self.data_link.bind("<Button-1>", lambda _e: self.open_data_folder())
        self.data_link.bind("<Enter>", lambda _e: self.data_link.configure(fg=Palette.ACCENT))
        self.data_link.bind("<Leave>", lambda _e: self.data_link.configure(fg=Palette.MUTED))

    def _build_sidebar(self) -> None:
        brand = tk.Frame(self.sidebar, bg=Palette.SIDEBAR, padx=20, pady=18)
        brand.pack(fill="x")
        self._brand_icon = tk.PhotoImage(file=str(resource_path("assets/brand_40.png")))
        mark_frame = tk.Frame(brand, bg=Palette.GOLD, padx=1, pady=1)
        mark_frame.pack(side="left")
        mark = tk.Label(mark_frame, image=self._brand_icon, bg=Palette.SIDEBAR,
                        bd=0, highlightthickness=0)
        mark.pack()
        text_box = tk.Frame(brand, bg=Palette.SIDEBAR)
        text_box.pack(side="left", padx=(11, 0))
        tk.Label(text_box, text="角色卡创作清单", bg=Palette.SIDEBAR,
                 fg=Palette.SIDEBAR_TEXT, font=self.theme.font(14, "bold", "display"),
                 anchor="w").pack(anchor="w")
        tk.Label(text_box, text="角色创作工具", bg=Palette.SIDEBAR,
                 fg=Palette.SIDEBAR_MUTED, font=self.theme.tiny, anchor="w").pack(anchor="w")

        divider(self.sidebar, bg="#333B32")

        heading = tk.Frame(self.sidebar, bg=Palette.SIDEBAR, padx=20, pady=12)
        heading.pack(fill="x")
        tk.Label(heading, text="项目", bg=Palette.SIDEBAR, fg=Palette.SIDEBAR_MUTED,
                 font=self.theme.label, anchor="w").pack(side="left")
        FlatButton(heading, "＋", self.new_project, variant="sidebar",
                   font=self.theme.body, padx=8, pady=0).pack(side="right")

        self.project_list = ScrollFrame(self.sidebar, bg=Palette.SIDEBAR,
                                        scrollbar_style="Sidebar.TScrollbar",
                                        padding=10)
        self.project_list.pack(fill="both", expand=True)

        bottom = tk.Frame(self.sidebar, bg=Palette.SIDEBAR, padx=14, pady=12)
        bottom.pack(fill="x")
        FlatButton(bottom, "教程库", lambda: self.open_tutorial(None),
                   variant="sidebar", font=self.theme.small,
                   anchor="w").pack(fill="x", pady=1)
        FlatButton(bottom, "数据与备份", self.open_data_folder,
                   variant="sidebar", font=self.theme.small,
                   anchor="w").pack(fill="x", pady=1)
        tk.Label(bottom, text=f"v{APP_VERSION}  ·  离线本地保存",
                 bg=Palette.SIDEBAR, fg="#778071", font=self.theme.tiny,
                 anchor="w").pack(fill="x", padx=8, pady=(8, 0))
        self.rebuild_sidebar()

    # ------------------------------------------------------------------
    # 菜单与快捷键
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="新建项目", accelerator="Ctrl+N", command=self.new_project)
        file_menu.add_command(label="新建角色", accelerator="Ctrl+Shift+N", command=self.new_character)
        file_menu.add_separator()
        file_menu.add_command(label="保存", accelerator="Ctrl+S", command=self.save_now)
        file_menu.add_command(label="导出当前项目 Markdown", accelerator="Ctrl+E",
                              command=self.export_project)
        file_menu.add_separator()
        file_menu.add_command(label="打开数据文件夹", command=self.open_data_folder)
        file_menu.add_command(label="立即备份数据", command=self.backup_now)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        tutorial_menu = tk.Menu(menubar, tearoff=0)
        for group in TUTORIAL_GROUPS:
            sub = tk.Menu(tutorial_menu, tearoff=0)
            for item in group["items"]:
                sub.add_command(
                    label=f"{item['part']} · {item['title']}",
                    command=lambda k=item["key"]: self.open_tutorial(k),
                )
            tutorial_menu.add_cascade(label=group["title"], menu=sub)
        tutorial_menu.add_separator()
        tutorial_menu.add_command(label="打开教程库", accelerator="F1",
                                  command=lambda: self.open_tutorial(None))
        menubar.add_cascade(label="教程", menu=tutorial_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用说明", command=self.show_help)
        help_menu.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.configure(menu=menubar)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda _e: self.new_project())
        self.root.bind("<Control-N>", lambda _e: self.new_project())
        self.root.bind("<Control-Shift-N>", lambda _e: self.new_character())
        self.root.bind("<Control-Shift-n>", lambda _e: self.new_character())
        self.root.bind("<Control-s>", lambda _e: self.save_now())
        self.root.bind("<Control-S>", lambda _e: self.save_now())
        self.root.bind("<Control-e>", lambda _e: self.export_project())
        self.root.bind("<Control-E>", lambda _e: self.export_project())
        self.root.bind("<F1>", lambda _e: self.open_tutorial(None))

    # ------------------------------------------------------------------
    # 会话与项目
    # ------------------------------------------------------------------
    def _restore_session(self) -> None:
        projects = self.data.get("projects", [])
        last_id = self.data.get("settings", {}).get("last_project_id")
        project = store.find_project(self.data, last_id) if last_id else None
        if project is None and projects:
            project = projects[0]
        if project:
            self._show_project(project)
        else:
            self._show_welcome()

    def _show_welcome(self) -> None:
        self.current_project_id = None
        self.workspace = None
        for child in self.workspace_host.winfo_children():
            child.destroy()
        welcome = WelcomeView(self.workspace_host, self, self.theme)
        welcome.pack(fill="both", expand=True)
        self.set_status_tab("welcome")
        self.rebuild_sidebar()

    def _show_project(self, project: dict[str, Any]) -> None:
        self.current_project_id = project.get("id")
        self.data.setdefault("settings", {})["last_project_id"] = self.current_project_id
        for child in self.workspace_host.winfo_children():
            child.destroy()
        self.workspace = Workspace(self.workspace_host, self, self.theme, project)
        self.workspace.pack(fill="both", expand=True)
        self.rebuild_sidebar()
        self.save_soon()

    def select_project(self, project_id: str) -> None:
        if project_id == self.current_project_id and self.workspace is not None:
            return
        project = store.find_project(self.data, project_id)
        if not project:
            return
        self.save_now(silent=True)
        self._show_project(project)

    def current_project(self) -> dict[str, Any] | None:
        return store.find_project(self.data, self.current_project_id)

    def new_project(self) -> None:
        self.save_now(silent=True)
        name = self.ask_string("新建项目", "给这个项目起个名字：", "未命名项目")
        if name is None:
            return
        name = name.strip() or "未命名项目"
        project = store.create_project(name)
        self.data.setdefault("projects", []).insert(0, project)
        self._show_project(project)
        self.save_now()
        self.set_status("项目已创建")

    def rename_project(self) -> None:
        project = self.current_project()
        if not project:
            return
        name = self.ask_string("重命名项目", "新的项目名称：", project.get("name", ""))
        if name is None:
            return
        project["name"] = name.strip() or "未命名项目"
        project["updated_at"] = store.now_iso()
        if self.workspace:
            self.workspace.project_title.configure(text=project["name"])
            self.workspace._refresh_header()
        self.rebuild_sidebar()
        self.save_now()
        self.set_status("项目已重命名")

    def duplicate_project(self) -> None:
        self.save_now(silent=True)
        project = self.current_project()
        if not project:
            return
        clone = json.loads(json.dumps(project, ensure_ascii=False))
        clone["id"] = store.new_id("p")
        clone["name"] = project.get("name", "未命名项目") + " 副本"
        stamp = store.now_iso()
        clone["created_at"] = stamp
        clone["updated_at"] = stamp
        for item in clone.get("world", []):
            item["id"] = store.new_id("w")
        for character in clone.get("characters", []):
            character["id"] = store.new_id("c")
            source_name = store.find_name_field(character)
            old_name_id = character.get("name_field_id") or (
                source_name.get("id") if source_name else ""
            )
            new_name_field = None
            for section in character.get("sections", []):
                section["id"] = store.new_id("s")
                for group in section.get("children", []):
                    group["id"] = store.new_id("g")
                    for field in group.get("fields", []):
                        old_id = field.get("id")
                        field["id"] = store.new_id("f")
                        if old_id and old_id == old_name_id:
                            new_name_field = field
                for field in section.get("fields", []):
                    old_id = field.get("id")
                    field["id"] = store.new_id("f")
                    if old_id and old_id == old_name_id:
                        new_name_field = field
            character["name_field_id"] = (
                new_name_field.get("id") if new_name_field is not None else None
            )
        projects = self.data.setdefault("projects", [])
        index = next((i for i, p in enumerate(projects) if p is project), 0)
        projects.insert(index + 1, clone)
        self._show_project(clone)
        self.save_now()
        self.set_status("项目已复制")

    def delete_project(self) -> None:
        self.save_now(silent=True)
        project = self.current_project()
        if not project:
            return
        chars = len(project.get("characters", []))
        if not self.confirm(
            "删除项目",
            f"确定删除项目「{project.get('name', '')}」吗？\n\n"
            f"其中包含 {chars} 位角色。删除后无法恢复；建议先导出或备份。",
            "删除项目", danger=True,
        ):
            return
        projects = self.data.get("projects", [])
        index = next((i for i, p in enumerate(projects) if p is project), 0)
        projects.remove(project)
        if projects:
            next_project = projects[min(index, len(projects) - 1)]
            self._show_project(next_project)
        else:
            self._show_welcome()
        self.save_now()
        self.set_status("项目已删除")

    # ------------------------------------------------------------------
    # 角色
    # ------------------------------------------------------------------
    def new_character(self) -> None:
        project = self.current_project()
        if not project:
            self.show_info("还没有项目", "请先新建一个项目，再在项目里创建角色。")
            return
        name = self.ask_string("新建角色", "角色名字（也可以稍后修改）：", "未命名角色")
        if name is None:
            return
        character = store.create_character(name.strip() or "未命名角色")
        project.setdefault("characters", []).append(character)
        project["updated_at"] = store.now_iso()
        self.data_changed(structural=True)
        self.open_character(character.get("id"))
        self.save_now()

    def open_character(self, character_id: str | None,
                       field_id: str | None = None) -> None:
        if not self.workspace:
            return
        self.workspace.open_character(character_id, field_id=field_id)
        self.data.setdefault("settings", {})["last_character_id"] = character_id
        self.save_soon()

    def close_character(self) -> None:
        if self.workspace:
            self.workspace.close_character()
        self.data.setdefault("settings", {})["last_character_id"] = None
        self.save_soon()

    def show_tab(self, tab: str, focus_id: str | None = None) -> None:
        if self.workspace:
            self.workspace._show_tab(tab, focus_id=focus_id)

    def rebuild_current(self) -> None:
        if self.workspace:
            self.workspace.rebuild_current()

    def _current_character(self) -> dict[str, Any] | None:
        project = self.current_project()
        if not project or not self.workspace:
            return None
        return store.find_character(project, self.workspace.character_id)

    def rename_character(self, character: dict[str, Any]) -> None:
        name = self.ask_string("重命名角色", "新的角色名字：",
                               store.display_character_name(character))
        if name is None:
            return
        clean = name.strip() or "未命名角色"
        character["name"] = clean
        name_field = store.find_name_field(character)
        if name_field is not None:
            name_field["content"] = clean
        character["updated_at"] = store.now_iso()
        self.data_changed(structural=True)
        self.save_now()
        self.set_status("角色已重命名")

    def rename_character_for_editor(self) -> None:
        character = self._current_character()
        if character:
            self.rename_character(character)

    def duplicate_character(self, character: dict[str, Any]) -> None:
        project = self.current_project()
        if not project:
            return
        clone = store.duplicate_character(character)
        project.setdefault("characters", []).append(clone)
        project["updated_at"] = store.now_iso()
        self.data_changed(structural=True)
        self.open_character(clone.get("id"))
        self.save_now()
        self.set_status("角色已复制")

    def duplicate_character_for_editor(self) -> None:
        character = self._current_character()
        if character:
            self.duplicate_character(character)

    def delete_character(self, character: dict[str, Any]) -> None:
        project = self.current_project()
        if not project:
            return
        name = store.display_character_name(character)
        if not self.confirm("删除角色", f"确定删除角色「{name}」吗？\n\n删除后无法恢复。",
                            "删除角色", danger=True):
            return
        store.remove_from_list(project.get("characters", []), character)
        project["updated_at"] = store.now_iso()
        if self.workspace:
            if self.workspace.character_id == character.get("id"):
                self.workspace.character_id = None
                self.workspace._show_tab("characters")
            else:
                self.workspace.rebuild_current()
        self.data_changed(structural=False)
        self.save_now()
        self.set_status("角色已删除")

    def delete_character_for_editor(self) -> None:
        character = self._current_character()
        if character:
            self.delete_character(character)

    # ------------------------------------------------------------------
    # 编辑与保存
    # ------------------------------------------------------------------
    def flush_editors(self) -> None:
        """把所有文本框里尚未触发的防抖内容立即写回数据模型。"""
        stack: list[tk.Misc] = [self.root]
        while stack:
            widget = stack.pop()
            try:
                children = widget.winfo_children()
            except tk.TclError:
                continue
            stack.extend(children)
            flush = getattr(widget, "flush", None)
            if callable(flush):
                try:
                    flush()
                except Exception:  # noqa: BLE001
                    logging.exception("flush editor failed")

    def note_edit(self) -> None:
        project = self.current_project()
        if project:
            project["updated_at"] = store.now_iso()
        self.set_status("正在编辑…", accent=True)
        self.save_soon()

    def data_changed(self, structural: bool = False) -> None:
        self.flush_editors()
        project = self.current_project()
        if project:
            project["updated_at"] = store.now_iso()
        self.save_soon()
        if self.workspace:
            self.workspace.refresh_progress()
            if structural:
                self.workspace.rebuild_current()
        self.refresh_sidebar_progress()

    def complete_todo(self, todo: dict[str, Any]) -> None:
        project = self.current_project()
        if not project:
            return
        if todo.get("kind") == "world":
            for item in project.get("world", []):
                if item.get("id") == todo.get("field_id"):
                    item["done"] = True
                    break
        else:
            character = store.find_character(project, todo.get("character_id"))
            if character:
                field = store.find_field(character, field_id=todo.get("field_id"))
                if field:
                    field["done"] = True
        project["updated_at"] = store.now_iso()
        self.data_changed()

    def save_soon(self, delay: int = 650) -> None:
        if self._closing:
            return
        if self._save_job:
            try:
                self.root.after_cancel(self._save_job)
            except tk.TclError:
                pass
        self._save_job = self.root.after(delay, self.save_now)

    def save_now(self, silent: bool = False) -> None:
        if self._closing:
            return
        self.flush_editors()
        if self._save_job:
            try:
                self.root.after_cancel(self._save_job)
            except tk.TclError:
                pass
            self._save_job = None
        try:
            store.save_data(self.data)
            now = datetime.now().strftime("%H:%M")
            self.save_label.configure(text=f"已保存  {now}", fg=Palette.MUTED)
            if not silent:
                logging.info("saved")
        except Exception as exc:  # noqa: BLE001
            logging.exception("save failed")
            self.save_label.configure(text="保存失败", fg=Palette.DANGER)
            if not silent:
                self.show_info("保存失败", f"数据没有写入成功：\n{exc}\n\n"
                                         f"请检查数据目录是否可写：\n{store.data_dir()}")

    def _startup_backup(self) -> None:
        try:
            path = store.backup_if_needed()
            if path:
                logging.info("backup: %s", path)
        except Exception:  # noqa: BLE001
            logging.exception("backup failed")

    def on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.flush_editors()
        try:
            store.save_data(self.data)
        except Exception:  # noqa: BLE001
            logging.exception("final save failed")
        self.root.destroy()

    # ------------------------------------------------------------------
    # 侧栏
    # ------------------------------------------------------------------
    def rebuild_sidebar(self) -> None:
        if not hasattr(self, "project_list"):
            return
        for child in self.project_list.body.winfo_children():
            child.destroy()
        self.project_rows = {}
        projects = self.data.get("projects", [])
        if not projects:
            tk.Label(self.project_list.body, text="还没有项目。\n点击上方「＋」开始。",
                     bg=Palette.SIDEBAR, fg=Palette.SIDEBAR_MUTED,
                     font=self.theme.tiny, justify="left", anchor="w").pack(
                fill="x", padx=10, pady=16
            )
            return
        for project in projects:
            self._build_project_row(project)

    def _build_project_row(self, project: dict[str, Any]) -> None:
        pid = project.get("id")
        active = pid == self.current_project_id
        bg = Palette.SIDEBAR_ACTIVE if active else Palette.SIDEBAR
        row = tk.Frame(self.project_list.body, bg=bg)
        row.pack(fill="x", pady=2)
        marker = tk.Frame(row, bg=Palette.ACCENT if active else bg, width=3)
        marker.pack(side="left", fill="y")
        inner = tk.Frame(row, bg=bg, padx=10, pady=9)
        inner.pack(side="left", fill="x", expand=True)
        top = tk.Frame(inner, bg=bg)
        top.pack(fill="x")
        name = tk.Label(top, text=project.get("name", "未命名项目"), bg=bg,
                        fg=Palette.SIDEBAR_TEXT, font=self.theme.font(
                            10, "bold" if active else "normal"), anchor="w",
                        justify="left", wraplength=170)
        name.pack(side="left", fill="x", expand=True)
        FlatButton(top, "⋯", lambda p=project: self._project_row_menu(p),
                   variant="sidebar", bg=bg, fg=Palette.SIDEBAR_MUTED,
                   font=self.theme.tiny, padx=4, pady=0).pack(side="right")
        done, _filled, total = store.project_progress(project)
        meta = tk.Label(inner, text=f"{len(project.get('characters', []))} 位角色 · {done}/{total}",
                        bg=bg, fg=Palette.SIDEBAR_MUTED, font=self.theme.tiny,
                        anchor="w")
        meta.pack(fill="x", pady=(3, 0))
        bar = ProgressBar(inner, height=3, bg=bg, track="#3B4539", fill=Palette.GOLD)
        bar.pack(fill="x", pady=(5, 0))
        bar.set(done, total)
        self.project_rows[pid] = {"meta": meta, "bar": bar, "frame": row, "bg": bg}

        def select(_event: tk.Event | None = None) -> None:
            self.select_project(pid)

        bind_click_tree(inner, select)
        row.bind("<Button-1>", select, add="+")
        try:
            inner.configure(cursor="hand2")
        except tk.TclError:
            pass

    def refresh_sidebar_progress(self) -> None:
        for project in self.data.get("projects", []):
            row = self.project_rows.get(project.get("id"))
            if not row:
                continue
            done, _filled, total = store.project_progress(project)
            row["meta"].configure(
                text=f"{len(project.get('characters', []))} 位角色 · {done}/{total}"
            )
            row["bar"].set(done, total)

    def _project_row_menu(self, project: dict[str, Any]) -> None:
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="打开项目", command=lambda: self.select_project(project.get("id")))
        menu.add_command(label="重命名项目",
                         command=lambda: (self.select_project(project.get("id")),
                                          self.rename_project()))
        menu.add_command(label="复制项目",
                         command=lambda: (self.select_project(project.get("id")),
                                          self.duplicate_project()))
        menu.add_command(label="导出 Markdown",
                         command=lambda: (self.select_project(project.get("id")),
                                          self.export_project()))
        menu.add_separator()
        menu.add_command(label="删除项目",
                         command=lambda: (self.select_project(project.get("id")),
                                          self.delete_project()))
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------
    # 状态栏
    # ------------------------------------------------------------------
    def set_status(self, text: str, accent: bool = False) -> None:
        self.save_label.configure(text=text, fg=Palette.ACCENT if accent else Palette.MUTED)

    def set_status_tab(self, tab: str) -> None:
        labels = {
            "overview": "总览",
            "world": "世界观",
            "characters": "角色",
            "todos": "待完成",
            "welcome": "欢迎",
        }
        self.context_label.configure(text=labels.get(tab, ""))

    def set_status_character(self, name: str) -> None:
        self.context_label.configure(text=f"角色 · {name}")

    # ------------------------------------------------------------------
    # 教程、导出、数据
    # ------------------------------------------------------------------
    def open_tutorial(self, key: str | None = None) -> Any:
        try:
            return open_tutorial(self.root, self.theme, key)
        except Exception as exc:  # noqa: BLE001
            logging.exception("open tutorial failed")
            self.show_info("教程打开失败", str(exc))
            return None

    def _safe_filename(self, name: str) -> str:
        clean = re.sub(r'[\\/:*?"<>|]+', "_", name).strip().strip(".")
        return clean or "角色卡"

    def export_project(self) -> None:
        project = self.current_project()
        if not project:
            self.show_info("没有可导出的项目", "请先新建或打开一个项目。")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出项目 Markdown",
            defaultextension=".md",
            initialfile=self._safe_filename(project.get("name", "角色卡")) + ".md",
            filetypes=[("Markdown", "*.md"), ("文本文件", "*.txt")],
        )
        if not path:
            return
        try:
            Path(path).write_text(store.export_markdown(project), encoding="utf-8-sig")
            self.set_status("已导出项目")
            self.show_info("导出完成", f"项目已导出到：\n{path}")
        except OSError as exc:
            self.show_info("导出失败", f"文件没有写入成功：\n{exc}")

    def export_character(self, character: dict[str, Any]) -> None:
        name = store.display_character_name(character)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出角色 Markdown",
            defaultextension=".md",
            initialfile=self._safe_filename(name) + ".md",
            filetypes=[("Markdown", "*.md"), ("文本文件", "*.txt")],
        )
        if not path:
            return
        try:
            Path(path).write_text(store.export_character_markdown(character),
                                  encoding="utf-8-sig")
            self.set_status("已导出角色")
            self.show_info("导出完成", f"角色已导出到：\n{path}")
        except OSError as exc:
            self.show_info("导出失败", f"文件没有写入成功：\n{exc}")

    def open_data_folder(self) -> None:
        folder = store.data_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            self.show_info("无法打开数据文件夹", f"{folder}\n\n{exc}")

    def backup_now(self) -> None:
        self.save_now(silent=True)
        try:
            path = store.backup_now()
            if path:
                self.show_info("备份完成", f"已保存一份数据备份：\n{path}")
            else:
                self.show_info("暂无数据可备份", "还没有生成数据文件。")
        except OSError as exc:
            self.show_info("备份失败", str(exc))

    # ------------------------------------------------------------------
    # 对话框与错误
    # ------------------------------------------------------------------
    def ask_string(self, title: str, prompt: str, initial: str = "") -> str | None:
        return InputDialog(self.root, self.theme, title, prompt, initial).show()

    def confirm(self, title: str, message: str, confirm_text: str = "确定",
                danger: bool = False) -> bool:
        return ConfirmDialog(self.root, self.theme, title, message,
                             confirm_text=confirm_text, danger=danger).show() is True

    def show_info(self, title: str, message: str) -> None:
        InfoDialog(self.root, self.theme, title, message).show()

    def show_help(self) -> None:
        message = (
            "1. 在左侧新建项目。一个项目可以包含共同的世界观和多位角色。\n\n"
            "2. 「世界观」默认有舞台、时代、玩法三个条目，也可以继续添加。\n\n"
            "3. 在「角色」里新建角色。每个角色默认包含基础信息，下面分生理与外貌、自然属性两组。\n\n"
            "4. 每个条目前面有一个方框：点一下方框（或点条目本身），出现对勾即为完成。\n\n"
            "5. 总览页用数字、进度条和角色进度表显示当前完成情况，一屏之内可以看完。\n\n"
            "6. 条目右侧的「⋯」可以重命名、上移、下移或删除；条目标题旁也有同样的菜单。\n\n"
            "7. 所有修改都会自动保存到本机。建议定期使用「文件 → 立即备份数据」。\n\n"
            "8. 项目右上角的「导出」可以把当前项目导出为 Markdown，方便备份或在别处继续写。"
        )
        InfoDialog(self.root, self.theme, "使用说明", message,
                   width=620, height=500).show()

    def show_about(self) -> None:
        message = (
            f"{APP_TITLE}  v{APP_VERSION}\n\n"
            "一个离线的角色卡创作工具：把人物放回她自己的生活里。\n\n"
            f"作者：{APP_AUTHOR}\n"
            f"类脑：{APP_LINK_LEINAP or '待补充'}\n"
            f"GitHub：{APP_LINK_GITHUB or '待补充'}\n\n"
            f"数据目录：\n{store.data_dir()}\n\n"
            "教程来源：三明月《人物生境写法》（四篇正文与附录已内置）。\n"
            "程序不会联网，也不收集任何内容。"
        )
        InfoDialog(self.root, self.theme, "关于", message,
                   width=560, height=420).show()

    def _report_exception(self, exc: type[BaseException], value: BaseException,
                          tb: Any) -> None:
        logging.exception("unhandled exception", exc_info=(exc, value, tb))
        try:
            self.show_info("出现了一个错误",
                           f"{value}\n\n错误已经记录到数据目录下的 app.log。")
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        pass
    setup_logging()
    mutex = acquire_single_instance()
    if mutex is None:
        return
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
