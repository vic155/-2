"""Headless Pygame integration checks using actual input events and drawing.

These tests create a real SDL software surface, render all three screens, and
feed mouse/keyboard events through GameApp.handle_event. No Pillow is required.
This is automated UI verification, not a record of the student's own playtest.
"""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"  # 真实软件画布，不弹出桌面窗口
os.environ["SDL_AUDIODRIVER"] = "dummy"  # 无需音频设备
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import ast
from pathlib import Path
import unittest

import pygame

from arrow_game.app import ENTRANCE_SECONDS, GameApp, HEIGHT, WIDTH
from unittest.mock import patch

from arrow_game.levels import LEVEL_SPECS, Level
from arrow_game.model import Game, solve


class GameAppIntegrationTests(unittest.TestCase):
    def setUp(self):  # 每项测试创建新应用，避免状态相互影响
        self.app = GameApp(seed=42)

    def tearDown(self):  # 每项结束后释放 Pygame 资源
        pygame.quit()

    def mouse(self, point, button=1):  # 把屏幕坐标转成鼠标事件
        point = tuple(round(value) for value in point)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"pos": point, "button": button}
        )
        self.app.handle_event(event)  # 走正式界面的输入处理入口

    def key(self, key):
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": key}))

    def button(self, name):  # 按按钮中心点击，不硬编码坐标
        self.mouse(self.app.buttons()[name].center)

    def arrow(self, position):  # 由棋盘行列换算箭头中心
        self.mouse(self.app.cell_center(position))

    def render(self):
        self.app.draw()
        self.assertEqual(self.app.screen.get_size(), (WIDTH, HEIGHT))

    def finish_animation(self):  # 分别检查动画中途与结束后的画面
        self.assertIsNotNone(self.app.animation)
        self.app.update(0.20)
        self.render()
        self.app.update(0.30)
        self.render()

    def fixture(self, *rows):  # 简化棋盘，仍保留真实输入和渲染流程
        level = Level("界面测试", "事件与绘制测试", tuple(rows), 3)
        self.app.game = Game((level, level, level))  # 保留三关结构以匹配正式按钮逻辑
        self.app.reset_view()
        self.render()
        return level

    def test_mouse_selects_third_level_and_starts(self):  # 准备菜单 → 点击 → 检查目标关
        self.render()
        self.button("level2")
        self.assertEqual(self.app.selected_level, 2)
        self.assertEqual(self.app.scene, "menu")
        self.render()
        self.button("start")
        self.assertEqual(self.app.scene, "game")
        self.assertEqual(self.app.game.level_index, 2)
        self.assertEqual(self.app.game.board, self.app.game.level.arrows)
        self.assertEqual(len(self.app.game.board), LEVEL_SPECS[2].arrow_count)
        self.render()

    def test_bundled_font_covers_chinese_strings_in_game_source(self):
        source_root = Path(__file__).resolve().parents[1] / "arrow_game"  # 按文件定位源码
        source_files = list(source_root.rglob("*.py"))
        self.assertTrue(source_files, "No game source files found for glyph coverage")
        glyph_sources = {}  # 只收集源码字符串中的汉字，不包含注释
        for source in source_files:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for char in node.value:  # 覆盖常用汉字、扩展 A 和兼容字形
                        if ("\u3400" <= char <= "\u4dbf"
                                or "\u4e00" <= char <= "\u9fff"
                                or "\uf900" <= char <= "\ufaff"):
                            glyph_sources.setdefault(char, set()).add(source.name)
        self.assertTrue(glyph_sources, "No Chinese strings found for glyph coverage")
        font = self.app.font(20)
        for char, sources in sorted(glyph_sources.items()):
            with self.subTest(char=char, codepoint=f"U+{ord(char):04X}"):
                metric = font.metrics(char)[0]  # 缺字可能返回空白包围框，而非 None
                message = (
                    f"Bundled font is missing {char!r} used in {', '.join(sorted(sources))}; "
                    "regenerate the font subset after changing interface text"
                )
                self.assertIsNotNone(metric, message)
                self.assertGreater(metric[1] - metric[0], 0, message)  # 可见字形宽度必须大于零
                self.assertGreater(metric[3] - metric[2], 0, message)  # 可见字形高度必须大于零

    def test_enter_and_space_start_selected_third_level(self):
        for key in (pygame.K_RETURN, pygame.K_SPACE):
            with self.subTest(key=key):
                self.app.action("menu")
                self.button("level2")
                self.key(key)
                self.assertEqual(self.app.scene, "game")
                self.assertEqual(self.app.game.level_index, 2)
                self.render()

    def test_collision_animation_locks_rapid_repeated_clicks(self):  # 连点不重复扣次数
        level = self.fixture("RL")
        before = pygame.image.tobytes(self.app.screen, "RGB")
        self.arrow((0, 0))
        self.assertEqual(self.app.animation.kind, "blocked")
        self.assertEqual(self.app.animation.blocker, (0, 1))
        self.assertEqual(self.app.game.mistakes_left, 2)
        self.app.update(0.10)
        self.render()
        self.assertNotEqual(pygame.image.tobytes(self.app.screen, "RGB"), before)
        for _ in range(8):
            self.arrow((0, 0))
            self.arrow((0, 1))
        self.assertEqual(self.app.game.mistakes_left, 2)
        self.assertEqual(self.app.game.board, level.arrows)
        self.assertEqual(self.app.game.moves, 0)
        self.assertEqual(self.app.message_kind, "blocked")
        self.app.update(0.40)
        self.assertIsNone(self.app.animation)
        self.assertEqual(self.app.scene, "game")
        self.render()

    def test_last_arrow_finishes_flight_before_result_screen(self):  # 飞完再显示结果
        self.fixture("R")
        self.arrow((0, 0))
        self.assertEqual(self.app.game.status, "won")
        self.assertEqual(self.app.game.board, {})
        self.assertEqual(self.app.scene, "game")
        self.assertEqual(self.app.animation.kind, "removed")
        self.app.update(0.20)
        self.render()
        self.assertEqual(self.app.scene, "game")
        self.assertIsNotNone(self.app.animation)
        self.app.update(0.30)
        self.assertEqual(self.app.scene, "result")
        self.assertIsNone(self.app.animation)
        self.render()

    def test_restart_button_cancels_success_or_collision_animation(self):  # 重开取消旧动画
        for position in ((0, 1), (0, 0)):
            with self.subTest(position=position):
                level = self.fixture("RR")
                self.arrow(position)
                self.assertIsNotNone(self.app.animation)
                self.app.update(0.10)
                self.render()
                self.button("restart")
                self.assertIsNone(self.app.animation)
                self.assertEqual(self.app.game.board, level.arrows)
                self.assertEqual(self.app.game.mistakes_left, 3)
                self.assertEqual(self.app.game.moves, 0)
                self.assertEqual(self.app.elapsed, 0)
                self.app.update(0.60)
                self.assertEqual(self.app.scene, "game")
                self.assertEqual(self.app.game.board, level.arrows)
                self.render()

    def test_empty_cell_grid_edges_and_gaps_do_not_cost_mistakes(self):  # 检查点击边界
        self.button("start")
        initial = dict(self.app.game.board)
        grid, cell = self.app.grid_geometry()
        empty = next(
            (row, col)
            for row in range(self.app.game.level.height)
            for col in range(self.app.game.level.width)
            if (row, col) not in initial
        )
        points = [
            self.app.cell_center(empty),
            (grid.left - 1, grid.centery),
            (grid.right, grid.centery),
            (grid.centerx, grid.top - 1),
            (grid.centerx, grid.bottom),
            (grid.left, grid.top),
            (grid.left + 1, grid.top + cell // 2),
            (grid.left + cell, grid.top + cell // 2),
            (0, 0),
            (WIDTH - 1, HEIGHT - 1),
        ]
        for point in points:
            with self.subTest(point=point):
                self.mouse(point)
                self.assertEqual(self.app.game.board, initial)
                self.assertEqual(self.app.game.mistakes_left, 3)
                self.assertEqual(self.app.game.moves, 0)
                self.assertIsNone(self.app.animation)
        self.render()

    def test_right_mouse_button_does_not_remove_arrow(self):
        self.fixture("R")
        initial = dict(self.app.game.board)
        self.mouse(self.app.cell_center((0, 0)), button=3)
        self.assertEqual(self.app.game.board, initial)
        self.assertIsNone(self.app.animation)
        self.assertEqual(self.app.game.mistakes_left, 3)

    def test_failure_waits_for_collision_then_restart_button_recovers(self):  # 失败后可重开
        level = self.fixture("RL")
        for remaining in (2, 1, 0):
            self.arrow((0, 0))
            self.assertEqual(self.app.game.mistakes_left, remaining)
            self.assertEqual(self.app.scene, "game")
            self.finish_animation()
        self.assertEqual(self.app.game.status, "lost")
        self.assertEqual(self.app.scene, "result")
        self.assertIn("restart", self.app.buttons())
        self.assertNotIn("next", self.app.buttons())
        self.button("restart")
        self.assertEqual(self.app.scene, "game")
        self.assertEqual(self.app.game.status, "playing")
        self.assertEqual(self.app.game.board, level.arrows)
        self.assertEqual(self.app.game.mistakes_left, 3)
        self.assertEqual(self.app.game.moves, 0)
        self.render()

    def test_mouse_completes_all_three_levels_and_final_has_no_next(self):  # 完整三关回放
        self.button("start")
        for index in range(len(LEVEL_SPECS)):
            level = self.app.game.level  # 每次切关都重新生成，必须求解当前题目。
            with self.subTest(level=level.name):
                self.assertEqual(self.app.game.level_index, index)
                solution = solve(level)
                self.assertIsNotNone(solution)
                for position in solution:
                    self.arrow(position)
                    self.assertIsNotNone(self.app.animation)
                    self.assertEqual(self.app.animation.kind, "removed")
                    self.assertEqual(self.app.scene, "game")
                    self.finish_animation()
                self.assertEqual(self.app.scene, "result")
                self.assertEqual(self.app.game.status, "won")
                self.assertEqual(self.app.game.moves, len(level.arrows))
                self.assertEqual(self.app.game.mistakes_left, level.max_mistakes)
                self.assertEqual(self.app.game.board, {})
                if index < len(LEVEL_SPECS) - 1:
                    self.assertIn("next", self.app.buttons())
                    self.button("next")
                    self.assertEqual(self.app.scene, "game")
                    self.assertEqual(self.app.game.moves, 0)
                else:
                    self.assertNotIn("next", self.app.buttons())
                    self.assertIn("restart", self.app.buttons())
                    self.button("restart")
                    self.assertEqual(self.app.game.level_index, 2)
                    self.assertEqual(self.app.game.board, level.arrows)
                    self.assertEqual(self.app.scene, "game")
                    self.render()

    def test_hint_button_and_key_leave_board_and_mistakes_unchanged(self):  # 提示不改状态
        self.fixture("RR")
        initial = dict(self.app.game.board)
        self.button("hint")
        self.assertEqual(self.app.hint_position, (0, 1))
        self.assertEqual(self.app.hints_used, 1)
        self.render()
        self.key(pygame.K_h)
        self.assertEqual(self.app.hints_used, 2)
        self.assertEqual(self.app.game.board, initial)
        self.assertEqual(self.app.game.moves, 0)
        self.assertEqual(self.app.game.mistakes_left, 3)
        self.app.update(2.60)
        self.assertIsNone(self.app.hint_position)
        self.assertEqual(self.app.game.board, initial)
        self.render()

    def test_hint_is_ignored_during_flight(self):  # 动画期间忽略提示输入
        self.fixture("RR")
        self.arrow((0, 1))
        self.button("hint")
        self.key(pygame.K_h)
        self.assertEqual(self.app.hints_used, 0)
        self.assertIsNone(self.app.hint_position)
        self.assertEqual(self.app.game.moves, 1)
        self.finish_animation()

    def test_escape_cancels_old_animation_before_starting_new_game(self):  # 旧动画不影响新局
        level = self.fixture("R")
        self.arrow((0, 0))
        self.assertEqual(self.app.game.status, "won")
        self.app.update(0.10)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.app.scene, "menu")
        self.assertIsNone(self.app.animation)
        self.app.update(1.0)
        self.assertEqual(self.app.scene, "menu")
        self.render()
        self.button("start")
        self.assertEqual(self.app.game.board, level.arrows)
        self.assertEqual(self.app.game.status, "playing")
        self.app.update(0.60)
        self.assertEqual(self.app.scene, "game")
        self.assertEqual(self.app.game.board, level.arrows)
        self.assertEqual(self.app.game.moves, 0)
        self.render()

    def test_r_key_restarts_while_last_arrow_is_flying(self):
        level = self.fixture("R")
        self.arrow((0, 0))
        self.assertEqual(self.app.game.status, "won")
        self.key(pygame.K_r)
        self.assertIsNone(self.app.animation)
        self.assertEqual(self.app.game.status, "playing")
        self.assertEqual(self.app.game.board, level.arrows)
        self.app.update(1.0)
        self.assertEqual(self.app.scene, "game")
        self.render()

    def test_enter_uses_result_next_button(self):
        self.fixture("R")
        self.arrow((0, 0))
        self.finish_animation()
        self.assertEqual(self.app.scene, "result")
        self.key(pygame.K_RETURN)
        self.assertEqual(self.app.game.level_index, 1)
        self.assertEqual(self.app.scene, "game")
        self.assertEqual(self.app.game.status, "playing")
        self.render()

    def test_new_puzzle_button_cancels_animation_and_resets_view(self):
        self.button("start")
        initial = self.app.game.level.rows
        self.arrow(self.app.game.hint())
        self.assertIsNotNone(self.app.animation)
        self.button("new")
        self.assertNotEqual(self.app.game.level.rows, initial)
        self.assertIsNone(self.app.animation)
        self.assertIsNone(self.app.hint_position)
        self.assertEqual(self.app.elapsed, 0)
        self.assertEqual(self.app.game.moves, 0)
        self.assertEqual(self.app.game.mistakes_left, 3)
        self.app.update(0.6)
        self.assertEqual(self.app.scene, "game")
        self.render()

    def test_n_key_from_result_starts_fresh_puzzle_at_same_difficulty(self):
        self.button("start")
        original = self.app.game.level.rows
        for position in solve(self.app.game.level):
            self.arrow(position)
            self.app.update(0.5)
        self.assertEqual(self.app.scene, "result")
        self.key(pygame.K_n)
        self.assertNotEqual(self.app.game.level.rows, original)
        self.assertEqual(self.app.game.level_index, 0)
        self.assertEqual(self.app.scene, "game")
        self.render()

    def test_mute_button_and_key_persist_through_scene_changes(self):
        self.assertTrue(self.app.audio.available)
        self.button("sound")
        self.assertFalse(self.app.audio.enabled)
        self.button("start")
        self.button("restart")
        self.button("new")
        self.assertFalse(self.app.audio.enabled)
        self.key(pygame.K_m)
        self.assertTrue(self.app.audio.enabled)
        self.key(pygame.K_ESCAPE)
        self.render()
        self.assertTrue(self.app.audio.enabled)

    def test_arrow_and_result_sounds_fire_once_and_locked_clicks_are_silent(self):
        self.fixture("RR")
        with patch.object(self.app.audio, "play") as play:
            self.arrow((0, 0))
            play.assert_called_once_with("blocked")
            self.arrow((0, 0))
            self.app.update(0.5)
            play.assert_called_once_with("blocked")
            play.reset_mock()
            self.arrow((0, 1))
            play.assert_called_once_with("removed")
            self.app.update(0.5)
            self.arrow((0, 0))
            self.app.update(0.5)
            self.app.update(1)
            self.assertEqual([call.args[0] for call in play.call_args_list], ["removed", "removed", "won"])

    def test_game_remains_playable_without_audio_device(self):
        pygame.mixer.quit()
        with patch("pygame.mixer.init", side_effect=pygame.error("No audio device")):
            app = GameApp(seed=8)
        self.assertFalse(app.audio.available)
        app.action("sound")
        app.action("start")
        position = app.game.hint()
        app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=app.cell_center(position)))
        self.assertEqual(app.game.moves, 1)
        app.update(0.5)
        app.draw()

    def test_menu_arrow_can_fly_without_changing_game_or_difficulty(self):
        self.app.update(1)
        before = dict(self.app.game.board)
        selected = self.app.selected_level
        x, y, _ = self.app.menu_tile_pose(0)
        with patch.object(self.app.audio, "play") as play:
            self.mouse((x, y))
            self.mouse((x, y))
            play.assert_called_once_with("removed")
        self.assertIn(0, self.app.menu_flights)
        self.app.update(0.25)
        self.render()
        self.assertEqual(self.app.game.board, before)
        self.assertEqual(self.app.game.mistakes_left, 3)
        self.assertEqual(self.app.selected_level, selected)
        self.app.update(0.65)
        self.assertNotIn(0, self.app.menu_flights)
        self.assertEqual(self.app.scene, "menu")
        self.render()

    def test_first_click_during_board_entrance_is_accepted_immediately(self):
        self.button("start")
        self.app.update(0.15)
        position = self.app.game.hint()
        self.arrow(position)
        self.assertNotIn(position, self.app.game.board)
        self.assertEqual(self.app.game.moves, 1)
        self.assertEqual(self.app.animation.kind, "removed")
        self.assertEqual(self.app.entrance_age, ENTRANCE_SECONDS)
        self.render()

    def test_board_entrance_does_not_consume_play_time_or_mutate_board(self):
        self.button("start")
        initial = dict(self.app.game.board)
        self.app.update(0.3)
        self.render()
        self.assertEqual(self.app.elapsed, 0)
        self.assertEqual(self.app.game.board, initial)
        self.app.update(0.5)
        self.assertAlmostEqual(self.app.elapsed, 0.8 - ENTRANCE_SECONDS)
        self.assertEqual(self.app.game.board, initial)
        self.button("restart")
        self.assertEqual(self.app.elapsed, 0)
        self.assertEqual(self.app.entrance_age, 0)
        self.assertEqual(self.app.game.board, initial)


if __name__ == "__main__":  # 由 unittest 单独运行，不随游戏启动
    unittest.main()
