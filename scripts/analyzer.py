#!/usr/bin/env python3
"""analyzer.py – ホットピクセル特性解析エンジン

Prophesee GenX320 イベントカメラのホットピクセル検出結果（座標リスト）を
時系列で読み込み、以下の数理統計指標を算出する。

1. **Jaccard 係数 (Jaccard Index)**
   2つの有限集合 A, B に対して
       J(A, B) = |A ∩ B| / |A ∪ B|
   を計算する。J = 1.0 は A と B が完全一致、J = 0.0 は共通要素なしを意味する。
   ホットピクセル座標の「固定度」を定量化するために使用する。

2. **Fixed-Baseline 比較**
   初回測定 a_1 を基準とし、(a_1, a_2), (a_1, a_3), ..., (a_1, a_N) の
   Jaccard 係数を算出する。時間経過に伴うドリフトの検出に有用。

3. **Adjacent-Step 比較**
   隣接する連続測定間 (a_1, a_2), (a_2, a_3), ..., (a_{N-1}, a_N) の
   Jaccard 係数を算出する。短期変動の検出に有用。

4. **出現頻度カウント**
   全 N 回の測定にわたり、各 (x, y) 座標が何回ホットピクセルとして検出
   されたかを集計する。全回出現 (N/N) は「固定型ホットピクセル」、
   低頻度のみは「変動型（間欠型）ホットピクセル」と分類できる。

Usage
-----
    from analyzer import load_hotpixel_file, jaccard_index, analyze_timeseries

Authors
-------
    Auto-generated for M1 Research – Event Camera Hot Pixel Characterization
"""

from __future__ import annotations

import glob
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# データ型
# ---------------------------------------------------------------------------

class AnalysisResult(NamedTuple):
    """時系列解析の結果をまとめて返すコンテナ。"""
    files: list[str]                    # 読み込んだファイルパスのリスト (時系列順)
    fixed_baseline: list[float]         # 初期値基準 Jaccard 係数の列
    adjacent_step: list[float]          # 隣接基準 Jaccard 係数の列
    frequency: dict[tuple[int, int], int]  # (x,y) → 出現回数
    pixel_sets: list[set[tuple[int, int]]]  # 各ファイルの座標集合
    hot_pixel_counts: list[int]         # 各時点のホットピクセル数


# ---------------------------------------------------------------------------
# パーサー
# ---------------------------------------------------------------------------

def load_hotpixel_file(filepath: str | Path) -> set[tuple[int, int]]:
    """Prophesee ホットピクセル検出結果ファイルをパースし、座標集合を返す。

    ファイル形式
    ----------
    - ``%`` で始まる行はコメント（メタデータ・ログ）としてスキップ。
    - データ行は ``X, Y`` 形式（カンマ区切り、前後にスペース可）。
    - 空行はスキップ。

    Parameters
    ----------
    filepath : str or Path
        ホットピクセルファイルのパス。

    Returns
    -------
    set of (int, int)
        ホットピクセル座標の集合。

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合。
    ValueError
        座標をパースできない不正な行が含まれている場合。
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"ホットピクセルファイルが見つかりません: {filepath}")

    coords: set[tuple[int, int]] = set()
    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()

            # 空行・コメント行をスキップ
            if not line or line.startswith("%"):
                continue

            # "X, Y" 形式をパース
            parts = line.split(",")
            if len(parts) != 2:
                raise ValueError(
                    f"{filepath}:{line_no}: 座標を解析できません "
                    f"(カンマ区切りの2値が必要): '{raw_line.rstrip()}'"
                )
            try:
                x = int(parts[0].strip())
                y = int(parts[1].strip())
            except ValueError as e:
                raise ValueError(
                    f"{filepath}:{line_no}: 整数への変換に失敗: "
                    f"'{raw_line.rstrip()}'"
                ) from e

            coords.add((x, y))

    return coords


# ---------------------------------------------------------------------------
# Jaccard 係数
# ---------------------------------------------------------------------------

def jaccard_index(set_a: set, set_b: set) -> float:
    """2つの集合の Jaccard 係数を計算する。

    Jaccard 係数（Jaccard similarity coefficient）は、2つの有限集合の
    類似度を [0, 1] の範囲で表す指標である。

        J(A, B) = |A ∩ B| / |A ∪ B|

    - J = 1.0 : A と B が完全に一致
    - J = 0.0 : A と B に共通要素なし

    特殊ケースとして、両集合が空の場合は慣例的に J = 1.0 を返す
    （空集合同士は「完全一致」とみなす）。

    Parameters
    ----------
    set_a : set
        比較対象の集合 A。
    set_b : set
        比較対象の集合 B。

    Returns
    -------
    float
        Jaccard 係数 (0.0 ～ 1.0)。
    """
    # 空集合同士 → 定義上 1.0
    if not set_a and not set_b:
        return 1.0

    intersection = len(set_a & set_b)
    union = len(set_a | set_b)

    return intersection / union


# ---------------------------------------------------------------------------
# ファイル探索
# ---------------------------------------------------------------------------

def discover_files(data_dir: str | Path, pattern: str = "hp_*.txt") -> list[Path]:
    """指定ディレクトリ内のホットピクセルファイルを名前順に列挙する。

    Parameters
    ----------
    data_dir : str or Path
        検索対象ディレクトリ。
    pattern : str
        glob パターン（デフォルト: ``hp_*.txt``）。

    Returns
    -------
    list of Path
        名前の辞書順にソートされたファイルパスのリスト。

    Raises
    ------
    FileNotFoundError
        ディレクトリが存在しない場合。
    ValueError
        パターンに一致するファイルが1つも見つからない場合。
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"データディレクトリが存在しません: {data_dir}")

    files = sorted(data_dir.glob(pattern))
    if not files:
        raise ValueError(
            f"'{pattern}' に一致するファイルが {data_dir} 内に見つかりません"
        )

    return files


