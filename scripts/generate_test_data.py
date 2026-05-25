#!/usr/bin/env python3
"""ダミーのホットピクセルデータを生成するテストヘルパー。

GenX320 (320x320) を想定し、固定型・変動型のホットピクセルを
シミュレートした30ファイルを data/run_continuous/ に生成する。
"""
import random
from pathlib import Path

random.seed(42)

SENSOR_W, SENSOR_H = 320, 320
NUM_FILES = 30
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "run_continuous"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- 固定型ホットピクセル (全30回出現) ---
fixed_pixels = set()
while len(fixed_pixels) < 80:
    fixed_pixels.add((random.randint(0, SENSOR_W - 1), random.randint(0, SENSOR_H - 1)))

# --- 変動型ホットピクセルのプール (各ファイルで部分的に出現) ---
transient_pool = set()
while len(transient_pool) < 200:
    coord = (random.randint(0, SENSOR_W - 1), random.randint(0, SENSOR_H - 1))
    if coord not in fixed_pixels:
        transient_pool.add(coord)

transient_list = list(transient_pool)

for i in range(NUM_FILES):
    ts = f"20260525_{i * 30:04d}"
    filename = OUTPUT_DIR / f"hp_{ts}.txt"

    # 温度上昇に伴い変動型が徐々に増加するシミュレーション
    num_transient = random.randint(10, 30 + i * 3)
    transient_sample = set(random.sample(transient_list, min(num_transient, len(transient_list))))

    all_pixels = fixed_pixels | transient_sample

    with open(filename, "w") as f:
        f.write("% Proprietary info or logs\n")
        f.write(f"% Width: {SENSOR_W}, Height: {SENSOR_H}\n")
        f.write(f"% Measurement index: {i}\n")
        for x, y in sorted(all_pixels):
            f.write(f"{x}, {y}\n")

    print(f"  Generated: {filename.name}  ({len(all_pixels)} pixels)")

print(f"\nDone: {NUM_FILES} files written to {OUTPUT_DIR}")
