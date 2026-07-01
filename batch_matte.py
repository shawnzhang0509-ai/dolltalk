#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量抠图（可选）— 本地处理，无 AI API。

你自己生图若已是透明 PNG，可跳过此步，直接 sort_assets.py。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

from matte_utils import HAS_REMBG, matte_image

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "inbox" / "raw"
DEFAULT_OUTPUT = ROOT / "inbox"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def next_index(out_dir: Path, doll: str) -> int:
    existing = list(out_dir.glob(f"doll_{doll}_*.png")) + list(
        out_dir.glob(f"doll-{doll}-*.png")
    )
    nums = []
    for p in existing:
        m = re.search(rf"doll[-_]{doll}[-_](\d+)", p.name, re.I)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="批量抠娃娃图")
    parser.add_argument("--doll", required=True, help="娃娃 slug，如 nova")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="原图目录")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出到 inbox/")
    parser.add_argument("--method", choices=["auto", "black", "rembg"], default="auto")
    parser.add_argument("--threshold", type=int, default=35, help="黑底阈值")
    args = parser.parse_args()

    inp = args.input if args.input.is_absolute() else ROOT / args.input
    out = args.output if args.output.is_absolute() else ROOT / args.output

    if not inp.exists():
        inp.mkdir(parents=True)
        raise SystemExit(f"请把原图放进: {inp.resolve()}")

    images = sorted(
        p for p in inp.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    )
    if not images:
        raise SystemExit(f"{inp} 里没有图片")

    print("=" * 55)
    print("  DollWorldwide — 批量抠图")
    print("=" * 55)
    print(f"  娃娃: {args.doll}")
    print(f"  输入: {inp.resolve()} ({len(images)} 张)")
    print(f"  方法: {args.method}" + (" (rembg 已安装)" if HAS_REMBG else " (rembg 未装，复杂背景建议 pip install rembg)"))
    print("-" * 55)

    out.mkdir(parents=True, exist_ok=True)
    idx = next_index(out, args.doll)
    start_idx = idx
    done = 0

    for src in images:
        dest = out / f"doll_{args.doll}_{idx:02d}.png"
        print(f"  抠图: {src.name} → {dest.name}")
        try:
            result = matte_image(src, method=args.method, threshold=args.threshold)
            result.save(dest, "PNG")
            idx += 1
            done += 1
        except Exception as e:
            print(f"   ❌ 失败: {e}")

    print(f"\n✅ 完成 {done} 张 → {out.resolve()}/")
    print("\n💡 下一步: python sort_assets.py → python drama_builder.py dramas/xxx.yaml")


if __name__ == "__main__":
    main()
