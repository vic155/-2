# 资源说明

- 箭头、方块、按钮和背景均由 `arrow_game/app.py` 的 Pygame 绘图代码绘制，没有使用原游戏素材。
- `ArrowPuzzleSans.ttf` 是 Noto Sans SC 的 Medium（500）静态字形子集，包含本程序中文和基础字符。字体经裁剪后重命名，不需要用户安装字体。
- 原始字体：[Google Fonts / Noto Sans SC](https://github.com/google/fonts/tree/main/ofl/notosanssc)。下载日期：2026-09-17。
- 字体许可证：SIL Open Font License 1.1，完整文本见 [OFL.txt](OFL.txt)。字体修改与重新分发遵循该许可。
- 如新增中文界面文字，使用 `tools/build_font.py` 从原始可变字体重新生成子集；需要额外安装 `fonttools`。运行游戏不需要此依赖。
