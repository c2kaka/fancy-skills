#!/usr/bin/env python3
"""Validate PNG, JPEG, and WebP evidence without image-library dependencies."""

from __future__ import annotations

import os
import stat
import struct
import zlib
from pathlib import Path
from typing import Any, BinaryIO

from video_common import VideoInsightError, sha256_file


def read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise VideoInsightError("图片文件已截断。")
    return data


def png_info(stream: BinaryIO, size: int) -> tuple[str, int, int]:
    stream.seek(8)
    seen_ihdr = seen_idat = seen_iend = False
    width = height = 0
    while stream.tell() < size:
        length = struct.unpack(">I", read_exact(stream, 4))[0]
        kind = read_exact(stream, 4)
        if length > size - stream.tell() - 4:
            raise VideoInsightError("PNG chunk 长度越界。")
        data = read_exact(stream, length)
        expected_crc = struct.unpack(">I", read_exact(stream, 4))[0]
        actual_crc = zlib.crc32(data, zlib.crc32(kind)) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise VideoInsightError("PNG CRC 校验失败。")
        if kind == b"IHDR":
            if seen_ihdr or length != 13:
                raise VideoInsightError("PNG IHDR 无效。")
            width, height = struct.unpack(">II", data[:8])
            seen_ihdr = True
        elif kind == b"IDAT":
            seen_idat = True
        elif kind == b"IEND":
            if length != 0 or stream.tell() != size:
                raise VideoInsightError("PNG IEND 无效或存在尾随数据。")
            seen_iend = True
            break
    if not (seen_ihdr and seen_idat and seen_iend):
        raise VideoInsightError("PNG 缺少必要 chunk。")
    return "image/png", width, height


def jpeg_info(stream: BinaryIO) -> tuple[str, int, int]:
    stream.seek(2)
    while True:
        marker_start = stream.read(1)
        if not marker_start:
            break
        if marker_start != b"\xff":
            continue
        marker = stream.read(1)
        while marker == b"\xff":
            marker = stream.read(1)
        if not marker:
            break
        marker_value = marker[0]
        if marker_value in {0x01, *range(0xD0, 0xD9)}:
            continue
        length = struct.unpack(">H", read_exact(stream, 2))[0]
        if length < 2:
            raise VideoInsightError("JPEG segment 长度无效。")
        if marker_value in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        }:
            read_exact(stream, 1)
            height, width = struct.unpack(">HH", read_exact(stream, 4))
            return "image/jpeg", width, height
        stream.seek(length - 2, os.SEEK_CUR)
    raise VideoInsightError("JPEG 缺少尺寸信息。")


def webp_info(stream: BinaryIO) -> tuple[str, int, int]:
    stream.seek(12)
    kind = read_exact(stream, 4)
    chunk_size = struct.unpack("<I", read_exact(stream, 4))[0]
    if kind == b"VP8X":
        if chunk_size < 10:
            raise VideoInsightError("WebP VP8X 无效。")
        read_exact(stream, 4)
        return (
            "image/webp",
            int.from_bytes(read_exact(stream, 3), "little") + 1,
            int.from_bytes(read_exact(stream, 3), "little") + 1,
        )
    if kind == b"VP8L":
        if chunk_size < 5 or read_exact(stream, 1) != b"\x2f":
            raise VideoInsightError("WebP VP8L 无效。")
        bits = int.from_bytes(read_exact(stream, 4), "little")
        return "image/webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8 ":
        frame = read_exact(stream, 10)
        if chunk_size < 10 or frame[3:6] != b"\x9d\x01\x2a":
            raise VideoInsightError("WebP VP8 无效。")
        return (
            "image/webp",
            struct.unpack("<H", frame[6:8])[0] & 0x3FFF,
            struct.unpack("<H", frame[8:10])[0] & 0x3FFF,
        )
    raise VideoInsightError("不支持的 WebP 首个 chunk。")


def inspect_image(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise VideoInsightError(f"图片不能是符号链接：{path}")
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_size <= 0:
            raise VideoInsightError(f"图片必须是非空普通文件：{path}")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            header = read_exact(stream, min(12, file_stat.st_size))
            stream.seek(0)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                mime_type, width, height = png_info(stream, file_stat.st_size)
            elif header.startswith(b"\xff\xd8"):
                mime_type, width, height = jpeg_info(stream)
                stream.seek(-2, os.SEEK_END)
                if read_exact(stream, 2) != b"\xff\xd9":
                    raise VideoInsightError("JPEG 缺少 EOI。")
            elif (
                len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
            ):
                declared = struct.unpack("<I", header[4:8])[0] + 8
                if declared != file_stat.st_size:
                    raise VideoInsightError("WebP RIFF size 不匹配。")
                mime_type, width, height = webp_info(stream)
            else:
                raise VideoInsightError(f"图片必须是 PNG、JPEG 或 WebP：{path}")
    except OSError as exc:
        raise VideoInsightError(f"无法读取图片 {path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if width <= 0 or height <= 0:
        raise VideoInsightError(f"图片尺寸无效：{path}")
    return {
        "sha256": sha256_file(path),
        "size": file_stat.st_size,
        "mime_type": mime_type,
        "width": width,
        "height": height,
    }
