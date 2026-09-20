"""用标准库合成清脆的短音效；固定音高、快速衰减，避免低频滑音。"""
import math
from pathlib import Path
import struct
import wave

ROOT = Path(__file__).resolve().parents[1]
RATE = 44100
TONES = {  # 每个音符为开始时间、固定频率、时长、衰减时间、相对音量。
    "click": [(0.0, 2100, 0.055, 0.012, 0.65)],  # 轻巧的高音短点。
    "removed": [(0.0, 1568, 0.18, 0.038, 0.85), (0.035, 2352, 0.12, 0.024, 0.30)],
    "blocked": [(0.0, 1100, 0.07, 0.014, 0.70)],  # 单次轻敲，不使用低沉的下滑音。
    "won": [(0.0, 1568, 0.18, 0.04, 0.62), (0.07, 1976, 0.18, 0.04, 0.62),
            (0.14, 2352, 0.20, 0.045, 0.68)],
    "lost": [(0.0, 1320, 0.075, 0.016, 0.58), (0.065, 1100, 0.13, 0.027, 0.55)],
}


def main():
    directory = ROOT / "assets" / "sounds"
    directory.mkdir(parents=True, exist_ok=True)
    for name, notes in TONES.items():
        mixed = [0.0] * round(RATE * max(start + duration for start, _, duration, _, _ in notes))
        for start, frequency, duration, decay, gain in notes:
            offset = round(RATE * start)
            count = round(RATE * duration)
            for i in range(count):
                t = i / RATE
                fade = min(1, i / (RATE * 0.0015), (count - 1 - i) / (RATE * 0.008))
                tone = sum(weight * math.sin(2 * math.pi * frequency * ratio * t)
                           * math.exp(-t / (decay * sustain))
                           for ratio, weight, sustain in ((1, 1, 1), (2.4, 0.22, 0.45), (3.8, 0.08, 0.25)))
                mixed[offset + i] += gain * fade * tone  # 高频泛音迅速消退，留下短促的清亮尾音。
        peak = max(1.0, max(abs(value) for value in mixed))
        samples = [round(23000 * value / peak) for value in mixed]  # 保留余量，叠加音符也不削波。
        with wave.open(str(directory / f"{name}.wav"), "wb") as output:
            output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            output.writeframes(struct.pack(f"<{len(samples)}h", *samples))
        print(f"{name}.wav: {len(samples) / RATE:.2f}s")


if __name__ == "__main__":
    main()
