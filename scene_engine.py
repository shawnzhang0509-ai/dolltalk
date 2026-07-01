#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================
DollWorldwide 场景引擎 v2.0
====================================================
用文件夹结构控制视频场景走向

项目结构:
📁 scenes/
  📁 01_scene_name/          ← 场景文件夹(01开头会自动排序)
    📄 script.txt             ← 字幕+时序+位置控制
    🖼️ bg.jpg                 ← 场景背景(必须叫bg.*)
    🖼️ model_01.png           ← model照片(按文件名排序出场)
    🖼️ model_02.png
  📁 02_next_scene/
    ...

script.txt 格式:
  时间段,字幕文字,位置,缩放
  例如:
    0-3,"Auckland. 7PM.",center,0.5
    3-8,"Just got home...",right,0.45
    8-15,"Good company.",left,0.48

运行:
  python scene_engine.py
"""

from PIL import Image, ImageEnhance, ImageDraw, ImageFont, ImageFilter
import os
import glob
import re

# ===================== 全局配置 =====================
SCENES_DIR = os.environ.get("SCENES_DIR", "./scenes")           # 场景源文件夹
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "./output_scenes")    # 输出文件夹

# 默认合成参数（可在单个场景的script.txt中覆盖）
DEFAULTS = {
    "brightness": 0.82,
    "saturation": 0.88,
    "contrast": 1.05,
    "bg_threshold": 35,
    "edge_smooth": 1,
}

# 字幕样式
SUBTITLE_STYLE = {
    "font_size_ratio": 0.035,      # 字号 = 画面高度的3.5%
    "y_position_ratio": 0.78,      # 字幕Y位置 = 画面高度的78%
    "text_color": (255, 255, 255),
    "outline_color": (0, 0, 0),
    "outline_width": 2,
}

# ==================================================


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


from matte_utils import remove_black_bg


def get_font(size):
    """获取字体（尽量用系统自带）"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def add_subtitle(img, text, style=None):
    """在图片底部添加字幕"""
    if not text:
        return img
    if style is None:
        style = SUBTITLE_STYLE

    draw = ImageDraw.Draw(img)
    w, h = img.size

    font_size = int(h * style["font_size_ratio"])
    font = get_font(font_size)

    # 计算文字位置（居中）
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (w - text_w) // 2
    y = int(h * style["y_position_ratio"])

    # 画描边
    outline = style["outline_width"]
    for dx in range(-outline, outline+1):
        for dy in range(-outline, outline+1):
            draw.text((x+dx, y+dy), text, font=font, fill=style["outline_color"])

    # 画主文字
    draw.text((x, y), text, font=font, fill=style["text_color"])

    return img


def composite_frame(bg_path, model_path, config, subtitle=""):
    """
    合成一帧画面
    config: dict with position, scale, brightness, saturation, contrast
    """
    # 加载素材
    model = remove_black_bg(model_path, config.get("bg_threshold", DEFAULTS["bg_threshold"]))
    bg = Image.open(bg_path).convert("RGBA")
    bg_w, bg_h = bg.size

    # 调整model大小
    scale = config.get("scale", 0.5)
    target_h = int(bg_h * scale)
    ratio = target_h / model.height
    target_w = int(model.width * ratio)
    model = model.resize((target_w, target_h), Image.LANCZOS)

    # 边缘柔化
    edge = config.get("edge_smooth", DEFAULTS["edge_smooth"])
    if edge > 0:
        r, g, b, a = model.split()
        a = a.filter(ImageFilter.GaussianBlur(edge))
        model = Image.merge("RGBA", (r, g, b, a))

    # 光影匹配
    model = ImageEnhance.Brightness(model).enhance(
        config.get("brightness", DEFAULTS["brightness"]))
    model = ImageEnhance.Color(model).enhance(
        config.get("saturation", DEFAULTS["saturation"]))
    model = ImageEnhance.Contrast(model).enhance(
        config.get("contrast", DEFAULTS["contrast"]))

    # 位置
    position = config.get("position", "center")
    if position == "center":
        x = (bg_w - target_w) // 2
    elif position == "left":
        x = int(bg_w * 0.12)
    elif position == "right":
        x = bg_w - target_w - int(bg_w * 0.12)
    else:
        x = (bg_w - target_w) // 2
    y = bg_h - target_h - int(bg_h * 0.02)

    # 合成
    result = bg.copy()
    result.paste(model, (x, y), model)

    # 加字幕
    if subtitle:
        result = add_subtitle(result.convert("RGB"), subtitle)
    else:
        result = result.convert("RGB")

    return result


def safe_filename_part(text: str, max_len: int = 20) -> str:
    """去掉 Windows/macOS 文件名非法字符。"""
    text = text[:max_len]
    text = re.sub(r'[\\/:*?"<>|]', "", text)
    text = text.replace(" ", "_").replace(".", "")
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "frame"


