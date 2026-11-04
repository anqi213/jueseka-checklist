# -*- coding: utf-8 -*-
"""内置教程库与 Markdown 阅读器。"""
from __future__ import annotations

import re
import tkinter as tk
from tkinter import ttk
import webbrowser
from typing import Any

from paths import resource_path
from theme import Palette, Theme
from widgets import FlatButton, Pill, ScrollFrame, divider


TUTORIAL_GROUPS: list[dict[str, Any]] = [
    {
        "key": "sanmingyue",
        "title": "三明月的人物生境教程",
        "note": "人物生境写法 · 四篇正文与附录",
        "items": [
            {
                "key": "basic",
                "part": "第一部分",
                "title": "基础信息",
                "file": "assets/tutorials/01_basic.md",
                "desc": "人物是谁：身体、身份与长期社会坐标。",
            },
            {
                "key": "life",
                "part": "第二部分",
                "title": "生活结构",
                "file": "assets/tutorials/02_life.md",
                "desc": "没有主线触发时，她原本生活在什么里面。",
            },
            {
                "key": "personality",
                "part": "第三部分",
                "title": "人物性情",
                "file": "assets/tutorials/03_personality.md",
                "desc": "她怎样理解事情、在乎什么、如何取舍。",
            },
            {
                "key": "scene",
                "part": "第四部分",
                "title": "场景表达",
                "file": "assets/tutorials/04_scene.md",
                "desc": "让已经写清的人真正站进场景里。",
            },
            {
                "key": "appendix",
                "part": "附录",
                "title": "落进角色卡",
                "file": "assets/tutorials/05_appendix.md",
                "desc": "从原始资料到最终角色卡的整理顺序。",
            },
        ],
    },
]

# 以后加别的写法：在 TUTORIAL_GROUPS 里再加一组即可，其余代码不用动。
TUTORIALS: list[dict[str, str]] = [
    item for group in TUTORIAL_GROUPS for item in group["items"]
]

_BY_KEY = {item["key"]: item for item in TUTORIALS}


def tutorial_meta(key: str | None) -> dict[str, str] | None:
    if not key:
        return None
    return _BY_KEY.get(key)


def tutorial_title(key: str | None) -> str:
    meta = tutorial_meta(key)
    return meta["title"] if meta else ""


def load_tutorial(key: str) -> str:
    meta = tutorial_meta(key)
    if not meta:
        return "没有找到这篇教程。"
    path = resource_path(meta["file"])
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return f"教程文件读取失败：{exc}\n\n路径：{path}"


def open_tutorial(parent: tk.Misc, theme: Theme, key: str | None = None) -> "TutorialLibrary":
    window = TutorialLibrary(parent, theme, initial_key=key)
    return window


