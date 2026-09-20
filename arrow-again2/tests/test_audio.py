"""验证真实 WAV 加载、静音和音频不可用时的容错。"""
import os
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import wave

import pygame
from arrow_game.audio import SoundEffects

SOUNDS = Path(__file__).resolve().parents[1] / "assets" / "sounds"


class SoundTests(unittest.TestCase):
    def tearDown(self):
        pygame.mixer.quit()

    def test_bundled_wavs_are_non_silent_and_load_and_play(self):
        audio = SoundEffects(SOUNDS)
        self.assertTrue(audio.available)
        for name in ("click", "removed", "blocked", "won", "lost"):
            with self.subTest(name=name):
                with wave.open(str(SOUNDS / f"{name}.wav"), "rb") as source:
                    self.assertEqual(source.getnchannels(), 1)
                    self.assertEqual(source.getsampwidth(), 2)
                    data = source.readframes(source.getnframes())
                samples = struct.unpack(f"<{len(data) // 2}h", data)
                self.assertGreater(max(samples), 1000)
                self.assertLess(min(samples), -1000)
                self.assertEqual((samples[0], samples[-1]), (0, 0))
                channel = audio.play(name)
                self.assertIsNotNone(channel)
                self.assertTrue(channel.get_busy())
                channel.stop()

    def test_mute_stops_playback_and_unmute_restores_it(self):
        audio = SoundEffects(SOUNDS)
        channel = audio.play("won")
        audio.toggle()
        self.assertFalse(channel.get_busy())
        self.assertIsNone(audio.play("click"))
        audio.toggle()
        self.assertIsNotNone(audio.play("click"))

    def test_missing_resource_disables_audio_without_crashing(self):
        audio = SoundEffects(SOUNDS / "missing")
        self.assertFalse(audio.available)
        self.assertIsNone(audio.play("removed"))
        audio.toggle()

    def test_device_failure_and_device_loss_are_safe(self):
        with patch("pygame.mixer.init", side_effect=pygame.error("No device")):
            audio = SoundEffects(SOUNDS)
        self.assertFalse(audio.available)
        audio = SoundEffects(SOUNDS)
        pygame.mixer.quit()
        self.assertIsNone(audio.play("blocked"))
        self.assertFalse(audio.available)
