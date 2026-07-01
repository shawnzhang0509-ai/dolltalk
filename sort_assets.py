#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 inbox/ 里的图片按命名规则自动归类到 assets/，并同步 config/*.yaml。

命名规则见 config/asset_rules.yaml

用法:
  python sort_assets.py              # 执行归类
  python sort_assets.py --dry-run    # 只预览，不移动
  python sort_assets.py --list-rules  # 查看命名规则
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

import yaml

from doll_assets import scan_dolls_assets

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
RULES_PATH = CONFIG_DIR / "asset_rules.yaml"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


def normalize_ext(ext: str) -> str:
    ext = ext.lower()
    return "jpg" if ext == "jpeg" else ext


def match_doll(filename: str, patterns: list[str]) -> tuple[str, str, str, str | None] | None:
    """返回 (doll, pose, ext, emotion_or_none)"""
    for pat in patterns:
        m = re.match(pat, filename, re.IGNORECASE)
        if not m:
            continue
        doll = m.group("doll").lower()
        pose = f"{int(m.group('pose')):02d}"
        emotion = m.groupdict().get("emotion")
        if emotion:
            emotion = emotion.lower()
            return doll, pose, "png", emotion
        ext = normalize_ext(m.group("ext"))
        return doll, pose, ext, None
    return None


def match_background(filename: str, patterns: list[str]) -> tuple[str, str] | None:
    for pat in patterns:
        m = re.match(pat, filename, re.IGNORECASE)
        if m:
            bg = m.group("bg").lower()
            ext = normalize_ext(m.group("ext"))
            return bg, ext
    return None


def flat_dest_filename(slug: str, pose: str, ext: str, emotion: str | None) -> str:
    if emotion:
        return f"{slug}_{emotion}_{pose}.png"
    return f"{slug}_{pose}.{ext}"


def classify_file(filename: str, rules: dict) -> Path | None:
    layout = rules.get("doll_layout", "flat")
    doll = match_doll(filename, rules.get("doll_patterns", []))
    if doll:
        slug, pose, ext, emotion = doll
        if layout == "flat":
            fname = flat_dest_filename(slug, pose, ext, emotion)
            return Path("assets") / "dolls" / fname
        if emotion:
            return Path("assets") / "dolls" / slug / emotion / f"pose_{pose}.png"
        return Path("assets") / "dolls" / slug / f"pose_{pose}.{ext}"

    # 长文件名含 Nova 等 → 平铺原样放入 assets/dolls/
    if layout == "flat":
        for pat in rules.get("doll_loose_patterns", []):
            if re.search(pat, filename, re.I):
                return Path("assets") / "dolls" / filename

    bg = match_background(filename, rules.get("background_patterns", []))
    if bg:
        slug, ext = bg
        return Path("assets") / "backgrounds" / f"{slug}.{ext}"

    return None


def sync_dolls_config(assets_root: Path) -> list[str]:
    dolls_path = CONFIG_DIR / "dolls.yaml"
    dolls = load_yaml(dolls_path)
    changes: list[str] = []
    dolls_dir = assets_root / "dolls"
    known = list(dolls.keys()) or ["nova"]

    scanned = scan_dolls_assets(dolls_dir, ROOT, known)

    for slug, data in scanned.items():
        if slug not in dolls:
            dolls[slug] = {
                "name": slug.capitalize(),
                "personality": "",
                "default_scale": 0.5,
                "poses": data["poses"],
            }
            changes.append(f"新增娃娃: {slug} ({len(data['poses'])} 张)")
        else:
            if data["poses"]:
                dolls[slug]["poses"] = data["poses"]
                changes.append(f"更新姿势: {slug} ({len(data['poses'])} 张)")
            if data["emotions"]:
                dolls[slug]["emotions"] = data["emotions"]
                emo_summary = ", ".join(f"{k}:{len(v)}" for k, v in data["emotions"].items())
                changes.append(f"更新情绪: {slug} [{emo_summary}]")

    save_yaml(dolls_path, dolls)
    return changes


def sync_backgrounds_config(assets_root: Path) -> list[str]:
    bg_path = CONFIG_DIR / "backgrounds.yaml"
    backgrounds = load_yaml(bg_path)
    changes: list[str] = []
    bg_dir = assets_root / "backgrounds"
    if not bg_dir.exists():
        return changes

    for img in sorted(bg_dir.iterdir()):
        if not img.is_file() or img.name.startswith("."):
            continue
        slug = img.stem.lower()
        rel = str(img.relative_to(ROOT)).replace("\\", "/")
        if slug not in backgrounds:
            name = slug.replace("_", " ").title()
            backgrounds[slug] = {"name": name, "tags": [], "image": rel}
            changes.append(f"新增背景: {slug}")
        elif backgrounds[slug].get("image") != rel:
            backgrounds[slug]["image"] = rel
            changes.append(f"更新背景路径: {slug}")

    save_yaml(bg_path, backgrounds)
    return changes


