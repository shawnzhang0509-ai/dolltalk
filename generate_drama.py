#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 AI 根据娃娃人设和场景关键词，自动生成 dramas/*.yaml。

用法:
  export OPENAI_API_KEY=sk-...
  python generate_drama.py --doll nova --theme "雨夜咖啡馆,思念"
  python generate_drama.py --doll nova --theme "奥克兰清晨" --background coffee_morning
  python generate_drama.py --doll nova --theme "雨夜" --build
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
DRAMAS_DIR = ROOT / "dramas"

POSITIONS = ("center", "left", "right")


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def slugify(text: str, max_len: int = 48) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "_", text)
    return text[:max_len].strip("_") or "drama"


def match_backgrounds(theme: str, backgrounds: dict, count: int) -> list[str]:
    """按主题关键词匹配背景 slug，返回得分最高的若干个。"""
    keywords = [k.strip().lower() for k in re.split(r"[,，、\s]+", theme) if k.strip()]
    if not keywords:
        return list(backgrounds.keys())[:count]

    scored: list[tuple[int, str]] = []
    for slug, bg in backgrounds.items():
        haystack = " ".join(
            [slug, bg.get("name", ""), " ".join(bg.get("tags", []))]
        ).lower()
        score = sum(1 for kw in keywords if kw in haystack)
        if score > 0:
            scored.append((score, slug))

    scored.sort(key=lambda x: (-x[0], x[1]))
    picks = [s for _, s in scored[:count]]
    if not picks:
        picks = list(backgrounds.keys())[:count]
    return picks


def build_prompt(
    doll_name: str,
    personality: str,
    theme: str,
    bg_slugs: list[str],
    backgrounds: dict,
    scenes_count: int,
    language: str,
) -> str:
    bg_desc = []
    for slug in bg_slugs:
        bg = backgrounds[slug]
        tags = ", ".join(bg.get("tags", []))
        bg_desc.append(f"- {slug}: {bg.get('name', slug)} (tags: {tags})")

    lang_hint = "中文" if language == "zh" else "English"
    return f"""你是 DollWorldwide 短剧编剧。为娃娃「{doll_name}」写一集氛围感短剧。

娃娃人设: {personality}
主题/氛围: {theme}
台词语言: {lang_hint}

可用背景（每幕必须从中选一个，用 slug 字段）:
{chr(10).join(bg_desc)}

要求:
1. 写 {scenes_count} 个场景（每幕 3-5 句台词）
2. 每句台词 3-12 个词，简短、有画面感、符合人设
3. 时间段连续不重叠，每句 3-5 秒，第一幕从 0 秒开始
4. position 在 center / left / right 间变化，scale 建议 0.45-0.55
5. 只返回 JSON，不要 markdown 代码块

JSON 格式:
{{
  "title": "剧集标题",
  "scenes": [
    {{
      "title": "场景名",
      "background": "背景slug",
      "beats": [
        {{"start": 0, "end": 4, "subtitle": "台词", "position": "center", "scale": 0.5}}
      ]
    }}
  ]
}}"""


def call_llm(prompt: str, api_key: str, base_url: str, model: str) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": "You output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"API 请求失败 ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"无法连接 API: {e.reason}") from e

    content = payload["choices"][0]["message"]["content"]
    return json.loads(content)


def validate_drama(data: dict, doll_slug: str, backgrounds: dict) -> dict:
    if "scenes" not in data or not data["scenes"]:
        raise SystemExit("AI 返回的 JSON 缺少 scenes")

    title = str(data.get("title", "未命名剧集"))
    scenes = []
    for scene in data["scenes"]:
        bg_slug = scene.get("background", "")
        if bg_slug not in backgrounds:
            valid = ", ".join(backgrounds.keys())
            raise SystemExit(f"未知背景 {bg_slug!r}，可用: {valid}")

        beats = []
        for beat in scene.get("beats", []):
            pos = beat.get("position", "center")
            if pos not in POSITIONS:
                pos = "center"
            beats.append(
                {
                    "start": int(beat["start"]),
                    "end": int(beat["end"]),
                    "subtitle": str(beat.get("subtitle", "")),
                    "position": pos,
                    "scale": round(float(beat.get("scale", 0.5)), 2),
                }
            )
        if not beats:
            continue
        scenes.append(
            {
                "title": str(scene.get("title", bg_slug)),
                "background": bg_slug,
                "beats": beats,
            }
        )

    if not scenes:
        raise SystemExit("AI 返回的场景没有有效 beats")

    return {"title": title, "doll": doll_slug, "scenes": scenes}


