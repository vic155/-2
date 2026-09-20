"""Rule tests and completion checks for all shipped levels.

Run from the project root with ``python -m unittest discover -v``.
T01--T06 correspond to the assignment's required test cases. These tests
exercise the actual game model, not graphical animation or human playtesting.
"""

import unittest

from arrow_game.levels import LEVELS, Level
from arrow_game.model import Direction, Game, find_blocker, solve  # 直接测试正式规则，无需窗口


def make_level(*rows, max_mistakes=3):  # 用最小布局单独验证一种规则
    return Level("测试关卡", "仅供自动化测试", tuple(rows), max_mistakes)


class RequiredBehaviorTests(unittest.TestCase):  # T01—T06：准备 → 操作 → 断言
    def test_t01_clear_path_removes_arrow(self):  # 成功消除后，其他箭头仍保留
        game = Game([make_level("RR")])
        result = game.click(0, 1)
        self.assertEqual(result.kind, "removed")
        self.assertEqual(result.position, (0, 1))
        self.assertEqual(result.direction, Direction.RIGHT)
        self.assertIsNone(result.blocker)
        self.assertNotIn((0, 1), game.board)
        self.assertEqual(game.mistakes_left, 3)
        self.assertEqual(game.moves, 1)
        self.assertEqual(game.status, "playing")

    def test_t02_blocked_arrow_stays_and_costs_one_mistake(self):  # 远处箭头也会阻挡
        game = Game([make_level("R...U")])
        initial = dict(game.board)
        result = game.click(0, 0)
        self.assertEqual(result.kind, "blocked")
        self.assertEqual(result.blocker, (0, 4))
        self.assertEqual(game.board, initial)
        self.assertEqual(game.mistakes_left, 2)
        self.assertEqual(game.moves, 0)

    def test_t03_all_four_outward_edges_remove_without_overflow(self):  # 覆盖四向边缘
        fixtures = [
            ((".U.", "...", "..."), (0, 1)),
            (("...", "...", ".D."), (2, 1)),
            (("...", "L..", "..."), (1, 0)),
            (("...", "..R", "..."), (1, 2)),
        ]
        for rows, position in fixtures:  # 逐个检查，失败时可定位具体方向
            with self.subTest(rows=rows):
                game = Game([make_level(*rows)])
                self.assertEqual(game.click(*position).kind, "removed")
                self.assertEqual(game.board, {})
                self.assertEqual(game.status, "won")
                self.assertEqual(game.mistakes_left, 3)

    def test_t04_clearing_level_enables_next_level(self):  # 切关有条件，末关不能越界
        levels = [make_level("R"), make_level("U", max_mistakes=4)]
        game = Game(levels)
        self.assertFalse(game.next_level())
        self.assertEqual(game.level_index, 0)
        self.assertEqual(game.click(0, 0).kind, "removed")
        self.assertEqual(game.status, "won")
        self.assertTrue(game.next_level())
        self.assertEqual(game.level_index, 1)
        self.assertEqual(game.board, levels[1].arrows)
        self.assertEqual(game.status, "playing")
        self.assertEqual(game.mistakes_left, 4)
        self.assertEqual(game.moves, 0)
        self.assertEqual(game.click(0, 0).kind, "removed")
        self.assertEqual(game.status, "won")
        self.assertFalse(game.next_level())
        self.assertEqual(game.level_index, 1)

    def test_t05_exhausted_mistakes_lose_and_allow_restart(self):  # 失败后锁定，重开后恢复
        game = Game([make_level("RL")])
        initial = dict(game.board)
        for remaining in (2, 1, 0):
            self.assertEqual(game.click(0, 0).kind, "blocked")
            self.assertEqual(game.mistakes_left, remaining)
        self.assertEqual(game.status, "lost")
        self.assertEqual(game.board, initial)
        self.assertEqual(game.click(0, 1).kind, "inactive")
        self.assertEqual(game.mistakes_left, 0)
        self.assertFalse(game.next_level())
        game.restart()
        self.assertEqual(game.board, initial)
        self.assertEqual(game.mistakes_left, 3)
        self.assertEqual(game.status, "playing")

    def test_t06_restart_restores_initial_layout_and_counters(self):  # 消除和碰撞后重开
        level = make_level("R.L", "U..", "..D")
        game = Game([level])
        initial = dict(game.board)
        self.assertEqual(game.click(2, 2).kind, "removed")
        self.assertEqual(game.click(0, 0).kind, "blocked")
        self.assertEqual(game.moves, 1)
        self.assertEqual(game.mistakes_left, 2)
        self.assertNotEqual(game.board, initial)
        game.restart()
        self.assertEqual(game.board, initial)
        self.assertEqual(game.board, level.arrows)
        self.assertEqual(game.moves, 0)
        self.assertEqual(game.mistakes_left, 3)
        self.assertEqual(game.status, "playing")


