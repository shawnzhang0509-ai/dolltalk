#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键全流程: 整理素材 → 按大纲生成剧情 → 渲染帧

用法:
  python make.py --outline outlines/nova_rain_reunion.yaml
  python make.py --drama dramas/nova_auckland_night.yaml   # 跳过 AI，直接渲染
  python make.py --outline outlines/nova_rain_reunion.yaml --sort-only
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
    parser = argparse.ArgumentParser(description="DollWorldwide 一键制作")
    parser.add_argument("--outline", type=Path, help="剧情大纲 outlines/xxx.yaml")
    parser.add_argument("--drama", type=Path, help="已有剧集 dramas/xxx.yaml（跳过 AI）")
    parser.add_argument("--sort-only", action="store_true", help="只整理 inbox 素材")
    parser.add_argument("--dry-sort", action="store_true", help="预览素材归类，不移动")
    args = parser.parse_args()

    print("=" * 55)
    print("  DollWorldwide — 一键制作")
    print("=" * 55)

    sort_cmd = ["sort_assets.py"]
    if args.dry_sort:
        sort_cmd.append("--dry-run")
    if run(sort_cmd) != 0:
        sys.exit(1)

    if args.sort_only:
        return

    drama_path: Path | None = None

    if args.outline:
        outline = args.outline if args.outline.is_absolute() else ROOT / args.outline
        gen_cmd = ["generate_drama.py", "--outline", str(outline)]
        if run(gen_cmd) != 0:
            sys.exit(1)
        # generate_drama 输出路径由标题决定，交给 builder 交互或传 dramas
        drama_path = None  # builder will pick if needed
        # Re-run generate with knowing output - simpler: generate then list newest yaml
        dramas = sorted((ROOT / "dramas").glob("*.yaml"), key=lambda p: p.stat().st_mtime, reverse=True)
        if dramas:
            drama_path = dramas[0]
    elif args.drama:
        drama_path = args.drama if args.drama.is_absolute() else ROOT / args.drama
    else:
        print("\n请指定 --outline 或 --drama")
        print("  python make.py --outline outlines/nova_rain_reunion.yaml")
        print("  python make.py --drama dramas/nova_auckland_night.yaml")
        sys.exit(1)

    if drama_path and drama_path.exists():
        if run(["drama_builder.py", str(drama_path)]) != 0:
            sys.exit(1)
    else:
        if run(["drama_builder.py"]) != 0:
            sys.exit(1)

    print("\n" + "=" * 55)
    print("🎉 完成！帧在 output_scenes/ 文件夹")
    print("=" * 55)


if __name__ == "__main__":
    main()
