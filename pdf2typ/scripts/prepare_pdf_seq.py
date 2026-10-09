#!/usr/bin/env python3
"""Render a sequence-diagram PDF to PNGs and collect basic extraction output."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"required tool not found: {name}")
    return path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render PDF pages to PNG for visual sequence-diagram reconstruction."
    )
    parser.add_argument("pdf", type=Path, help="Source PDF")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--dpi", type=int, default=180, help="PNG render DPI")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        raise SystemExit(f"PDF not found: {pdf}")

    pdftoppm = require_tool("pdftoppm")
    pdfinfo = shutil.which("pdfinfo")
    pdftotext = shutil.which("pdftotext")

    args.out.mkdir(parents=True, exist_ok=True)
    prefix = args.out / pdf.stem

    info_text = ""
    if pdfinfo:
        info_text = run([pdfinfo, str(pdf)]).stdout
        (args.out / "pdfinfo.txt").write_text(info_text, encoding="utf-8")

    run([pdftoppm, "-png", "-r", str(args.dpi), str(pdf), str(prefix)])
    pngs = sorted(args.out.glob(f"{pdf.stem}-*.png"))

    text_path = None
    if pdftotext:
        candidate = args.out / "pdftotext-layout.txt"
        run([pdftotext, "-layout", str(pdf), str(candidate)])
        if candidate.read_text(encoding="utf-8", errors="replace").strip():
            text_path = candidate

    manifest = {
        "source_pdf": str(pdf),
        "dpi": args.dpi,
        "pages": [str(path) for path in pngs],
        "pdfinfo": str(args.out / "pdfinfo.txt") if info_text else None,
        "text": str(text_path) if text_path else None,
    }
    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
