"""娃娃素材路径解析 — 支持平铺 assets/dolls/ 和旧版子文件夹两种放法"""

from __future__ import annotations

import re
from pathlib import Path

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

PARSE_PATTERNS = [
    re.compile(r"^doll[-_](?P<slug>[a-z0-9]+)[-_]", re.I),
    re.compile(r"^(?P<slug>[a-z0-9]+)[-_](?P<emo>happy|sad|waiting|angry|shy|surprised|neutral|loving|tired)[-_]", re.I),
    re.compile(r"^(?P<slug>[a-z0-9]+)[-_](?P<pose>\d+)", re.I),
    re.compile(r".*[-_](?P<slug>nova)[-_].*", re.I),
    re.compile(r".*\b(?P<slug>nova)\b.*", re.I),
]

EMO_PATTERN = re.compile(
    r"^(?:doll[-_])?(?P<slug>[a-z0-9]+)[-_](?P<emotion>happy|sad|waiting|angry|shy|surprised|neutral|loving|tired)[-_]",
    re.I,
)


def parse_doll_slug(filename: str, known_slugs: list[str]) -> str | None:
    name = Path(filename).stem
    lower = name.lower()
    for slug in known_slugs:
        if slug.lower() in lower:
            return slug.lower()
    for pat in PARSE_PATTERNS:
        m = pat.match(name) or pat.search(name)
        if m and m.groupdict().get("slug"):
            return m.group("slug").lower()
    return None


def parse_emotion(filename: str) -> str | None:
    m = EMO_PATTERN.match(Path(filename).stem)
    return m.group("emotion").lower() if m else None


def is_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXT and not path.name.startswith(".")


def scan_dolls_assets(dolls_dir: Path, root: Path, known_slugs: list[str]) -> dict[str, dict]:
    """
    扫描 assets/dolls/，支持:
      - 平铺: assets/dolls/nova_04.png
      - 平铺长名: assets/dolls/DWWD01_-_Nova_-_Xuexian-4-removebg-preview.png
      - 旧版: assets/dolls/nova/pose_01.png
    """
    result: dict[str, dict] = {}

    if not dolls_dir.exists():
        return result

    def ensure(slug: str) -> dict:
        if slug not in result:
            result[slug] = {"poses": [], "emotions": {}}
        return result[slug]

    def rel_path(p: Path) -> str:
        return str(p.relative_to(root)).replace("\\", "/")

    for f in sorted(dolls_dir.iterdir()):
        if is_image(f):
            slug = parse_doll_slug(f.name, known_slugs)
            if not slug:
                continue
            rel = rel_path(f)
            entry = ensure(slug)
            emo = parse_emotion(f.name)
            if emo:
                entry["emotions"].setdefault(emo, []).append(rel)
            entry["poses"].append(rel)

    for doll_dir in sorted(dolls_dir.iterdir()):
        if not doll_dir.is_dir():
            continue
        slug = doll_dir.name.lower()
        entry = ensure(slug)

        for sub in sorted(doll_dir.iterdir()):
            if sub.is_dir():
                for p in sorted(sub.iterdir()):
                    if is_image(p):
                        rel = rel_path(p)
                        entry["emotions"].setdefault(sub.name, []).append(rel)
                        entry["poses"].append(rel)
            elif is_image(sub):
                entry["poses"].append(rel_path(sub))

    for data in result.values():
        data["poses"] = sorted(set(data["poses"]))
        for emo in list(data["emotions"]):
            data["emotions"][emo] = sorted(set(data["emotions"][emo]))
    return result
