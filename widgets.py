# -*- coding: utf-8 -*-
"""可复用的 Tk 组件：滚动容器、按钮、方框勾选、清单行、进度条、文本编辑器与对话框。"""
from __future__ import annotations

import re
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Any, Callable, Sequence

from theme import Palette, Theme


# ---------------------------------------------------------------------------
# 滚轮
# ---------------------------------------------------------------------------

# 这些控件自己会处理滚轮（Tk 的类绑定），不要再替它们滚一次。
_NATIVE_WHEEL_WIDGETS = (
    tk.Text, tk.Listbox, tk.Scrollbar, ttk.Scrollbar,
    ttk.Combobox, ttk.Spinbox, ttk.Scale,
)

_wheel_root: tk.Misc | None = None
_wheel_active: "ScrollFrame | None" = None


def install_wheel_scrolling(root: tk.Misc) -> None:
    """让滚轮在整个窗口内都生效。

    指针落在哪里就滚哪一块：落在滚动区域上就滚那一块，落在标题、页签、
    侧栏空白处就滚当前页。不再要求先把指针移到滚动条上。
    """
    global _wheel_root
    if _wheel_root is not None:
        return
    _wheel_root = root
    root.bind_all("<MouseWheel>", _on_wheel, add="+")
    root.bind_all("<Button-4>", _on_wheel, add="+")
    root.bind_all("<Button-5>", _on_wheel, add="+")


def set_active_scroll(frame: "ScrollFrame | None") -> None:
    """记下当前页的滚动区域，供指针不在滚动区域上时使用。"""
    global _wheel_active
    _wheel_active = frame


def _nearest_scroll(widget: tk.Misc | None) -> "ScrollFrame | None":
    while widget is not None:
        if isinstance(widget, ScrollFrame):
            return widget
        widget = getattr(widget, "master", None)
    return None


def _has_native_wheel(widget: tk.Misc | None, stop: tk.Misc) -> bool:
    while widget is not None and widget is not stop:
        if isinstance(widget, _NATIVE_WHEEL_WIDGETS):
            return True
        widget = getattr(widget, "master", None)
    return False


def _wheel_steps(event: tk.Event) -> int:
    """把滚轮事件换算成「行」，向下为正。"""
    if getattr(event, "num", None) == 4:
        return -1
    if getattr(event, "num", None) == 5:
        return 1
    delta = int(getattr(event, "delta", 0) or 0)
    if delta == 0:
        return 0
    steps = int(-delta / 120)
    return steps if steps else (-1 if delta > 0 else 1)


def _on_wheel(event: tk.Event) -> str | None:
    try:
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
    except (tk.TclError, KeyError):
        widget = None
    if widget is None:
        widget = event.widget

    target = _nearest_scroll(widget)
    if target is not None and _has_native_wheel(widget, target):
        return None  # 交给控件自己的类绑定
    if target is None:
        try:
            same_window = widget.winfo_toplevel() is _wheel_root
        except tk.TclError:
            same_window = False
        if not same_window:
            return None  # 对话框里的滚轮不去滚主窗口
        target = _wheel_active
    if target is None:
        return None
    try:
        if not target.winfo_exists():
            return None
    except tk.TclError:
        return None

    steps = _wheel_steps(event)
    if steps == 0:
        return None
    if not target.can_scroll():
        # 指针下的这块本来就装得下，就滚当前页。
        fallback = _wheel_active
        if fallback is not None and fallback is not target and fallback.can_scroll():
            target = fallback
    if not target.can_scroll():
        return None
    target.scroll_steps(steps)
    return "break"


# ---------------------------------------------------------------------------
# 基础容器
# ---------------------------------------------------------------------------