class PathDetectionTests(unittest.TestCase):  # 路径占用检测与阻挡者朝向无关
    def test_four_directions_detect_distant_arrows(self):
        fixtures = [
            (Direction.UP, (0, 2)),
            (Direction.DOWN, (4, 2)),
            (Direction.LEFT, (2, 0)),
            (Direction.RIGHT, (2, 4)),
        ]
        for direction, blocker in fixtures:
            with self.subTest(direction=direction):
                board = {(2, 2): direction, blocker: Direction.UP}
                self.assertEqual(find_blocker(board, (2, 2), 5, 5), blocker)

    def test_closest_blocker_is_reported_in_all_directions(self):  # 返回最近阻挡位置
        fixtures = [
            (Direction.UP, (1, 2), (0, 2)),
            (Direction.DOWN, (3, 2), (4, 2)),
            (Direction.LEFT, (2, 1), (2, 0)),
            (Direction.RIGHT, (2, 3), (2, 4)),
        ]
        for direction, near, far in fixtures:
            with self.subTest(direction=direction):
                board = {(2, 2): direction, far: Direction.DOWN, near: Direction.LEFT}
                self.assertEqual(find_blocker(board, (2, 2), 5, 5), near)

    def test_arrows_behind_and_in_other_rows_do_not_block(self):  # 排除后方与斜向箭头
        fixtures = [
            (Direction.UP, (3, 2), (1, 1)),
            (Direction.DOWN, (1, 2), (3, 3)),
            (Direction.LEFT, (2, 3), (1, 1)),
            (Direction.RIGHT, (2, 1), (3, 3)),
        ]
        for direction, behind, diagonal in fixtures:
            with self.subTest(direction=direction):
                board = {(2, 2): direction, behind: Direction.UP, diagonal: Direction.LEFT}
                self.assertIsNone(find_blocker(board, (2, 2), 5, 5))

    def test_rectangular_board_uses_separate_height_and_width(self):  # 行列上界不混用
        level = make_level(".....D", "R....U")
        self.assertEqual((level.height, level.width), (2, 6))
        self.assertEqual(find_blocker(level.arrows, (1, 0), 2, 6), (1, 5))
        self.assertEqual(find_blocker(level.arrows, (0, 5), 2, 6), (1, 5))

    def test_empty_position_has_no_blocker(self):
        self.assertIsNone(find_blocker({(0, 0): Direction.RIGHT}, (0, 1), 1, 2))


