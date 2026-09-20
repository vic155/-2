"""运行测试并保存 UTF-8 原始报告，避免终端编码或标准错误重定向干扰。

python tools/run_checks.py
"""
from datetime import datetime
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]  # 确保测试能找到 tests 和 arrow_game


def main():  # 单独运行 unittest，自动发现测试文件
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,  # 合并测试输出和错误输出
                            encoding='utf-8', errors='replace')
    header = (f'Executed: {datetime.now().astimezone().isoformat(timespec="seconds")}\n'  # 保留真实时间及退出码
              f'Command: python -m unittest discover -s tests -v\n'
              f'Exit code: {result.returncode}\n\n')
    (ROOT / 'docs' / 'test-results.txt').write_text(header + result.stdout, encoding='utf-8')
    print(result.stdout)
    return result.returncode  # 向调用者传递测试结果：0 成功，非零失败


if __name__ == '__main__':  # 正常启动游戏不会执行测试
    sys.exit(main())
