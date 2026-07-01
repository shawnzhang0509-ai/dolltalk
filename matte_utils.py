"""抠图工具 — 黑底阈值法 + 可选 rembg AI 抠图"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

try:
    from rembg import remove as rembg_remove

    HAS_REMBG = True
except ImportError:
    HAS_REMBG = False


def remove_black_bg(img: Image.Image | str | Path, threshold: int = 35) -> Image.Image:
    if not isinstance(img, Image.Image):
        img = Image.open(img).convert("RGBA")
    else:
        img = img.convert("RGBA")
    arr = np.array(img)
    mask = (
        (arr[:, :, 0] < threshold)
        & (arr[:, :, 1] < threshold)
        & (arr[:, :, 2] < threshold)
    )
    arr[mask] = [0, 0, 0, 0]
    return Image.fromarray(arr)


def remove_with_rembg(img: Image.Image | str | Path) -> Image.Image:
    if not HAS_REMBG:
        raise SystemExit(
            "rembg 未安装。运行: pip install rembg\n"
            "或使用: python batch_matte.py --method black"
        )
    if not isinstance(img, Image.Image):
        img = Image.open(img)
    out = rembg_remove(img)
    return out.convert("RGBA")


def matte_image(
    src: Image.Image | str | Path,
    method: str = "auto",
    threshold: int = 35,
    edge_smooth: int = 1,
) -> Image.Image:
    """method: auto | black | rembg"""
    if method == "black":
        result = remove_black_bg(src, threshold)
    elif method == "rembg":
        result = remove_with_rembg(src)
    else:
        # auto: 黑底图用阈值法（快），其他用 rembg
        if not isinstance(src, Image.Image):
            pil = Image.open(src).convert("RGB")
        else:
            pil = src.convert("RGB")
        arr = np.array(pil)
        dark_ratio = np.mean((arr < 30).all(axis=2))
        if dark_ratio > 0.25:
            result = remove_black_bg(pil, threshold)
        elif HAS_REMBG:
            result = remove_with_rembg(pil)
        else:
            result = remove_black_bg(pil, threshold)

    if edge_smooth > 0:
        r, g, b, a = result.split()
        a = a.filter(ImageFilter.GaussianBlur(edge_smooth))
        result = Image.merge("RGBA", (r, g, b, a))
    return result
