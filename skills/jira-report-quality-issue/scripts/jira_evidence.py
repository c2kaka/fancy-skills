#!/usr/bin/env python3
"""Validate screenshot evidence without changing the source files."""

from __future__ import annotations

import hashlib
import os
import stat
import struct
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO


class EvidenceError(ValueError):
    """Raised when screenshot evidence is unsafe or unsupported."""


@dataclass(frozen=True)
class ImageEvidence:
    path: str
    sha256: str
    size: int
    mime_type: str
    width: int
    height: int
    upload_name: str
    description: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise EvidenceError("截图文件已截断或损坏。")
    return data


def _png_dimensions(stream: BinaryIO) -> tuple[int, int]:
    stream.seek(8)
    length = struct.unpack(">I", _read_exact(stream, 4))[0]
    chunk_type = _read_exact(stream, 4)
    if chunk_type != b"IHDR" or length != 13:
        raise EvidenceError("PNG 缺少有效的 IHDR。")
    width, height = struct.unpack(">II", _read_exact(stream, 8))
    return width, height


def _validate_png(stream: BinaryIO, file_size: int) -> None:
    stream.seek(8)
    seen_ihdr = False
    seen_idat = False
    seen_iend = False
    while stream.tell() < file_size:
        length = struct.unpack(">I", _read_exact(stream, 4))[0]
        chunk_type = _read_exact(stream, 4)
        if length > file_size - stream.tell() - 4:
            raise EvidenceError("PNG chunk 长度超出文件边界。")
        chunk_data = _read_exact(stream, length)
        expected_crc = struct.unpack(">I", _read_exact(stream, 4))[0]
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise EvidenceError("PNG chunk CRC 无效。")
        if chunk_type == b"IHDR":
            if seen_ihdr or stream.tell() != 33:
                raise EvidenceError("PNG IHDR 顺序无效。")
            seen_ihdr = True
        elif chunk_type == b"IDAT":
            seen_idat = True
        elif chunk_type == b"IEND":
            if length != 0 or stream.tell() != file_size:
                raise EvidenceError("PNG IEND 无效或文件包含尾随数据。")
            seen_iend = True
            break
    if not (seen_ihdr and seen_idat and seen_iend):
        raise EvidenceError("PNG 缺少 IHDR、IDAT 或 IEND。")


def _jpeg_dimensions(stream: BinaryIO) -> tuple[int, int]:
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
        segment_length = struct.unpack(">H", _read_exact(stream, 2))[0]
        if segment_length < 2:
            raise EvidenceError("JPEG segment 长度无效。")
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
            _read_exact(stream, 1)
            height, width = struct.unpack(">HH", _read_exact(stream, 4))
            return width, height
        stream.seek(segment_length - 2, os.SEEK_CUR)
    raise EvidenceError("JPEG 缺少可识别的尺寸信息。")


def _webp_dimensions(stream: BinaryIO) -> tuple[int, int]:
    stream.seek(12)
    chunk_type = _read_exact(stream, 4)
    chunk_size = struct.unpack("<I", _read_exact(stream, 4))[0]
    if chunk_type == b"VP8X":
        if chunk_size < 10:
            raise EvidenceError("WebP VP8X chunk 无效。")
        _read_exact(stream, 4)
        width = int.from_bytes(_read_exact(stream, 3), "little") + 1
        height = int.from_bytes(_read_exact(stream, 3), "little") + 1
        return width, height
    if chunk_type == b"VP8L":
        if chunk_size < 5 or _read_exact(stream, 1) != b"\x2f":
            raise EvidenceError("WebP VP8L chunk 无效。")
        bits = int.from_bytes(_read_exact(stream, 4), "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height
    if chunk_type == b"VP8 ":
        if chunk_size < 10:
            raise EvidenceError("WebP VP8 chunk 无效。")
        frame_header = _read_exact(stream, 10)
        if frame_header[3:6] != b"\x9d\x01\x2a":
            raise EvidenceError("WebP VP8 frame header 无效。")
        width = struct.unpack("<H", frame_header[6:8])[0] & 0x3FFF
        height = struct.unpack("<H", frame_header[8:10])[0] & 0x3FFF
        return width, height
    raise EvidenceError("WebP 使用了不支持的首个 chunk。")


def inspect_image(path_value: str, upload_name: str, description: str) -> ImageEvidence:
    path = Path(path_value).expanduser()
    if path.is_symlink():
        raise EvidenceError(f"截图不能是符号链接：{path_value}")
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        file_stat = os.fstat(descriptor)
    except OSError as exc:
        raise EvidenceError(f"无法读取截图：{path_value}: {exc}") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        os.close(descriptor)
        raise EvidenceError(f"截图必须是普通文件：{path_value}")
    if file_stat.st_size <= 0:
        os.close(descriptor)
        raise EvidenceError(f"截图不能为空：{path_value}")

    digest = hashlib.sha256()
    try:
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            header = _read_exact(stream, min(12, file_stat.st_size))
            stream.seek(0)
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                mime_type = "image/png"
                width, height = _png_dimensions(stream)
                _validate_png(stream, file_stat.st_size)
            elif header.startswith(b"\xff\xd8"):
                mime_type = "image/jpeg"
                width, height = _jpeg_dimensions(stream)
                stream.seek(-2, os.SEEK_END)
                if _read_exact(stream, 2) != b"\xff\xd9":
                    raise EvidenceError("JPEG 缺少 EOI，文件可能已截断。")
            elif (
                len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
            ):
                mime_type = "image/webp"
                declared_size = struct.unpack("<I", header[4:8])[0] + 8
                if declared_size != file_stat.st_size:
                    raise EvidenceError("WebP RIFF size 与实际文件大小不一致。")
                width, height = _webp_dimensions(stream)
            else:
                raise EvidenceError(f"截图格式必须是 PNG、JPEG 或 WebP：{path_value}")
            stream.seek(0)
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise EvidenceError(f"读取截图失败：{path_value}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)

    if width <= 0 or height <= 0:
        raise EvidenceError(f"截图尺寸无效：{path_value}")
    return ImageEvidence(
        path=str(path.absolute()),
        sha256=digest.hexdigest(),
        size=file_stat.st_size,
        mime_type=mime_type,
        width=width,
        height=height,
        upload_name=upload_name,
        description=description,
    )
