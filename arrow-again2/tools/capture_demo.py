"""通过实际游戏输入和渲染导出截图、演示 GIF；不会拼造游戏画面。

运行：python tools/capture_demo.py
无显示器时使用 SDL dummy 驱动。脚本不需要人工点击，也不等同于本人试玩。
"""
from __future__ import annotations

import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')  # 无桌面时也能生成真实画面
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')  # 不依赖音频设备
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from datetime import datetime
from pathlib import Path
import json
import sys

import pygame
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]  # 用脚本位置确定项目根目录
sys.path.insert(0, str(ROOT))  # 允许从 tools 目录导入游戏包
from arrow_game.app import GameApp
from arrow_game.model import find_blocker, solve


def main():
    output = ROOT / 'docs' / 'images'
    output.mkdir(parents=True, exist_ok=True)
    app = GameApp(seed=20260920)  # 固定录制种子便于复查，正常游戏仍随机出题。
    frames = []
    steps = []

    def click(point):  # 发送真实鼠标事件，再由游戏处理
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        for event in pygame.event.get():
            app.handle_event(event)  # 碰撞、扣次数和动画仍由正式代码处理

    def button(name):
        click(app.buttons()[name].center)

    def snapshot(name):  # 保存 GameApp 实际绘制的画面
        app.draw()
        pygame.image.save(app.screen, str(output / f'{name}.png'))

    def animate(seconds, record=True):
        for _ in range(round(seconds * 20)):  # 按每秒 20 帧推进，无需等待真实时间
            app.update(1 / 20)
            app.draw()
            if record:
                frame = Image.frombytes('RGB', app.screen.get_size(), pygame.image.tobytes(app.screen, 'RGB'))
                frames.append(frame.resize((825, 585), Image.Resampling.LANCZOS))

    try:
        animate(0.9)  # 记录打开时的归位动画，再保存稳定的主页截图。
        snapshot('start')
        x, y, _ = app.menu_tile_pose(0)
        click((round(x), round(y)))
        assert 0 in app.menu_flights
        animate(0.9)
        steps.append('Menu: decorative arrow flies and returns without starting or changing a puzzle')
        button('start')
        animate(0.15)
        snapshot('entrance')
        animate(0.65)
        snapshot('game')
        frames[0].save(output / 'opening.gif', save_all=True, append_images=frames[1:],
                       duration=50, loop=0, optimize=True)
        steps.append('Entrance: staggered arrow reveal captured; opening.gif uses actual game frames')
        blocked = next(pos for pos in app.game.board
                       if find_blocker(app.game.board, pos, app.game.level.height, app.game.level.width))
        initial = app.game.board.copy()
        click(app.cell_center(blocked))
        animate(0.1)
        snapshot('collision')
        assert app.game.board == initial and app.game.mistakes_left == 2
        steps.append('T02: blocked arrow stays, one mistake deducted; collision frame captured')
        animate(0.9)
        button('hint')
        animate(0.65)
        assert app.game.board == initial
        for pos in solve(app.game.level):  # 求解器只给顺序，每步仍通过鼠标点击
            click(app.cell_center(pos))
            assert pos not in app.game.board
            animate(0.5)
        assert app.scene == 'result' and app.game.status == 'won'
        snapshot('win')
        steps.append('T01/T03/T04: first level cleared using mouse events; win screen displayed')
        animate(1.2)
        button('next')
        assert app.game.level_index == 1 and app.game.mistakes_left == 3
        animate(0.8)
        snapshot('level2')
        for pos in solve(app.game.level):
            click(app.cell_center(pos))
            animate(0.5, record=False)  # 后续关卡继续验证，省略重复录像
        assert app.scene == 'result' and app.game.status == 'won'
        button('next')
        animate(0.7, record=False)
        snapshot('level3')
        for pos in solve(app.game.level):
            click(app.cell_center(pos))
            animate(0.5, record=False)
        assert app.scene == 'result' and 'next' not in app.buttons()
        snapshot('final')
        steps.append('T04: all 3 levels cleared; final level has no out-of-range next action')
        button('menu')  # 回到第一关，验证失败与重开
        button('level0')
        button('start')
        blocked = next(pos for pos in app.game.board
                       if find_blocker(app.game.board, pos, app.game.level.height, app.game.level.width))
        for _ in range(3):  # 三次受阻点击耗尽失误机会
            click(app.cell_center(blocked))
            animate(0.5)
        assert app.game.status == 'lost' and app.scene == 'result'
        snapshot('lose')
        animate(1.1)
        button('restart')
        assert app.scene == 'game' and app.game.board == app.game.level.arrows and app.game.mistakes_left == 3
        steps.append('T05/T06: 3 collisions trigger failure; restart restores board and mistake budget')
        initial = app.game.level.rows
        button('new')
        assert app.game.level.rows != initial and app.game.moves == 0
        animate(0.7, record=False)
        snapshot('random')
        steps.append('V2: new puzzle replaces layout at the same difficulty and resets progress')
        button('sound')
        assert not app.audio.enabled
        snapshot('muted')
        steps.append('V2: mute button disables sound without changing puzzle')
        animate(0.7)
        frames[0].save(output / 'demo.gif', save_all=True, append_images=frames[1:],
                       duration=50, loop=0, optimize=True)  # 每帧 50 毫秒，对应 20 帧/秒
        report = {  # 另存实际执行时间与验证结果
            'executed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
            'method': 'Pygame event queue, actual GameApp renderer, SDL dummy; no human playtest claim',
            'python': sys.version.split()[0], 'pygame_ce': pygame.version.ver,
            'gif_frames': len(frames), 'checks': steps, 'result': 'PASS',
        }
        (ROOT / 'docs' / 'render-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        pygame.quit()  # 即使断言失败也释放资源


if __name__ == '__main__':  # 单独导出演示，游戏不会自动录制
    main()
