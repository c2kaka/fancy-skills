from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jira_evidence import EvidenceError, inspect_image


def png_bytes(width: int = 2, height: int = 3) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    raw_scanline = b"\x00" + (b"\x00\x00\x00" * width)
    raw = raw_scanline * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class EvidenceTests(unittest.TestCase):
    def test_valid_png_reports_hash_dimensions_and_mime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.png"
            path.write_bytes(png_bytes())
            evidence = inspect_image(
                str(path), "01-dialog-deadbeef.png", "Dialog proves failure"
            )

        self.assertEqual(evidence.mime_type, "image/png")
        self.assertEqual((evidence.width, evidence.height), (2, 3))
        self.assertEqual(len(evidence.sha256), 64)

    def test_rejects_corrupt_png_crc(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corrupt.png"
            data = bytearray(png_bytes())
            data[-1] ^= 0xFF
            path.write_bytes(data)
            with self.assertRaisesRegex(EvidenceError, "CRC"):
                inspect_image(str(path), "evidence.png", "broken")

    def test_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.png"
            source.write_bytes(png_bytes())
            link = Path(directory) / "link.png"
            link.symlink_to(source)
            with self.assertRaisesRegex(EvidenceError, "符号链接"):
                inspect_image(str(link), "evidence.png", "linked")


if __name__ == "__main__":
    unittest.main()