class TutorialLibrary(tk.Toplevel):
    def __init__(self, parent: tk.Misc, theme: Theme, initial_key: str | None = None):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme
        self.current_key = initial_key if initial_key in _BY_KEY else "basic"
        self.font_size = 10
        self._link_count = 0

        self.title("角色卡创作清单 · 教程库")
        icon = resource_path("assets/app.ico")
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                pass
        self.configure(bg=Palette.BG)
        self.geometry("1120x780")
        self.minsize(920, 620)
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Control-f>", lambda _e: self._focus_search())

        self._build()
        self.after(20, self._center)
        self.after(60, self.lift)
        self.after(80, self.focus_force)
        self._show_tutorial(self.current_key)

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------
    def _build(self) -> None:
        header = tk.Frame(self, bg=Palette.SURFACE, padx=28, pady=16)
        header.pack(fill="x")
        title_box = tk.Frame(header, bg=Palette.SURFACE)
        title_box.pack(side="left", fill="x", expand=True)
        tk.Label(title_box, text="角色卡创作清单 · 教程库", bg=Palette.SURFACE,
                 fg=Palette.INK, font=self.theme.h1, anchor="w").pack(anchor="w")
        tk.Label(title_box, text="写人物时，随时回来查。教程都已内置，不依赖网络。",
                 bg=Palette.SURFACE, fg=Palette.MUTED, font=self.theme.small,
                 anchor="w").pack(anchor="w", pady=(4, 0))

        tools = tk.Frame(header, bg=Palette.SURFACE)
        tools.pack(side="right")
        FlatButton(tools, "A−", lambda: self._change_font(-1), variant="ghost",
                   font=self.theme.small, padx=8, pady=5).pack(side="left")
        self.font_label = tk.Label(tools, text="10 pt", bg=Palette.SURFACE,
                                   fg=Palette.MUTED, font=self.theme.tiny, width=5)
        self.font_label.pack(side="left")
        FlatButton(tools, "A＋", lambda: self._change_font(1), variant="ghost",
                   font=self.theme.small, padx=8, pady=5).pack(side="left")
        FlatButton(tools, "复制全文", self._copy_all, variant="secondary",
                   font=self.theme.small, padx=10, pady=5).pack(side="left", padx=(12, 0))
        FlatButton(tools, "关闭", self.destroy, variant="ghost",
                   font=self.theme.small, padx=10, pady=5).pack(side="left", padx=(6, 0))

        divider(self)

        body = tk.Frame(self, bg=Palette.BG)
        body.pack(fill="both", expand=True)

        # 左侧：教程列表（按写法分组）
        left = tk.Frame(body, bg=Palette.BG, width=268)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        left_scroll = ScrollFrame(left, bg=Palette.BG, padding=14)
        left_scroll.pack(fill="both", expand=True)

        self.nav_buttons: dict[str, tk.Button] = {}
        for index, group in enumerate(TUTORIAL_GROUPS):
            tk.Label(
                left_scroll.body, text=group["title"], bg=Palette.BG, fg=Palette.INK,
                font=self.theme.font(10, "bold"), anchor="w", justify="left",
                wraplength=218,
            ).pack(fill="x", padx=8, pady=(2 if index == 0 else 18, 2))
            if group.get("note"):
                tk.Label(
                    left_scroll.body, text=group["note"], bg=Palette.BG,
                    fg=Palette.FAINT, font=self.theme.tiny, anchor="w",
                    justify="left", wraplength=218,
                ).pack(fill="x", padx=8, pady=(0, 6))
            for item in group["items"]:
                btn = tk.Button(
                    left_scroll.body,
                    text=f"{item['part']}  ·  {item['title']}",
                    anchor="w", justify="left", relief="flat", bd=0,
                    highlightthickness=0, padx=14, pady=8, cursor="hand2",
                    font=self.theme.body, bg=Palette.BG, fg=Palette.INK_SOFT,
                    activebackground=Palette.ACCENT_SOFT,
                    activeforeground=Palette.ACCENT_DARK,
                    command=lambda k=item["key"]: self._show_tutorial(k),
                )
                btn.pack(fill="x", padx=(10, 2), pady=1)
                self.nav_buttons[item["key"]] = btn

        # 右侧：阅读区
        right = tk.Frame(body, bg=Palette.SURFACE)
        right.pack(side="left", fill="both", expand=True)
        self.right_head = tk.Frame(right, bg=Palette.SURFACE, padx=34, pady=18)
        self.right_head.pack(fill="x")
        self.part_pill = Pill(self.right_head, "第一部分", bg=Palette.ACCENT_SOFT,
                              fg=Palette.ACCENT_DARK, font=self.theme.tiny)
        self.part_pill.pack(side="left", anchor="n", pady=(4, 0))
        self.title_label = tk.Label(self.right_head, text="基础信息", bg=Palette.SURFACE,
                                    fg=Palette.INK, font=self.theme.h1, anchor="w")
        self.title_label.pack(side="left", anchor="n", padx=(12, 0))
        self.search_box = tk.Frame(self.right_head, bg=Palette.SURFACE)
        self.search_box.pack(side="right", anchor="n")
        tk.Label(self.search_box, text="搜索", bg=Palette.SURFACE, fg=Palette.MUTED,
                 font=self.theme.tiny).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            self.search_box, textvariable=self.search_var, width=18,
            bg=Palette.CARD, fg=Palette.INK, insertbackground=Palette.INK,
            relief="flat", highlightthickness=1, highlightbackground=Palette.BORDER,
            highlightcolor=Palette.ACCENT, font=self.theme.small,
        )
        self.search_entry.pack(side="left", ipady=5)
        self.search_entry.bind("<Return>", lambda _e: self._search_next())
        FlatButton(self.search_box, "下一个", self._search_next, variant="ghost",
                   font=self.theme.tiny, padx=8, pady=4).pack(side="left", padx=(4, 0))

        divider(right, bg=Palette.BORDER)
        text_wrap = tk.Frame(right, bg=Palette.SURFACE)
        text_wrap.pack(fill="both", expand=True)
        self.text = tk.Text(
            text_wrap, wrap="word", bg=Palette.SURFACE, fg=Palette.INK_SOFT,
            relief="flat", bd=0, highlightthickness=0, padx=34, pady=22,
            font=self.theme.body, cursor="arrow", spacing1=1, spacing3=2,
            selectbackground=Palette.ACCENT_SOFT, selectforeground=Palette.INK,
        )
        self.text_scroll = ttk.Scrollbar(text_wrap, orient="vertical",
                                         command=self.text.yview, style="App.TScrollbar")
        self.text.configure(yscrollcommand=self.text_scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        self.text_scroll.pack(side="right", fill="y")
        self._configure_tags()

    # ------------------------------------------------------------------
    # 教程切换与目录
    # ------------------------------------------------------------------
    def _show_tutorial(self, key: str) -> None:
        meta = tutorial_meta(key)
        if not meta:
            return
        self.current_key = key
        self.part_pill.configure(text=meta["part"])
        self.title_label.configure(text=meta["title"])
        self.search_var.set("")
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(bg=Palette.ACCENT_SOFT, fg=Palette.ACCENT_DARK,
                              font=self.theme.font(10, "bold"))
            else:
                btn.configure(bg=Palette.BG, fg=Palette.INK_SOFT,
                              font=self.theme.body)
        self._render(load_tutorial(key))
        self.text.yview_moveto(0)
        self.after_idle(lambda: self.text.yview_moveto(0))

    def _render(self, markdown: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self._link_count = 0

        lines = markdown.splitlines()
        in_code = False
        code_lines: list[str] = []
        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    self._insert_code_block(code_lines)
                    code_lines = []
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_lines.append(line)
                continue

            stripped = line.strip()
            if not stripped:
                self.text.insert("end", "\n", ("body",))
                continue

            if stripped.startswith("# "):
                text = stripped[2:].strip()
                self.text.insert("end", text + "\n", ("h1",))
            elif stripped.startswith("## "):
                text = stripped[3:].strip()
                self.text.insert("end", text + "\n", ("h2",))
            elif stripped.startswith("### "):
                text = stripped[4:].strip()
                self.text.insert("end", text + "\n", ("h3",))
            elif stripped.startswith("#### "):
                text = stripped[5:].strip()
                self.text.insert("end", text + "\n", ("h4",))
            elif stripped.startswith(">"):
                quote = stripped[1:].strip()
                self._insert_inline(quote, base_tag="quote")
                self.text.insert("end", "\n", ("quote",))
            elif stripped.startswith("- "):
                self.text.insert("end", "•  ", ("bullet",))
                self._insert_inline(stripped[2:], base_tag="bullet_text")
                self.text.insert("end", "\n", ("bullet",))
            elif re.match(r"^\d+\.\s", stripped):
                prefix, rest = stripped.split(" ", 1)
                self.text.insert("end", prefix + "  ", ("bullet",))
                self._insert_inline(rest, base_tag="bullet_text")
                self.text.insert("end", "\n", ("bullet",))
            elif stripped.startswith("|"):
                # 教程里没有表格；按普通正文显示，避免内容消失。
                self._insert_inline(stripped, base_tag="body")
                self.text.insert("end", "\n", ("body",))
            else:
                self._insert_inline(stripped, base_tag="body")
                self.text.insert("end", "\n", ("body",))
        if in_code and code_lines:
            self._insert_code_block(code_lines)

        self.text.configure(state="disabled")

    def _insert_code_block(self, lines: list[str]) -> None:
        if not lines:
            return
        self.text.insert("end", "\n", ("body",))
        for line in lines:
            self.text.insert("end", (line if line else " ") + "\n", ("code",))
        self.text.insert("end", "\n", ("body",))

    def _insert_inline(self, text: str, base_tag: str = "body") -> None:
        pattern = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")
        pos = 0
        for match in pattern.finditer(text):
            if match.start() > pos:
                self.text.insert("end", text[pos:match.start()], (base_tag,))
            token = match.group(0)
            if token.startswith("**") and token.endswith("**") and len(token) > 4:
                self.text.insert("end", token[2:-2], (base_tag, "bold"))
            elif token.startswith("`") and token.endswith("`") and len(token) > 2:
                self.text.insert("end", token[1:-1], (base_tag, "inline_code"))
            elif token.startswith("["):
                label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", token).groups()
                tag = f"link_{self._link_count}"
                self._link_count += 1
                self.text.insert("end", label, (base_tag, "link", tag))
                self.text.tag_bind(tag, "<Button-1>",
                                   lambda _e, u=url: webbrowser.open(u))
                self.text.tag_bind(tag, "<Enter>",
                                   lambda _e: self.text.configure(cursor="hand2"))
                self.text.tag_bind(tag, "<Leave>",
                                   lambda _e: self.text.configure(cursor="arrow"))
            pos = match.end()
        if pos < len(text):
            self.text.insert("end", text[pos:], (base_tag,))

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def _configure_tags(self) -> None:
        t = self.text
        s = self.font_size
        t.tag_configure("body", font=self.theme.font(s), foreground=Palette.INK_SOFT,
                        spacing1=2, spacing3=7, lmargin1=0, lmargin2=0)
        t.tag_configure("h1", font=self.theme.font(s + 10, "bold", "display"),
                        foreground=Palette.INK, spacing1=4, spacing3=16)
        t.tag_configure("h2", font=self.theme.font(s + 7, "bold", "display"),
                        foreground=Palette.INK, spacing1=18, spacing3=10)
        t.tag_configure("h3", font=self.theme.font(s + 2, "bold"),
                        foreground=Palette.GREEN, spacing1=15, spacing3=6)
        t.tag_configure("h4", font=self.theme.font(s + 1, "bold"),
                        foreground=Palette.INK_SOFT, spacing1=12, spacing3=4)
        t.tag_configure("bullet", font=self.theme.font(s), foreground=Palette.INK_SOFT,
                        lmargin1=18, lmargin2=34, spacing1=1, spacing3=3)
        t.tag_configure("bullet_text", font=self.theme.font(s),
                        foreground=Palette.INK_SOFT, lmargin1=18, lmargin2=34,
                        spacing1=1, spacing3=3)
        t.tag_configure("quote", font=self.theme.font(s), foreground=Palette.MUTED,
                        background=Palette.CARD_ALT, lmargin1=22, lmargin2=22,
                        rmargin=22, spacing1=5, spacing3=5)
        t.tag_configure("code", font=self.theme.font(s - 1, family="mono"),
                        foreground=Palette.INK, background="#F0EBE0",
                        lmargin1=24, lmargin2=24, rmargin=24, spacing1=2, spacing3=2)
        t.tag_configure("bold", font=self.theme.font(s, "bold"),
                        foreground=Palette.INK)
        t.tag_configure("inline_code", font=self.theme.font(s - 1, family="mono"),
                        foreground=Palette.ACCENT_DARK, background="#F1E8DC")
        t.tag_configure("link", foreground=Palette.ACCENT, underline=True)
        t.tag_raise("sel")

    def _change_font(self, delta: int) -> None:
        new_size = max(9, min(16, self.font_size + delta))
        if new_size == self.font_size:
            return
        self.font_size = new_size
        self.font_label.configure(text=f"{new_size} pt")
        self._configure_tags()

    def _copy_all(self) -> None:
        meta = tutorial_meta(self.current_key)
        text = load_tutorial(self.current_key)
        self.clipboard_clear()
        self.clipboard_append(text)
        old = self.title()
        self.title(f"角色卡创作清单 · 教程库 — 已复制《{meta['title'] if meta else ''}》")
        self.after(1800, lambda: self.title(old))

    def _focus_search(self) -> None:
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def _search_next(self) -> None:
        query = self.search_var.get().strip()
        if not query:
            self._focus_search()
            return
        self.text.tag_remove("search_hit", "1.0", "end")
        start = "insert"
        index = self.text.search(query, start, stopindex="end", nocase=True)
        if not index:
            index = self.text.search(query, "1.0", stopindex="end", nocase=True)
        if not index:
            return
        end = f"{index}+{len(query)}c"
        self.text.tag_add("search_hit", index, end)
        self.text.tag_configure("search_hit", background=Palette.GOLD_SOFT,
                                foreground=Palette.INK)
        self.text.mark_set("insert", end)
        self.text.see(index)
        self.text.yview_scroll(-2, "units")

    def _center(self) -> None:
        self.update_idletasks()
        parent = self.parent.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, min(x, screen_w - self.winfo_width() - 20))
        y = max(0, min(y, screen_h - self.winfo_height() - 40))
        self.geometry(f"+{x}+{y}")
