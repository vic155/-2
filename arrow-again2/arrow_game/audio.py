"""短音效播放；音频设备不可用时自动保持静音，游戏仍可运行。"""
from pathlib import Path

import pygame


class SoundEffects:
    def __init__(self, directory: Path):
        self.enabled = True
        self.available = False
        self.sounds = {}
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            for name in ("click", "removed", "blocked", "won", "lost"):
                sound = pygame.mixer.Sound(str(directory / f"{name}.wav"))
                sound.set_volume(0.35)  # 短促、较轻的提示，避免连续点击时音量过大。
                self.sounds[name] = sound
            self.available = True
        except (pygame.error, OSError):
            self.sounds.clear()  # 缺少设备或资源时禁用音效，不影响规则和动画。

    def play(self, name: str):
        if not self.enabled or not self.available:
            return None
        if pygame.mixer.get_init() is None:
            self.available = False  # 设备已关闭时不能再调用旧 Sound，避免底层库异常。
            return None
        try:
            return self.sounds[name].play()  # 后台播放，不阻塞游戏主循环。
        except pygame.error:
            self.available = False
            return None

    def toggle(self) -> None:
        if not self.available:
            return
        if pygame.mixer.get_init() is None:
            self.available = False
            return
        self.enabled = not self.enabled
        if not self.enabled:
            try:
                for sound in self.sounds.values():
                    sound.stop()  # 静音时也停止已经响起的音效。
            except pygame.error:
                self.available = False
