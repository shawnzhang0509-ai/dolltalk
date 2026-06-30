#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================
DollWorldwide 场景合成器 v1.0 (MVP)
====================================================
功能：自动抠像 + 光影匹配 + 批量合成场景图

用法：
    1. 把Nova照片放进 ./models/ 文件夹
    2. 把背景图放进 ./backgrounds/ 文件夹
    3. python doll_compositor.py
    4. 合成图输出到 ./output_scenes/

文件要求：
    - Nova照片：黑色背景的产品照 (.png .jpg .jpeg)
    - 背景图：16:9 横版图 (.jpg .png)

作者：AI Assistant
"""

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import os
import glob

# ===================== 配置区域 =====================

MODELS_DIR = "./models"              # Nova照片文件夹
BACKGROUNDS_DIR = "./backgrounds"    # 背景图文件夹
OUTPUT_DIR = "./output_scenes"       # 输出文件夹

# Nova在画面中的比例 (0.3=很小, 0.5=适中, 0.7=很大)
DOLL_SCALE = 0.48

# 放置位置: "center"居中 / "left"偏左 / "right"偏右
POSITION = "center"

# 光影匹配参数
BRIGHTNESS = 0.82      # 亮度 (0.5-1.5, <1变暗更融合)
SATURATION = 0.88      # 饱和度 (0.5-1.5, <1更自然)
CONTRAST = 1.05        # 对比度

# 黑底抠像阈值 (0-255, 越大越激进)
BG_THRESHOLD = 35

# 边缘柔化 (像素, 0=不柔化, 1-3=轻微柔化更自然)
EDGE_SMOOTH = 1

# ==================================================


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def remove_black_bg(img_path, threshold=35):
    """用numpy快速去掉黑色背景"""
    img = Image.open(img_path).convert("RGBA")
    arr = np.array(img)
    # mask: RGB都小于threshold的像素设为透明
    mask = ((arr[:,:,0] < threshold) & 
            (arr[:,:,1] < threshold) & 
            (arr[:,:,2] < threshold))
    arr[mask] = [0, 0, 0, 0]
    return Image.fromarray(arr)


def composite(doll_path, bg_path, output_path):
    """核心合成函数"""

    # 1. 加载并抠像
    doll = remove_black_bg(doll_path, BG_THRESHOLD)
    bg = Image.open(bg_path).convert("RGBA")
    bg_w, bg_h = bg.size

    # 2. 调整Nova大小
    target_h = int(bg_h * DOLL_SCALE)
    ratio = target_h / doll.height
    target_w = int(doll.width * ratio)
    doll = doll.resize((target_w, target_h), Image.LANCZOS)

    # 3. 边缘柔化 (可选)
    if EDGE_SMOOTH > 0:
        # 只对alpha通道柔化边缘
        r, g, b, a = doll.split()
        a = a.filter(ImageFilter.GaussianBlur(EDGE_SMOOTH))
        doll = Image.merge("RGBA", (r, g, b, a))

    # 4. 光影匹配
    doll = ImageEnhance.Brightness(doll).enhance(BRIGHTNESS)
    doll = ImageEnhance.Color(doll).enhance(SATURATION)
    doll = ImageEnhance.Contrast(doll).enhance(CONTRAST)

    # 5. 计算位置
    if POSITION == "center":
        x = (bg_w - target_w) // 2
    elif POSITION == "left":
        x = int(bg_w * 0.15)
    elif POSITION == "right":
        x = bg_w - target_w - int(bg_w * 0.15)
    y = bg_h - target_h - int(bg_h * 0.02)

    # 6. 合成
    result = bg.copy()
    result.paste(doll, (x, y), doll)

    # 7. 保存
    result.convert("RGB").save(output_path, quality=95)


def main():
    print("=" * 55)
    print("  DollWorldwide 场景合成器 v1.0")
    print("=" * 55)

    ensure_dir(OUTPUT_DIR)

    # 扫描素材
    valid_ext = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
    dolls = sorted([f for f in glob.glob(os.path.join(MODELS_DIR, "*")) 
                    if f.lower().endswith(valid_ext)])
    bgs = sorted([f for f in glob.glob(os.path.join(BACKGROUNDS_DIR, "*")) 
                  if f.lower().endswith(valid_ext)])

    if not dolls:
        print(f"\n❌ 错误: {MODELS_DIR}/ 目录下没有找到图片")
        print("   请把Nova照片（黑底产品照）放进 models/ 文件夹")
        return
    if not bgs:
        print(f"\n❌ 错误: {BACKGROUNDS_DIR}/ 目录下没有找到图片")
        print("   请把背景图放进 backgrounds/ 文件夹")
        return

    print(f"\n📸 Nova照片: {len(dolls)} 张")
    for d in dolls:
        print(f"   - {os.path.basename(d)}")
    print(f"\n🏠 背景图: {len(bgs)} 张")
    for b in bgs:
        print(f"   - {os.path.basename(b)}")

    total = len(dolls) * len(bgs)
    print(f"\n🎯 将合成: {len(dolls)} × {len(bgs)} = {total} 张场景图")
    print(f"   配置: 缩放={DOLL_SCALE} | 位置={POSITION} | 亮度={BRIGHTNESS}")
    print("-" * 55)

    count = 0
    for doll_path in dolls:
        doll_name = os.path.splitext(os.path.basename(doll_path))[0]
        for bg_path in bgs:
            bg_name = os.path.splitext(os.path.basename(bg_path))[0]
            out_name = f"{doll_name}_on_{bg_name}.jpg"
            out_path = os.path.join(OUTPUT_DIR, out_name)

            print(f"\n[{count+1}/{total}] {doll_name} + {bg_name}")
            try:
                composite(doll_path, bg_path, out_path)
                print(f"   ✅ {out_name}")
                count += 1
            except Exception as e:
                print(f"   ❌ 失败: {e}")

    print("\n" + "=" * 55)
    print(f"🎉 完成！成功合成 {count}/{total} 张")
    print(f"📁 输出: {os.path.abspath(OUTPUT_DIR)}/")
    print("\n💡 下一步：把合成图拖进CapCut")
    print("   加字幕 + BGM + 转场 = 成品视频")
    print("=" * 55)


if __name__ == "__main__":
    main()