class StateAndInputTests(unittest.TestCase):  # 无效输入和辅助操作不应破坏状态
    def test_empty_and_outside_clicks_do_not_change_state(self):
        game = Game([make_level("R.R")])
        initial = dict(game.board)
        for position in ((0, 1), (-1, 0), (0, -1), (1, 0), (0, 3), (999, 999)):
            with self.subTest(position=position):
                self.assertEqual(game.click(*position).kind, "empty")
                self.assertEqual(game.board, initial)
                self.assertEqual(game.mistakes_left, 3)
                self.assertEqual(game.moves, 0)
                self.assertEqual(game.status, "playing")

    def test_second_click_on_removed_arrow_is_harmless(self):
        game = Game([make_level("RR")])
        self.assertEqual(game.click(0, 1).kind, "removed")
        self.assertEqual(game.click(0, 1).kind, "empty")
        self.assertEqual(game.moves, 1)
        self.assertEqual(game.mistakes_left, 3)
        self.assertEqual(len(game.board), 1)

    def test_won_game_is_locked_until_restart_or_next_level(self):
        game = Game([make_level("R")])
        game.click(0, 0)
        self.assertEqual(game.click(0, 0).kind, "inactive")
        self.assertEqual(game.moves, 1)
        self.assertEqual(game.mistakes_left, 3)
        self.assertEqual(game.board, {})
        game.restart()
        self.assertEqual(game.status, "playing")
        self.assertEqual(game.moves, 0)
        self.assertEqual(len(game.board), 1)

    def test_game_does_not_mutate_shared_level_data(self):  # 本局只能修改自己的副本
        level = make_level("RR")
        initial = dict(level.arrows)
        game = Game([level])
        game.click(0, 1)
        self.assertEqual(level.arrows, initial)
        another_game = Game([level])
        self.assertEqual(another_game.board, initial)
        copy_of_arrows = level.arrows
        copy_of_arrows.clear()
        self.assertEqual(level.arrows, initial)

    def test_hint_is_legal_and_does_not_modify_board_or_counters(self):  # 提示只查询
        game = Game([make_level("RR", "U.")])
        initial = dict(game.board)
        self.assertEqual(set(game.available_moves()), {(0, 1)})
        self.assertEqual(game.hint(), (0, 1))
        self.assertEqual(game.board, initial)
        self.assertEqual(game.mistakes_left, 3)
        self.assertEqual(game.moves, 0)
        self.assertEqual(game.status, "playing")
        self.assertEqual(game.click(*game.hint()).kind, "removed")

    def test_cycle_has_no_available_move_or_hint(self):
        game = Game([make_level("RL")])
        self.assertEqual(list(game.available_moves()), [])
        self.assertIsNone(game.hint())
        self.assertEqual(game.status, "playing")

    def test_load_level_resets_state_to_selected_level(self):
        levels = [make_level("RL"), make_level("U.D", max_mistakes=5)]
        game = Game(levels)
        game.click(0, 0)
        game.load_level(1)
        self.assertEqual(game.level_index, 1)
        self.assertEqual(game.level, levels[1])
        self.assertEqual(game.board, levels[1].arrows)
        self.assertEqual(game.mistakes_left, 5)
        self.assertEqual(game.moves, 0)
        self.assertEqual(game.status, "playing")


class LevelSolvabilityTests(unittest.TestCase):  # 验证正式关卡，而非仅验证测试布局
    def test_at_least_three_levels_with_all_four_directions(self):
        self.assertGreaterEqual(len(LEVELS), 3)
        for level in LEVELS:
            with self.subTest(level=level.name):
                self.assertEqual(set(level.arrows.values()), set(Direction))
                self.assertGreater(level.max_mistakes, 0)

    def test_every_shipped_solution_replays_to_win_without_mistakes(self):  # 实际回放求解顺序
        for level in LEVELS:
            with self.subTest(level=level.name):
                initial = dict(level.arrows)
                solution = solve(level)
                self.assertIsNotNone(solution, "Shipped level must have a valid solution")
                self.assertEqual(len(solution), len(initial))
                self.assertEqual(len(set(solution)), len(solution))
                self.assertEqual(level.arrows, initial)
                game = Game([level])
                for position in solution:
                    self.assertEqual(game.click(*position).kind, "removed", position)
                self.assertEqual(game.status, "won")
                self.assertEqual(game.board, {})
                self.assertEqual(game.moves, len(initial))
                self.assertEqual(game.mistakes_left, level.max_mistakes)

    def test_solver_reports_impossible_cycle(self):  # 互相阻挡时返回无解，模板不变
        level = make_level("RL")
        initial = dict(level.arrows)
        self.assertIsNone(solve(level))
        self.assertEqual(level.arrows, initial)

    def test_solver_reports_cycle_after_removing_independent_arrow(self):
        self.assertIsNone(solve(make_level("RL", "D.")))


if __name__ == "__main__":  # 单独运行测试，游戏启动不会执行此处
    unittest.main()
