#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 AI 根据娃娃人设和场景关键词，自动生成 dramas/*.yaml。

Kimi（推荐）:
  1. 复制 .env.example 为 .env，填入 MOONSHOT_API_KEY
  2. python generate_drama.py --provider kimi --doll nova --theme "雨夜咖啡馆"

OpenAI:
  export OPENAI_API_KEY=sk-...
  python generate_drama.py --doll nova --theme "雨夜咖啡馆"
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

# Kimi 与 OpenAI 接口兼容，换 base_url + model 即可
PROVIDERS = {
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "key_envs": ("MOONSHOT_API_KEY", "KIMI_API_KEY"),
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_envs": ("OPENAI_API_KEY",),
    },
}


def load_dotenv(path: Path | None = None) -> None:
    """加载项目根目录 .env（不覆盖已有环境变量）。"""
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def resolve_api_key(provider: str, explicit: str) -> str:
    if explicit:
        return explicit
    for name in PROVIDERS[provider]["key_envs"]:
        val = os.environ.get(name, "")
        if val:
            return val
    return ""


def parse_json_content(content: str) -> dict:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # 去掉可能的 markdown 代码块
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    start, end = content.find("{"), content.rfind("}")
    if start >= 0 and end > start:
        return json.loads(content[start : end + 1])
    raise SystemExit(f"无法解析 AI 返回的 JSON:\n{content[:500]}")


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
    messages = [
        {"role": "system", "content": "You output valid JSON only. 请用 JSON 格式回复。"},
        {"role": "user", "content": prompt},
    ]
    payloads = [
        {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
            "response_format": {"type": "json_object"},
        },
        {
            "model": model,
            "messages": messages,
            "temperature": 0.8,
        },
    ]

    last_error = ""
    for body_obj in payloads:
        body = json.dumps(body_obj).encode("utf-8")
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
            content = payload["choices"][0]["message"]["content"]
            return parse_json_content(content)
        except urllib.error.HTTPError as e:
            last_error = e.read().decode("utf-8", errors="replace")
            if e.code == 400 and body_obj.get("response_format"):
                continue
            raise SystemExit(f"API 请求失败 ({e.code}): {last_error}") from e
        except urllib.error.URLError as e:
            raise SystemExit(f"无法连接 API: {e.reason}") from e

    raise SystemExit(f"API 请求失败: {last_error}")


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
    load_dotenv()

    parser = argparse.ArgumentParser(description="AI 生成剧集 YAML")
    parser.add_argument("--provider", choices=list(PROVIDERS), default="kimi",
                        help="API 提供商，默认 kimi（月之暗面）")
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
    parser.add_argument("--model", default="", help="模型名，默认随 provider 自动选择")
    parser.add_argument("--api-key", default="", help="API Key（建议写在 .env，不要贴在聊天里）")
    parser.add_argument("--base-url", default="", help="API 地址，Kimi 国内默认 api.moonshot.cn")
    args = parser.parse_args()

    provider_cfg = PROVIDERS[args.provider]
    api_key = resolve_api_key(args.provider, args.api_key)
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL", provider_cfg["base_url"])
    model = args.model or os.environ.get("OPENAI_MODEL", provider_cfg["model"])

    if not api_key:
        key_names = " / ".join(provider_cfg["key_envs"])
        raise SystemExit(
            f"请设置 {args.provider} API Key（不要发到聊天里）:\n"
            f"  1. 复制 .env.example 为 .env\n"
            f"  2. 填入 {key_names}=你的key\n"
            f"  或: export {provider_cfg['key_envs'][0]}=sk-..."
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
    print(f"  接口: {args.provider} ({model})")
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
