#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量情绪标注 — 用 Kimi 视觉识别每张娃娃图的情绪，并按规则重命名。

用法:
  python batch_emotion.py --doll nova --tag
  python batch_emotion.py --doll nova --manifest emotions_nova.yaml
  python batch_emotion.py --doll nova --list

标注后文件名:
  doll_nova_happy_01.png → assets/dolls/nova/happy/pose_01.png

情绪清单（可在 config/emotions.yaml 自定义）:
  happy, sad, waiting, angry, shy, surprised, neutral, loving, tired
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
INBOX = ROOT / "inbox"
EMOTIONS_CONFIG = CONFIG_DIR / "emotions.yaml"

DEFAULT_EMOTIONS = [
    "happy", "sad", "waiting", "angry", "shy",
    "surprised", "neutral", "loving", "tired",
]

PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k-vision-preview",
        "key_envs": ("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    },
}


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


def get_emotion_list() -> list[str]:
    if EMOTIONS_CONFIG.exists():
        data = load_yaml(EMOTIONS_CONFIG)
        return data.get("emotions", DEFAULT_EMOTIONS)
    return DEFAULT_EMOTIONS


def resolve_api_key() -> str:
    for name in PROVIDERS["kimi"]["key_envs"]:
        val = os.environ.get(name, "")
        if val:
            return val
    return ""


