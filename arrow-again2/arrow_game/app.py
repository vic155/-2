"""Pygame 界面：输入 → 纯逻辑模型 → 动画 → 绘制。

所有坐标均使用固定的 1100×780 逻辑窗口。模型不依赖 Pygame，便于测试。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import sys

import pygame

from .audio import SoundEffects
from .levels import LEVEL_SPECS  # 主页显示难度参数，具体题目在开始时随机生成。
from .model import Direction, Game  # 导入规则对象，界面不重复实现路径检测

WIDTH, HEIGHT = 1100, 780  # 绘制与鼠标定位共用固定窗口尺寸
BG = '#F5F3EC'
INK = '#193B36'
MUTED = '#77877D'
TEAL = '#237969'
LINE = '#DEE5DC'
WHITE = '#FFFEF9'
RED = '#C45342'
COLORS = {  # 方向对应（方块底色，箭头颜色）
    Direction.UP: ('#DCECE1', '#316E54'),
    Direction.DOWN: ('#ECE5D8', '#887443'),
    Direction.LEFT: ('#E4E8EE', '#60718B'),
    Direction.RIGHT: ('#F6E3D8', '#BB7052'),
}
MENU_TILES = (  # 复用游戏中的箭头方块，作为可以点击的小小开场。
    (550, 355, Direction.RIGHT, 88),
    (395, 312, Direction.UP, 58),
    (426, 429, Direction.LEFT, 66),
    (556, 473, Direction.DOWN, 52),
    (688, 412, Direction.RIGHT, 64),
    (711, 289, Direction.UP, 56),
    (555, 246, Direction.LEFT, 46),
)
ENTRANCE_SECONDS = 0.62


def asset_path(filename: str) -> Path:  # 打包资源从 _MEIPASS 解包目录查找
    """兼容源码启动与 PyInstaller 打包，资源不依赖当前工作目录。"""
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return base / 'assets' / filename


@dataclass
class Animation:  # 仅记录视觉反馈，不扣机会或修改棋盘
    kind: str  # removed 飞出；blocked 碰撞
    position: tuple[int, int]  # 原始行列位置，用于绘制已消除的箭头
    direction: Direction
    blocker: tuple[int, int] | None = None  # 碰撞时的阻挡位置
    elapsed: float = 0.0  # 动画已播放时间，单位秒
    duration: float = 0.48  # 一段动画的持续时间


class GameApp:
    def __init__(self, *, seed: int | None = None):
        pygame.display.init()  # 先启动画面，音频失败时仍可游玩。
        pygame.font.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption('一箭又一箭 · Arrow Again')
        icon = pygame.Surface((48, 48), pygame.SRCALPHA)
        pygame.draw.rect(icon, TEAL, (0, 0, 48, 48), border_radius=12)
        self.arrow(icon, (24, 24), Direction.RIGHT, WHITE, 15, 4)
        pygame.display.set_icon(icon)
        self.game = Game(seed=seed)  # 正常启动不指定种子，自动随机出题。
        self.audio = SoundEffects(asset_path('sounds'))
        self.scene = 'menu'  # 界面场景独立于 Game 的规则状态
        self.selected_level = 0
        self.running = True
        self.animation: Animation | None = None  # 同时最多播放一个箭头动画
        self.hint_position = None
        self.hint_seconds = 0.0
        self.hints_used = 0
        self.elapsed = 0.0
        self.clock_time = 0.0
        self.menu_age = 0.0
        self.menu_flights: dict[int, float] = {}  # 主页小箭头的飞行时间，不参与游戏判定。
        self.entrance_age = ENTRANCE_SECONDS
        self.pointer = (-1, -1)  # 悬停位置初始在窗口外，避免默认高亮
        self.message = '前方无阻挡，就能飞出。'
        self.message_kind = 'normal'
        self.board_panel = pygame.Rect(40, 166, 688, 552)

    @lru_cache(maxsize=32)  # 缓存不同字号，避免每帧重新加载字体
    def font(self, size: int):
        return pygame.font.Font(str(asset_path('ArrowPuzzleSans.ttf')), size)

    def text(self, value, xy, size=18, color=INK, center=False):  # 绘制文字
        surface = self.font(size).render(str(value), True, color)
        rect = surface.get_rect(center=xy) if center else surface.get_rect(topleft=xy)
        self.screen.blit(surface, rect)  # 按左上角或中心点定位后贴到窗口
        return rect

    def card(self, rect, color=WHITE, radius=22, border=None, shadow=False):
        rect = pygame.Rect(rect)
        if shadow:  # 先画阴影，再画主体和可选边框
            pygame.draw.rect(self.screen, '#E9ECE2', rect.move(0, 5), border_radius=radius)
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        if border:
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=radius)

    @staticmethod
    def arrow(surface, center, direction, color, length=18, width=4):
        """由线段画箭头，方向识别不依赖字体或颜色。"""
        dr, dc = direction.delta  # 模型按行列，屏幕横向用 dc、纵向用 dr
        cx, cy = center
        tip = (round(cx + dc * length), round(cy + dr * length))
        tail = (round(cx - dc * length), round(cy - dr * length))
        wing = length * 0.58  # 利用垂直方向计算箭头两翼
        left = (round(tip[0] - dc * wing - dr * wing),
                round(tip[1] - dr * wing + dc * wing))
        right = (round(tip[0] - dc * wing + dr * wing),
                 round(tip[1] - dr * wing - dc * wing))
        pygame.draw.line(surface, color, tail, tip, width)
        pygame.draw.lines(surface, color, False, [left, tip, right], width)
        for point in (tail, tip, left, right):
            pygame.draw.circle(surface, color, point, max(1, width // 2))

    def button(self, rect, label, primary=False, small=False):  # 只绘制，不处理点击
        hovered = pygame.Rect(rect).collidepoint(self.pointer)
        fill = ('#196453' if hovered else TEAL) if primary else ('#E5EBE1' if hovered else '#EFF1E8')
        self.card(rect, fill, 14)
        self.text(label, pygame.Rect(rect).center, 17 if small else 20,
                  WHITE if primary else INK, center=True)

    def buttons(self):  # 返回操作名称与矩形，供绘制和点击检测共用
        if self.scene == 'menu':
            result = {'start': pygame.Rect(410, 547, 280, 62)}
            result.update({f'level{i}': pygame.Rect(338 + i * 146, 634, 132, 50)
                           for i in range(len(LEVEL_SPECS))})
        elif self.scene == 'result':
            action = 'next' if self.game.status == 'won' and self.game.level_index < len(self.game.levels) - 1 else 'restart'
            result = {action: pygame.Rect(360, 505, 380, 54),
                      'new': pygame.Rect(360, 574, 180, 48),
                      'menu': pygame.Rect(560, 574, 180, 48)}
        else:
            result = {'restart': pygame.Rect(780, 509, 252, 48),
                      'new': pygame.Rect(780, 569, 252, 48),
                      'hint': pygame.Rect(780, 448, 252, 48),
                      'menu': pygame.Rect(938, 48, 120, 42)}
        result['sound'] = pygame.Rect(780 if self.scene == 'game' else 938, 48, 120, 42)
        return result  # 音效按钮放在最后，不改变 Enter 对主按钮的选择。

    def grid_geometry(self):  # 返回棋盘矩形和单格边长
        level = self.game.level
        cell = min(84, 448 // max(level.height, level.width))  # 按网格大小缩放，确保棋盘放得下
        return pygame.Rect(384 - level.width * cell // 2,
                           434 - level.height * cell // 2,
                           level.width * cell, level.height * cell), cell

    def cell_center(self, position):  # 行列转像素；加半格取中心点
        grid, cell = self.grid_geometry()
        row, col = position
        return grid.x + (col + 0.5) * cell, grid.y + (row + 0.5) * cell

    def cell_at(self, point):  # 屏幕像素坐标转棋盘行列
        grid, cell = self.grid_geometry()
        if not grid.collidepoint(point):  # 先排除棋盘外点击
            return None
        col, row = (point[0] - grid.x) // cell, (point[1] - grid.y) // cell  # 整除确定所在格
        rect = pygame.Rect(grid.x + col * cell + 5, grid.y + row * cell + 5, cell - 10, cell - 10)
        return (int(row), int(col)) if rect.collidepoint(point) else None  # 方块间隙不响应

    def reset_view(self):  # 模型重开后，清除旧动画、提示和计时
        self.animation = None
        self.hint_position = None
        self.hint_seconds = 0.0
        self.hints_used = 0
        self.elapsed = 0.0
        self.entrance_age = 0.0  # 箭头按行列依次轻落，入场时间不计入游戏用时。
        self.message = '前方无阻挡，就能飞出。'
        self.message_kind = 'normal'
        self.scene = 'game'

    def action(self, name):  # 按钮与快捷键共用同一操作入口
        if name == 'sound':
            self.audio.toggle()
            self.audio.play('click')  # 开启时给提示，关闭时保持安静。
            return
        if name == 'hint' and (self.animation is not None or self.game.status != 'playing'):
            return
        self.audio.play('click')
        if name == 'start':
            self.game.load_level(self.selected_level)
            self.reset_view()
        elif name.startswith('level'):
            self.selected_level = int(name[-1])  # 卡片只改变选择，点击开始才加载
        elif name == 'restart':
            self.game.restart()
            self.reset_view()
        elif name == 'new':
            self.game.new_puzzle()
            self.reset_view()
        elif name == 'menu':
            self.scene = 'menu'
            self.animation = None
            self.menu_age = 0.0
            self.menu_flights.clear()
        elif name == 'next':
            if self.game.next_level():
                self.selected_level = self.game.level_index
                self.reset_view()
        elif name == 'hint' and self.animation is None and self.game.status == 'playing':
            self.entrance_age = ENTRANCE_SECONDS
            self.hint_position = self.game.hint()  # 只查询安全位置，不代替玩家消除
            if self.hint_position is not None:
                self.hint_seconds = 2.5
                self.hints_used += 1
                self.message = '这一箭，可以出发。'
                self.message_kind = 'hint'

    def handle_event(self, event):  # 分流处理关闭、移动、键盘和鼠标事件
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.MOUSEMOTION:
            self.pointer = event.pos
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.scene != 'menu':
                    self.action('menu')
            elif event.key == pygame.K_r and self.scene != 'menu':
                self.action('restart')
            elif event.key == pygame.K_n and self.scene != 'menu':
                self.action('new')
            elif event.key == pygame.K_m:
                self.action('sound')
            elif event.key == pygame.K_h and self.scene == 'game':
                self.action('hint')
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                if self.scene == 'menu':
                    self.action('start')
                elif self.scene == 'result':
                    self.action(next(iter(self.buttons())))  # 执行结果页主按钮：下一关或重试
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        self.pointer = event.pos
        for name, rect in self.buttons().items():  # 按钮优先，动画期间仍可重开或回主页
            if rect.collidepoint(event.pos):
                self.action(name)
                return
        if self.scene == 'menu':
            for index in reversed(range(len(MENU_TILES))):
                if index in self.menu_flights:
                    continue
                x, y, size = self.menu_tile_pose(index)
                if pygame.Rect(round(x - size / 2), round(y - size / 2), size, size).collidepoint(event.pos):
                    self.menu_flights[index] = 0.0
                    self.audio.play('removed')
                    break
            return
        if self.scene != 'game' or self.animation is not None:  # 锁定棋盘连点，避免重复扣机会
            return
        pos = self.cell_at(event.pos)
        if pos is None:
            return
        self.entrance_age = ENTRANCE_SECONDS  # 第一次点击立即结束入场，直接执行操作。
        result = self.game.click(*pos)  # 展开行列参数，交给模型判断并更新状态
        if result.kind in ('removed', 'blocked'):  # 依据模型结果选择视觉反馈
            self.audio.play(result.kind)  # 仅有效操作发声；空格和动画期间连点保持安静。
            self.hint_position = None
            self.hint_seconds = 0
            self.animation = Animation(result.kind, pos, result.direction, result.blocker)
            if result.kind == 'blocked':
                self.message = '被挡住了，机会 −1。'
                self.message_kind = 'blocked'
            else:
                self.message = '又一箭，出发！'
                self.message_kind = 'normal'

    def update(self, dt):  # dt 为帧间秒数，用于按时间推进动画
        dt = max(0.0, dt)
        self.clock_time += dt
        if self.scene == 'menu':
            self.menu_age += dt
            self.menu_flights = {index: age + dt for index, age in self.menu_flights.items() if age + dt < 0.85}
        if self.scene == 'game':
            intro_time = min(dt, max(0, ENTRANCE_SECONDS - self.entrance_age))
            self.entrance_age = min(ENTRANCE_SECONDS, self.entrance_age + dt)
            if self.game.status == 'playing' or self.animation:
                self.elapsed += dt - intro_time
            self.hint_seconds = max(0, self.hint_seconds - dt)  # 提示倒计时
            if self.hint_seconds == 0:
                self.hint_position = None
            if self.animation:
                self.animation.elapsed += dt  # 累计动画播放时间
                if self.animation.elapsed >= self.animation.duration:
                    self.animation = None
            if self.game.status != 'playing' and self.animation is None:
                self.scene = 'result'  # 等待最后一箭或碰撞动画结束再显示结果
                self.audio.play(self.game.status)  # 切换场景时播放一次通关或失败音效。

    def draw_tile(self, center, direction, size, selected=False, error=False, offset=(0, 0)):
        x, y = center[0] + offset[0], center[1] + offset[1]  # 偏移只影响绘制，不改行列
        fill, ink = COLORS[direction]
        if error:
            fill, ink = '#F8DCD5', RED
        rect = pygame.Rect(round(x - size / 2), round(y - size / 2), size, size)
        pygame.draw.rect(self.screen, '#E6E8DE', rect.move(0, 3), border_radius=14)
        pygame.draw.rect(self.screen, fill, rect, border_radius=14)
        if selected:
            pygame.draw.rect(self.screen, TEAL, rect.inflate(6, 6), 2, border_radius=17)
        self.arrow(self.screen, (x, y), direction, ink, size * 0.23, max(3, int(size / 15)))

    def menu_tile_pose(self, index):
        x, y, direction, size = MENU_TILES[index]
        progress = min(1.0, max(0.0, (self.menu_age - index * 0.035) / 0.48))
        eased = 1 - (1 - progress) ** 3
        dr, dc = direction.delta
        x -= dc * (1 - eased) * 160  # 初次打开时从箭头反方向归位。
        y -= dr * (1 - eased) * 160
        x += math.sin(self.menu_age * 0.8 + index * 1.7) * 4
        y += math.sin(self.menu_age * 1.1 + index * 1.3) * 6
        return x, y, size

    def draw_menu(self):  # 简洁主页：一个标题、一个主操作、三档难度。
        self.text('一箭又一箭', (550, 118), 56, INK, True)
        self.text('点一下，飞出去。', (550, 181), 17, MUTED, True)
        pygame.draw.circle(self.screen, '#ECEFE5', (550, 355), 131)
        pygame.draw.circle(self.screen, LINE, (550, 355), 151, 1)
        pygame.draw.circle(self.screen, BG, (550, 355), 91)
        old_clip = self.screen.get_clip()
        self.screen.set_clip((40, 208, 1020, 310))  # 点飞的小箭头不会遮住标题和开始按钮。
        for index, (_, _, direction, _) in enumerate(MENU_TILES):
            x, y, size = self.menu_tile_pose(index)
            age = self.menu_flights.get(index)
            if age is not None and age < 0.5:
                dr, dc = direction.delta
                distance = 750 * (age / 0.5) ** 2
                x, y = x + dc * distance, y + dr * distance
                for step in range(1, 4):
                    tail = (x - dc * step * 15, y - dr * step * 15)
                    pygame.draw.circle(self.screen, LINE, (round(tail[0]), round(tail[1])), 4 - step)
            elif age is not None:
                size = max(4, round(size * min(1, (age - 0.5) / 0.25)))
            hovered = age is None and abs(self.pointer[0] - x) < size / 2 and abs(self.pointer[1] - y) < size / 2
            self.draw_tile((x, y), direction, size, selected=hovered)
        self.screen.set_clip(old_clip)
        rect = self.buttons()['start']
        hovered = rect.collidepoint(self.pointer)
        self.card(rect, '#196453' if hovered else TEAL, 22, shadow=True)
        self.text('开始', (rect.centerx - 12, rect.centery), 23, WHITE, True)
        self.arrow(self.screen, (rect.right - 42 + (5 if hovered else 0), rect.centery), Direction.RIGHT, WHITE, 11, 3)
        for i, label in enumerate(('轻松', '进阶', '挑战')):
            rect = self.buttons()[f'level{i}']
            active = i == self.selected_level
            self.card(rect, '#E3EBDE' if active else WHITE, 16, TEAL if active else LINE)
            self.text(label, (rect.centerx - 22, rect.centery), 17, TEAL if active else MUTED, True)
            spec = LEVEL_SPECS[i]
            self.text(f'{spec.width}×{spec.height}', (rect.centerx + 31, rect.centery), 13, MUTED, True)

    def draw_board(self):  # 依次绘制底板、现存箭头、动画和提示
        self.card(self.board_panel, WHITE, 24, shadow=True)
        self.text('随机挑战', (64, 187), 15, MUTED)
        grid, cell = self.grid_geometry()
        level = self.game.level
        for col in range(level.width):
            self.text(str(col + 1), (grid.x + (col + 0.5) * cell, grid.y - 15), 12, MUTED, True)
        for row in range(level.height):
            self.text(str(row + 1), (grid.x - 16, grid.y + (row + 0.5) * cell), 12, MUTED, True)
            for col in range(level.width):
                pygame.draw.circle(self.screen, LINE, self.cell_center((row, col)), 3)
        anim = self.animation
        if anim and anim.kind == 'blocked' and anim.blocker is not None:
            pygame.draw.line(self.screen, '#D9937F', self.cell_center(anim.position),
                             self.cell_center(anim.blocker), 2)
        hovered = self.cell_at(self.pointer)
        for pos, direction in self.game.board.items():
            error = bool(anim and anim.kind == 'blocked' and pos in (anim.position, anim.blocker))
            offset = (0.0, 0.0)
            size = cell - 10
            if self.entrance_age < ENTRANCE_SECONDS:
                delay = 0.2 * sum(pos) / max(1, level.height + level.width - 2)
                progress = min(1.0, max(0.0, (self.entrance_age - delay) / 0.42))
                eased = 1 - (1 - progress) ** 3
                size = max(8, round(size * (0.6 + 0.4 * eased)))
                offset = (0.0, -22 * (1 - eased))  # 按对角线依次轻落，动画不改棋盘坐标。
            if anim and anim.kind == 'blocked' and pos == anim.position:
                t = anim.elapsed / anim.duration
                push = math.sin(t * math.pi * 4) * 8 * (1 - t)  # 往返晃动，幅度逐渐减小
                dr, dc = direction.delta
                offset = (dc * push, dr * push)
            self.draw_tile(self.cell_center(pos), direction, size,
                           pos == self.hint_position or (pos == hovered and anim is None), error, offset)
        if anim and anim.kind == 'removed':  # 用动画记录继续绘制已从棋盘删除的箭头
            grid, cell = self.grid_geometry()
            x, y = self.cell_center(anim.position)
            dr, dc = anim.direction.delta
            distance = {Direction.RIGHT: grid.right - x, Direction.LEFT: x - grid.left,
                        Direction.UP: y - grid.top, Direction.DOWN: grid.bottom - y}[anim.direction] + cell
            t = min(1.0, anim.elapsed / anim.duration)  # 进度限定为 0～1
            travel = distance * (t * t * (3 - 2 * t))  # 平滑起步和收尾，飞行距离包含额外一格
            old_clip = self.screen.get_clip()
            self.screen.set_clip(grid)  # 越出棋盘的箭头部分不再显示
            for step in range(1, 5):
                behind = max(0, travel - step * 14)
                start = (round(x + dc * behind), round(y + dr * behind))
                end = (round(start[0] - dc * 7), round(start[1] - dr * 7))
                pygame.draw.line(self.screen, '#C9DED1', start, end, max(1, 4 - step // 2))
            self.draw_tile((x + dc * travel, y + dr * travel), anim.direction, cell - 10)
            self.screen.set_clip(old_clip)  # 恢复范围，避免裁掉后续面板和文字
        color = RED if self.message_kind == 'blocked' else TEAL
        pygame.draw.circle(self.screen, color, (68, 690), 4)
        self.text(self.message, (82, 678), 16, color)

    def draw_game(self):  # 组合棋盘、统计和按钮；数据以 Game 为准
        self.text('ARROW AGAIN', (40, 29), 13, TEAL)
        self.text('一箭又一箭', (40, 56), 29)
        for i in range(len(self.game.levels)):
            x = 481 + i * 84
            if i < len(self.game.levels) - 1:
                pygame.draw.line(self.screen, LINE, (x + 18, 68), (x + 66, 68), 2)
            active = i == self.game.level_index
            pygame.draw.circle(self.screen, TEAL if active else '#E4E8DF', (x, 68), 17)
            self.text(str(i + 1), (x, 67), 15, WHITE if active else MUTED, True)
        self.button(self.buttons()['menu'], '返回主页', small=True)
        self.text(f'第 {self.game.level_index + 1} 关  /  {self.game.level.name}', (42, 118), 23)
        self.draw_board()
        self.card((752, 166, 306, 473), WHITE, 22, shadow=True)
        self.text('本关进度', (779, 188), 16, MUTED)
        self.text(f'{len(self.game.board):02d}', (777, 215), 62, INK)
        self.text(f'/ {len(self.game.level.arrows):02d} 支待出发', (878, 253), 17, MUTED)
        self.card((780, 302, 250, 6), '#E6ECE2', 3)
        fraction = 1 - len(self.game.board) / len(self.game.level.arrows)  # 已消除数占初始总数的比例
        if fraction:
            self.card((780, 302, max(6, round(250 * fraction)), 6), TEAL, 3)
        self.text('剩余失误机会', (780, 331), 16, MUTED)
        for i in range(self.game.level.max_mistakes):
            cx = 796 + i * 43
            color = '#C6885B' if i < self.game.mistakes_left else '#DCE2D8'
            pygame.draw.circle(self.screen, color, (cx, 388), 13)
            if i < self.game.mistakes_left:
                self.text('✓', (cx, 387), 15, WHITE, True)
        self.text(f'{self.game.mistakes_left} 次', (978, 377), 16, INK)
        self.button(self.buttons()['hint'], '提示   H', True, True)
        self.button(self.buttons()['restart'], '重开本题   R', small=True)
        self.button(self.buttons()['new'], '换一道题   N', small=True)
        self.card((752, 655, 306, 63), '#E8ECDF', 16)
        self.text('只看同一行或同一列。', (775, 664), 15, MUTED)
        self.text('前方没有箭头，就能飞出。', (775, 688), 15, MUTED)
        seconds = int(self.elapsed)
        self.text('H 提示  /  R 重开  /  N 换题  /  M 音效  /  Esc 主页', (40, 744), 13, MUTED)
        self.text(f'用时 {seconds // 60:02d}:{seconds % 60:02d}  ·  提示 {self.hints_used} 次',
                  (832, 744), 13, MUTED)

    def draw_result(self):  # 按胜负状态显示结果，末关不提供下一关
        won = self.game.status == 'won'
        final = won and self.game.level_index == len(self.game.levels) - 1
        self.text('ARROW AGAIN  /  一箭又一箭', (550, 65), 16, TEAL, True)
        self.card((280, 126, 540, 545), WHITE, 30, shadow=True)
        for i, (x, y) in enumerate([(225, 280), (860, 360), (228, 538), (862, 171)]):
            self.draw_tile((x, y), list(Direction)[i], 50)
        pygame.draw.circle(self.screen, '#E2EDDE' if won else '#F4E3D8', (550, 213), 48)
        if won:
            pygame.draw.lines(self.screen, TEAL, False, [(527, 214), (545, 231), (575, 194)], 6)
        else:
            self.arrow(self.screen, (550, 213), Direction.UP, RED, 21, 5)
            pygame.draw.line(self.screen, RED, (526, 180), (574, 180), 4)
        title = '最后一关，挑战成功！' if final else ('这一关，畅通无阻！' if won else '停一下，再想一想。')
        self.text(title, (550, 305), 32, INK, True)
        description = '每一箭都找到了自己的出口。' if won else '失误机会用完了，重新出发也没关系。'
        self.text(description, (550, 354), 17, MUTED, True)
        self.text(f'第 {self.game.level_index + 1} 关 · {self.game.level.name}', (550, 393), 16, TEAL, True)
        self.card((360, 428, 380, 49), '#F2F3EB', 12)
        seconds = int(self.elapsed)
        self.text(f'移出 {self.game.moves} 支    用时 {seconds // 60:02d}:{seconds % 60:02d}    提示 {self.hints_used} 次',
                  (550, 452), 15, MUTED, True)
        first = next(iter(self.buttons()))
        label = '下一关，继续出发' if first == 'next' else ('再玩一次本关' if won else '重新挑战本关')
        self.button(self.buttons()[first], label, True)
        self.button(self.buttons()['new'], '换一道题   N', small=True)
        self.button(self.buttons()['menu'], '返回主页', small=True)
        self.text('每一步，都让棋盘更开阔。', (550, 722), 15, MUTED, True)

    def draw(self):  # 清空旧画面，再绘制当前场景
        self.screen.fill(BG)
        if self.scene == 'menu':
            self.draw_menu()
        elif self.scene == 'game':
            self.draw_game()
        else:
            self.draw_result()
        label = '音效：开' if self.audio.enabled else '音效：关'
        if not self.audio.available:
            label = '音效不可用'
        self.button(self.buttons()['sound'], label, small=True)
        pygame.display.flip()  # 将本帧画面更新到实际窗口

    def run(self):  # 主循环：处理输入 → 更新时间 → 绘制画面
        clock = pygame.time.Clock()
        try:
            while self.running:
                dt = min(clock.tick(60) / 1000, 0.1)  # 约 60 FPS；毫秒转秒，卡顿后最多推进 0.1 秒
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update(dt)
                self.draw()
        finally:
            pygame.quit()  # 正常关闭或异常退出时都释放资源