def parse_script(script_path):
    """
    解析script.txt
    返回: list of dicts [{start, end, subtitle, position, scale}, ...]
    """
    entries = []
    with open(script_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = [p.strip().strip('"') for p in line.split(",")]
                time_range = parts[0].split("-")
                entry = {
                    "start": int(time_range[0]),
                    "end": int(time_range[1]),
                    "subtitle": parts[1] if len(parts) > 1 else "",
                    "position": parts[2] if len(parts) > 2 else "center",
                    "scale": float(parts[3]) if len(parts) > 3 else 0.5,
                }
                entries.append(entry)
            except Exception as e:
                print(f"   ⚠️  跳过无效行: {line} ({e})")
    return entries


def process_scene(scene_dir, output_dir):
    """处理一个场景文件夹"""
    scene_name = os.path.basename(scene_dir)
    print(f"\n📂 场景: {scene_name}")

    # 查找素材
    script_path = os.path.join(scene_dir, "script.txt")

    # 找背景 (优先bg.*)
    bg_candidates = (glob.glob(os.path.join(scene_dir, "bg.*")) or
                     glob.glob(os.path.join(scene_dir, "background.*")))
    if not bg_candidates:
        # 找最大的jpg/png作为背景
        imgs = glob.glob(os.path.join(scene_dir, "*.jpg")) + \
               glob.glob(os.path.join(scene_dir, "*.png"))
        if imgs:
            bg_candidates = [max(imgs, key=os.path.getsize)]

    if not bg_candidates:
        print(f"   ❌ 跳过: 没有背景图")
        return 0
    bg_path = bg_candidates[0]

    # 找model照片 (排除bg, 按文件名排序)
    all_imgs = sorted(glob.glob(os.path.join(scene_dir, "*.png")) +
                      glob.glob(os.path.join(scene_dir, "*.jpg")) +
                      glob.glob(os.path.join(scene_dir, "*.jpeg")))
    model_paths = [p for p in all_imgs 
                   if os.path.basename(p).lower() not in ["bg.jpg", "bg.png", "background.jpg", "background.png"]]

    if not model_paths:
        print(f"   ❌ 跳过: 没有model照片")
        return 0

    print(f"   🖼️  背景: {os.path.basename(bg_path)}")
    print(f"   👤 Models: {len(model_paths)} 张")
    for mp in model_paths:
        print(f"      - {os.path.basename(mp)}")

    # 解析script
    if os.path.exists(script_path):
        entries = parse_script(script_path)
        print(f"   📜 字幕段: {len(entries)} 段")
    else:
        # 默认: 只有一段，用第一张model
        entries = [{"start": 0, "end": 5, "subtitle": "", "position": "center", "scale": 0.5}]
        print(f"   ⚠️  没有script.txt，使用默认配置")

    # 创建输出目录
    scene_output = os.path.join(output_dir, scene_name)
    ensure_dir(scene_output)

    # 逐帧合成
    count = 0
    for i, entry in enumerate(entries):
        # 循环使用model照片
        model_path = model_paths[i % len(model_paths)]

        config = {
            "position": entry.get("position", "center"),
            "scale": entry.get("scale", 0.5),
            "brightness": DEFAULTS["brightness"],
            "saturation": DEFAULTS["saturation"],
            "contrast": DEFAULTS["contrast"],
            "bg_threshold": DEFAULTS["bg_threshold"],
            "edge_smooth": DEFAULTS["edge_smooth"],
        }

        frame = composite_frame(bg_path, model_path, config, entry.get("subtitle", ""))

        # 文件名: frame_0001_00-05s_Auckland7PM.jpg
        safe_sub = safe_filename_part(entry.get("subtitle", ""))
        fname = f"frame_{i+1:04d}_{entry['start']:02d}-{entry['end']:02d}s_{safe_sub}.jpg"
        out_path = os.path.join(scene_output, fname)
        frame.save(out_path, quality=95)
        count += 1

    print(f"   ✅ 输出 {count} 帧到: {scene_output}/")
    return count


def main():
    print("=" * 55)
    print("  DollWorldwide 场景引擎 v2.0")
    print("  文件夹 = 场景 | script.txt = 导演")
    print("=" * 55)

    if not os.path.exists(SCENES_DIR):
        print(f"\n❌ 错误: 没有找到 {SCENES_DIR}/ 目录")
        print("   请创建 scenes/ 文件夹，里面放场景子文件夹")
        return

    ensure_dir(OUTPUT_DIR)

    # 扫描场景文件夹 (按文件夹名排序)
    scene_dirs = sorted([d for d in glob.glob(os.path.join(SCENES_DIR, "*"))
                         if os.path.isdir(d)])

    if not scene_dirs:
        print(f"\n❌ 错误: {SCENES_DIR}/ 下没有找到场景文件夹")
        return

    print(f"\n🎬 发现 {len(scene_dirs)} 个场景:")
    for sd in scene_dirs:
        print(f"   📁 {os.path.basename(sd)}")

    print("-" * 55)

    # 逐个处理
    total = 0
    for sd in scene_dirs:
        total += process_scene(sd, OUTPUT_DIR)

    print("\n" + "=" * 55)
    print(f"🎉 全部完成！共生成 {total} 帧")
    print(f"📁 输出目录: {os.path.abspath(OUTPUT_DIR)}/")
    print("\n💡 使用流程:")
    print("   1. 把帧按顺序拖进CapCut时间轴")
    print("   2. 每帧时长 = script.txt里定义的时间段")
    print("   3. 加转场 + BGM = 成品视频")
    print("=" * 55)


if __name__ == "__main__":
    main()
