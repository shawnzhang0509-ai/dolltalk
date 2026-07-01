#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量改表情 — 用一张娃娃原图，AI 生成多种情绪版本。

需要 Replicate API Key（按张计费，约几分钱一张）:
  1. 注册 https://replicate.com
  2. .env 里加 REPLICATE_API_TOKEN=r8_...

用法:
  python batch_expression.py --doll nova --source inbox/raw/ref.jpg
  python batch_expression.py --doll nova --source ref.jpg --emotions happy,sad,waiting
  python batch_expression.py --doll nova --source ref.jpg --all --matte

流程:
  原图 → AI改表情 → inbox/doll_nova_happy_01.png → sort_assets.py
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import yaml

from matte_utils import matte_image
from replicate_client import download_url, run_model, upload_file

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
INBOX = ROOT / "inbox"
DEFAULT_MODEL = "black-forest-labs/flux-kontext-pro"


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_emotions() -> list[str]:
    path = CONFIG_DIR / "emotions.yaml"
    if path.exists():
        return load_yaml(path).get("emotions", [])
    return ["happy", "sad", "waiting", "neutral", "loving"]


def build_prompt(emotion: str) -> str:
    cfg = load_yaml(CONFIG_DIR / "expression_prompts.yaml")
    base = cfg.get("base", "Same doll figure, only change expression.")
    prompts = cfg.get("prompts", {})
    template = prompts.get(emotion, "{base} Expression: {emotion}.")
    return template.format(base=base.strip(), emotion=emotion).strip()


def next_index(out_dir: Path, doll: str, emotion: str) -> int:
    pat = re.compile(rf"doll[-_]{doll}[-_]{emotion}[-_](\d+)", re.I)
    nums = []
    for p in out_dir.glob(f"doll_{doll}_{emotion}_*.png"):
        m = pat.match(p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def resolve_source(path: Path) -> Path:
    p = path if path.is_absolute() else ROOT / path
    if not p.exists():
        raise SystemExit(f"找不到原图: {p}")
    return p


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="批量改娃娃表情")
    parser.add_argument("--doll", required=True, help="娃娃 slug")
    parser.add_argument("--source", type=Path, required=True, help="一张参考原图")
    parser.add_argument("--emotions", default="", help="逗号分隔，如 happy,sad,waiting")
    parser.add_argument("--all", action="store_true", help="生成 emotions.yaml 里全部情绪")
    parser.add_argument("--output", type=Path, default=INBOX)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--matte", action="store_true", help="生成后自动抠图")
    parser.add_argument("--matte-method", choices=["auto", "black", "rembg"], default="auto")
    parser.add_argument("--token", default=os.environ.get("REPLICATE_API_TOKEN", ""))
    args = parser.parse_args()

    token = args.token
    if not token:
        raise SystemExit(
            "需要 Replicate API Token（改表情用图像 AI，Kimi 做不了）:\n"
            "  1. 注册 https://replicate.com 获取 token\n"
            "  2. .env 添加: REPLICATE_API_TOKEN=r8_...\n"
            "  或: python batch_expression.py --token r8_... ..."
        )

    if args.all:
        emotions = [e for e in get_emotions() if e != "neutral"]
    elif args.emotions:
        emotions = [e.strip() for e in re.split(r"[,，]", args.emotions) if e.strip()]
    else:
        emotions = ["happy", "sad", "waiting", "loving"]

    source = resolve_source(args.source)
    out_dir = args.output if args.output.is_absolute() else ROOT / args.output
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  DollWorldwide — 批量改表情")
    print("=" * 55)
    print(f"  娃娃: {args.doll}")
    print(f"  原图: {source.name}")
    print(f"  情绪: {', '.join(emotions)}")
    print(f"  模型: {args.model}")
    print("-" * 55)
    print("  上传原图...")
    image_url = upload_file(source, token)
    if not image_url:
        raise SystemExit("上传原图失败")

    done = 0
    for emotion in emotions:
        prompt = build_prompt(emotion)
        idx = next_index(out_dir, args.doll, emotion)
        dest = out_dir / f"doll_{args.doll}_{emotion}_{idx:02d}.png"
        print(f"\n  🎭 生成 {emotion} ...")

        try:
            output = run_model(
                args.model,
                {
                    "prompt": prompt,
                    "input_image": image_url,
                    "aspect_ratio": "match_input_image",
                    "output_format": "png",
                },
                token,
            )
            url = output[0] if isinstance(output, list) else output
            if not url:
                print(f"   ❌ 无输出")
                continue

            tmp = dest.with_suffix(".tmp.png")
            download_url(url, tmp)

            if args.matte:
                result = matte_image(tmp, method=args.matte_method)
                result.save(dest, "PNG")
                tmp.unlink(missing_ok=True)
            else:
                tmp.rename(dest)

            print(f"   ✅ → {dest.name}")
            done += 1
        except SystemExit as e:
            print(f"   ❌ {e}")
        except Exception as e:
            print(f"   ❌ {e}")

    print(f"\n✅ 完成 {done}/{len(emotions)} 张 → {out_dir.resolve()}/")
    print("\n💡 下一步:")
    print("   python sort_assets.py")
    print("   python drama_builder.py --list")


if __name__ == "__main__":
    main()
