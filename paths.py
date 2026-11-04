# -*- coding: utf-8 -*-
"""开发环境与 PyInstaller 单文件环境下的资源路径。"""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / relative
    return Path(__file__).resolve().parent / relative


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
