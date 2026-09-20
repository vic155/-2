"""不依赖图形库的游戏规则，可直接用 unittest 测试。

坐标统一采用 (row, col)，即先行后列，并从 0 开始计数。
棋盘只保存仍存在的箭头；删除字典中的位置即表示箭头已离开。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Mapping, Sequence

from .levels import LEVEL_SPECS, Level, generate_level  # 规则层不依赖界面，测试时无需打开窗口。

Position = tuple[int, int]  # 坐标类型别名：(行, 列)，本身不会创建棋盘。


class Direction(str, Enum):  # 将关卡中的单字母表示为有名称的方向。
    UP = "U"
    DOWN = "D"
    LEFT = "L"
    RIGHT = "R"

    @property
    def delta(self) -> tuple[int, int]:
        """屏幕行号向下增长，因此向上是 (-1, 0)。"""
        return {  # (dr, dc) 是前进一格的行列变化，四个方向共用扫描逻辑。
            Direction.UP: (-1, 0),
            Direction.DOWN: (1, 0),
            Direction.LEFT: (0, -1),
            Direction.RIGHT: (0, 1),
        }[self]


@dataclass(frozen=True)  # 禁止改写结果对象的字段，供界面只读使用。
class MoveResult:
    """一次点击的结果，界面据此播放飞出或碰撞动画。"""

    kind: str  # inactive / empty / blocked / removed：无效、空格、阻挡、消除。
    position: Position
    direction: Direction | None = None  # 空格没有方向。
    blocker: Position | None = None  # 成功消除时没有阻挡者。


def find_blocker(
    board: Mapping[Position, Direction],
    position: Position,
    height: int,
    width: int,
) -> Position | None:
    """从箭头前方一格扫描至边界，返回最近的阻挡者。

    阻挡只与格子是否被占据有关，与阻挡箭头朝向无关。
    越界前停止，所以位于边缘且朝向棋盘外的箭头可以直接离开。
    空位置没有需要检测的箭头，返回 None。
    """
    direction = board.get(position)
    if direction is None:
        return None
    dr, dc = direction.delta
    row, col = position
    row += dr  # 先前进一步，跳过箭头自身。
    col += dc
    while 0 <= row < height and 0 <= col < width:  # 先检查边界；朝外的边缘箭头直接跳过循环。
        if (row, col) in board:  # 字典只存箭头位置；是否阻挡与其朝向无关。
            return row, col
        row += dr
        col += dc
    return None


def solve(level: Level) -> list[Position] | None:
    """在棋盘副本上贪心求解；有解返回完整消除顺序，否则返回 None。

    每次选择按行列排序的第一个可消除箭头，结果可复现。
    删除箭头不会添加新的阻挡，因此不会把原本可消除的箭头变为
    不可消除。故只要存在解，任选当前可消除箭头都不会破坏可解性。
    若剩余箭头全部被阻挡，就没有合法的下一步。
    """
    board = level.arrows  # 获取独立字典，求解不会改动模板或正在玩的棋盘。
    order: list[Position] = []
    while board:
        available = next(  # 取第一个可消除位置；全被阻挡则返回 None。
            (
                position
                for position in sorted(board)
                if find_blocker(board, position, level.height, level.width) is None
            ),
            None,
        )
        if available is None:
            return None  # 仍有箭头却无合法操作，说明剩余布局无解。
        order.append(available)
        del board[available]  # 删除只会减少阻挡，因此贪心求解无需回溯。
    return order


class Game:  # app.py 调用此类，再将状态和操作结果画成界面。
    """管理当前关卡状态；动画和鼠标坐标转换由界面模块负责。"""

    def __init__(self, levels: Sequence[Level] | None = None, *, seed: int | None = None) -> None:
        self.random_mode = levels is None  # 默认随机出题；测试仍可传入明确的小关卡。
        self._rng = Random(seed)  # 独立随机源，不干扰其他对象；种子用于复现问题。
        self.levels = (tuple(generate_level(i, rng=self._rng) for i in range(len(LEVEL_SPECS)))
                       if self.random_mode else tuple(levels))
        if not self.levels:
            raise ValueError("游戏至少需要一个关卡")
        self.level_index = 0
        self.board: dict[Position, Direction] = {}  # 本局可修改的状态，界面直接读取。
        self.mistakes_left = 0
        self.status = "playing"
        self.moves = 0  # 只统计成功消除数，空格和碰撞不计数。
        self.restart()  # 初始化与重开共用恢复逻辑，保证初始状态一致。

    @property
    def level(self) -> Level:
        return self.levels[self.level_index]  # 通过 game.level 读取当前模板，不复制或修改它。

    def click(self, row: int, col: int) -> MoveResult:
        position = (row, col)  # 输入为网格坐标，由 app.py 从鼠标像素坐标转换。
        if self.status != "playing":  # 游戏结束后不再修改状态或扣次数。
            return MoveResult("inactive", position)
        direction = self.board.get(position)
        if direction is None:
            return MoveResult("empty", position)  # 点空格不改变状态，也不扣次数。
        blocker = find_blocker(self.board, position, self.level.height, self.level.width)
        if blocker is not None:
            self.mistakes_left -= 1  # 每次点击只扣一次，动画不能再次触发此逻辑。
            if self.mistakes_left == 0:
                self.status = "lost"
            return MoveResult("blocked", position, direction, blocker)
        del self.board[position]  # 立即更新逻辑；app.py 根据结果继续绘制飞出动画。
        self.moves += 1
        if not self.board:
            self.status = "won"  # 标记通关；界面展示结果后，由玩家操作进入下一关。
        return MoveResult("removed", position, direction)

    def restart(self) -> None:
        """从不可变模板恢复，避免重开时使用已被删改的棋盘。"""
        self.board = self.level.arrows  # 保持当前关编号；计时和动画由界面重置。
        self.mistakes_left = self.level.max_mistakes
        self.status = "playing"
        self.moves = 0

    def load_level(self, index: int) -> None:  # index 从 0 开始。
        if not isinstance(index, int) or not 0 <= index < len(self.levels):  # 先校验，避免非法编号改变状态。
            raise ValueError("关卡编号超出范围")
        if self.random_mode:
            self._generate_at(index)  # 从主页开始或进入下一关时生成新题。
        self.level_index = index
        self.restart()

    def _generate_at(self, index: int) -> None:
        level = generate_level(index, rng=self._rng)
        self.levels = self.levels[:index] + (level,) + self.levels[index + 1:]  # 仅替换目标模板。

    def new_puzzle(self) -> None:
        """当前难度重新出题；restart 则始终恢复同一道题。"""
        if self.random_mode:
            self._generate_at(self.level_index)
        self.restart()

    def next_level(self) -> bool:
        """仅通关后允许进入下一关；最终关通关后保留 won 状态。"""
        if self.status != "won" or self.level_index + 1 >= len(self.levels):
            return False  # 告知界面切关未成功。
        self.load_level(self.level_index + 1)  # 切换成功时同时重置本局状态。
        return True

    def available_moves(self) -> list[Position]:  # 提供全部安全操作，不修改棋盘。
        if self.status != "playing":
            return []
        return [
            position
            for position in sorted(self.board)  # 按行列排序，让提示与测试结果可复现。
            if find_blocker(self.board, position, self.level.height, self.level.width) is None
        ]

    def hint(self) -> Position | None:
        """只返回提示，不更改棋盘、次数或状态。"""
        available = self.available_moves()  # 获取安全位置，供界面高亮，不自动点击。
        return available[0] if available else None  # 没有可用位置时返回 None。