class ScrollFrame(tk.Frame):
    """带细滚动条的垂直滚动容器。内容放在 .body。"""

    def __init__(self, master: tk.Misc, *, bg: str = Palette.BG,
                 scrollbar_style: str = "App.TScrollbar", padding: int = 0,
                 **kwargs: Any):
        super().__init__(master, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                                yscrollincrement=24)
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview,
            style=scrollbar_style,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        # 滚动条上也按同样的步长走，避免一格跳四倍远。
        self.scrollbar.bind("<MouseWheel>", self._on_own_scrollbar_wheel)
        self._scroll_visible = True
        self.body = tk.Frame(self.canvas, bg=bg, padx=padding, pady=padding)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_body_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._sync_scrollbar()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self._sync_scrollbar()

    def _sync_scrollbar(self) -> None:
        """内容装得下时不显示滚动条。"""
        box = self.canvas.bbox("all")
        if box is None:
            return
        needed = (box[3] - box[1]) > self.canvas.winfo_height() + 1
        if needed and not self._scroll_visible:
            self.scrollbar.pack(side="right", fill="y")
            self._scroll_visible = True
        elif not needed and self._scroll_visible:
            self.scrollbar.pack_forget()
            self._scroll_visible = False

    def _on_own_scrollbar_wheel(self, event: tk.Event) -> str:
        steps = _wheel_steps(event)
        if steps:
            self.scroll_steps(steps)
        return "break"  # 不让 Tk 默认的四倍步长再滚一次

    def can_scroll(self) -> bool:
        """内容比可视区高时才算能滚。"""
        try:
            first, last = self.canvas.yview()
        except tk.TclError:
            return False
        return not (first <= 0.0 and last >= 1.0)

    def scroll_steps(self, steps: int) -> None:
        """按行滚动；内容装得下时不动。"""
        if not self.can_scroll():
            return
        self.canvas.yview_scroll(steps, "units")

    def scroll_to(self, y: int) -> None:
        self.canvas.yview_moveto(max(0.0, min(1.0, y)))

    def see_widget(self, widget: tk.Widget) -> None:
        self.update_idletasks()
        try:
            y = widget.winfo_rooty() - self.body.winfo_rooty()
        except tk.TclError:
            return
        height = max(1, self.body.winfo_height())
        self.canvas.yview_moveto(max(0.0, min(1.0, y / height)))


class Card(tk.Frame):
    """带 1px 边框的卡片。内容放在 .body。"""

    def __init__(self, master: tk.Misc, *, bg: str = Palette.CARD,
                 border: str = Palette.BORDER, padding: int = 16,
                 **kwargs: Any):
        super().__init__(master, bg=border, highlightthickness=0, bd=0, **kwargs)
        self.inner = tk.Frame(self, bg=bg, padx=padding, pady=padding)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.body = self.inner


# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------

class FlatButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command: Callable[[], None] | None = None,
                 *, variant: str = "secondary", bg: str | None = None,
                 fg: str | None = None, font: Any = None, padx: int = 14, pady: int = 7,
                 width: int | None = None, anchor: str = "center", **kwargs: Any):
        self.variant = variant
        self._base_bg = bg
        self._base_fg = fg
        colors = self._colors(variant, bg, fg)
        super().__init__(
            master, text=text, command=command, font=font or "AppBody",
            bg=colors["bg"], fg=colors["fg"], activebackground=colors["hover"],
            activeforeground=colors["fg"], disabledforeground=Palette.FAINT,
            relief="flat", bd=0, highlightthickness=0, padx=padx, pady=pady,
            cursor="hand2", anchor=anchor, **kwargs,
        )
        if width is not None:
            self.configure(width=width)
        self._hover_bg = colors["hover"]
        self._normal_bg = colors["bg"]
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    @staticmethod
    def _colors(variant: str, bg: str | None, fg: str | None) -> dict[str, str]:
        if variant == "primary":
            return {"bg": bg or Palette.ACCENT, "fg": fg or Palette.WHITE,
                    "hover": Palette.ACCENT_DARK}
        if variant == "green":
            return {"bg": bg or Palette.GREEN, "fg": fg or Palette.WHITE,
                    "hover": Palette.GREEN_DARK}
        if variant == "danger":
            return {"bg": bg or Palette.DANGER, "fg": fg or Palette.WHITE,
                    "hover": "#87392D"}
        if variant == "ghost":
            return {"bg": bg or Palette.SURFACE, "fg": fg or Palette.INK_SOFT,
                    "hover": Palette.ACCENT_SOFT}
        if variant == "sidebar":
            return {"bg": bg or Palette.SIDEBAR_ALT, "fg": fg or Palette.SIDEBAR_TEXT,
                    "hover": Palette.SIDEBAR_ACTIVE}
        if variant == "quiet":
            return {"bg": bg or Palette.CARD_ALT, "fg": fg or Palette.INK_SOFT,
                    "hover": Palette.BORDER}
        return {"bg": bg or Palette.CARD, "fg": fg or Palette.INK_SOFT,
                "hover": Palette.CARD_ALT}

    def _on_enter(self, _event: tk.Event) -> None:
        if str(self.cget("state")) != "disabled":
            self.configure(bg=self._hover_bg)

    def _on_leave(self, _event: tk.Event) -> None:
        if str(self.cget("state")) != "disabled":
            self.configure(bg=self._normal_bg)

    def set_text(self, text: str) -> None:
        self.configure(text=text)


