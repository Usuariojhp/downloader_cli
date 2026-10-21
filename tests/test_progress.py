"""Tests for aria2 control-file progress parsing."""

from __future__ import annotations

import struct
from pathlib import Path

from veluz.core.progress import (
    PartialFileMonitor,
    _count_bits,
    _parse_aria2_control,
)


def _control(
    piece_length: int,
    total_length: int,
    completed: set[int] | None = None,
    in_flight: list[tuple[int, int, bytes]] | None = None,
) -> bytes:
    """Build a version-1 aria2 control file for tests."""
    completed = completed or set()
    num_pieces = (total_length + piece_length - 1) // piece_length
    bitfield_length = (num_pieces + 7) // 8
    bitfield = bytearray(bitfield_length)
    for index in completed:
        bitfield[index // 8] |= 0x80 >> (index % 8)

    data = bytearray()
    data += struct.pack(">HI", 1, 0)  # version, extension
    data += struct.pack(">I", 0)  # info-hash length (not BitTorrent)
    data += struct.pack(">IQQ", piece_length, total_length, 0)
    data += struct.pack(">I", bitfield_length)
    data += bitfield
    pieces = in_flight or []
    data += struct.pack(">I", len(pieces))
    for index, length, sub_bitfield in pieces:
        data += struct.pack(">III", index, length, len(sub_bitfield))
        data += sub_bitfield
    return bytes(data)


class TestCountBits:
    def test_counts_full_bytes(self):
        assert _count_bits(b"\xff\x00\x0f") == 12

    def test_ignores_padding_bits(self):
        assert _count_bits(b"\xff", 3) == 3
        assert _count_bits(b"\x80", 1) == 1
        assert _count_bits(b"\x01", 1) == 0


class TestParseAria2Control:
    def test_completed_pieces(self):
        data = _control(1_048_576, 3_145_728, completed={0, 1, 2})
        assert _parse_aria2_control(data) == (3_145_728, 3_145_728)

    def test_short_last_piece(self):
        data = _control(1_048_576, 2_621_440, completed={0, 2})
        assert _parse_aria2_control(data) == (1_572_864, 2_621_440)

    def test_in_flight_partial_bitfield(self):
        # One 1 MiB piece, half of its 64 blocks received.
        data = _control(
            1_048_576,
            1_048_576,
            in_flight=[(0, 1_048_576, b"\xff\xff\xff\xff\x00\x00\x00\x00")],
        )
        assert _parse_aria2_control(data) == (524_288, 1_048_576)

    def test_rejects_truncated_header(self):
        data = _control(1_048_576, 1_048_576, completed={0})
        assert _parse_aria2_control(data[:20]) is None

    def test_rejects_unknown_version(self):
        data = bytearray(_control(1_048_576, 1_048_576))
        data[1] = 9
        assert _parse_aria2_control(bytes(data)) is None


class TestPartialFileMonitor:
    def test_patterns_cover_part_and_plain_control_files(self):
        part_pattern = PartialFileMonitor._build_pattern("/tmp/video [abc].%(ext)s")
        patterns = PartialFileMonitor._build_control_patterns(part_pattern)
        assert patterns == (
            "/tmp/video [[]abc].*.part.aria2",
            "/tmp/video [[]abc].*.aria2",
        )

    def test_prefers_control_bitfield_over_part_size(self, tmp_path: Path):
        part = tmp_path / "video.mp4.part"
        part.write_bytes(b"\0" * 1_000_000)  # looks almost complete
        control = tmp_path / "video.mp4.part.aria2"
        control.write_bytes(
            _control(
                1_048_576,
                1_048_576,
                in_flight=[(0, 1_048_576, b"\xff\xff\xff\xff\x00\x00\x00\x00")],
            )
        )

        monitor = PartialFileMonitor(
            progress=object(),  # type: ignore[arg-type]
            task_id=0,  # type: ignore[arg-type]
            outtmpl=str(tmp_path / "video.%(ext)s"),
            expected_total=1_048_576,
        )
        assert monitor._downloaded_bytes() == 524_288

    def test_falls_back_to_part_size_before_control_file(self, tmp_path: Path):
        part = tmp_path / "video.mp4.part"
        part.write_bytes(b"\0" * 4096)

        monitor = PartialFileMonitor(
            progress=object(),  # type: ignore[arg-type]
            task_id=0,  # type: ignore[arg-type]
            outtmpl=str(tmp_path / "video.%(ext)s"),
            expected_total=1_048_576,
        )
        assert monitor._downloaded_bytes() == 4096

    def test_ignores_control_file_from_another_download(self, tmp_path: Path):
        control = tmp_path / "video.mp4.part.aria2"
        control.write_bytes(_control(1_048_576, 50_000_000, completed={0}))

        monitor = PartialFileMonitor(
            progress=object(),  # type: ignore[arg-type]
            task_id=0,  # type: ignore[arg-type]
            outtmpl=str(tmp_path / "video.%(ext)s"),
            expected_total=1_048_576,
        )
        # The mismatched control file is ignored; there is no .part, so 0.
        assert monitor._downloaded_bytes() == 0
