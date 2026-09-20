"""随机关卡生成；点号表示空格，U/D/L/R 表示四种箭头方向。"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 运行时为 False，配合延迟注解避免循环导入。
    from .model import Direction, Position  # 反向依赖仅用于类型提示。


@dataclass(frozen=True)  # 禁止改写模板字段。
class Level:
    """不可变关卡模板；每次读取 arrows 都得到独立的可修改棋盘。"""

    name: str  # 界面展示的关卡名称。
    subtitle: str  # 界面展示的关卡说明。
    rows: tuple[str, ...]  # 元组与字符串保存初始布局，供规则层恢复棋盘。
    max_mistakes: int = 3  # 规则层据此设置失误机会。

    def __post_init__(self) -> None:  # 构造函数自动调用，尽早发现数据错误。
        if not self.rows or not self.rows[0]:  # 此处只检查格式，可解性由 model.solve 和测试验证。
            raise ValueError("关卡棋盘不能为空")
        if any(len(row) != len(self.rows[0]) for row in self.rows):
            raise ValueError("关卡各行必须等长")
        if any(char not in ".UDLR" for row in self.rows for char in row):
            raise ValueError("关卡只允许使用点号和 U/D/L/R")
        if all(char == "." for row in self.rows for char in row):
            raise ValueError("关卡至少需要一个箭头")
        if not isinstance(self.max_mistakes, int) or self.max_mistakes < 1:
            raise ValueError("失误机会必须是正整数")

    @property
    def height(self) -> int:
        return len(self.rows)  # 高度由行数决定，无须另存尺寸。

    @property
    def width(self) -> int:
        return len(self.rows[0])  # 宽度由每行字符数决定。

    @property
    def arrows(self) -> dict[Position, Direction]:
        from .model import Direction  # 读取属性时才导入，避免模块初始化时循环依赖。

        return {  # 每次构造独立字典，重开与求解的删除操作互不影响。
            (row, col): Direction(char)
            for row, line in enumerate(self.rows)  # enumerate 从 0 开始生成行列编号。
            for col, char in enumerate(line)
            if char != "."  # 跳过空格，只保存实际箭头。
        }


@dataclass(frozen=True)
class LevelSpec:
    """只保存难度参数，具体箭头布局在开始游戏时随机生成。"""

    name: str
    height: int
    width: int
    arrow_count: int


LEVEL_SPECS = (  # 三档难度保持原有棋盘尺寸和箭头数量。
    LevelSpec("初见方向", 5, 5, 12),
    LevelSpec("回旋小径", 6, 6, 22),
    LevelSpec("层层解围", 7, 7, 33),
)


def generate_level(index: int, *, rng: Random | None = None) -> Level:
    """随机选格子，再逐个剥离有出口的格子，为每一步指定可离开的方向。"""
    if not isinstance(index, int) or not 0 <= index < len(LEVEL_SPECS):
        raise ValueError("关卡编号超出范围")
    rng = rng if rng is not None else Random()  # 测试可注入固定种子，正式游戏每次随机。
    spec = LEVEL_SPECS[index]
    cells = [(row, col) for row in range(spec.height) for col in range(spec.width)]
    original = set(rng.sample(cells, spec.arrow_count))  # 抽样不重复，箭头数固定。
    remaining = set(original)
    rows = [["."] * spec.width for _ in range(spec.height)]
    deltas = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
    used = set()
    while remaining:
        choices = []
        for row, col in sorted(remaining):  # 排序让相同种子在不同进程中也能复现。
            for direction, (dr, dc) in deltas.items():
                r, c = row + dr, col + dc
                ray = []
                while 0 <= r < spec.height and 0 <= c < spec.width:
                    ray.append((r, c))
                    r, c = r + dr, c + dc
                if not any(pos in remaining for pos in ray):
                    choices.append(((row, col), direction, any(pos in original for pos in ray)))
        missing = set(deltas) - used
        if missing:
            choices = [choice for choice in choices if choice[1] in missing]  # 优先补齐四种方向。
        dependent = [choice for choice in choices if choice[2]]
        position, direction, _ = rng.choice(dependent or choices)  # 优先形成先后阻挡关系。
        rows[position[0]][position[1]] = direction
        remaining.remove(position)  # 此时前方没有剩余格子，剥离顺序就是一个合法解。
        used.add(direction)
    return Level(spec.name, "随机棋盘 · 重开保留本题，换题生成新布局。",
                 tuple("".join(row) for row in rows))