class LinkButton(tk.Label):
    """看起来像文字链接的按钮。"""

    def __init__(self, master: tk.Misc, text: str, command: Callable[[], None],
                 *, bg: str = Palette.CARD, fg: str = Palette.ACCENT,
                 font: Any = None, **kwargs: Any):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font or "AppSmall",
                         cursor="hand2", **kwargs)
        self._fg = fg
        self._hover = Palette.ACCENT_DARK if fg == Palette.ACCENT else Palette.INK
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Enter>", lambda _e: self.configure(fg=self._hover))
        self.bind("<Leave>", lambda _e: self.configure(fg=self._fg))


# ---------------------------------------------------------------------------
# 勾选与进度
# ---------------------------------------------------------------------------

class CheckBox(tk.Canvas):
    """方形勾选框：空方框 → 点一下 → 填色并出现对勾。"""

    def __init__(self, master: tk.Misc, checked: bool = False,
                 command: Callable[[bool], None] | None = None, *,
                 bg: str = Palette.CARD, size: int = 19, **kwargs: Any):
        super().__init__(master, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, cursor="hand2",
                         takefocus=1, **kwargs)
        self.size = size
        self._checked = bool(checked)
        self._command = command
        self._hover = False
        self._focused = False
        self._bg = bg
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self._draw()

    def _toggle(self, _event: tk.Event | None = None) -> str:
        self._checked = not self._checked
        self._draw()
        if self._command:
            self._command(self._checked)
        return "break"

    def _enter(self, _event: tk.Event) -> None:
        self._hover = True
        self._draw()

    def _leave(self, _event: tk.Event) -> None:
        self._hover = False
        self._draw()

    def _focus_in(self, _event: tk.Event) -> None:
        self._focused = True
        self._draw()

    def _focus_out(self, _event: tk.Event) -> None:
        self._focused = False
        self._draw()

    def set_checked(self, checked: bool) -> None:
        self._checked = bool(checked)
        self._draw()

    def set_bg(self, bg: str) -> None:
        self._bg = bg
        self.configure(bg=bg)
        self._draw()

    def get_checked(self) -> bool:
        return self._checked

    def _draw(self) -> None:
        self.delete("all")
        s = self.size
        pad = 1.5
        if self._checked:
            fill = Palette.GREEN
            outline = Palette.GREEN
        else:
            fill = self._bg
            outline = Palette.ACCENT if self._hover else Palette.BORDER_STRONG
        self.create_rectangle(pad, pad, s - pad, s - pad, fill=fill,
                              outline=outline, width=1.4)
        if self._checked:
            self.create_line(s * 0.26, s * 0.53, s * 0.43, s * 0.70,
                             s * 0.76, s * 0.31, fill=Palette.WHITE,
                             width=2.2, capstyle="round", joinstyle="round")
        if self._focused:
            self.create_rectangle(0.5, 0.5, s - 0.5, s - 0.5,
                                  outline=Palette.ACCENT, dash=(2, 2))