# ---------------------------------------------------------------------------
# 時系列解析
# ---------------------------------------------------------------------------

def analyze_timeseries(data_dir: str | Path, pattern: str = "hp_*.txt") -> AnalysisResult:
    """時系列のホットピクセルデータを一括解析する。

    処理内容:
    1. ``data_dir`` からファイルを時系列順（名前順）に収集。
    2. 各ファイルをパースして座標集合に変換。
    3. Fixed-Baseline Jaccard 係数列を算出。
    4. Adjacent-Step Jaccard 係数列を算出。
    5. 出現頻度カウントを集計。

    Parameters
    ----------
    data_dir : str or Path
        ホットピクセルファイルが格納されたディレクトリ。
    pattern : str
        glob パターン（デフォルト: ``hp_*.txt``）。

    Returns
    -------
    AnalysisResult
        解析結果のコンテナ（NamedTuple）。
    """
    files = discover_files(data_dir, pattern)

    # 全ファイルをパースして座標集合のリストを構築
    pixel_sets: list[set[tuple[int, int]]] = []
    for fp in files:
        try:
            coords = load_hotpixel_file(fp)
        except (ValueError, IOError) as e:
            print(f"[WARNING] ファイルの読み込みをスキップしました: {fp} ({e})",
                  file=sys.stderr)
            continue
        pixel_sets.append(coords)

    if len(pixel_sets) < 2:
        raise ValueError(
            "Jaccard 解析には最低2つの有効なデータファイルが必要です "
            f"(有効ファイル数: {len(pixel_sets)})"
        )

    # ファイル名リスト (有効なもののみ; スキップ分は除外)
    valid_files = [str(fp) for fp in files[:len(pixel_sets)]]

    # 各時点のホットピクセル数
    hot_pixel_counts = [len(ps) for ps in pixel_sets]

    # --- Fixed-Baseline Jaccard 係数 ---
    # 基準: 最初の測定 a_1
    baseline = pixel_sets[0]
    fixed_baseline: list[float] = []
    for i in range(1, len(pixel_sets)):
        j = jaccard_index(baseline, pixel_sets[i])
        fixed_baseline.append(j)

    # --- Adjacent-Step Jaccard 係数 ---
    adjacent_step: list[float] = []
    for i in range(len(pixel_sets) - 1):
        j = jaccard_index(pixel_sets[i], pixel_sets[i + 1])
        adjacent_step.append(j)

    # --- 出現頻度カウント ---
    # 全データセットにわたり各座標が何回出現したかをカウント
    freq_counter: Counter[tuple[int, int]] = Counter()
    for ps in pixel_sets:
        for coord in ps:
            freq_counter[coord] += 1

    return AnalysisResult(
        files=valid_files,
        fixed_baseline=fixed_baseline,
        adjacent_step=adjacent_step,
        frequency=dict(freq_counter),
        pixel_sets=pixel_sets,
        hot_pixel_counts=hot_pixel_counts,
    )


