# 随机题生成与可解性

第二版不再使用固定题目。三个难度分别是 5×5 / 12 支、6×6 / 22 支、7×7 / 33 支，每题包含四种方向。不存在适用于所有新题的固定通关坐标。

## 为什么随机题一定有解

`generate_level()` 先随机抽取互不重复的格子，再在临时集合上逐步“剥离”格子：

1. 找出至少一个方向上没有其他剩余格子的候选项。
2. 随机选择候选格子，并把这个可离开的方向保存为该格的箭头方向。
3. 从临时集合移除它，继续处理剩余格子。

任何非空有限格子集合都有最上、最下、最左和最右的格子，所以每一步一定存在候选；即使限定一个方向，也总能找到朝该方向的极端格子。前四步优先补齐尚未使用的方向，保证四向均出现。后续优先选择会被已剥离格子阻挡的朝向，形成消除的先后关系。

真正游玩时，按照剥离顺序消除：前面已经消除的格子不再阻挡，后面尚未消除的格子在选择方向时已被检查。因此每一步都合法，整题可解。生成过程每轮至少移除一个格子，不需要无限随机重试。

`solve()` 是独立的验证工具：只使用实际路径检测在棋盘副本上求解，不读取生成器的剥离顺序。测试还把求解结果逐个传入 `Game.click()`，验证实际游戏最终为 `won`。

## 重开与换题

- `restart()` 从本局保存的不可变 `Level.rows` 恢复，所以布局保持不变。
- `new_puzzle()` 在当前难度生成新的 `Level`，然后重置次数、状态和进度。
- `load_level()` 从主页开始或进入下一关时生成新题。
- 正常 `Game()` 不固定种子；测试可传入 `Game(seed=42)` 复现相同的生成和操作序列。

## 复现一组三个难度的题目

在项目根目录运行以下 Python 代码：

```python
from arrow_game.model import Game, solve

game = Game(seed=42)  # 固定种子只用于测试，普通启动不指定种子。
for index in range(3):
    game.load_level(index)
    order = solve(game.level)
    assert order is not None
    print(index + 1, game.level.rows)
    print([(row + 1, col + 1) for row, col in order])  # 显示从 1 开始的行列坐标。
    for position in order:
        assert game.click(*position).kind == "removed"
    assert game.status == "won" and game.mistakes_left == 3
```

第二版测试使用每档难度 100 个种子，共 300 题，全部通过尺寸、箭头数、四向覆盖、求解和逐步通关检查。运行 `python tools/run_checks.py` 可复现，实际报告见 [test-results.txt](test-results.txt)。自动回放不等同于学生本人试玩。
