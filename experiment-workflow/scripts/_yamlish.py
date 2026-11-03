"""零依赖 YAML 子集读写。

实验工作流的所有状态文件都使用本模块定义的 YAML 子集，因为目标环境
可能没有 PyYAML，而 skill 不应要求用户 pip install。

支持的写法
----------
- 缩进映射与序列（每层 2 个空格）
- 行内列表 ``[a, b]``
- 标量：字符串、整数、浮点、true/false、null/~、空值
- 注释 ``#``（引号内不算）
- 块字面量 ``|`` 与折叠 ``>``
- 双引号转义 ``\\\\`` ``\\"`` ``\\n`` ``\\t``

不支持的写法：锚点与别名、多文档、流式映射 ``{a: b}``、复杂键、制表符缩进。
遇到不支持的写法一律抛出 :class:`YamlError` 并指出行号，绝不静默猜解。
"""

from __future__ import annotations

import math
import re

__all__ = ["YamlError", "loads", "dumps"]

_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
_SPECIAL_START = set("-?[]{},&*!|>%@`\"'#:")


class YamlError(ValueError):
    """YAML 子集无法解析。"""


def _strip_comment(line: str) -> str:
    out: list[str] = []
    quote: str | None = None
    prev = ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote and prev != "\\":
                quote = None
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (not prev or prev in " \t"):
            break
        else:
            out.append(ch)
        prev = ch
    return "".join(out).rstrip()


def _split_key(text: str, no: int) -> tuple[str, str]:
    quote: str | None = None
    for idx, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == ":" and (idx + 1 == len(text) or text[idx + 1] == " "):
            key = text[:idx].strip()
            if not key:
                raise YamlError(f"第 {no} 行键名为空")
            return _unquote(key), text[idx + 1 :].strip()
    raise YamlError(f"第 {no} 行缺少 ':'（不是合法的映射项）")


def _looks_like_kv(text: str) -> bool:
    if text.startswith("[") or text.startswith("{"):
        return False
    quote: str | None = None
    for idx, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == ":" and (idx + 1 == len(text) or text[idx + 1] == " "):
            return True
    return False