class CheckRow(tk.Frame):
    """一行清单：方框 + 标题（+ 说明）+ ⋯ 菜单。整行可点勾选。"""

    def __init__(self, master: tk.Misc, *, title: str, done: bool = False,
                 on_toggle: Callable[[bool], None] | None = None,
                 on_menu: Callable[[], None] | None = None,
                 meta: str = "", font: Any = None, bg: str = Palette.CARD,
                 size: int = 19, padx: int = 13, pady: int = 9,
                 wrap: int = 0, **kwargs: Any):
        super().__init__(master, bg=Palette.BORDER, **kwargs)
        self._done = bool(done)
        self._on_toggle = on_toggle
        self._bg = bg
        self._flash_job: str | None = None
        self._title_font = font or "AppBody"

        self.inner = tk.Frame(self, bg=bg, padx=padx, pady=pady)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.check = CheckBox(self.inner, self._done, self._toggle, bg=bg, size=size)
        self.check.pack(side="left", pady=(1, 0))
        self.title_label = tk.Label(self.inner, text=title, bg=bg, fg=Palette.INK,
                                    font=self._title_font, anchor="w", justify="left")
        self.title_label.pack(side="left", fill="x", expand=True, padx=(10, 8))
        self.meta_label = None
        if meta:
            self.meta_label = tk.Label(self.inner, text=meta, bg=bg, fg=Palette.FAINT,
                                       font="AppTiny")
            self.meta_label.pack(side="right", padx=(8, 0))
        self.menu_label = None
        if on_menu:
            self.menu_label = tk.Label(self.inner, text="⋯", bg=bg, fg=Palette.MUTED,
                                       font="AppBody", cursor="hand2", padx=5)
            self.menu_label.pack(side="right")
            self.menu_label.bind("<Button-1>", lambda _e: on_menu())
            self.menu_label.bind(
                "<Enter>", lambda _e: self.menu_label.configure(fg=Palette.ACCENT)
            )
            self.menu_label.bind(
                "<Leave>", lambda _e: self.menu_label.configure(fg=Palette.MUTED)
            )

        self.inner.configure(cursor="hand2")
        self.title_label.configure(cursor="hand2")
        self.inner.bind("<Button-1>", self._row_click)
        self.title_label.bind("<Button-1>", self._row_click)
        if self.meta_label is not None:
            self.meta_label.configure(cursor="hand2")
            self.meta_label.bind("<Button-1>", self._row_click)
        if wrap:
            self.title_label.configure(wraplength=wrap)
        else:
            self.inner.bind("<Configure>", self._on_resize)
        self._apply_style()

    def _on_resize(self, event: tk.Event) -> None:
        width = event.width - 96 - (46 if self.meta_label is not None else 0)
        self.title_label.configure(wraplength=max(160, width))

    def _row_click(self, _event: tk.Event | None = None) -> str:
        self._toggle()
        return "break"

    def _toggle(self, checked: bool | None = None) -> None:
        self._done = bool(checked) if checked is not None else not self._done
        self.check.set_checked(self._done)
        self._apply_style()
        if self._on_toggle:
            self._on_toggle(self._done)

    def set_done(self, done: bool) -> None:
        self._done = bool(done)
        self.check.set_checked(self._done)
        self._apply_style()

    def _apply_style(self) -> None:
        bg = Palette.GREEN_SOFT if self._done else self._bg
        self.inner.configure(bg=bg)
        self.title_label.configure(
            bg=bg, fg=Palette.MUTED if self._done else Palette.INK
        )
        if self.meta_label is not None:
            self.meta_label.configure(
                bg=bg, fg=Palette.GREEN_DARK if self._done else Palette.FAINT
            )
        if self.menu_label is not None:
            self.menu_label.configure(bg=bg)
        self.check.set_bg(bg)
        self.configure(bg=Palette.GREEN if self._done else Palette.BORDER)

    def flash(self) -> None:
        if self._flash_job:
            try:
                self.after_cancel(self._flash_job)
            except tk.TclError:
                pass
        self.configure(bg=Palette.ACCENT)
        self._flash_job = self.after(1600, self._end_flash)

    def _end_flash(self) -> None:
        self._flash_job = None
        self._apply_style()


class ProgressBar(tk.Canvas):
    def __init__(self, master: tk.Misc, *, height: int = 6,
                 track: str = Palette.BORDER, fill: str = Palette.ACCENT,
                 bg: str = Palette.CARD, **kwargs: Any):
        super().__init__(master, height=height, bg=bg, highlightthickness=0,
                         bd=0, **kwargs)
        self._height = height
        self._track = track
        self._fill = fill
        self._done = 0
        self._total = 0
        self.bind("<Configure>", lambda _e: self._draw())
        self.bind("<Map>", lambda _e: self._draw())

    def set(self, done: int, total: int, fill: str | None = None) -> None:
        self._done = max(0, done)
        self._total = max(0, total)
        if fill:
            self._fill = fill
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        if width <= 2:
            return
        h = self._height
        y = h / 2
        self.create_line(2, y, width - 2, y, width=h, capstyle="round",
                         fill=self._track)
        if self._total > 0 and self._done > 0:
            ratio = min(1.0, self._done / self._total)
            end = 2 + (width - 4) * ratio
            if end > 3:
                self.create_line(2, y, end, y, width=h, capstyle="round",
                                 fill=self._fill)


