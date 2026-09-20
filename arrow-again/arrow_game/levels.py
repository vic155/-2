"""固定关卡数据；点号表示空格，U/D/L/R 表示四种箭头方向。"""

from __future__ import annotations

from dataclasses import dataclass
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


LEVELS: tuple[Level, ...] = (  # 按游戏顺序排列；新增关卡还需检查首页卡片等固定布局。
    Level(  # 第一关 5×5：较多空格，学习直接消除与阻挡规则。
        name="初见方向",
        subtitle="观察方向，从通向边界的箭头开始。",
        rows=(
            "R.URD",
            "L..D.",
            "U.R.D",
            "..LL.",
            "....R",
        ),
    ),
    Level(  # 第二关 6×6：提高密度，先消除阻挡者再处理后面的箭头。
        name="回旋小径",
        subtitle="解除外围阻挡，让回旋的路径逐渐打开。",
        rows=(
            "UL...L",
            "D.LLL.",
            "DD...U",
            "D.R.UU",
            ".R.RU.",
            "RRR.RU",
        ),
    ),
    Level(  # 第三关 7×7：增加连续阻挡，反复找出口、消除、重新观察。
        name="层层解围",
        subtitle="从外围深入中心，耐心拆解每一层阻挡。",
        rows=(
            "UL.LLLL",
            "DLLL..U",
            "D...L.U",
            "DDD.UU.",
            "..R.UUU",
            "..R.RUU",
            "RR.RRRU",
        ),
    ),
)
