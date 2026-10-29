# -*- coding: utf-8 -*-
"""
盘古 · 零依赖 PNG 编码器
=======================
PIL 不是标准库，禁止 import。这里用 zlib + struct 手写最小 PNG。

结构：签名(8) + IHDR + IDAT + IEND，每段 = 长度(4) + 类型(4) + 数据 + CRC32(4)。
颜色类型固定 2（RGB，位深 8），每行前置 filter 0。

供 ca 子命令（快照图）与将来的图表复用。
"""

from __future__ import annotations

import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def encode_png(width: int, height: int, rows) -> bytes:
    """
    编码为 PNG 字节串。

    rows: 可迭代，每项是长度 = width*3 的 bytes-like（RGB 扫描行）。
    """
    if width <= 0 or height <= 0:
        raise ValueError("宽高必须为正")
    raw = bytearray()
    n = 0
    for row in rows:
        if len(row) != width * 3:
            raise ValueError(f"第 {n} 行长度 {len(row)} ≠ {width * 3}")
        raw.append(0)          # filter type 0（None）
        raw += row
        n += 1
    if n != height:
        raise ValueError(f"行数 {n} ≠ 高度 {height}")

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (PNG_SIGNATURE
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def write_png(path: str, width: int, height: int, rows) -> int:
    data = encode_png(width, height, rows)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def write_rgb(path: str, width: int, height: int, pixels) -> int:
    """pixels: 扁平 bytes/bytearray，长度必须是 width*height*3（行优先）。"""
    stride = width * 3
    if len(pixels) != stride * height:
        raise ValueError(f"像素长度 {len(pixels)} ≠ {width}×{height}×3")
    return write_png(path, width, height,
                     (pixels[y * stride:(y + 1) * stride] for y in range(height)))


def hex_to_rgb(color, default=(128, 128, 128)):
    """'#RRGGBB' / '#RGB' / (r,g,b) -> (r,g,b)。失败返回 default。"""
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        try:
            return tuple(max(0, min(255, int(c))) for c in color[:3])
        except (TypeError, ValueError):
            return default
    s = str(color or "").strip().lstrip("#")
    try:
        if len(s) == 3:
            return tuple(int(c * 2, 16) for c in s)  # type: ignore[return-value]
        if len(s) >= 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        pass
    return default