def write_drama_yaml(drama: dict, out_path: Path) -> None:
    lines = [
        "# AI 生成 — 可用编辑器微调后运行 drama_builder.py",
        f"# 生成: python generate_drama.py ...",
        "",
        f"title: {drama['title']}",
        f"doll: {drama['doll']}",
        "",
        "scenes:",
    ]
    for scene in drama["scenes"]:
        lines.append(f"  - title: {scene['title']}")
        lines.append(f"    background: {scene['background']}")
        lines.append("    beats:")
        for beat in scene["beats"]:
            sub = beat["subtitle"].replace('"', "'")
            lines.append(
                f'      - {{ start: {beat["start"]}, end: {beat["end"]}, '
                f'subtitle: "{sub}", position: {beat["position"]}, '
                f'scale: {beat["scale"]} }}'
            )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_builder(drama_path: Path) -> int:
    builder = ROOT / "drama_builder.py"
    result = subprocess.run([sys.executable, str(builder), str(drama_path)], cwd=str(ROOT))
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="AI 生成剧集 YAML")
    parser.add_argument("--doll", required=True, help="娃娃 slug，见 config/dolls.yaml")
    parser.add_argument("--theme", required=True, help="主题关键词，如「雨夜咖啡馆,思念」")
    parser.add_argument(
        "--background",
        action="append",
        dest="backgrounds",
        help="指定背景 slug，可多次使用；不指定则按 theme 自动匹配",
    )
    parser.add_argument("--scenes", type=int, default=2, help="场景数量，默认 2")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="台词语言")
    parser.add_argument("--output", type=Path, help="输出路径，默认 dramas/{slug}.yaml")
    parser.add_argument("--build", action="store_true", help="生成后自动运行 drama_builder")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY", ""),
        help="OpenAI API Key，也可用环境变量 OPENAI_API_KEY",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="API 地址，兼容 OpenAI 格式的服务可改此项",
    )
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit(
            "请设置 API Key:\n"
            "  export OPENAI_API_KEY=sk-...\n"
            "或: python generate_drama.py --api-key sk-... ..."
        )

    dolls = load_yaml(CONFIG_DIR / "dolls.yaml")
    backgrounds = load_yaml(CONFIG_DIR / "backgrounds.yaml")

    if args.doll not in dolls:
        valid = ", ".join(dolls.keys())
        raise SystemExit(f"未知娃娃 {args.doll!r}，可用: {valid}")

    doll = dolls[args.doll]
    if args.backgrounds:
        for bg in args.backgrounds:
            if bg not in backgrounds:
                valid = ", ".join(backgrounds.keys())
                raise SystemExit(f"未知背景 {bg!r}，可用: {valid}")
        bg_slugs = args.backgrounds
    else:
        bg_slugs = match_backgrounds(args.theme, backgrounds, args.scenes)

    scenes_count = len(bg_slugs) if args.backgrounds else args.scenes
    if args.backgrounds:
        scenes_count = len(bg_slugs)

    print("=" * 55)
    print("  DollWorldwide — AI 起剧")
    print("=" * 55)
    print(f"  娃娃: {doll.get('name', args.doll)}")
    print(f"  主题: {args.theme}")
    print(f"  背景: {', '.join(bg_slugs)}")
    print(f"  场景: {scenes_count} 幕")
    print("-" * 55)
    print("  正在生成台词...")

    prompt = build_prompt(
        doll_name=doll.get("name", args.doll),
        personality=doll.get("personality", ""),
        theme=args.theme,
        bg_slugs=bg_slugs,
        backgrounds=backgrounds,
        scenes_count=scenes_count,
        language=args.lang,
    )

    raw = call_llm(prompt, args.api_key, args.base_url, args.model)
    drama = validate_drama(raw, args.doll, backgrounds)

    if args.output:
        out_path = args.output if args.output.is_absolute() else ROOT / args.output
    else:
        out_path = DRAMAS_DIR / f"{slugify(drama['title'])}.yaml"

    write_drama_yaml(drama, out_path)
    print(f"\n✅ 已生成: {out_path}")
    print(f"   标题: {drama['title']}")
    print(f"   场景: {len(drama['scenes'])} 幕")

    if args.build:
        print("\n" + "-" * 55)
        sys.exit(run_builder(out_path))

    print(f"\n💡 下一步: python drama_builder.py {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
