#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量一键流程（无 AI）: 整理素材 → 渲染场景

用法:
  python make.py --drama dramas/nova_auckland_night.yaml
  python make.py --sort-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str]) -> int:
    print(f"\n▶ {' '.join(cmd)}\n")
    return subprocess.run([sys.executable, *cmd], cwd=str(ROOT)).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="DollWorldwide 场景制作（无 AI）")
    parser.add_argument("--drama", type=Path, help="剧集 dramas/xxx.yaml")
    parser.add_argument("--sort-only", action="store_true", help="只整理 inbox 素材")
    parser.add_argument("--dry-sort", action="store_true", help="预览归类")
    args = parser.parse_args()

    print("=" * 55)
    print("  DollWorldwide — 场景制作")
    print("=" * 55)

    sort_cmd = ["sort_assets.py"]
    if args.dry_sort:
        sort_cmd.append("--dry-run")
    if run(sort_cmd) != 0:
        sys.exit(1)

    if args.sort_only:
        return

    if args.drama:
        drama = args.drama if args.drama.is_absolute() else ROOT / args.drama
        if not drama.exists():
            raise SystemExit(f"找不到: {drama}")
        if run(["drama_builder.py", str(drama)]) != 0:
            sys.exit(1)
    else:
        if run(["drama_builder.py"]) != 0:
            sys.exit(1)

    print("\n" + "=" * 55)
    print("🎉 完成！帧在 output_scenes/")
    print("=" * 55)


if __name__ == "__main__":
    main()
