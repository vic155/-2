"""运行：python main.py。"""
import os
import sys
import argparse

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'  # 在导入前隐藏 Pygame 欢迎文字


def main():  # 解析启动参数，创建并运行游戏
    parser = argparse.ArgumentParser(description='一箭又一箭 · Arrow Again')
    parser.add_argument('--smoke-test', action='store_true', help='短暂显示开始页和棋盘后退出，用于验证打包结果')
    args = parser.parse_args()  # 识别可选的 --smoke-test 启动检查
    try:
        from arrow_game.app import GameApp  # 入口 → 界面 GameApp → 规则 Game
    except ModuleNotFoundError as error:
        if error.name == 'pygame':  # 只处理缺少图形库的情况
            print('缺少 pygame-ce，请先运行：python -m pip install -r requirements.txt')
            return 1  # 失败退出码：先安装依赖
        raise  # 其他导入异常继续报告，便于排查
    app = GameApp()  # 创建窗口与逻辑对象，初始为开始页
    if args.smoke_test:  # 只检查启动与资源加载，完整规则另有测试
        import pygame
        try:
            app.draw()  # 绘制开始页
            app.update(0.75)
            app.draw()  # 同时检查主页开场动画结束后的布局。
            event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=app.buttons()['start'].center)
            app.handle_event(event)  # 通过正式输入入口模拟点击开始
            app.update(1 / 60)  # 推进一帧，再绘制棋盘
            app.draw()
            assert app.scene == 'game' and len(app.game.board) == 12
            app.action('new')  # 打包检查覆盖随机出题、重开和音效开关。
            initial = app.game.board.copy()
            pos = app.game.hint()
            app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=app.cell_center(pos)))
            assert app.game.moves == 1
            app.action('restart')
            assert app.game.board == initial and app.animation is None
            app.action('sound')
            app.draw()
        finally:
            pygame.quit()  # 检查成功或失败都释放窗口资源
    else:
        app.run()  # 进入输入 → 更新 → 绘制的主循环
    return 0  # 正常结束


if __name__ == '__main__':  # 直接运行才启动；被 import 时不执行
    sys.exit(main())  # 把成功或失败的退出码交给操作系统
