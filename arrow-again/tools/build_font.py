"""可选：从已下载的 Noto Sans SC 生成项目所需字形。

运行：python tools/build_font.py /path/to/NotoSansSC.ttf
额外依赖：fonttools。正常玩游戏不需要运行这个工具。
"""
from pathlib import Path
import sys

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]  # 按脚本位置定位项目，不依赖工作目录


def main():
    font = TTFont(sys.argv[1])  # 手动传入原始字体路径
    font = instantiateVariableFont(font, {'wght': 500}, inplace=True)  # 固定字重后再裁剪字形
    characters = set(chr(i) for i in range(32, 127))
    for path in (ROOT / 'arrow_game').glob('*.py'):  # 收集游戏源码字符，新增文字后需重建
        characters.update(path.read_text(encoding='utf-8'))
    characters.update('0123456789−×✓')
    options = subset.Options()  # 保留字体名称和版权等元数据
    options.name_IDs = ['*']
    options.name_legacy = True
    options.name_languages = ['*']
    sub = subset.Subsetter(options=options)
    sub.populate(unicodes=[ord(char) for char in characters])
    sub.subset(font)  # 仅保留所需字形，减小资源体积
    for record in font['name'].names:  # 修改字体名称，保留版权与许可记录
        if record.nameID in (1, 3, 4, 6, 16, 17):
            value = 'Medium' if record.nameID == 17 else 'ArrowPuzzleSans'
            record.string = value.encode(record.getEncoding())
    output = ROOT / 'assets' / 'ArrowPuzzleSans.ttf'
    font.save(output)  # 输出供 app.py 直接加载的字体
    print(f'Font: {output.stat().st_size} bytes, {len(font.getBestCmap())} glyph mappings')


if __name__ == '__main__':  # 可选开发工具，不随游戏自动执行
    main()