def sort_inbox(inbox: Path, dry_run: bool) -> tuple[list[str], list[str]]:
    rules = load_yaml(RULES_PATH)
    moved: list[str] = []
    skipped: list[str] = []

    if not inbox.exists():
        inbox.mkdir(parents=True)
        return moved, skipped

    for src in sorted(inbox.iterdir()):
        if not src.is_file() or src.name.startswith("."):
            continue

        dest_rel = classify_file(src.name, rules)
        if not dest_rel:
            skipped.append(src.name)
            continue

        dest = ROOT / dest_rel
        action = "移动" if not dry_run else "将移动"
        line = f"{action}: {src.name} → {dest_rel}"
        moved.append(line)

        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                dest.unlink()
            shutil.move(str(src), str(dest))

    return moved, skipped


def print_rules() -> None:
    rules = load_yaml(RULES_PATH)
    print("=" * 55)
    print("  素材命名规则（扔进 inbox/ 后运行 sort_assets.py）")
    print("=" * 55)
    print("\n娃娃图（平铺，直接放 assets/dolls/）:")
    print("  nova_04.png")
    print("  Nova-4.png")
    print("  doll_nova_happy_01.png")
    print("  DWWD01_-_Nova_-_Xuexian-4-removebg-preview.png")
    print("\n也支持旧版子文件夹 assets/dolls/nova/pose_01.png")
    print("\n背景:")
    print("  bg_rainy_night.jpg")
    print("  bg-auckland_night.png")
    print("  background_coffee_morning.jpg")
    print("\n正则规则文件: config/asset_rules.yaml")
    for label, key in [("娃娃", "doll_patterns"), ("背景", "background_patterns")]:
        print(f"\n{label}:")
        for p in rules.get(key, []):
            print(f"  {p}")


def main() -> None:
    parser = argparse.ArgumentParser(description="按命名规则整理 inbox 素材")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不实际移动")
    parser.add_argument("--list-rules", action="store_true", help="显示命名规则")
    parser.add_argument("--sync-only", action="store_true", help="只扫描 assets/ 同步 config，不处理 inbox")
    parser.add_argument("--inbox", type=Path, default=None, help="素材收件箱目录")
    args = parser.parse_args()

    if args.list_rules:
        print_rules()
        return

    rules = load_yaml(RULES_PATH)

    if args.sync_only:
        print("=" * 55)
        print("  DollWorldwide — 同步素材配置")
        print("=" * 55)
        doll_changes = sync_dolls_config(ROOT / "assets")
        bg_changes = sync_backgrounds_config(ROOT / "assets")
        for c in doll_changes + bg_changes:
            print(f"   {c}")
        if not doll_changes and not bg_changes:
            print("   无变化（确认图片在 assets/dolls/ 且文件名含娃娃名如 Nova）")
        return

    inbox = args.inbox or ROOT / rules.get("inbox", "inbox")

    print("=" * 55)
    print("  DollWorldwide — 素材自动归类")
    print("=" * 55)
    print(f"  收件箱: {inbox.resolve()}")

    moved, skipped = sort_inbox(inbox, args.dry_run)

    if moved:
        print(f"\n✅ 处理 {len(moved)} 个文件:")
        for line in moved:
            print(f"   {line}")
    else:
        print("\n📭 inbox 里没有可识别的文件")
        dolls_dir = ROOT / "assets" / "dolls"
        flat_imgs = [p for p in dolls_dir.glob("*") if p.is_file() and not p.name.startswith(".")] if dolls_dir.exists() else []
        if flat_imgs:
            print(f"   但 assets/dolls/ 里已有 {len(flat_imgs)} 张图，下面会同步 config")
        else:
            print("   两种用法:")
            print("   ① 新图扔进 inbox/ → 再运行本脚本")
            print("   ② 图已在 assets/dolls/ → 运行: python sort_assets.py --sync-only")
            print("   命名规则: python sort_assets.py --list-rules")

    if skipped:
        print(f"\n⚠️  无法识别 ({len(skipped)} 个，请检查文件名):")
        for name in skipped:
            print(f"   - {name}")

    if not args.dry_run:
        print("\n🔄 同步 config/ ...")
        doll_changes = sync_dolls_config(ROOT / "assets")
        bg_changes = sync_backgrounds_config(ROOT / "assets")
        for c in doll_changes + bg_changes:
            print(f"   {c}")
        if not doll_changes and not bg_changes:
            print("   无变化")

    print("\n💡 下一步: python drama_builder.py dramas/xxx.yaml")


if __name__ == "__main__":
    main()