class Avatar(tk.Canvas):
    """圆形角色头像，用姓名首字和稳定配色。"""

    PALETTES = [
        ("#DDE8DF", "#3F6853"),
        ("#F1E1D6", "#A65332"),
        ("#EEE5CF", "#8A6A2E"),
        ("#DDE4EA", "#456275"),
        ("#E8DFE8", "#6D526E"),
        ("#E5E2D6", "#5E5A46"),
    ]

    def __init__(self, master: tk.Misc, initial: str, *, bg: str = Palette.CARD,
                 size: int = 46, **kwargs: Any):
        super().__init__(master, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0, **kwargs)
        self.size = size
        self._bg = bg
        self.set_initial(initial)

    def set_initial(self, initial: str) -> None:
        self.delete("all")
        s = self.size
        idx = sum(ord(ch) for ch in (initial or "角")) % len(self.PALETTES)
        fill, fg = self.PALETTES[idx]
        self.create_oval(1, 1, s - 1, s - 1, fill=fill, outline="")
        self.create_text(s / 2, s / 2 + 1, text=(initial or "角")[:1],
                         fill=fg, font=("Microsoft YaHei UI", max(11, s // 3), "bold"))


class Pill(tk.Label):
    def __init__(self, master: tk.Misc, text: str, *, bg: str = Palette.ACCENT_SOFT,
                 fg: str = Palette.ACCENT_DARK, font: Any = None, padx: int = 9,
                 pady: int = 3, **kwargs: Any):
        super().__init__(master, text=text, bg=bg, fg=fg,
                         font=font or "AppTiny", padx=padx, pady=pady, **kwargs)


# ---------------------------------------------------------------------------
# 文本编辑
# ---------------------------------------------------------------------------

class TextEditor(tk.Frame):
    """带边框、占位提示、撤销与右键菜单的多行文本编辑器。"""

    def __init__(self, master: tk.Misc, *, height: int = 3, placeholder: str = "",
                 on_change: Callable[[], None] | None = None,
                 bg: str = Palette.CARD, font: Any = None,
                 padx: int = 10, pady: int = 8, **kwargs: Any):
        super().__init__(master, bg=Palette.BORDER, highlightthickness=0, bd=0, **kwargs)
        self._on_change = on_change
        self._bg = bg
        self._placeholder = placeholder
        self._after_id: str | None = None
        self._suppress = False
        self._placeholder_visible = False

        self.text = tk.Text(
            self, height=height, wrap="word", undo=True, maxundo=200,
            font=font or "AppBody", bg=bg, fg=Palette.INK,
            insertbackground=Palette.INK, selectbackground=Palette.ACCENT_SOFT,
            selectforeground=Palette.INK, relief="flat", bd=0,
            highlightthickness=0, padx=padx, pady=pady,
            spacing1=1, spacing3=2, tabs="1c",
        )
        self.text.pack(fill="both", expand=True, padx=1, pady=1)
        self.text.bind("<FocusIn>", self._on_focus_in)
        self.text.bind("<FocusOut>", self._on_focus_out)
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<Control-a>", self._select_all)
        self.text.bind("<Button-3>", self._show_context_menu)
        self.text.bind("<Configure>", self._on_configure)
        self.bind("<Destroy>", self._on_destroy)
        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="撤销", command=self._undo)
        self._menu.add_command(label="重做", command=self._redo)
        self._menu.add_separator()
        self._menu.add_command(label="剪切", command=lambda: self.text.event_generate("<<Cut>>"))
        self._menu.add_command(label="复制", command=lambda: self.text.event_generate("<<Copy>>"))
        self._menu.add_command(label="粘贴", command=lambda: self.text.event_generate("<<Paste>>"))
        self._menu.add_separator()
        self._menu.add_command(label="全选", command=self._select_all)

        self._placeholder_label = tk.Label(
            self, text=placeholder, bg=bg, fg=Palette.FAINT, font=font or "AppBody",
            anchor="nw", justify="left", cursor="xterm",
        )
        self._placeholder_label.bind("<Button-1>", lambda _e: self.text.focus_set())
        self._update_placeholder()

    def _select_all(self, _event: tk.Event | None = None) -> str:
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "1.0")
        return "break"

    def _undo(self) -> None:
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass

    def _redo(self) -> None:
        try:
            self.text.edit_redo()
        except tk.TclError:
            pass

    def _show_context_menu(self, event: tk.Event) -> None:
        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def _on_configure(self, _event: tk.Event) -> None:
        if self._placeholder_visible:
            self._place_placeholder()

    def _on_focus_in(self, _event: tk.Event) -> None:
        self.configure(bg=Palette.ACCENT)
        self._update_placeholder()

    def _on_focus_out(self, _event: tk.Event) -> None:
        self.configure(bg=Palette.BORDER)
        self._update_placeholder()
        # 失焦时立即提交，避免切换视图或关闭窗口时丢掉最后几个字。
        self.flush()

    def _place_placeholder(self) -> None:
        self._placeholder_label.configure(
            wraplength=max(80, self.text.winfo_width() - 22)
        )
        self._placeholder_label.place(x=11, y=9, relwidth=1.0, width=-22)
        self._placeholder_label.lift()
        self._placeholder_visible = True

    def _update_placeholder(self) -> None:
        empty = not self.text.get("1.0", "end-1c").strip()
        focused = self.focus_get() is self.text
        if empty and not focused and self._placeholder:
            self._place_placeholder()
        else:
            self._placeholder_label.place_forget()
            self._placeholder_visible = False

    def _on_modified(self, _event: tk.Event) -> None:
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self._suppress:
            return
        self._update_placeholder()
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self._after_id = self.after(280, self._fire_change)

    def _fire_change(self) -> None:
        self._after_id = None
        if self._on_change:
            self._on_change()

    def flush(self) -> None:
        """立即把当前文本提交回数据模型。

        即使 <<Modified>> 还没来得及被事件循环处理，也以文本框当前内容为准。
        """
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._on_change:
            self._on_change()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def get(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set(self, value: str) -> None:
        self._suppress = True
        self.text.delete("1.0", "end")
        if value:
            self.text.insert("1.0", value)
        self.text.edit_modified(False)
        self.text.edit_reset()
        self._suppress = False
        self._update_placeholder()

    def focus_editor(self) -> None:
        self.text.focus_set()

    def set_readonly(self, readonly: bool) -> None:
        self.text.configure(state="disabled" if readonly else "normal")


class BigTextDialog(tk.Toplevel):
    """放大编辑一段文字。"""

    def __init__(self, parent: tk.Misc, theme: Theme, title: str, value: str,
                 hint: str = "", on_save: Callable[[str], None] | None = None):
        super().__init__(parent)
        self.theme = theme
        self.on_save = on_save
        self.result: str | None = None
        self.title("编辑 · " + title)
        self.configure(bg=Palette.SURFACE)
        self.transient(parent)
        self.resizable(True, True)
        self.geometry("760x620")
        self.minsize(560, 420)
        self._build(title, value, hint)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Control-Return>", lambda _e: self._save())
        self.after(10, self._center)

    def _build(self, title: str, value: str, hint: str) -> None:
        head = tk.Frame(self, bg=Palette.SURFACE, padx=28, pady=18)
        head.pack(fill="x")
        tk.Label(head, text=title, bg=Palette.SURFACE, fg=Palette.INK,
                 font=self.theme.h2, anchor="w").pack(anchor="w")
        if hint:
            tk.Label(head, text=hint, bg=Palette.SURFACE, fg=Palette.MUTED,
                     font=self.theme.small, anchor="w", justify="left",
                     wraplength=680).pack(anchor="w", pady=(4, 0))
        tk.Frame(self, bg=Palette.BORDER, height=1).pack(fill="x")
        body = tk.Frame(self, bg=Palette.SURFACE, padx=28, pady=18)
        body.pack(fill="both", expand=True)
        self.editor = TextEditor(body, height=18, bg=Palette.CARD,
                                 font=self.theme.body_lg)
        self.editor.pack(fill="both", expand=True)
        self.editor.set(value)
        footer = tk.Frame(self, bg=Palette.SURFACE, padx=28, pady=14)
        footer.pack(fill="x")
        tk.Label(footer, text="Ctrl + Enter 保存 · Esc 取消", bg=Palette.SURFACE,
                 fg=Palette.FAINT, font=self.theme.tiny).pack(side="left")
        FlatButton(footer, "保存", self._save, variant="primary",
                   font=self.theme.body).pack(side="right")
        FlatButton(footer, "取消", self._cancel, variant="ghost",
                   font=self.theme.body).pack(side="right", padx=(0, 8))
        self.after(80, self.editor.focus_editor)

    def _center(self) -> None:
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _save(self) -> None:
        self.result = self.editor.get()
        if self.on_save:
            self.on_save(self.result)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def show(self) -> str | None:
        self.update_idletasks()
        self.deiconify()
        self.wait_visibility()
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window()
        return self.result


# ---------------------------------------------------------------------------
# 通用对话框
# ---------------------------------------------------------------------------

class Modal(tk.Toplevel):
    def __init__(self, parent: tk.Misc, theme: Theme, title: str,
                 width: int = 460, height: int = 260, resizable: bool = False):
        super().__init__(parent)
        self.parent = parent
        self.theme = theme
        self.result: Any = None
        self.title(title)
        self.configure(bg=Palette.SURFACE)
        self.transient(parent)
        self.resizable(resizable, resizable)
        self.geometry(f"{width}x{height}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _e: self._on_close())
        self.body = tk.Frame(self, bg=Palette.SURFACE, padx=26, pady=22)
        self.body.pack(fill="both", expand=True)
        self.after(10, self._center)

    def _center(self) -> None:
        self.update_idletasks()
        parent = self.parent.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _on_close(self) -> None:
        self.result = None
        self.destroy()

    def show(self) -> Any:
        self.update_idletasks()
        self.deiconify()
        self.wait_visibility()
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window()
        return self.result


class InputDialog(Modal):
    def __init__(self, parent: tk.Misc, theme: Theme, title: str, prompt: str,
                 initial: str = "", ok_text: str = "确定"):
        super().__init__(parent, theme, title, width=480, height=250)
        self.ok_text = ok_text
        tk.Label(self.body, text=prompt, bg=Palette.SURFACE, fg=Palette.INK,
                 font=theme.body_lg, anchor="w", justify="left",
                 wraplength=420).pack(fill="x", pady=(0, 12))
        self.entry = tk.Entry(
            self.body, bg=Palette.CARD, fg=Palette.INK, insertbackground=Palette.INK,
            relief="flat", highlightthickness=1, highlightbackground=Palette.BORDER,
            highlightcolor=Palette.ACCENT, font=theme.body_lg,
        )
        self.entry.pack(fill="x", ipady=9)
        self.entry.insert(0, initial)
        self.entry.select_range(0, "end")
        self.entry.bind("<Return>", lambda _e: self._ok())
        self.entry.focus_set()
        footer = tk.Frame(self.body, bg=Palette.SURFACE)
        footer.pack(fill="x", pady=(20, 0))
        FlatButton(footer, ok_text, self._ok, variant="primary",
                   font=theme.body).pack(side="right")
        FlatButton(footer, "取消", self._on_close, variant="ghost",
                   font=theme.body).pack(side="right", padx=(0, 8))

    def _ok(self) -> None:
        self.result = self.entry.get()
        self.destroy()


class ConfirmDialog(Modal):
    def __init__(self, parent: tk.Misc, theme: Theme, title: str, message: str,
                 confirm_text: str = "确定", danger: bool = False):
        super().__init__(parent, theme, title, width=500, height=280)
        tk.Label(self.body, text=title, bg=Palette.SURFACE, fg=Palette.INK,
                 font=theme.h2, anchor="w", justify="left").pack(fill="x")
        tk.Label(self.body, text=message, bg=Palette.SURFACE, fg=Palette.INK_SOFT,
                 font=theme.body, anchor="w", justify="left",
                 wraplength=440).pack(fill="x", pady=(12, 18))
        footer = tk.Frame(self.body, bg=Palette.SURFACE)
        footer.pack(fill="x", side="bottom")
        FlatButton(footer, confirm_text, self._ok,
                   variant="danger" if danger else "primary",
                   font=theme.body).pack(side="right")
        FlatButton(footer, "取消", self._on_close, variant="ghost",
                   font=theme.body).pack(side="right", padx=(0, 8))

    def _ok(self) -> None:
        self.result = True
        self.destroy()


class InfoDialog(Modal):
    def __init__(self, parent: tk.Misc, theme: Theme, title: str, message: str,
                 width: int = 540, height: int = 320, ok_text: str = "知道了"):
        super().__init__(parent, theme, title, width=width, height=height)
        tk.Label(self.body, text=title, bg=Palette.SURFACE, fg=Palette.INK,
                 font=theme.h2, anchor="w", justify="left").pack(fill="x")
        footer = tk.Frame(self.body, bg=Palette.SURFACE)
        footer.pack(fill="x", side="bottom", pady=(12, 0))
        FlatButton(footer, ok_text, self._on_close, variant="primary",
                   font=theme.body).pack(side="right")
        text_wrap = tk.Frame(self.body, bg=Palette.SURFACE)
        text_wrap.pack(fill="both", expand=True, pady=(12, 0))
        text = tk.Text(
            text_wrap, wrap="word", bg=Palette.SURFACE, fg=Palette.INK_SOFT,
            relief="flat", bd=0, highlightthickness=0, font=theme.body,
            spacing3=5, padx=0, pady=0,
        )
        scroll = ttk.Scrollbar(text_wrap, orient="vertical", command=text.yview,
                               style="App.TScrollbar")
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("1.0", message)
        self._linkify(text)
        text.configure(state="disabled")

    @staticmethod
    def _linkify(text: tk.Text) -> None:
        """正文里的 http(s) 网址变成可点的链接。"""
        pattern = re.compile(r"https?://[^\s，。、；：）)】\]]+")
        for index, match in enumerate(pattern.finditer(text.get("1.0", "end"))):
            url = match.group(0)
            tag = f"url_{index}"
            text.tag_add(tag, f"1.0+{match.start()}c", f"1.0+{match.end()}c")
            text.tag_configure(tag, foreground=Palette.ACCENT, underline=True)
            text.tag_bind(tag, "<Button-1>", lambda _e, u=url: webbrowser.open(u))
            text.tag_bind(tag, "<Enter>",
                          lambda _e, t=text: t.configure(cursor="hand2"))
            text.tag_bind(tag, "<Leave>", lambda _e, t=text: t.configure(cursor=""))


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def popup_menu(parent: tk.Misc, event: tk.Event,
               items: Sequence[tuple[str, Callable[[], None]] | None]) -> None:
    menu = tk.Menu(parent, tearoff=0)
    for item in items:
        if item is None:
            menu.add_separator()
        else:
            label, command = item
            menu.add_command(label=label, command=command)
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def bind_tree(widget: tk.Misc, sequence: str, func: Callable[[tk.Event], Any]) -> None:
    widget.bind(sequence, func, add="+")
    for child in widget.winfo_children():
        bind_tree(child, sequence, func)


def bind_click_tree(widget: tk.Misc, func: Callable[[tk.Event], Any]) -> None:
    bind_tree(widget, "<Button-1>", func)


def bind_hover_tree(widget: tk.Misc, enter: Callable[[tk.Event], Any],
                    leave: Callable[[tk.Event], Any]) -> None:
    bind_tree(widget, "<Enter>", enter)
    bind_tree(widget, "<Leave>", leave)


def clear_children(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        child.destroy()


def divider(parent: tk.Misc, bg: str = Palette.BORDER, pady: int = 0) -> tk.Frame:
    frame = tk.Frame(parent, bg=bg, height=1)
    frame.pack(fill="x", pady=pady)
    return frame


def label(parent: tk.Misc, text: str, *, bg: str = Palette.SURFACE,
          fg: str = Palette.INK, font: Any = None, anchor: str = "w",
          justify: str = "left", **kwargs: Any) -> tk.Label:
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=font or "AppBody",
                    anchor=anchor, justify=justify, **kwargs)


def stat_text(done: int, total: int) -> str:
    if total <= 0:
        return "未设置条目"
    return f"已完成 {done} / {total}"