def _unquote(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return _scalar(text, 0)
    return text


def _split_flow(text: str, no: int) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    depth = 0
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    if depth != 0:
        raise YamlError(f"第 {no} 行行内列表括号不匹配")
    return parts


def _scalar(text: str, no: int):
    s = text.strip()
    if s == "":
        return None
    if s == "{}":
        return {}
    if s == "[]":
        return []
    if s[0] == '"':
        if len(s) < 2 or s[-1] != '"':
            raise YamlError(f"第 {no} 行双引号未闭合")
        return _unescape(s[1:-1], no)
    if s[0] == "'":
        if len(s) < 2 or s[-1] != "'":
            raise YamlError(f"第 {no} 行单引号未闭合")
        return s[1:-1].replace("''", "'")
    if s.startswith("["):
        if not s.endswith("]"):
            raise YamlError(f"第 {no} 行行内列表缺少 ']'")
        inner = s[1:-1].strip()
        return [] if not inner else [_scalar(x, no) for x in _split_flow(inner, no)]
    if s.startswith("{"):
        raise YamlError(f"第 {no} 行不支持流式映射 {{}}，请改用缩进写法")
    low = s.lower()
    if low in ("null", "~", "none"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _unescape(s: str, no: int) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(s):
            raise YamlError(f"第 {no} 行转义不完整")
        esc = s[i]
        mapping = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r", "0": "\0"}
        if esc not in mapping:
            raise YamlError(f"第 {no} 行不支持的转义 \\{esc}")
        out.append(mapping[esc])
        i += 1
    return "".join(out)


def _parse_block_scalar(lines, i, parent_indent, style):
    collected = []
    while i < len(lines) and lines[i][0] > parent_indent:
        collected.append(lines[i])
        i += 1
    if not collected:
        return "", i
    base = min(item[0] for item in collected)
    body = [" " * (item[0] - base) + item[1] for item in collected]
    if style == "|":
        return "\n".join(body), i
    return " ".join(part for part in body if part.strip()), i


def _parse_map(lines, i, indent):
    result: dict = {}
    while i < len(lines):
        ind, text, no = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError(f"第 {no} 行缩进过深（期望 {indent} 个空格）")
        if text.startswith("- ") or text == "-":
            break
        key, rest = _split_key(text, no)
        i += 1
        if rest == "":
            if i < len(lines) and lines[i][0] > ind:
                value, i = _parse_block(lines, i, lines[i][0])
            else:
                value = None
        elif rest in ("|", ">"):
            value, i = _parse_block_scalar(lines, i, ind, rest)
        else:
            value = _scalar(rest, no)
        result[key] = value
    return result, i


def _parse_seq(lines, i, indent):
    result: list = []
    while i < len(lines):
        ind, text, no = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise YamlError(f"第 {no} 行缩进过深（期望 {indent} 个空格）")
        if not (text.startswith("- ") or text == "-"):
            break
        body = text[2:].strip() if text.startswith("- ") else ""
        i += 1
        if body == "":
            if i < len(lines) and lines[i][0] > ind:
                value, i = _parse_block(lines, i, lines[i][0])
            else:
                value = None
            result.append(value)
        elif _looks_like_kv(body):
            sub_indent = ind + 2
            sub = [(sub_indent, body, no)]
            while i < len(lines) and lines[i][0] > ind:
                sub.append(lines[i])
                i += 1
            value, j = _parse_map(sub, 0, sub_indent)
            if j != len(sub):
                raise YamlError(f"第 {sub[j][2]} 行无法解析为序列项")
            result.append(value)
        else:
            result.append(_scalar(body, no))
    return result, i


def _parse_block(lines, i, indent):
    text = lines[i][1]
    if text in ("{}", "[]"):
        return ({} if text == "{}" else []), i + 1
    if text.startswith("- ") or text == "-":
        return _parse_seq(lines, i, indent)
    return _parse_map(lines, i, indent)


def loads(text: str):
    """把 YAML 子集文本解析为 Python 对象。空文档返回 None。"""
    if text is None:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines: list[tuple[int, str, int]] = []
    for no, raw in enumerate(text.split("\n"), 1):
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        if "\t" in stripped[: indent + 1]:
            raise YamlError(f"第 {no} 行使用制表符缩进，请改用空格")
        lines.append((indent, stripped.strip(), no))
    if not lines:
        return None
    value, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YamlError(f"第 {lines[i][2]} 行无法解析（缩进或结构异常）")
    return value


def _needs_quote(s: str) -> bool:
    if s == "" or s != s.strip():
        return True
    if s.lower() in ("null", "~", "none", "true", "false", "yes", "no", "on", "off"):
        return True
    if _INT_RE.match(s) or _FLOAT_RE.match(s):
        return True
    if s[0] in _SPECIAL_START:
        return True
    if ": " in s or s.endswith(":") or " #" in s:
        return True
    if any(ch in s for ch in "\n\t"):
        return True
    return False


def _render_scalar(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise YamlError("不支持 NaN/Infinity")
        text = repr(value)
        return text if not _INT_RE.match(text) else text + ".0"
    text = str(value)
    if _needs_quote(text):
        escaped = (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )
        return f'"{escaped}"'
    return text


def _is_scalar(value) -> bool:
    return not isinstance(value, (dict, list, tuple))


def dumps(value, _indent: int = 0) -> str:
    """把 Python 对象序列化为 YAML 子集文本（结尾带换行）。"""
    lines: list[str] = []
    _emit(value, _indent, lines)
    return "\n".join(lines) + "\n"


def _emit(value, indent: int, lines: list[str]) -> None:
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            lines.append(pad + "{}")
            return
        for key, item in value.items():
            rendered_key = _render_scalar(str(key))
            if _is_scalar(item):
                lines.append(f"{pad}{rendered_key}: {_render_scalar(item)}")
            elif isinstance(item, list) and all(_is_scalar(x) for x in item):
                lines.append(f"{pad}{rendered_key}: [{', '.join(_render_scalar(x) for x in item)}]")
            elif isinstance(item, (list, dict)) and not item:
                lines.append(f"{pad}{rendered_key}: {'[]' if isinstance(item, list) else '{}'}")
            else:
                lines.append(f"{pad}{rendered_key}:")
                _emit(item, indent + 2, lines)
    elif isinstance(value, (list, tuple)):
        if not value:
            lines.append(pad + "[]")
            return
        for item in value:
            if _is_scalar(item):
                lines.append(f"{pad}- {_render_scalar(item)}")
            elif isinstance(item, dict) and item:
                sub: list[str] = []
                _emit(item, indent + 2, sub)
                first = sub[0][indent + 2 :]
                lines.append(f"{pad}- {first}")
                lines.extend(sub[1:])
            elif isinstance(item, (list, dict)) and not item:
                lines.append(f"{pad}- {'[]' if isinstance(item, list) else '{}'}")
            else:
                lines.append(f"{pad}-")
                _emit(item, indent + 2, lines)
    else:
        lines.append(pad + _render_scalar(value))
