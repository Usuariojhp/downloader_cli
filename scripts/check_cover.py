#!/usr/bin/env python3
"""Check if an MP3 file has an embedded cover (APIC frame).

Used by the CI e2e test to verify the cover was embedded.
"""

import os
import sys

from mutagen.id3 import ID3


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_cover.py <mp3_file>", file=sys.stderr)
        return 1

    mp3_path = sys.argv[1]
    try:
        audio = ID3(mp3_path)
    except Exception as exc:
        print(f"❌ Error leyendo MP3: {exc}")
        return 1

    apic_frames = audio.getall("APIC")
    if apic_frames:
        size_kb = len(apic_frames[0].data) // 1024
        print(f"✅ Carátula: {size_kb} KB")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as f:
                f.write(f"✅ Carátula incrustada: {len(apic_frames[0].data) // 1024} KB\n")
        return 0
    else:
        print("❌ Sin carátula")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as f:
                f.write("❌ **Sin carátula** (revisa el log)\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
