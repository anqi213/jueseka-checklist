# -*- coding: utf-8 -*-
"""项目工作区：总览、世界观、角色、待完成与角色清单。

清单以「方框 + 条目」呈现：点一下方框即完成，进度始终可见。
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Callable

import store
from theme import Palette, Theme
from widgets import (
    Avatar,
    Card,
    CheckBox,
    CheckRow,
    FlatButton,
    ProgressBar,
    ScrollFrame,
    clear_children,
    divider,
    set_active_scroll,
    stat_text,
)


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def page_heading(parent: tk.Misc, theme: Theme, title: str, subtitle: str = "",
                 actions: list[tuple[str, Callable[[], None], str]] | None = None) -> tk.Frame:
    row = tk.Frame(parent, bg=Palette.BG)
    row.pack(fill="x", pady=(0, 16))
    left = tk.Frame(row, bg=Palette.BG)
    left.pack(side="left", fill="x", expand=True)
    tk.Label(left, text=title, bg=Palette.BG, fg=Palette.INK,
             font=theme.h1, anchor="w").pack(anchor="w")
    if subtitle:
        tk.Label(left, text=subtitle, bg=Palette.BG, fg=Palette.MUTED,
                 font=theme.small, anchor="w", justify="left",
                 wraplength=680).pack(anchor="w", pady=(5, 0))
    if actions:
        right = tk.Frame(row, bg=Palette.BG)
        right.pack(side="right", anchor="n", padx=(16, 0))
        for text, command, variant in actions:
            FlatButton(right, text, command, variant=variant,
                       bg=Palette.BG if variant == "ghost" else None,
                       font=theme.body).pack(side="left", padx=(8, 0))
    return row


def section_heading(parent: tk.Misc, theme: Theme, title: str,
                    meta: str = "",
                    action: tuple[str, Callable[[], None], str] | None = None) -> tk.Frame:
    row = tk.Frame(parent, bg=Palette.BG)
    row.pack(fill="x", pady=(6, 9))
    tk.Label(row, text=title, bg=Palette.BG, fg=Palette.INK,
             font=theme.h2, anchor="w").pack(side="left")
    if meta:
        tk.Label(row, text=meta, bg=Palette.BG, fg=Palette.MUTED,
                 font=theme.small, anchor="w").pack(side="left", padx=(10, 0),
                                                   pady=(4, 0))
    if action:
        text, command, variant = action
        FlatButton(row, text, command, variant=variant,
                   bg=Palette.BG if variant == "ghost" else None,
                   font=theme.small).pack(side="right")
    return row


def empty_state(parent: tk.Misc, theme: Theme, title: str, button_text: str,
                command: Callable[[], None]) -> None:
    """空状态：只有一句标题和一个按钮，不放说明文字。"""
    card = Card(parent, bg=Palette.CARD, padding=30)
    card.pack(fill="x", pady=(4, 0))
    tk.Label(card.body, text=title, bg=Palette.CARD, fg=Palette.INK,
             font=theme.h2).pack(pady=(0, 14))
    FlatButton(card.body, button_text, command, variant="primary",
               font=theme.body).pack()


def _short(text: str, limit: int) -> str:
    text = (text or "").strip() or "未命名"
    return text if len(text) <= limit else text[:limit] + "…"


def _bind_card_click(widget: tk.Misc, command: Callable[[], None]) -> None:
    if isinstance(widget, (tk.Button, tk.Entry, tk.Text, tk.Canvas)):
        return
    widget.bind("<Button-1>", lambda _e: command(), add="+")
    try:
        widget.configure(cursor="hand2")
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        _bind_card_click(child, command)


def _progress_rows(character: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """进度展示单位：有分组就按分组，没有分组就按条目本身。"""
    rows: list[tuple[str, dict[str, Any]]] = []
    for section in character.get("sections", []):
        groups = section.get("children") or []
        if groups:
            for group in groups:
                rows.append((group.get("title") or "分组", group))
        else:
            rows.append((section.get("title") or "条目", section))
    return rows


def _progress_map(character: dict[str, Any]) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for title, node in _progress_rows(character):
        done, _filled, total = store.section_progress(node)
        result[title] = (done, total)
    return result


class MiniProgress(tk.Frame):
    def __init__(self, master: tk.Misc, theme: Theme, title: str,
                 done: int = 0, total: int = 0, *, bg: str = Palette.CARD,
                 width: int = 180, compact: bool = False):
        super().__init__(master, bg=bg)
        self.theme = theme
        self.bg = bg
        self._width = width
        self._compact = compact
        top = tk.Frame(self, bg=bg)
        top.pack(fill="x")
        self.title_label = tk.Label(top, text=title, bg=bg, fg=Palette.INK_SOFT,
                                    font=theme.small, anchor="w")
        self.title_label.pack(side="left")
        self.count_label = tk.Label(top, text=self._text(done, total), bg=bg,
                                    fg=Palette.MUTED, font=theme.tiny, anchor="e")
        self.count_label.pack(side="right")
        self.bar = ProgressBar(self, height=3, bg=bg, track=Palette.BORDER,
                               fill=Palette.GREEN)
        self.bar.pack(fill="x", pady=(4, 0))
        self.set(done, total)

    def _text(self, done: int, total: int) -> str:
        if self._compact:
            return f"{done}/{total}" if total else "—"
        return stat_text(done, total)

    def set(self, done: int, total: int) -> None:
        self.count_label.configure(text=self._text(done, total))
        self.bar.set(done, total)
        if total and done >= total:
            self.title_label.configure(fg=Palette.GREEN_DARK)
        else:
            self.title_label.configure(fg=Palette.INK_SOFT)


# ---------------------------------------------------------------------------
# 世界观
# ---------------------------------------------------------------------------

class WorldView(ScrollFrame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any], focus_id: str | None = None):
        super().__init__(master, bg=Palette.BG, padding=28)
        self.app = app
        self.theme = theme
        self.project = project
        self.focus_id = focus_id
        self.rows: dict[str, CheckRow] = {}
        self.count_label: tk.Label | None = None
        self.bar: ProgressBar | None = None
        self._build()

    def _build(self) -> None:
        items = self.project.setdefault("world", [])
        page_heading(
            self.body, self.theme, "世界观", "",
            [
                ("＋ 添加条目", self.add_item, "primary"),
                ("补齐默认", self.merge_defaults, "ghost"),
            ],
        )
        meta = tk.Frame(self.body, bg=Palette.BG)
        meta.pack(fill="x", pady=(0, 12))
        self.count_label = tk.Label(meta, text="", bg=Palette.BG, fg=Palette.MUTED,
                                    font=self.theme.small, anchor="w")
        self.count_label.pack(side="left")
        self.bar = ProgressBar(meta, height=5, bg=Palette.BG, width=200)
        self.bar.pack(side="left", padx=(14, 0))
        self._refresh_meta()

        if not items:
            empty_state(self.body, self.theme, "还没有世界观条目",
                        "＋ 添加第一个条目", self.add_item)
            return

        for item in items:
            row = CheckRow(
                self.body,
                title=item.get("title", "未命名条目"),
                done=bool(item.get("done")),
                on_toggle=lambda value, i=item: self._toggle(i, value),
                on_menu=lambda i=item: self._menu(i),
                font=self.theme.body_lg,
            )
            row.pack(fill="x", pady=(0, 7))
            self.rows[item.get("id")] = row

        if self.focus_id and self.focus_id in self.rows:
            card = self.rows[self.focus_id]
            self.after(120, lambda: (self.see_widget(card), card.flash()))

    def _refresh_meta(self) -> None:
        items = self.project.get("world", [])
        done = sum(1 for item in items if item.get("done"))
        if self.count_label is not None:
            self.count_label.configure(text=f"已完成 {done} / {len(items)}")
        if self.bar is not None:
            self.bar.set(done, len(items))

    def _toggle(self, item: dict[str, Any], checked: bool) -> None:
        item["done"] = checked
        self._refresh_meta()
        self.app.data_changed()

    # ------------------------------------------------------------------
    def add_item(self) -> None:
        title = self.app.ask_string("添加世界观条目", "这个条目叫什么？", "新条目")
        if not title:
            return
        self.project.setdefault("world", []).append({
            "id": store.new_id("w"),
            "title": title.strip(),
            "hint": "",
            "content": "",
            "done": False,
        })
        self.app.data_changed(structural=True)

    def merge_defaults(self) -> None:
        added = store.merge_world_defaults(self.project)
        if added:
            self.app.data_changed(structural=True)
            self.app.show_info("已补齐默认条目", f"新增了 {added} 个世界观条目。已有内容没有被覆盖。")
        else:
            self.app.show_info("默认条目已齐全", "没有需要补齐的舞台、时代或玩法。")

    def rename_item(self, item: dict[str, Any]) -> None:
        title = self.app.ask_string("重命名条目", "新的名称：", item.get("title", ""))
        if title:
            item["title"] = title.strip()
            self.app.data_changed(structural=True)

    def delete_item(self, item: dict[str, Any]) -> None:
        message = f"确定删除「{item.get('title', '未命名条目')}」吗？"
        if not self.app.confirm("删除世界观条目", message, "删除", danger=True):
            return
        store.remove_from_list(self.project.get("world", []), item)
        self.app.data_changed(structural=True)

    def move_item(self, item: dict[str, Any], delta: int) -> None:
        if store.move_in_list(self.project.get("world", []), item, delta):
            self.app.data_changed(structural=True)

    def _menu(self, item: dict[str, Any]) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="重命名条目", command=lambda: self.rename_item(item))
        menu.add_command(label="上移", command=lambda: self.move_item(item, -1))
        menu.add_command(label="下移", command=lambda: self.move_item(item, 1))
        menu.add_separator()
        menu.add_command(label="删除条目", command=lambda: self.delete_item(item))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()


# ---------------------------------------------------------------------------
# 角色列表
# ---------------------------------------------------------------------------

class CharacterCard(tk.Frame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any], character: dict[str, Any]):
        super().__init__(master, bg=Palette.BORDER)
        self.app = app
        self.theme = theme
        self.project = project
        self.character = character
        name = store.display_character_name(character)
        done, _filled, total = store.character_progress(character)

        inner = tk.Frame(self, bg=Palette.CARD, padx=18, pady=15)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        top = tk.Frame(inner, bg=Palette.CARD)
        top.pack(fill="x")
        Avatar(top, store.display_character_initial(character), bg=Palette.CARD,
               size=42).pack(side="left")
        name_box = tk.Frame(top, bg=Palette.CARD)
        name_box.pack(side="left", fill="x", expand=True, padx=(12, 0))
        tk.Label(name_box, text=name, bg=Palette.CARD, fg=Palette.INK,
                 font=theme.h2, anchor="w").pack(anchor="w")
        tk.Label(name_box, text=f"{total} 个条目",
                 bg=Palette.CARD, fg=Palette.MUTED, font=theme.tiny,
                 anchor="w").pack(anchor="w", pady=(2, 0))
        menu = tk.Label(top, text="⋯", bg=Palette.CARD, fg=Palette.MUTED,
                        font=theme.body, cursor="hand2", padx=6)
        menu.pack(side="right", anchor="n")
        menu.bind("<Button-1>", lambda _e: self._menu())
        menu.bind("<Enter>", lambda _e: menu.configure(fg=Palette.ACCENT))
        menu.bind("<Leave>", lambda _e: menu.configure(fg=Palette.MUTED))

        prog_row = tk.Frame(inner, bg=Palette.CARD)
        prog_row.pack(fill="x", pady=(13, 6))
        tk.Label(prog_row, text="完成度", bg=Palette.CARD, fg=Palette.MUTED,
                 font=theme.tiny).pack(side="left")
        tk.Label(prog_row, text=f"{done} / {total}", bg=Palette.CARD,
                 fg=Palette.INK, font=theme.small).pack(side="right")
        bar = ProgressBar(inner, height=5, bg=Palette.CARD)
        bar.pack(fill="x")
        bar.set(done, total)

        mini = tk.Frame(inner, bg=Palette.CARD)
        mini.pack(fill="x", pady=(12, 6))
        for i in range(2):
            mini.grid_columnconfigure(i, weight=1, uniform="mini")
        summaries: list[tuple[str, int, int]] = []
        for title, node in _progress_rows(character):
            d, _f, t = store.section_progress(node)
            summaries.append((title, d, t))
        for idx, (title, d, t) in enumerate(summaries):
            item = MiniProgress(mini, theme, title, d, t, bg=Palette.CARD,
                                width=180, compact=True)
            item.grid(row=idx // 2, column=idx % 2, sticky="ew",
                      padx=(0 if idx % 2 == 0 else 12, 0), pady=3)

        footer = tk.Frame(inner, bg=Palette.CARD)
        footer.pack(fill="x", pady=(4, 0))
        tk.Label(footer, text="打开清单  →", bg=Palette.CARD, fg=Palette.ACCENT,
                 font=theme.small).pack(side="right")

        _bind_card_click(inner, lambda: self.app.open_character(character.get("id")))

    def _menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="打开角色", command=lambda: self.app.open_character(self.character.get("id")))
        menu.add_command(label="重命名角色", command=lambda: self.app.rename_character(self.character))
        menu.add_command(label="复制角色", command=lambda: self.app.duplicate_character(self.character))
        menu.add_separator()
        menu.add_command(label="删除角色", command=lambda: self.app.delete_character(self.character))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()


class CharactersView(ScrollFrame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any]):
        super().__init__(master, bg=Palette.BG, padding=28)
        self.app = app
        self.theme = theme
        self.project = project
        self._build()

    def _build(self) -> None:
        page_heading(
            self.body, self.theme, "角色", "",
            [("＋ 新建角色", self.app.new_character, "primary")],
        )
        characters = self.project.get("characters", [])
        if not characters:
            empty_state(self.body, self.theme, "还没有角色",
                        "＋ 创建第一个角色", self.app.new_character)
            return

        grid = tk.Frame(self.body, bg=Palette.BG)
        grid.pack(fill="both", expand=True)
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1, uniform="characters")
        for idx, character in enumerate(characters):
            card = CharacterCard(grid, self.app, self.theme, self.project, character)
            card.grid(row=idx // 2, column=idx % 2, sticky="nsew",
                      padx=(0 if idx % 2 == 0 else 14, 0), pady=(0, 14))


# ---------------------------------------------------------------------------
# 总览（一屏内看完，不滚动）
# ---------------------------------------------------------------------------

class OverviewView(tk.Frame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any]):
        super().__init__(master, bg=Palette.BG)
        self.app = app
        self.theme = theme
        self.project = project
        self._build()

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        clear_children(self)
        self._build()

    def _schedule_refresh(self) -> None:
        try:
            self.after(40, self._safe_refresh)
        except tk.TclError:
            pass

    def _safe_refresh(self) -> None:
        try:
            self.refresh()
        except tk.TclError:
            pass

    def _build(self) -> None:
        wrap = tk.Frame(self, bg=Palette.BG)
        wrap.pack(fill="both", expand=True, padx=28, pady=(18, 14))
        self._build_hero(wrap)
        self._build_world(wrap)
        self._build_characters(wrap)

    # ------------------------------------------------------------------
    def _build_hero(self, parent: tk.Misc) -> None:
        project = self.project
        done, _filled, total = store.project_progress(project)
        characters = project.get("characters", [])
        world = project.get("world", [])
        todos = store.collect_todos(project)

        hero = tk.Frame(parent, bg=Palette.GREEN_DARK, padx=24, pady=15)
        hero.pack(fill="x")
        hero.grid_columnconfigure(0, weight=1)

        left = tk.Frame(hero, bg=Palette.GREEN_DARK)
        left.grid(row=0, column=0, sticky="nsew")
        tk.Label(left, text="项目进度", bg=Palette.GREEN_DARK, fg="#BFD1C2",
                 font=self.theme.tiny, anchor="w").pack(anchor="w")
        number = tk.Frame(left, bg=Palette.GREEN_DARK)
        number.pack(anchor="w", pady=(1, 0))
        tk.Label(number, text=str(done), bg=Palette.GREEN_DARK, fg=Palette.WHITE,
                 font=self.theme.font(28, "bold", "display"),
                 anchor="w").pack(side="left")
        tk.Label(number, text=f" / {total}", bg=Palette.GREEN_DARK, fg="#BFD1C2",
                 font=self.theme.font(13, "bold", "display"),
                 anchor="w").pack(side="left", pady=(9, 0))
        bar = ProgressBar(left, height=6, bg=Palette.GREEN_DARK,
                          track="#4A6655", fill=Palette.GOLD)
        bar.pack(fill="x", pady=(9, 0))
        bar.set(done, total)

        right = tk.Frame(hero, bg=Palette.GREEN_DARK)
        right.grid(row=0, column=1, sticky="ne", padx=(26, 0))
        stats = [
            ("角色", len(characters), None),
            ("世界观", len(world), lambda: self.app.show_tab("world")),
            ("待完成", len(todos), lambda: self.app.show_tab("todos")),
        ]
        for idx, (label, value, command) in enumerate(stats):
            cell = tk.Frame(right, bg=Palette.GREEN_DARK, cursor="hand2")
            cell.grid(row=0, column=idx, sticky="e", padx=(18, 0))
            value_label = tk.Label(cell, text=str(value), bg=Palette.GREEN_DARK,
                                   fg=Palette.WHITE,
                                   font=self.theme.font(20, "bold", "display"))
            value_label.pack(anchor="e")
            text_label = tk.Label(cell, text=label, bg=Palette.GREEN_DARK,
                                  fg="#BFD1C2", font=self.theme.tiny)
            text_label.pack(anchor="e")
            if command is not None:
                for widget in (cell, value_label, text_label):
                    widget.configure(cursor="hand2")
                    widget.bind("<Button-1>", lambda _e, c=command: c())

    # ------------------------------------------------------------------
    def _build_world(self, parent: tk.Misc) -> None:
        world = self.project.get("world", [])
        done = sum(1 for item in world if item.get("done"))
        section_heading(
            parent, self.theme, "世界观", f"已完成 {done} / {len(world)}",
            ("查看全部  →", lambda: self.app.show_tab("world"), "ghost"),
        )
        if not world:
            tk.Label(parent, text="还没有世界观条目。", bg=Palette.BG,
                     fg=Palette.FAINT, font=self.theme.small).pack(
                anchor="w", pady=(0, 12))
            return

        chips = tk.Frame(parent, bg=Palette.BG)
        chips.pack(fill="x")
        for i in range(3):
            chips.grid_columnconfigure(i, weight=1, uniform="worldchip")
        for idx, item in enumerate(world[:6]):
            row = CheckRow(
                chips,
                title=item.get("title", "未命名条目"),
                done=bool(item.get("done")),
                on_toggle=lambda value, i=item: self._toggle_world(i, value),
                font=self.theme.body,
                padx=11,
                pady=7,
            )
            row.grid(row=idx // 3, column=idx % 3, sticky="ew",
                     padx=(0 if idx % 3 == 0 else 10, 0), pady=(0, 7))
        if len(world) > 6:
            tk.Label(parent, text=f"还有 {len(world) - 6} 个条目…", bg=Palette.BG,
                     fg=Palette.FAINT, font=self.theme.tiny).pack(anchor="w")

    def _toggle_world(self, item: dict[str, Any], checked: bool) -> None:
        item["done"] = checked
        self.app.data_changed()
        self._schedule_refresh()

    # ------------------------------------------------------------------
    def _build_characters(self, parent: tk.Misc) -> None:
        characters = self.project.get("characters", [])
        section_heading(
            parent, self.theme, "角色", f"{len(characters)} 位",
            ("＋ 新建角色", self.app.new_character, "ghost"),
        )
        if not characters:
            tk.Label(parent, text="还没有角色。", bg=Palette.BG, fg=Palette.FAINT,
                     font=self.theme.small).pack(anchor="w", pady=(0, 10))
            return

        titles: list[str] = []
        for character in characters:
            for title, _node in _progress_rows(character):
                if title not in titles:
                    titles.append(title)
        titles = titles[:6]

        outer = tk.Frame(parent, bg=Palette.BORDER)
        outer.pack(fill="x")
        table = tk.Frame(outer, bg=Palette.CARD, padx=14, pady=9)
        table.pack(fill="both", expand=True, padx=1, pady=1)
        table.grid_columnconfigure(0, minsize=170)
        for i in range(len(titles)):
            table.grid_columnconfigure(i + 1, minsize=84)
        table.grid_columnconfigure(len(titles) + 1, minsize=64)
        table.grid_columnconfigure(len(titles) + 2, weight=1)

        headers = ["角色"] + [_short(t, 5) for t in titles] + ["合计"]
        for col, text in enumerate(headers):
            tk.Label(table, text=text, bg=Palette.CARD, fg=Palette.MUTED,
                     font=self.theme.tiny,
                     anchor="w" if col == 0 else "e").grid(
                row=0, column=col, sticky="ew", pady=(0, 5))

        for idx, character in enumerate(characters[:6]):
            row = idx + 1
            widgets: list[tk.Label] = []
            name_label = tk.Label(
                table, text=_short(store.display_character_name(character), 10),
                bg=Palette.CARD, fg=Palette.INK, font=self.theme.small, anchor="w",
            )
            name_label.grid(row=row, column=0, sticky="ew", pady=2)
            widgets.append(name_label)

            by_title = _progress_map(character)
            for col, title in enumerate(titles, start=1):
                counts = by_title.get(title)
                if counts is None:
                    text, color = "—", Palette.FAINT
                else:
                    d, t = counts
                    text = f"{d}/{t}" if t else "—"
                    if t and d >= t:
                        color = Palette.GREEN_DARK
                    elif d:
                        color = Palette.INK_SOFT
                    else:
                        color = Palette.MUTED
                cell = tk.Label(table, text=text, bg=Palette.CARD, fg=color,
                                font=self.theme.small, anchor="e")
                cell.grid(row=row, column=col, sticky="ew", pady=2)
                widgets.append(cell)

            d, _f, t = store.character_progress(character)
            total_label = tk.Label(
                table, text=f"{d}/{t}", bg=Palette.CARD,
                fg=Palette.GREEN_DARK if t and d >= t else Palette.INK,
                font=self.theme.label, anchor="e",
            )
            total_label.grid(row=row, column=len(titles) + 1, sticky="ew", pady=2)
            widgets.append(total_label)

            for widget in widgets:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>",
                            lambda _e, c=character: self.app.open_character(c.get("id")))

        if len(characters) > 6:
            tk.Label(parent, text=f"还有 {len(characters) - 6} 位角色…",
                     bg=Palette.BG, fg=Palette.FAINT,
                     font=self.theme.tiny).pack(anchor="w", pady=(6, 0))


# ---------------------------------------------------------------------------
# 待完成
# ---------------------------------------------------------------------------

class TodoRow(tk.Frame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 todo: dict[str, Any], on_done: Callable[[], None],
                 *, compact: bool = False):
        super().__init__(master, bg=Palette.BORDER)
        self.app = app
        self.theme = theme
        self.todo = todo
        self.on_done = on_done
        inner = tk.Frame(self, bg=Palette.CARD,
                         padx=13 if compact else 16, pady=9 if compact else 11)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        check = CheckBox(inner, False, self._complete, bg=Palette.CARD,
                         size=18 if compact else 20)
        check.pack(side="left", pady=(1, 0))
        body = tk.Frame(inner, bg=Palette.CARD)
        body.pack(side="left", fill="x", expand=True, padx=(10, 8))
        title_row = tk.Frame(body, bg=Palette.CARD)
        title_row.pack(fill="x")
        tk.Label(title_row, text=todo.get("title", "未命名条目"), bg=Palette.CARD,
                 fg=Palette.INK, font=theme.body if compact else theme.body_lg,
                 anchor="w").pack(side="left")
        tk.Label(title_row, text=todo.get("path", ""), bg=Palette.CARD,
                 fg=Palette.FAINT, font=theme.tiny, anchor="w").pack(
            side="left", padx=(10, 0)
        )
        tk.Label(inner, text="→", bg=Palette.CARD, fg=Palette.BORDER_STRONG,
                 font=theme.h3).pack(side="right")
        _bind_card_click(body, self._open)

    def _open(self) -> None:
        if self.todo.get("kind") == "world":
            self.app.show_tab("world", focus_id=self.todo.get("field_id"))
        else:
            self.app.open_character(self.todo.get("character_id"),
                                    field_id=self.todo.get("field_id"))

    def _complete(self, checked: bool) -> None:
        if checked:
            self.app.complete_todo(self.todo)
            self.on_done()


class TodoView(ScrollFrame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any]):
        super().__init__(master, bg=Palette.BG, padding=28)
        self.app = app
        self.theme = theme
        self.project = project
        self._build()

    def _build(self) -> None:
        todos = store.collect_todos(self.project)
        page_heading(
            self.body, self.theme, "待完成", f"{len(todos)} 项未勾选",
            [("回到总览", lambda: self.app.show_tab("overview"), "ghost")],
        )
        if not todos:
            empty_state(self.body, self.theme, "暂时没有待完成条目",
                        "回到总览", lambda: self.app.show_tab("overview"))
            return
        for todo in todos:
            row = TodoRow(self.body, self.app, self.theme, todo,
                          on_done=self.app.rebuild_current)
            row.pack(fill="x", pady=(0, 8))


# ---------------------------------------------------------------------------
# 角色清单
# ---------------------------------------------------------------------------

class CharacterEditor(tk.Frame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any], character: dict[str, Any],
                 focus_field_id: str | None = None):
        super().__init__(master, bg=Palette.BG)
        self.app = app
        self.theme = theme
        self.project = project
        self.character = character
        self.focus_field_id = focus_field_id
        self.section_frames: dict[str, tk.Frame] = {}
        self.section_bodies: dict[str, tk.Frame] = {}
        self.section_progress_labels: dict[str, tk.Label] = {}
        self.section_toggle_buttons: dict[str, FlatButton] = {}
        self.field_rows: dict[str, CheckRow] = {}
        self.group_frames: dict[str, tk.Frame] = {}
        self.collapsed_sections: set[str] = set()
        self._build()
        self._refresh_progress()
        if focus_field_id:
            self.after(160, self._focus_requested_field)

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _build(self) -> None:
        top = tk.Frame(self, bg=Palette.BG, padx=28, pady=12)
        top.pack(fill="x")
        FlatButton(top, "← 返回角色", self.app.close_character, variant="ghost",
                   bg=Palette.BG, font=self.theme.body,
                   padx=10, pady=5).pack(side="left")
        crumb = tk.Frame(top, bg=Palette.BG)
        crumb.pack(side="left", padx=(12, 0))
        tk.Label(crumb, text=self.project.get("name", "项目"), bg=Palette.BG,
                 fg=Palette.MUTED, font=self.theme.tiny, anchor="w").pack(anchor="w")
        tk.Label(crumb, text="角色清单", bg=Palette.BG, fg=Palette.INK,
                 font=self.theme.small, anchor="w").pack(anchor="w")
        FlatButton(top, "⋯", self._menu, variant="ghost", bg=Palette.BG,
                   font=self.theme.body, padx=10, pady=5).pack(side="right")
        FlatButton(top, "导出此角色", lambda: self.app.export_character(self.character),
                   variant="secondary", font=self.theme.small,
                   padx=12, pady=5).pack(side="right", padx=(0, 6))

        divider(self)

        self.scroll = ScrollFrame(self, bg=Palette.BG, padding=26)
        self.scroll.pack(fill="both", expand=True)
        self._build_header()
        for index, section in enumerate(self.character.get("sections", [])):
            self._build_section(self.scroll.body, section, index)

    def _build_header(self) -> None:
        card = Card(self.scroll.body, bg=Palette.CARD, padding=18)
        card.pack(fill="x", pady=(0, 16))
        top = tk.Frame(card.body, bg=Palette.CARD)
        top.pack(fill="x")
        self.avatar = Avatar(top, store.display_character_initial(self.character),
                             bg=Palette.CARD, size=54)
        self.avatar.pack(side="left", anchor="n")
        info = tk.Frame(top, bg=Palette.CARD)
        info.pack(side="left", fill="x", expand=True, padx=(14, 20))
        self.name_label = tk.Label(
            info, text=store.display_character_name(self.character), bg=Palette.CARD,
            fg=Palette.INK, font=self.theme.font(22, "bold", "display"), anchor="w",
        )
        self.name_label.pack(anchor="w")
        self.meta_label = tk.Label(info, text="", bg=Palette.CARD, fg=Palette.MUTED,
                                   font=self.theme.small, anchor="w")
        self.meta_label.pack(anchor="w", pady=(3, 0))
        right = tk.Frame(top, bg=Palette.CARD)
        right.pack(side="right", anchor="n")
        self.header_progress_label = tk.Label(right, text="", bg=Palette.CARD,
                                              fg=Palette.INK, font=self.theme.small)
        self.header_progress_label.pack(anchor="e")
        self.header_bar = ProgressBar(right, height=6, bg=Palette.CARD, width=170)
        self.header_bar.pack(anchor="e", pady=(6, 0), fill="x")

    def _build_section(self, parent: tk.Misc, section: dict[str, Any], index: int) -> None:
        card = Card(parent, bg=Palette.CARD, padding=0)
        card.pack(fill="x", pady=(0, 14))
        self.section_frames[section.get("id")] = card
        header = tk.Frame(card.body, bg=Palette.CARD, padx=16, pady=12)
        header.pack(fill="x")
        if len(self.character.get("sections", [])) > 1:
            tk.Label(header, text=f"{index + 1:02d}", bg=Palette.CARD,
                     fg=Palette.ACCENT, font=self.theme.tiny).pack(
                side="left", anchor="n", pady=(3, 0)
            )
            pad_left = 10
        else:
            pad_left = 0
        tk.Label(header, text=section.get("title", "未命名条目"), bg=Palette.CARD,
                 fg=Palette.INK, font=self.theme.h3, anchor="w").pack(
            side="left", padx=(pad_left, 0)
        )
        prog = tk.Label(header, text="", bg=Palette.CARD_ALT, fg=Palette.MUTED,
                        font=self.theme.tiny, padx=8, pady=2)
        prog.pack(side="left", padx=(10, 0))
        self.section_progress_labels[section.get("id")] = prog
        FlatButton(header, "⋯", lambda s=section: self._section_menu(s),
                   variant="ghost", bg=Palette.CARD, font=self.theme.body,
                   padx=6, pady=0).pack(side="right")
        collapsed = section.get("id") in self.collapsed_sections
        toggle = FlatButton(header, "展开" if collapsed else "收起",
                            lambda s=section, b=None: None,
                            variant="ghost", bg=Palette.CARD, font=self.theme.tiny,
                            padx=7, pady=1)
        toggle.pack(side="right", padx=(0, 2))
        self.section_toggle_buttons[section.get("id")] = toggle
        if section.get("tutorial"):
            FlatButton(header, "教程", lambda k=section.get("tutorial"): self.app.open_tutorial(k),
                       variant="ghost", bg=Palette.CARD, font=self.theme.tiny,
                       padx=8, pady=2).pack(side="right", padx=(0, 4))

        body = tk.Frame(card.body, bg=Palette.CARD, padx=16)
        self.section_bodies[section.get("id")] = body
        toggle.configure(command=lambda: self._toggle_section(section, body, toggle))
        self._build_section_body(body, section)
        if not collapsed:
            body.pack(fill="x", pady=(0, 14))

    def _build_section_body(self, body: tk.Frame, section: dict[str, Any]) -> None:
        groups = list(section.get("children") or [])
        fields = list(section.get("fields", []))

        for group in groups:
            self._build_group(body, section, group)
        if groups:
            FlatButton(body, "＋ 添加分组", lambda s=section: self._add_group(s),
                       variant="ghost", bg=Palette.CARD,
                       font=self.theme.small).pack(anchor="w", pady=(0, 6))
        for field in fields:
            self._add_field_row(body, section, None, field)
        FlatButton(body, "＋ 添加条目", lambda s=section: self._add_field(s),
                   variant="ghost", bg=Palette.CARD,
                   font=self.theme.small).pack(anchor="w", pady=(2, 8))

    def _build_group(self, parent: tk.Misc, section: dict[str, Any],
                     group: dict[str, Any]) -> None:
        outer = tk.Frame(parent, bg=Palette.CARD_ALT)
        outer.pack(fill="x", pady=(0, 10))
        self.group_frames[group.get("id")] = outer
        head = tk.Frame(outer, bg=Palette.CARD_ALT, padx=12, pady=8)
        head.pack(fill="x")
        tk.Label(head, text=group.get("title", "未命名分组"), bg=Palette.CARD_ALT,
                 fg=Palette.GREEN_DARK, font=self.theme.label,
                 anchor="w").pack(side="left")
        menu = tk.Label(head, text="⋯", bg=Palette.CARD_ALT, fg=Palette.MUTED,
                        font=self.theme.body, cursor="hand2", padx=5)
        menu.pack(side="right")
        menu.bind("<Button-1>", lambda _e: self._group_menu(section, group))
        menu.bind("<Enter>", lambda _e: menu.configure(fg=Palette.ACCENT))
        menu.bind("<Leave>", lambda _e: menu.configure(fg=Palette.MUTED))
        fields = tk.Frame(outer, bg=Palette.CARD_ALT, padx=10, pady=0)
        fields.pack(fill="x")
        for field in group.get("fields", []):
            self._add_field_row(fields, section, group, field)
        FlatButton(fields, "＋ 添加条目", lambda s=section, g=group: self._add_field(s, g),
                   variant="ghost", bg=Palette.CARD_ALT,
                   font=self.theme.tiny).pack(anchor="w", pady=(0, 8))

    def _add_field_row(self, parent: tk.Misc, section: dict[str, Any],
                       group: dict[str, Any] | None, field: dict[str, Any]) -> None:
        bg = Palette.CARD_ALT if group is not None else Palette.CARD
        row = CheckRow(
            parent,
            title=field.get("title", "未命名条目"),
            done=bool(field.get("done")),
            on_toggle=lambda value, f=field: self._toggle_field(f, value),
            on_menu=lambda f=field: self._field_menu(f),
            font=self.theme.body,
            bg=bg,
            padx=12,
            pady=7,
        )
        row.pack(fill="x", pady=(0, 6))
        self.field_rows[field.get("id")] = row

    # ------------------------------------------------------------------
    # 进度
    # ------------------------------------------------------------------
    def _refresh_progress(self) -> None:
        done, _filled, total = store.character_progress(self.character)
        self.header_progress_label.configure(text=f"已完成 {done} / {total}")
        self.header_bar.set(done, total)
        self.meta_label.configure(
            text=f"共 {total} 个条目 · 已完成 {done}"
        )
        for section in self.character.get("sections", []):
            d, _f, t = store.section_progress(section)
            sid = section.get("id")
            if sid in self.section_progress_labels:
                self.section_progress_labels[sid].configure(
                    text=f"{d}/{t}" if t else "未设置"
                )

    def _toggle_field(self, field: dict[str, Any], checked: bool) -> None:
        field["done"] = checked
        self._refresh_progress()
        self.app.data_changed()

    # ------------------------------------------------------------------
    # 分组与条目操作
    # ------------------------------------------------------------------
    def _toggle_section(self, section: dict[str, Any], body: tk.Frame,
                        button: tk.Button) -> None:
        sid = section.get("id")
        if sid in self.collapsed_sections:
            self.collapsed_sections.remove(sid)
            body.pack(fill="x", pady=(0, 14))
            button.set_text("收起")
        else:
            self.collapsed_sections.add(sid)
            body.pack_forget()
            button.set_text("展开")

    def _section_menu(self, section: dict[str, Any]) -> None:
        menu = tk.Menu(self, tearoff=0)
        if section.get("tutorial"):
            menu.add_command(label="查看本篇教程",
                             command=lambda: self.app.open_tutorial(section.get("tutorial")))
            menu.add_separator()
        menu.add_command(label="重命名条目", command=lambda: self._rename_section(section))
        menu.add_command(label="上移", command=lambda: self._move_section(section, -1))
        menu.add_command(label="下移", command=lambda: self._move_section(section, 1))
        menu.add_separator()
        menu.add_command(label="补齐默认条目", command=self._merge_defaults)
        menu.add_command(label="删除条目", command=lambda: self._delete_section(section))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _group_menu(self, section: dict[str, Any], group: dict[str, Any]) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="重命名分组", command=lambda: self._rename_group(group))
        menu.add_command(label="上移", command=lambda: self._move_group(section, group, -1))
        menu.add_command(label="下移", command=lambda: self._move_group(section, group, 1))
        menu.add_separator()
        menu.add_command(label="删除分组", command=lambda: self._delete_group(section, group))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _rename_section(self, section: dict[str, Any]) -> None:
        title = self.app.ask_string("重命名条目", "新的名称：",
                                    section.get("title", ""))
        if title:
            section["title"] = title.strip()
            self.app.data_changed(structural=True)

    def _delete_section(self, section: dict[str, Any]) -> None:
        done, _filled, total = store.section_progress(section)
        message = f"确定删除条目「{section.get('title', '')}」吗？"
        if total:
            message += f"\n\n里面还有 {total} 个条目（已完成 {done} 个），删除后无法恢复。"
        if not self.app.confirm("删除条目", message, "删除", danger=True):
            return
        store.remove_from_list(self.character.get("sections", []), section)
        self.app.data_changed(structural=True)

    def _move_section(self, section: dict[str, Any], delta: int) -> None:
        if store.move_in_list(self.character.get("sections", []), section, delta):
            self.app.data_changed(structural=True)

    def _add_group(self, section: dict[str, Any]) -> None:
        title = self.app.ask_string("添加分组", "新分组的名称：", "新分组")
        if not title:
            return
        section.setdefault("children", []).append({
            "id": store.new_id("g"),
            "title": title.strip(),
            "hint": "",
            "fields": [],
        })
        self.app.data_changed(structural=True)

    def _rename_group(self, group: dict[str, Any]) -> None:
        title = self.app.ask_string("重命名分组", "新的名称：", group.get("title", ""))
        if title:
            group["title"] = title.strip()
            self.app.data_changed(structural=True)

    def _delete_group(self, section: dict[str, Any], group: dict[str, Any]) -> None:
        total = len(group.get("fields", []))
        message = f"确定删除分组「{group.get('title', '')}」吗？"
        if total:
            message += f"\n\n其中 {total} 个条目也会一起删除，无法恢复。"
        if not self.app.confirm("删除分组", message, "删除", danger=True):
            return
        store.remove_from_list(section.get("children", []), group)
        self.app.data_changed(structural=True)

    def _move_group(self, section: dict[str, Any], group: dict[str, Any],
                    delta: int) -> None:
        if store.move_in_list(section.get("children", []), group, delta):
            self.app.data_changed(structural=True)

    def _add_field(self, section: dict[str, Any],
                   group: dict[str, Any] | None = None) -> None:
        target = group if group is not None else section
        where = group.get("title") if group else section.get("title")
        title = self.app.ask_string("添加条目", f"在「{where}」下添加一个条目：", "新条目")
        if not title:
            return
        target.setdefault("fields", []).append({
            "id": store.new_id("f"),
            "title": title.strip(),
            "hint": "",
            "content": "",
            "done": False,
        })
        self.app.data_changed(structural=True)

    def _find_field_parent(self, field: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
        for section in self.character.get("sections", []):
            for f in section.get("fields", []):
                if f is field:
                    return section.get("fields", []), section, None
            for group in section.get("children", []):
                for f in group.get("fields", []):
                    if f is field:
                        return group.get("fields", []), section, group
        return [], {}, None

    def _rename_field(self, field: dict[str, Any]) -> None:
        title = self.app.ask_string("重命名条目", "新的名称：", field.get("title", ""))
        if title:
            field["title"] = title.strip()
            self.app.data_changed(structural=True)

    def _move_field(self, field: dict[str, Any], delta: int) -> None:
        fields, _section, _group = self._find_field_parent(field)
        if store.move_in_list(fields, field, delta):
            self.app.data_changed(structural=True)

    def _delete_field(self, field: dict[str, Any]) -> None:
        message = f"确定删除「{field.get('title', '未命名条目')}」吗？"
        if not self.app.confirm("删除条目", message, "删除", danger=True):
            return
        fields, _section, _group = self._find_field_parent(field)
        store.remove_from_list(fields, field)
        self.app.data_changed(structural=True)

    def _field_menu(self, field: dict[str, Any]) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="重命名条目", command=lambda: self._rename_field(field))
        menu.add_command(label="上移", command=lambda: self._move_field(field, -1))
        menu.add_command(label="下移", command=lambda: self._move_field(field, 1))
        menu.add_separator()
        menu.add_command(label="删除条目", command=lambda: self._delete_field(field))
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _merge_defaults(self) -> None:
        added = store.merge_character_defaults(self.character)
        if added:
            self.app.data_changed(structural=True)
            self.app.show_info("已补齐默认条目", f"新增了 {added} 个默认条目。已有内容没有被覆盖。")
        else:
            self.app.show_info("默认条目已齐全", "没有需要补齐的默认条目。")

    def _menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="重命名角色", command=self.app.rename_character_for_editor)
        menu.add_command(label="复制角色", command=self.app.duplicate_character_for_editor)
        menu.add_command(label="补齐默认条目", command=self._merge_defaults)
        menu.add_separator()
        menu.add_command(label="导出此角色", command=lambda: self.app.export_character(self.character))
        menu.add_separator()
        menu.add_command(label="删除角色", command=self.app.delete_character_for_editor)
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()

    def _focus_requested_field(self) -> None:
        if not self.winfo_exists():
            return
        row = self.field_rows.get(self.focus_field_id or "")
        if row is None:
            return
        # 目标条目可能在收起的条目里，先展开再滚动。
        for section in self.character.get("sections", []):
            if any(f.get("id") == self.focus_field_id for f in store.section_fields(section)):
                sid = section.get("id")
                if sid in self.collapsed_sections:
                    self.collapsed_sections.remove(sid)
                    body = self.section_bodies.get(sid)
                    if body is not None:
                        body.pack(fill="x", pady=(0, 14))
                    button = self.section_toggle_buttons.get(sid)
                    if button is not None:
                        button.set_text("收起")
                break
        self.update_idletasks()
        self.scroll.see_widget(row)
        row.flash()


# ---------------------------------------------------------------------------
# 项目工作区
# ---------------------------------------------------------------------------

def _short_time(value: str) -> str:
    if not value:
        return ""
    try:
        return value[5:16].replace("T", " ")
    except Exception:
        return value


class Workspace(tk.Frame):
    def __init__(self, master: tk.Misc, app: Any, theme: Theme,
                 project: dict[str, Any], tab: str = "overview"):
        super().__init__(master, bg=Palette.BG)
        self.app = app
        self.theme = theme
        self.project = project
        self.tab = tab
        self.focus_id: str | None = None
        self.character_id: str | None = None
        self.view: tk.Widget | None = None

        self.header = tk.Frame(self, bg=Palette.BG, padx=30, pady=16)
        self.header.pack(fill="x")
        self.tabs = tk.Frame(self, bg=Palette.BG, padx=30)
        self.tabs.pack(fill="x")
        self.content = tk.Frame(self, bg=Palette.BG)
        self.content.pack(fill="both", expand=True)

        self._build_header()
        self._build_tabs()
        self._show_tab(tab)

    # ------------------------------------------------------------------
    # 顶栏与页签
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        row = tk.Frame(self.header, bg=Palette.BG)
        row.pack(fill="x")
        left = tk.Frame(row, bg=Palette.BG)
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="项目", bg=Palette.BG, fg=Palette.ACCENT,
                 font=self.theme.label, anchor="w").pack(anchor="w")
        self.project_title = tk.Label(
            left, text=self.project.get("name", "未命名项目"), bg=Palette.BG,
            fg=Palette.INK, font=self.theme.font(23, "bold", "display"),
            anchor="w", justify="left", wraplength=560,
        )
        self.project_title.pack(anchor="w", pady=(1, 0))
        self.project_meta = tk.Label(left, text="", bg=Palette.BG,
                                     fg=Palette.MUTED, font=self.theme.small,
                                     anchor="w")
        self.project_meta.pack(anchor="w", pady=(3, 0))

        progress = tk.Frame(left, bg=Palette.BG)
        progress.pack(fill="x", pady=(8, 0))
        self.header_progress_label = tk.Label(progress, text="", bg=Palette.BG,
                                              fg=Palette.INK_SOFT, font=self.theme.tiny,
                                              anchor="w")
        self.header_progress_label.pack(anchor="w")
        self.header_bar = ProgressBar(progress, height=4, bg=Palette.BG, width=320)
        self.header_bar.pack(fill="x", pady=(4, 0))

        actions = tk.Frame(row, bg=Palette.BG)
        actions.pack(side="right", anchor="n", padx=(18, 0))
        FlatButton(actions, "＋ 新建角色", self.app.new_character,
                   variant="primary", font=self.theme.body).pack(side="left")
        FlatButton(actions, "导出", self.app.export_project, variant="secondary",
                   font=self.theme.body).pack(side="left", padx=(8, 0))
        FlatButton(actions, "⋯", self._project_menu, variant="ghost",
                   bg=Palette.BG, font=self.theme.body,
                   padx=10, pady=6).pack(side="left", padx=(4, 0))
        self._refresh_header()

    def _build_tabs(self) -> None:
        bar = tk.Frame(self.tabs, bg=Palette.BG)
        bar.pack(fill="x")
        self.tab_buttons: dict[str, tk.Button] = {}
        self.tab_lines: dict[str, tk.Frame] = {}
        for key, label in [("overview", "总览"), ("world", "世界观"),
                           ("characters", "角色"), ("todos", "待完成")]:
            item = tk.Frame(bar, bg=Palette.BG)
            item.pack(side="left", padx=(0, 4))
            btn = tk.Button(
                item, text=label, relief="flat", bd=0, highlightthickness=0,
                padx=12, pady=8, cursor="hand2", font=self.theme.body,
                bg=Palette.BG, fg=Palette.MUTED,
                activebackground=Palette.BG, activeforeground=Palette.INK,
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack()
            line = tk.Frame(item, bg=Palette.BG, height=2)
            line.pack(fill="x")
            self.tab_buttons[key] = btn
            self.tab_lines[key] = line
        divider(self.tabs)
        self._refresh_tabs()

    def _refresh_header(self) -> None:
        done, _filled, total = store.project_progress(self.project)
        self.header_progress_label.configure(text=f"已完成 {done} / {total}")
        self.header_bar.set(done, total)
        chars = len(self.project.get("characters", []))
        world = len(self.project.get("world", []))
        updated = _short_time(self.project.get("updated_at", ""))
        self.project_meta.configure(
            text=f"{chars} 位角色 · {world} 个世界观条目 · 更新于 {updated}"
        )

    def _refresh_tabs(self) -> None:
        counts = {
            "overview": "",
            "world": str(len(self.project.get("world", []))),
            "characters": str(len(self.project.get("characters", []))),
            "todos": str(len(store.collect_todos(self.project))),
        }
        labels = {"overview": "总览", "world": "世界观",
                  "characters": "角色", "todos": "待完成"}
        for key, btn in self.tab_buttons.items():
            count = counts[key]
            text = labels[key] + (f"  {count}" if count else "")
            active = (key == self.tab and not self.character_id)
            btn.configure(
                text=text,
                fg=Palette.ACCENT_DARK if active else Palette.MUTED,
                font=self.theme.font(10, "bold" if active else "normal"),
            )
            self.tab_lines[key].configure(bg=Palette.ACCENT if active else Palette.BG)

    # ------------------------------------------------------------------
    # 视图切换
    # ------------------------------------------------------------------
    def _clear_content(self) -> None:
        if self.view is not None:
            self.view.destroy()
            self.view = None
        else:
            clear_children(self.content)
        set_active_scroll(None)

    def _view_scroll(self) -> ScrollFrame | None:
        """当前页的滚动区域：页签页本身就是 ScrollFrame，角色清单里是 .scroll。"""
        if isinstance(self.view, ScrollFrame):
            return self.view
        scroll = getattr(self.view, "scroll", None)
        return scroll if isinstance(scroll, ScrollFrame) else None

    def _restore_chrome(self) -> None:
        self.header.pack(fill="x", before=self.content)
        self.tabs.pack(fill="x", before=self.content)

    def _show_tab(self, tab: str, focus_id: str | None = None) -> None:
        self.character_id = None
        self.tab = tab if tab in {"overview", "world", "characters", "todos"} else "overview"
        self.focus_id = focus_id
        self.app.flush_editors()
        self._restore_chrome()
        self._refresh_header()
        self._refresh_tabs()
        self._clear_content()
        if self.tab == "overview":
            self.view = OverviewView(self.content, self.app, self.theme, self.project)
        elif self.tab == "world":
            self.view = WorldView(self.content, self.app, self.theme, self.project,
                                  focus_id=focus_id)
        elif self.tab == "characters":
            self.view = CharactersView(self.content, self.app, self.theme, self.project)
        else:
            self.view = TodoView(self.content, self.app, self.theme, self.project)
        self.view.pack(fill="both", expand=True)
        set_active_scroll(self._view_scroll())
        self.app.set_status_tab(self.tab)

    def open_character(self, character_id: str | None,
                       field_id: str | None = None) -> None:
        character = store.find_character(self.project, character_id)
        if character is None:
            return
        self.character_id = character_id
        self.app.flush_editors()
        self.header.pack_forget()
        self.tabs.pack_forget()
        self._clear_content()
        self._refresh_tabs()
        self.view = CharacterEditor(self.content, self.app, self.theme,
                                    self.project, character, focus_field_id=field_id)
        self.view.pack(fill="both", expand=True)
        set_active_scroll(self._view_scroll())
        self.app.set_status_character(store.display_character_name(character))

    def close_character(self) -> None:
        self.character_id = None
        self._show_tab("characters")

    def rebuild_current(self) -> None:
        if self.character_id:
            character = store.find_character(self.project, self.character_id)
            if character is None:
                self.close_character()
                return
            self.open_character(self.character_id)
        else:
            self._show_tab(self.tab, focus_id=self.focus_id)

    def refresh_progress(self) -> None:
        if not self.character_id:
            self._refresh_header()
            self._refresh_tabs()
        self.app.refresh_sidebar_progress()

    def _project_menu(self) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="重命名项目", command=self.app.rename_project)
        menu.add_command(label="复制项目", command=self.app.duplicate_project)
        menu.add_separator()
        menu.add_command(label="导出 Markdown", command=self.app.export_project)
        menu.add_command(label="打开数据文件夹", command=self.app.open_data_folder)
        menu.add_separator()
        menu.add_command(label="删除项目", command=self.app.delete_project)
        try:
            menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())
        finally:
            menu.grab_release()
