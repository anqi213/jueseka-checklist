# -*- coding: utf-8 -*-
"""数据模型、持久化与导出。

程序把数据保存在用户目录（默认 %APPDATA%\\角色卡创作清单），
采用 JSON + 原子写入，并在启动时自动保留备份。
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

APP_NAME = "角色卡创作清单"
LEGACY_APP_NAMES = ("人物生境清单",)
SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# 默认结构
# ---------------------------------------------------------------------------

DEFAULT_WORLD = [
    {
        "title": "舞台",
        "hint": "故事发生在哪里？地理、空间、势力与日常环境。",
    },
    {
        "title": "时代",
        "hint": "什么时期？技术、制度、文化与人物的共同背景。",
    },
    {
        "title": "玩法",
        "hint": "故事如何运转？类型、冲突机制、叙事规则与边界。",
    },
]

DEFAULT_CHARACTER_SECTIONS = [
    {
        "title": "基础信息",
        "tutorial": "basic",
        "hint": "先固定人物是谁：身体、身份与长期社会坐标。追求确定性，不急着解释性格。",
        "children": [
            {
                "title": "生理与外貌",
                "hint": "稳定、可被反复识别的身体事实。",
                "fields": [
                    ("名字", "本名、常用称呼、别名；先写清别人怎么叫她。"),
                    ("性别", "生理性别、社会性别或作品中的性别设定。"),
                    ("年龄", "具体年龄或明确人生阶段；长篇故事可写不易过期的范围。"),
                    ("体型", "身高、骨架、体态、力量感等稳定身体事实。"),
                    ("面部", "脸型、五官结构、肤色、最易识别的神态基础。"),
                    ("头发", "发色、长度、发型、日常打理方式。"),
                    ("眼睛", "瞳色、眼型、视线习惯；特殊瞳色需与世界规则相容。"),
                    ("着装打扮", "长期衣着倾向、随身物件；不要把单张参考图当成永久造型。"),
                    ("标志性特征", "疤痕、义肢、纹身、特殊配饰等跨场景识别锚点。"),
                ],
            },
            {
                "title": "自然属性",
                "hint": "人物在社会与世界中的长期坐标。",
                "fields": [
                    ("身份", "稳定职业、社会角色、组织归属；避免写会随剧情立刻过期的头衔。"),
                    ("活动范围与生活地点", "长期生活区域、反复出入的场所、行动边界。"),
                    ("角色关系", "只写不会随一轮剧情失效的关系历史与长期影响。"),
                    ("天赋与才能", "她真正能做到什么，以及明确限制。"),
                    ("热衷的事物", "长期投入、愿意主动花时间的事，不只列爱好名称。"),
                    ("讨厌的事物", "会持续影响选择与反应的排斥、底线。"),
                    ("重大事件", "已经发生且不会被推翻的经历；不写当前阶段状态。"),
                ],
            },
        ],
    },
]

# 1.2.0 起不再提供这四个栏目：读取旧数据时直接移除，不留空壳。
REMOVED_SECTION_TITLES = ("生活结构", "角色性情", "场景表达", "穿衣风格")
REMOVED_SECTION_TUTORIALS = ("life", "personality", "scene")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str = "n") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "是"}
    return False


def _field(title: str, hint: str = "", content: str = "") -> dict[str, Any]:
    return {
        "id": new_id("f"),
        "title": title,
        "hint": hint,
        "content": content,
        "done": False,
    }


def _group(title: str, hint: str = "", fields: Iterable[tuple[str, str]] | None = None) -> dict[str, Any]:
    return {
        "id": new_id("g"),
        "title": title,
        "hint": hint,
        "fields": [_field(t, h) for t, h in (fields or [])],
    }


def _section(title: str, tutorial: str | None, hint: str = "",
             fields: Iterable[tuple[str, str]] | None = None,
             children: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": new_id("s"),
        "title": title,
        "tutorial": tutorial,
        "hint": hint,
        "fields": [_field(t, h) for t, h in (fields or [])],
    }
    if children is not None:
        data["children"] = list(children)
    return data


def default_world() -> list[dict[str, Any]]:
    return [
        {
            "id": new_id("w"),
            "title": item["title"],
            "hint": item["hint"],
            "content": "",
            "done": False,
        }
        for item in DEFAULT_WORLD
    ]


def default_character_sections() -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for spec in DEFAULT_CHARACTER_SECTIONS:
        children = None
        if "children" in spec:
            children = [
                _group(child["title"], child.get("hint", ""), child.get("fields", []))
                for child in spec["children"]
            ]
        sections.append(
            _section(
                spec["title"],
                spec.get("tutorial"),
                spec.get("hint", ""),
                spec.get("fields", []),
                children,
            )
        )
    return sections


def default_data() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "app": APP_NAME,
        "projects": [],
        "settings": {
            "last_project_id": None,
            "last_character_id": None,
        },
    }


# ---------------------------------------------------------------------------
# 新建对象
# ---------------------------------------------------------------------------

def create_project(name: str) -> dict[str, Any]:
    stamp = now_iso()
    return {
        "id": new_id("p"),
        "name": name.strip() or "未命名项目",
        "created_at": stamp,
        "updated_at": stamp,
        "world": default_world(),
        "characters": [],
    }


def create_character(name: str = "未命名角色") -> dict[str, Any]:
    stamp = now_iso()
    clean = name.strip() or "未命名角色"
    character = {
        "id": new_id("c"),
        "name": clean,
        "created_at": stamp,
        "updated_at": stamp,
        "sections": default_character_sections(),
    }
    # 让角色名和基础信息里的“名字”保持同一个起点。
    name_field = find_name_field(character)
    if name_field is not None:
        name_field["content"] = clean
        character["name_field_id"] = name_field.get("id")
    return character


def duplicate_character(character: dict[str, Any], name: str | None = None) -> dict[str, Any]:
    clone = json.loads(json.dumps(character, ensure_ascii=False))
    clone["id"] = new_id("c")
    stamp = now_iso()
    clone["created_at"] = stamp
    clone["updated_at"] = stamp
    clone["name"] = (name or display_character_name(character) + " 副本").strip()

    old_name_id = _text(character.get("name_field_id"))
    if not old_name_id:
        source_name_field = find_name_field(character)
        old_name_id = source_name_field.get("id") if source_name_field else ""
    new_name_field: dict[str, Any] | None = None

    for section in clone.get("sections", []):
        section["id"] = new_id("s")
        for group in section.get("children", []):
            group["id"] = new_id("g")
            for field in group.get("fields", []):
                old_id = field.get("id")
                field["id"] = new_id("f")
                if old_id and old_id == old_name_id:
                    new_name_field = field
        for field in section.get("fields", []):
            old_id = field.get("id")
            field["id"] = new_id("f")
            if old_id and old_id == old_name_id:
                new_name_field = field

    if new_name_field is None:
        clone["name_field_id"] = None
        new_name_field = _find_name_field_by_structure(clone)
    if new_name_field is not None:
        new_name_field["content"] = clone["name"]
        clone["name_field_id"] = new_name_field.get("id")
    else:
        clone["name_field_id"] = None
    return clone


# ---------------------------------------------------------------------------
# 规范化 / 兼容旧数据
# ---------------------------------------------------------------------------

def _normalize_field(raw: Any, fallback_title: str = "未命名条目") -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    field = dict(src)
    field["id"] = _text(field.get("id")) or new_id("f")
    field["title"] = _text(field.get("title")).strip() or fallback_title
    field["hint"] = _text(field.get("hint"))
    field["content"] = _text(field.get("content"))
    field["done"] = _bool(field.get("done", False))
    return field


def _normalize_group(raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    group = dict(src)
    group["id"] = _text(group.get("id")) or new_id("g")
    group["title"] = _text(group.get("title")).strip() or "未命名分组"
    group["hint"] = _text(group.get("hint"))
    fields = group.get("fields")
    group["fields"] = [
        _normalize_field(f) for f in (fields if isinstance(fields, list) else [])
    ]
    return group


def _normalize_section(raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    section = dict(src)
    section["id"] = _text(section.get("id")) or new_id("s")
    section["title"] = _text(section.get("title")).strip() or "未命名条目"
    section["hint"] = _text(section.get("hint"))
    tutorial = section.get("tutorial")
    section["tutorial"] = _text(tutorial) if tutorial else None
    fields = section.get("fields")
    section["fields"] = [
        _normalize_field(f) for f in (fields if isinstance(fields, list) else [])
    ]
    if "children" in section:
        children = section.get("children")
        section["children"] = [
            _normalize_group(g) for g in (children if isinstance(children, list) else [])
        ]
    return section


def is_removed_section(section: dict[str, Any]) -> bool:
    """生活结构 / 角色性情 / 场景表达 / 穿衣风格 已不再提供。"""
    return (section.get("title") in REMOVED_SECTION_TITLES
            or section.get("tutorial") in REMOVED_SECTION_TUTORIALS)


def drop_removed_sections(character: dict[str, Any]) -> int:
    """从角色里移除已下线的条目，返回移除数量。"""
    sections = character.get("sections", [])
    kept = [section for section in sections if not is_removed_section(section)]
    removed = len(sections) - len(kept)
    if removed:
        character["sections"] = kept
    return removed


def _normalize_world_item(raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    item = dict(src)
    item["id"] = _text(item.get("id")) or new_id("w")
    item["title"] = _text(item.get("title")).strip() or "未命名条目"
    item["hint"] = _text(item.get("hint"))
    item["content"] = _text(item.get("content"))
    item["done"] = _bool(item.get("done", False))
    return item


def _normalize_character(raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    character = dict(src)
    character["id"] = _text(character.get("id")) or new_id("c")
    character["name"] = _text(character.get("name")).strip() or "未命名角色"
    character["created_at"] = _text(character.get("created_at")) or now_iso()
    character["updated_at"] = _text(character.get("updated_at")) or character["created_at"]
    sections = character.get("sections")
    character["sections"] = [
        _normalize_section(s) for s in (sections if isinstance(sections, list) else [])
    ]
    drop_removed_sections(character)
    name_id = _text(character.get("name_field_id"))
    if name_id and find_field(character, field_id=name_id):
        character["name_field_id"] = name_id
    else:
        field = _find_name_field_by_structure(character)
        character["name_field_id"] = field.get("id") if field else None
    return character


def _normalize_project(raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    project = dict(src)
    project["id"] = _text(project.get("id")) or new_id("p")
    project["name"] = _text(project.get("name")).strip() or "未命名项目"
    project["created_at"] = _text(project.get("created_at")) or now_iso()
    project["updated_at"] = _text(project.get("updated_at")) or project["created_at"]
    world = project.get("world")
    project["world"] = [
        _normalize_world_item(w) for w in (world if isinstance(world, list) else [])
    ]
    characters = project.get("characters")
    project["characters"] = [
        _normalize_character(c) for c in (characters if isinstance(characters, list) else [])
    ]
    return project


def normalize_data(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("数据根节点不是对象")
    version = raw.get("schema_version", 0)
    try:
        version = int(version)
    except (TypeError, ValueError):
        version = 0
    if version > SCHEMA_VERSION:
        raise ValueError(f"数据版本 {version} 高于当前程序支持的 {SCHEMA_VERSION}")

    data = default_data()
    data.update(raw)
    data["schema_version"] = SCHEMA_VERSION
    data["app"] = APP_NAME
    projects = data.get("projects")
    data["projects"] = [
        _normalize_project(p) for p in (projects if isinstance(projects, list) else [])
    ]
    settings = data.get("settings")
    if not isinstance(settings, dict):
        settings = {}
    settings.setdefault("last_project_id", None)
    settings.setdefault("last_character_id", None)
    data["settings"] = settings
    return data


# ---------------------------------------------------------------------------
# 查找 / 统计
# ---------------------------------------------------------------------------

def find_project(data: dict[str, Any], project_id: str | None) -> dict[str, Any] | None:
    if not project_id:
        return None
    for project in data.get("projects", []):
        if project.get("id") == project_id:
            return project
    return None


def find_character(project: dict[str, Any], character_id: str | None) -> dict[str, Any] | None:
    if not character_id:
        return None
    for character in project.get("characters", []):
        if character.get("id") == character_id:
            return character
    return None


def find_section(character: dict[str, Any], section_id: str | None) -> dict[str, Any] | None:
    if not section_id:
        return None
    for section in character.get("sections", []):
        if section.get("id") == section_id:
            return section
    return None


def find_field(character: dict[str, Any], field_id: str | None = None,
               title: str | None = None, section_title: str | None = None) -> dict[str, Any] | None:
    for section in character.get("sections", []):
        if section_title and section.get("title") != section_title:
            continue
        for field in section.get("fields", []):
            if (field_id and field.get("id") == field_id) or (title and field.get("title") == title):
                return field
        for group in section.get("children", []):
            for field in group.get("fields", []):
                if (field_id and field.get("id") == field_id) or (title and field.get("title") == title):
                    return field
    return None


def _find_name_field_by_structure(character: dict[str, Any]) -> dict[str, Any] | None:
    """先找基础信息里的“名字”，再退回到任意同名条目。"""
    for section in character.get("sections", []):
        if section.get("tutorial") != "basic" and section.get("title") != "基础信息":
            continue
        for field in section.get("fields", []):
            if field.get("title") == "名字":
                return field
        for group in section.get("children", []):
            for field in group.get("fields", []):
                if field.get("title") == "名字":
                    return field
    return find_field(character, title="名字")


def find_name_field(character: dict[str, Any]) -> dict[str, Any] | None:
    """找到“名字”字段；字段被重命名后仍通过 name_field_id 保持关联。"""
    name_id = _text(character.get("name_field_id"))
    if name_id:
        field = find_field(character, field_id=name_id)
        if field is not None:
            return field
    return _find_name_field_by_structure(character)


def section_fields(section: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = list(section.get("fields", []))
    for group in section.get("children", []):
        fields.extend(group.get("fields", []))
    return fields


def section_progress(section: dict[str, Any]) -> tuple[int, int, int]:
    """返回 (已完成, 已填写, 总数)。"""
    fields = section_fields(section)
    done = sum(1 for f in fields if f.get("done"))
    filled = sum(1 for f in fields if _text(f.get("content")).strip())
    return done, filled, len(fields)


def character_progress(character: dict[str, Any]) -> tuple[int, int, int]:
    done = filled = total = 0
    for section in character.get("sections", []):
        d, f, t = section_progress(section)
        done += d
        filled += f
        total += t
    return done, filled, total


def project_progress(project: dict[str, Any]) -> tuple[int, int, int]:
    done = filled = total = 0
    for item in project.get("world", []):
        total += 1
        if item.get("done"):
            done += 1
        if _text(item.get("content")).strip():
            filled += 1
    for character in project.get("characters", []):
        d, f, t = character_progress(character)
        done += d
        filled += f
        total += t
    return done, filled, total


def project_section_counts(project: dict[str, Any]) -> dict[str, int]:
    return {
        "characters": len(project.get("characters", [])),
        "world": len(project.get("world", [])),
    }


def display_character_name(character: dict[str, Any]) -> str:
    field = find_name_field(character)
    if field:
        value = _text(field.get("content")).strip().splitlines()
        if value and value[0].strip():
            return value[0].strip()
    return _text(character.get("name")).strip() or "未命名角色"


def display_character_initial(character: dict[str, Any]) -> str:
    name = display_character_name(character)
    return name[0] if name else "角"


def character_section_summary(character: dict[str, Any]) -> list[tuple[str, int, int]]:
    result = []
    for section in character.get("sections", []):
        done, _filled, total = section_progress(section)
        result.append((section.get("title", "未命名条目"), done, total))
    return result


def collect_todos(project: dict[str, Any]) -> list[dict[str, Any]]:
    """汇总项目内所有未勾选条目，供“待完成”页使用。"""
    todos: list[dict[str, Any]] = []
    for item in project.get("world", []):
        if not item.get("done"):
            todos.append({
                "kind": "world",
                "project_id": project.get("id"),
                "title": item.get("title", "未命名条目"),
                "path": "世界观",
                "content": _text(item.get("content")),
                "character_id": None,
                "section_id": None,
                "field_id": item.get("id"),
            })
    for character in project.get("characters", []):
        char_name = display_character_name(character)
        for section in character.get("sections", []):
            for field in section.get("fields", []):
                if not field.get("done"):
                    todos.append({
                        "kind": "character",
                        "project_id": project.get("id"),
                        "title": field.get("title", "未命名条目"),
                        "path": f"{char_name} · {section.get('title', '')}",
                        "content": _text(field.get("content")),
                        "character_id": character.get("id"),
                        "section_id": section.get("id"),
                        "field_id": field.get("id"),
                    })
            for group in section.get("children", []):
                for field in group.get("fields", []):
                    if not field.get("done"):
                        todos.append({
                            "kind": "character",
                            "project_id": project.get("id"),
                            "title": field.get("title", "未命名条目"),
                            "path": f"{char_name} · {section.get('title', '')} / {group.get('title', '')}",
                            "content": _text(field.get("content")),
                            "character_id": character.get("id"),
                            "section_id": section.get("id"),
                            "field_id": field.get("id"),
                        })
    return todos


# ---------------------------------------------------------------------------
# 结构编辑辅助
# ---------------------------------------------------------------------------

def merge_world_defaults(project: dict[str, Any]) -> int:
    existing_titles = {_text(item.get("title")) for item in project.get("world", [])}
    existing_hints = {_text(item.get("hint")) for item in project.get("world", [])}
    added = 0
    for spec in DEFAULT_WORLD:
        # 如果用户只改了名称，hint 仍能识别出这是同一个默认条目。
        if spec["title"] in existing_titles or spec["hint"] in existing_hints:
            continue
        project.setdefault("world", []).append({
            "id": new_id("w"),
            "title": spec["title"],
            "hint": spec["hint"],
            "content": "",
            "done": False,
        })
        added += 1
    return added


def _merge_fields(target: dict[str, Any], specs: Iterable[tuple[str, str]]) -> int:
    existing_titles = {_text(f.get("title")) for f in target.get("fields", [])}
    existing_hints = {_text(f.get("hint")) for f in target.get("fields", [])}
    added = 0
    for title, hint in specs:
        if title in existing_titles or hint in existing_hints:
            continue
        target.setdefault("fields", []).append(_field(title, hint))
        added += 1
    return added


def merge_character_defaults(character: dict[str, Any]) -> int:
    """补齐缺失的默认条目，不覆盖已有内容，也不删除自定义条目。"""
    added = 0
    sections = character.setdefault("sections", [])
    by_title = {_text(s.get("title")): s for s in sections}
    by_tutorial = {
        s.get("tutorial"): s for s in sections if s.get("tutorial")
    }
    for index, spec in enumerate(DEFAULT_CHARACTER_SECTIONS):
        title = spec["title"]
        tutorial = spec.get("tutorial")
        section = by_tutorial.get(tutorial) if tutorial else None
        if section is None:
            section = by_title.get(title)
        if section is None:
            children = None
            if "children" in spec:
                children = [
                    _group(child["title"], child.get("hint", ""), child.get("fields", []))
                    for child in spec["children"]
                ]
            section = _section(
                title, tutorial, spec.get("hint", ""),
                spec.get("fields", []), children,
            )
            insert_at = min(index, len(sections))
            sections.insert(insert_at, section)
            by_title[title] = section
            if tutorial:
                by_tutorial[tutorial] = section
            added += 1
            continue
        if spec.get("tutorial") and not section.get("tutorial"):
            section["tutorial"] = spec["tutorial"]
        if "children" in spec:
            children = section.setdefault("children", [])
            group_by_title = {_text(g.get("title")): g for g in children}
            group_by_hint = {_text(g.get("hint")): g for g in children}
            for child_spec in spec["children"]:
                child_title = child_spec["title"]
                child_hint = child_spec.get("hint", "")
                group = group_by_title.get(child_title) or group_by_hint.get(child_hint)
                if group is None:
                    group = _group(child_title, child_hint, child_spec.get("fields", []))
                    children.append(group)
                    group_by_title[child_title] = group
                    if child_hint:
                        group_by_hint[child_hint] = group
                    added += 1
                else:
                    added += _merge_fields(group, child_spec.get("fields", []))
        added += _merge_fields(section, spec.get("fields", []))
    return added


def move_in_list(items: list[Any], item: Any, delta: int) -> bool:
    index = next((i for i, obj in enumerate(items) if obj is item), -1)
    if index < 0:
        return False
    new_index = max(0, min(len(items) - 1, index + delta))
    if new_index == index:
        return False
    items.pop(index)
    items.insert(new_index, item)
    return True


def remove_from_list(items: list[Any], item: Any) -> bool:
    index = next((i for i, obj in enumerate(items) if obj is item), -1)
    if index < 0:
        return False
    items.pop(index)
    return True


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def _checklist_lines(lines: list[str], items: Iterable[dict[str, Any]],
                     indent: int = 0) -> None:
    pad = "  " * indent
    for item in items:
        mark = "x" if item.get("done") else " "
        title = _text(item.get("title")).strip() or "未命名条目"
        lines.append(f"{pad}- [{mark}] {title}")
        content = _text(item.get("content")).strip()
        for line in content.splitlines():
            lines.append(f"{pad}  > {line}")


def _append_character_sections(lines: list[str], character: dict[str, Any]) -> None:
    for section in character.get("sections", []):
        done, _filled, total = section_progress(section)
        lines.append(f"**{section.get('title', '未命名条目')}**　{done}/{total}")
        lines.append("")
        groups = section.get("children") or []
        if groups:
            for group in groups:
                lines.append(f"*{group.get('title', '未命名分组')}*")
                lines.append("")
                _checklist_lines(lines, group.get("fields", []))
                lines.append("")
        elif section.get("fields"):
            _checklist_lines(lines, section.get("fields", []))
            lines.append("")
        else:
            lines.append("*（尚未设置条目）*")
            lines.append("")


def export_markdown(project: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# {project.get('name', '未命名项目')}")
    lines.append("")
    lines.append(f"> 角色卡创作清单 · 导出于 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    done, _filled, total = project_progress(project)
    lines.append(f"进度：{done} / {total}")
    lines.append("")

    lines.append("## 世界观")
    lines.append("")
    world = project.get("world", [])
    if world:
        _checklist_lines(lines, world)
    else:
        lines.append("*（尚未设置条目）*")
    lines.append("")

    characters = project.get("characters", [])
    lines.append("## 角色")
    lines.append("")
    if not characters:
        lines.append("*（尚未创建角色）*")
        lines.append("")
    for character in characters:
        lines.append(f"### {display_character_name(character)}")
        lines.append("")
        _append_character_sections(lines, character)
    return "\n".join(lines).rstrip() + "\n"


def export_character_markdown(character: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# {display_character_name(character)}")
    lines.append("")
    lines.append(f"> 角色卡创作清单 · 导出于 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    done, _filled, total = character_progress(character)
    lines.append(f"进度：{done} / {total}")
    lines.append("")
    _append_character_sections(lines, character)
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------

def _migrate_legacy_data(target: Path) -> None:
    """首次改名后，把旧目录里的数据复制到新目录，避免用户丢项目。"""
    if (target / "data.json").exists():
        return
    base = target.parent
    for legacy in LEGACY_APP_NAMES:
        old = base / legacy
        old_data = old / "data.json"
        if not old_data.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(old_data, target / "data.json")
        old_backups = old / "backups"
        if old_backups.exists():
            shutil.copytree(old_backups, target / "backups", dirs_exist_ok=True)
        return


def data_dir() -> Path:
    override = os.environ.get("RW_DATA_DIR")
    if override:
        return Path(override).expanduser()
    appdata = os.environ.get("APPDATA")
    target = Path(appdata) / APP_NAME if appdata else (
        Path.home() / "AppData" / "Roaming" / APP_NAME
    )
    try:
        _migrate_legacy_data(target)
    except OSError:
        # 迁移失败不应阻止程序启动；用户仍可手动复制数据。
        pass
    return target


def data_file() -> Path:
    return data_dir() / "data.json"


def backup_dir() -> Path:
    return data_dir() / "backups"


def load_data(path: Path | None = None) -> tuple[dict[str, Any], str | None]:
    """读取数据。损坏时保留坏文件并返回空数据，warning 供界面提示。"""
    target = path or data_file()
    if not target.exists():
        return default_data(), None
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return normalize_data(raw), None
    except Exception as exc:  # noqa: BLE001 - 需要向用户报告任何损坏
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        broken = target.with_name(f"data.broken-{stamp}.json")
        try:
            shutil.copy2(target, broken)
        except OSError:
            broken = None
        warning = f"数据文件无法读取，已使用空白数据启动。\n\n原因：{exc}"
        if broken:
            warning += f"\n\n原文件备份：{broken}"
        return default_data(), warning


def save_data(data: dict[str, Any], path: Path | None = None) -> Path:
    target = path or data_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    temp = target.with_name(f".{target.name}.tmp")
    temp.write_text(payload, encoding="utf-8")
    os.replace(temp, target)
    return target


def backup_now(path: Path | None = None) -> Path | None:
    target = path or data_file()
    if not target.exists():
        return None
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = folder / f"data-{stamp}.json"
    shutil.copy2(target, dest)
    _trim_backups(folder, keep=20)
    return dest


def backup_if_needed(path: Path | None = None, min_interval_hours: int = 12) -> Path | None:
    target = path or data_file()
    if not target.exists():
        return None
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    backups = sorted(folder.glob("data-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if backups:
        age = datetime.now().timestamp() - backups[0].stat().st_mtime
        if age < min_interval_hours * 3600:
            return None
    return backup_now(target)


def _trim_backups(folder: Path, keep: int = 20) -> None:
    backups = sorted(folder.glob("data-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def read_json_file(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return normalize_data(raw)