def image_to_b64(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    ext = path.suffix.lower().lstrip(".")
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return base64.b64encode(data).decode("ascii"), f"image/{mime}"


def tag_emotion_vision(img_path: Path, emotions: list[str], api_key: str, base_url: str, model: str) -> str:
    b64, mime = image_to_b64(img_path)
    emotion_str = ", ".join(emotions)
    prompt = (
        f"这是娃娃人偶的照片。请判断表情/情绪，只从以下选一个英文词回复，不要其他文字：\n"
        f"{emotion_str}\n"
        f"如果都不合适，选最接近的一个。"
    )
    body = json.dumps({
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "temperature": 0.2,
    }).encode("utf-8")

    url = base_url.rstrip("/") + "/chat/completions"
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    raw = payload["choices"][0]["message"]["content"].strip().lower()
    raw = re.sub(r"[^a-z_]", "", raw)
    if raw in emotions:
        return raw
    for e in emotions:
        if e in raw or raw in e:
            return e
    return "neutral"


def next_emotion_index(out_dir: Path, doll: str, emotion: str) -> int:
    pat = re.compile(rf"doll[-_]{doll}[-_]{emotion}[-_](\d+)", re.I)
    nums = []
    for p in out_dir.glob(f"doll_{doll}_{emotion}_*.png"):
        m = pat.match(p.name)
        if m:
            nums.append(int(m.group(1)))
    return max(nums, default=0) + 1


def find_doll_images(doll: str, input_dir: Path) -> list[Path]:
    patterns = [
        f"doll_{doll}_*.png", f"doll-{doll}-*.png",
        f"doll_{doll}_*.jpg", f"doll_{doll}_*.jpeg",
    ]
    files: list[Path] = []
    for pat in patterns:
        for p in sorted(input_dir.glob(pat)):
            # 跳过已标情绪的文件 doll_nova_happy_01.png
            if re.match(rf"doll[-_]{doll}[-_][a-z]+[-_]\d+", p.name, re.I):
                continue
            if p not in files:
                files.append(p)
    return files


def apply_manifest(doll: str, manifest_path: Path, input_dir: Path, output_dir: Path) -> None:
    manifest = load_yaml(manifest_path)
    mapping = manifest.get(doll, manifest)
    if not isinstance(mapping, dict):
        raise SystemExit("manifest 格式: {文件名: 情绪} 或 {doll: {文件名: 情绪}}")

    for filename, emotion in mapping.items():
        src = input_dir / filename
        if not src.exists():
            print(f"   ⚠️  找不到: {filename}")
            continue
        idx = next_emotion_index(output_dir, doll, emotion)
        dest = output_dir / f"doll_{doll}_{emotion}_{idx:02d}.png"
        dest.write_bytes(src.read_bytes())
        print(f"   {filename} → {dest.name} [{emotion}]")
        if src.parent == output_dir and src != dest:
            src.unlink(missing_ok=True)


def sync_emotions_to_config(doll: str) -> None:
    """扫描 assets/dolls/{doll}/{emotion}/ 写入 dolls.yaml"""
    dolls_path = CONFIG_DIR / "dolls.yaml"
    dolls = load_yaml(dolls_path)
    doll_dir = ROOT / "assets" / "dolls" / doll
    if not doll_dir.exists():
        return

    emotions: dict[str, list[str]] = {}
    all_poses: list[str] = []

    for sub in sorted(doll_dir.iterdir()):
        if sub.is_dir():
            poses = sorted(sub.glob("pose_*.*"))
            if poses:
                rel = [str(p.relative_to(ROOT)).replace("\\", "/") for p in poses]
                emotions[sub.name] = rel
                all_poses.extend(rel)
        elif sub.name.startswith("pose_"):
            rel = str(sub.relative_to(ROOT)).replace("\\", "/")
            all_poses.append(rel)

    if doll not in dolls:
        dolls[doll] = {"name": doll.capitalize(), "personality": "", "default_scale": 0.5}

    if emotions:
        dolls[doll]["emotions"] = emotions
    if all_poses:
        dolls[doll]["poses"] = sorted(set(all_poses))

    with open(dolls_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(dolls, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="批量情绪标注")
    parser.add_argument("--doll", required=True)
    parser.add_argument("--input", type=Path, default=INBOX)
    parser.add_argument("--output", type=Path, default=INBOX)
    parser.add_argument("--tag", action="store_true", help="Kimi 视觉自动识别情绪")
    parser.add_argument("--manifest", type=Path, help="手动情绪对照表 YAML")
    parser.add_argument("--list", action="store_true", help="查看支持的情绪")
    args = parser.parse_args()

    if args.list:
        emotions = get_emotion_list()
        print("支持的情绪:", ", ".join(emotions))
        doll_cfg = load_yaml(CONFIG_DIR / "dolls.yaml").get(args.doll, {})
        if doll_cfg.get("emotions"):
            print(f"\n{args.doll} 已有:")
            for e, paths in doll_cfg["emotions"].items():
                print(f"  {e}: {len(paths)} 张")
        return

    inp = args.input if args.input.is_absolute() else ROOT / args.input
    out = args.output if args.output.is_absolute() else ROOT / args.output
    emotions = get_emotion_list()

    print("=" * 55)
    print("  DollWorldwide — 批量情绪标注")
    print("=" * 55)

    if args.manifest:
        manifest = args.manifest if args.manifest.is_absolute() else ROOT / args.manifest
        print(f"  模式: 手动对照表 {manifest.name}")
        apply_manifest(args.doll, manifest, inp, out)
    elif args.tag:
        api_key = resolve_api_key()
        if not api_key:
            raise SystemExit("请先在 .env 设置 MOONSHOT_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", PROVIDERS["kimi"]["base_url"])
        model = os.environ.get("OPENAI_VISION_MODEL", PROVIDERS["kimi"]["model"])
        images = find_doll_images(args.doll, inp)
        if not images:
            raise SystemExit(f"inbox 里没有 doll_{args.doll}_XX 的抠图结果，请先运行 batch_matte.py")
        print(f"  模式: Kimi 视觉识别 ({len(images)} 张)")
        print("-" * 55)
        for src in images:
            print(f"  识别: {src.name} ...", end=" ", flush=True)
            try:
                emotion = tag_emotion_vision(src, emotions, api_key, base_url, model)
                idx = next_emotion_index(out, args.doll, emotion)
                dest = out / f"doll_{args.doll}_{emotion}_{idx:02d}.png"
                dest.write_bytes(src.read_bytes())
                print(f"→ {emotion} ({dest.name})")
                if src != dest and src.parent == out:
                    src.unlink(missing_ok=True)
            except Exception as e:
                print(f"❌ {e}")
    else:
        raise SystemExit("请指定 --tag 或 --manifest emotions.yaml")

    print("\n💡 下一步: python sort_assets.py")


if __name__ == "__main__":
    main()
