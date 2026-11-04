# -*- coding: utf-8 -*-
"""界面配色、字体与 ttk 样式。"""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk


class Palette:
    BG = "#F2EEE5"
    BG_DEEP = "#E8E1D3"
    SURFACE = "#FBF8F2"
    CARD = "#FFFDF9"
    CARD_ALT = "#F6F1E7"
    BORDER = "#E2D9C9"
    BORDER_STRONG = "#CEC1AC"
    INK = "#25251F"
    INK_SOFT = "#4C4A41"
    MUTED = "#81796B"
    FAINT = "#A9A092"
    ACCENT = "#B45634"
    ACCENT_DARK = "#8E3F25"
    ACCENT_SOFT = "#F4E3D8"
    GREEN = "#3F6853"
    GREEN_DARK = "#2F4F3F"
    GREEN_SOFT = "#E4EDE6"
    GOLD = "#C49A4A"
    GOLD_SOFT = "#F6EBD2"
    SIDEBAR = "#20261F"
    SIDEBAR_ALT = "#2B332A"
    SIDEBAR_ACTIVE = "#354033"
    SIDEBAR_TEXT = "#F1EBDD"
    SIDEBAR_MUTED = "#9DA695"
    DANGER = "#A64B3C"
    DANGER_SOFT = "#F7E6E1"
    WHITE = "#FFFFFF"
    SHADOW = "#D9D0C0"


class Theme:
    def __init__(self, root: tk.Misc):
        self.root = root
        families = set(tkfont.families(root))
        self.ui_family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else "Microsoft YaHei"
        self.display_family = "Noto Serif SC" if "Noto Serif SC" in families else self.ui_family
        self.mono_family = "Cascadia Mono" if "Cascadia Mono" in families else "Consolas"
        self._fonts: dict[tuple, tkfont.Font] = {}
        self._named: dict[str, tkfont.Font] = {}
        self._make_named_fonts()

        root.option_add("*Font", self.body)
        root.option_add("*Menu.font", self.font(10))
        root.option_add("*Menu.background", Palette.SURFACE)
        root.option_add("*Menu.foreground", Palette.INK)
        root.option_add("*Menu.activeBackground", Palette.ACCENT_SOFT)
        root.option_add("*Menu.activeForeground", Palette.ACCENT_DARK)
        root.option_add("*Menu.borderWidth", 0)

        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._configure_styles()

    def _make_named_fonts(self) -> None:
        specs = {
            "AppBody": (10, "normal", "ui"),
            "AppBodyLg": (11, "normal", "ui"),
            "AppSmall": (9, "normal", "ui"),
            "AppTiny": (8, "normal", "ui"),
            "AppLabel": (9, "bold", "ui"),
            "AppDisplay": (25, "bold", "display"),
            "AppH1": (20, "bold", "display"),
            "AppH2": (15, "bold", "display"),
            "AppH3": (12, "bold", "ui"),
            "AppMono": (9, "normal", "mono"),
        }
        for name, (size, weight, family) in specs.items():
            fam = {
                "ui": self.ui_family,
                "display": self.display_family,
                "mono": self.mono_family,
            }[family]
            try:
                self._named[name] = tkfont.Font(
                    root=self.root, name=name, family=fam, size=size,
                    weight=weight,
                )
            except tk.TclError:
                # 同一解释器里已经存在同名命名字体时直接复用。
                self._named[name] = tkfont.Font(root=self.root, name=name)

    def font(self, size: int = 10, weight: str = "normal",
             family: str = "ui", slant: str = "roman") -> tkfont.Font:
        key = (size, weight, family, slant)
        if key not in self._fonts:
            fam = {
                "ui": self.ui_family,
                "display": self.display_family,
                "mono": self.mono_family,
            }.get(family, self.ui_family)
            self._fonts[key] = tkfont.Font(
                root=self.root, family=fam, size=size, weight=weight, slant=slant
            )
        return self._fonts[key]

    @property
    def body(self) -> tkfont.Font:
        return self._named["AppBody"]

    @property
    def body_lg(self) -> tkfont.Font:
        return self._named["AppBodyLg"]

    @property
    def small(self) -> tkfont.Font:
        return self._named["AppSmall"]

    @property
    def tiny(self) -> tkfont.Font:
        return self._named["AppTiny"]

    @property
    def display(self) -> tkfont.Font:
        return self._named["AppDisplay"]

    @property
    def h1(self) -> tkfont.Font:
        return self._named["AppH1"]

    @property
    def h2(self) -> tkfont.Font:
        return self._named["AppH2"]

    @property
    def h3(self) -> tkfont.Font:
        return self._named["AppH3"]

    @property
    def label(self) -> tkfont.Font:
        return self._named["AppLabel"]

    @property
    def mono(self) -> tkfont.Font:
        return self._named["AppMono"]

    def _configure_styles(self) -> None:
        style = self.style
        try:
            base_layout = style.layout("Vertical.TScrollbar")
            style.layout("App.TScrollbar", base_layout)
            style.layout("Sidebar.TScrollbar", base_layout)
        except tk.TclError:
            pass
        style.configure(
            "App.TScrollbar",
            gripcount=0,
            background=Palette.BORDER_STRONG,
            darkcolor=Palette.BORDER_STRONG,
            lightcolor=Palette.BORDER_STRONG,
            troughcolor=Palette.BG,
            bordercolor=Palette.BG,
            arrowcolor=Palette.MUTED,
            relief="flat",
            width=10,
        )
        style.map(
            "App.TScrollbar",
            background=[("active", Palette.MUTED)],
            arrowcolor=[("active", Palette.INK_SOFT)],
        )
        style.configure(
            "Sidebar.TScrollbar",
            gripcount=0,
            background=Palette.SIDEBAR_ACTIVE,
            darkcolor=Palette.SIDEBAR_ACTIVE,
            lightcolor=Palette.SIDEBAR_ACTIVE,
            troughcolor=Palette.SIDEBAR,
            bordercolor=Palette.SIDEBAR,
            arrowcolor=Palette.SIDEBAR_MUTED,
            relief="flat",
            width=8,
        )
        style.map(
            "Sidebar.TScrollbar",
            background=[("active", Palette.SIDEBAR_MUTED)],
        )
        style.configure(
            "App.TEntry",
            fieldbackground=Palette.CARD,
            foreground=Palette.INK,
            bordercolor=Palette.BORDER,
            lightcolor=Palette.BORDER,
            darkcolor=Palette.BORDER,
            insertcolor=Palette.INK,
            padding=(10, 8),
        )
        style.map(
            "App.TEntry",
            bordercolor=[("focus", Palette.ACCENT)],
            lightcolor=[("focus", Palette.ACCENT)],
            darkcolor=[("focus", Palette.ACCENT)],
        )
        style.configure(
            "App.TCombobox",
            fieldbackground=Palette.CARD,
            background=Palette.CARD,
            foreground=Palette.INK,
            bordercolor=Palette.BORDER,
            arrowcolor=Palette.MUTED,
            padding=(8, 6),
        )
