"""在 Windows 64 位 Python 中运行，生成可独立启动的 Windows 可执行文件。

python -m pip install -r requirements-dev.txt
python tools/build_exe.py
可选：--output 指定输出目录。所有资源使用绝对路径，允许从其他目录调用。
"""
import argparse
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]  # 资源和入口均按项目绝对路径定位


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')  # 成品目录
    parser.add_argument('--work', type=Path, default=ROOT / 'build')  # 打包临时目录
    args = parser.parse_args()
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',  # 使用当前 Python 环境
               '--onefile', '--windowed', '--name', 'ArrowAgain',  # 单文件程序，不显示终端
               '--add-data', f'{ROOT / "assets"}{os.pathsep}assets',  # 字体等资源需显式加入
               '--distpath', str(args.output.resolve()),
               '--workpath', str(args.work.resolve() / 'temp'),
               '--specpath', str(args.work.resolve()), str(ROOT / 'main.py')]
    subprocess.run(command, cwd=ROOT, check=True)  # 失败时抛出异常，不误报打包成功


if __name__ == '__main__':  # 手动执行才打包，main.py 不调用此工具
    main()