def summarize_frequency(frequency: dict[tuple[int, int], int],
                        total_measurements: int) -> dict[int, int]:
    """出現頻度カウントを「頻度 → ピクセル数」のヒストグラム用データに変換する。

    Parameters
    ----------
    frequency : dict[(int, int), int]
        (x, y) → 出現回数のマッピング。
    total_measurements : int
        全測定回数 N（ヒストグラムの横軸上限）。

    Returns
    -------
    dict[int, int]
        freq_count → 該当ピクセル数。
        例: {1: 45, 2: 12, ..., 30: 83} は、
        「1回だけ出現した座標が45個、30回全部で出現した座標が83個」を意味する。
    """
    histogram: dict[int, int] = {}
    for count in frequency.values():
        histogram[count] = histogram.get(count, 0) + 1

    # 1 ～ total_measurements の全ビンを0で埋める（グラフ描画用）
    for i in range(1, total_measurements + 1):
        histogram.setdefault(i, 0)

    return histogram


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    """コマンドラインから解析を実行するエントリーポイント。

    使用例::

        python analyzer.py ../data/run_continuous
        python analyzer.py ../data/run_reboot --pattern "hp_reboot*.txt"
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="ホットピクセル時系列 Jaccard 解析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
使用例:
  python analyzer.py ../data/run_continuous
  python analyzer.py ../data/run_reboot --pattern "hp_reboot*.txt"
""",
    )
    parser.add_argument(
        "data_dir",
        help="ホットピクセルファイルが格納されたディレクトリ",
    )
    parser.add_argument(
        "--pattern",
        default="hp_*.txt",
        help="ファイル名のglobパターン (default: hp_*.txt)",
    )
    args = parser.parse_args()

    try:
        result = analyze_timeseries(args.data_dir, pattern=args.pattern)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    n = len(result.pixel_sets)
    print(f"=== ホットピクセル時系列解析結果 ===")
    print(f"有効データ数: {n} ファイル")
    print()

    # ホットピクセル数の推移
    print("--- 各時点のホットピクセル数 ---")
    for i, (fp, cnt) in enumerate(zip(result.files, result.hot_pixel_counts)):
        print(f"  [{i:3d}] {os.path.basename(fp):>30s}  →  {cnt:5d} pixels")
    print()

    # Fixed-Baseline Jaccard
    print("--- Fixed-Baseline Jaccard 係数 (基準: 最初の測定) ---")
    for i, j in enumerate(result.fixed_baseline, start=1):
        print(f"  J(a_0, a_{i:02d}) = {j:.6f}")
    print()

    # Adjacent-Step Jaccard
    print("--- Adjacent-Step Jaccard 係数 ---")
    for i, j in enumerate(result.adjacent_step):
        print(f"  J(a_{i:02d}, a_{i + 1:02d}) = {j:.6f}")
    print()

    # 出現頻度ヒストグラム
    histogram = summarize_frequency(result.frequency, n)
    print(f"--- 出現頻度ヒストグラム (全{n}回中) ---")
    for freq in sorted(histogram.keys()):
        count = histogram[freq]
        bar = "█" * min(count, 60)
        print(f"  {freq:3d}回: {count:5d} pixels  {bar}")

    # 固定型・変動型の要約
    total_unique = len(result.frequency)
    fixed_count = histogram.get(n, 0)
    transient_count = total_unique - fixed_count
    print()
    print(f"--- 要約 ---")
    print(f"  ユニーク座標総数 : {total_unique}")
    print(f"  固定型 ({n}/{n}回出現): {fixed_count}")
    print(f"  変動型 (1〜{n - 1}回出現): {transient_count}")
    if total_unique > 0:
        print(f"  固定率: {fixed_count / total_unique * 100:.1f}%")


if __name__ == "__main__":
    main()
