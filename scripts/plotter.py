#!/usr/bin/env python3
"""plotter.py – ホットピクセル特性解析の可視化モジュール

analyzer.py で算出した Jaccard 係数時系列および出現頻度データを、
論文・レポートに直接掲載可能な高品質グラフとして出力する。

出力グラフ:
1. **Jaccard 時系列プロット** – Fixed-Baseline と Adjacent-Step の2系列を重畳
2. **出現頻度ヒストグラム** – 固定型と変動型の二峰性を可視化

スタイルには SciencePlots (ieee スタイル) を優先的に使用し、
インストールされていない場合はフォールバックスタイルを適用する。

Usage
-----
    python plotter.py ../data/run_continuous
    python plotter.py ../data/run_continuous --output ../figures --dpi 300
    python plotter.py ../data/run_reboot --pattern "hp_reboot*.txt" --interval 0

Authors
-------
    Auto-generated for M1 Research – Event Camera Hot Pixel Characterization
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# analyzer.py と同じディレクトリにあることを前提にインポート
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyzer import AnalysisResult, analyze_timeseries, summarize_frequency


# ---------------------------------------------------------------------------
# スタイル設定
# ---------------------------------------------------------------------------

def _apply_style() -> None:
    """SciencePlots が利用可能であれば ieee スタイルを適用する。
    インストールされていない場合はフォールバックのカスタムスタイルを適用。
    """
    try:
        import scienceplots  # noqa: F401
        plt.style.use(["science", "ieee"])
        print("[INFO] SciencePlots (science + ieee) スタイルを適用しました。")
    except (ImportError, OSError):
        # SciencePlots がない場合のフォールバック
        plt.rcParams.update({
            "figure.figsize": (7, 4.5),
            "figure.dpi": 150,
            "axes.grid": True,
            "axes.linewidth": 0.8,
            "grid.alpha": 0.3,
            "grid.linewidth": 0.5,
            "font.size": 11,
            "font.family": "serif",
            "legend.fontsize": 9,
            "legend.framealpha": 0.9,
            "lines.linewidth": 1.8,
            "lines.markersize": 5,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
        })
        print("[INFO] フォールバックスタイルを適用しました（SciencePlots 未検出）。")


# ---------------------------------------------------------------------------
# カラーパレット
# ---------------------------------------------------------------------------

# 色覚多様性に配慮した2色パレット (Tol's Bright)
COLOR_FIXED = "#4477AA"   # Steel Blue – Fixed-Baseline
COLOR_ADJ   = "#EE6677"   # Coral Red  – Adjacent-Step
COLOR_BAR   = "#228833"   # Emerald    – Histogram bars
COLOR_FIXED_PIXEL = "#CCBB44"  # Gold – Fixed pixels highlight


# ---------------------------------------------------------------------------
# プロット関数
# ---------------------------------------------------------------------------

def plot_jaccard_timeseries(
    result: AnalysisResult,
    output_dir: str | Path = ".",
    interval_sec: float = 30.0,
    dpi: int = 300,
    filename: str = "jaccard_timeseries.png",
) -> Path:
    """Jaccard 係数の時系列変化を折れ線グラフとして出力する。

    横軸は時間（秒→分変換）またはインデックス。
    Fixed-Baseline と Adjacent-Step の2系列を重ねて描画する。

    Parameters
    ----------
    result : AnalysisResult
        analyzer.analyze_timeseries() の戻り値。
    output_dir : str or Path
        出力先ディレクトリ。
    interval_sec : float
        測定間隔（秒）。0 の場合はインデックス表記。
    dpi : int
        出力画像の解像度。
    filename : str
        出力ファイル名。

    Returns
    -------
    Path
        保存されたファイルのパス。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename

    n = len(result.pixel_sets)

    # 横軸の構築
    if interval_sec > 0:
        # Fixed-Baseline: index 1..N-1  → 時刻 interval_sec * i (秒)
        x_fixed = np.array([interval_sec * i for i in range(1, n)]) / 60.0
        # Adjacent-Step: 同じく index 0..N-2
        x_adj = np.array([interval_sec * (i + 0.5) for i in range(n - 1)]) / 60.0
        xlabel = "Elapsed time [min]"
    else:
        x_fixed = np.arange(1, n)
        x_adj = np.arange(0.5, n - 0.5)
        xlabel = "Measurement index"

    fig, ax = plt.subplots(figsize=(7, 4.2))

    ax.plot(
        x_fixed, result.fixed_baseline,
        marker="o", color=COLOR_FIXED, label="Fixed-Baseline",
        linewidth=1.8, markersize=4, zorder=3,
    )
    ax.plot(
        x_adj, result.adjacent_step,
        marker="s", color=COLOR_ADJ, label="Adjacent-Step",
        linewidth=1.8, markersize=4, zorder=3,
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Jaccard Index")
    ax.set_ylim(-0.02, 1.05)
    ax.set_title("Hot Pixel Stability – Jaccard Coefficient over Time")
    ax.legend(loc="best", frameon=True)
    ax.grid(True, alpha=0.3, linewidth=0.5)

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)

    print(f"[OK] Jaccard 時系列プロットを保存しました: {out_path}")
    return out_path


def plot_frequency_histogram(
    result: AnalysisResult,
    output_dir: str | Path = ".",
    dpi: int = 300,
    filename: str = "frequency_histogram.png",
) -> Path:
    """ホットピクセル出現頻度のヒストグラムを出力する。

    横軸は出現回数（1 ～ N）、縦軸はその回数だけ検出されたユニークピクセル数。
    固定型ホットピクセル（N/N 回出現）と変動型（低頻度）の二峰性が
    視覚的に識別できるように、最終ビンだけ色分けして強調する。

    Parameters
    ----------
    result : AnalysisResult
        analyzer.analyze_timeseries() の戻り値。
    output_dir : str or Path
        出力先ディレクトリ。
    dpi : int
        出力画像の解像度。
    filename : str
        出力ファイル名。

    Returns
    -------
    Path
        保存されたファイルのパス。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename

    n = len(result.pixel_sets)
    histogram = summarize_frequency(result.frequency, n)

    bins = sorted(histogram.keys())
    counts = [histogram[b] for b in bins]

    # 色配列: 最終ビン (全回出現=固定型) を別色で強調
    colors = []
    for b in bins:
        if b == n:
            colors.append(COLOR_FIXED_PIXEL)
        else:
            colors.append(COLOR_BAR)

    fig, ax = plt.subplots(figsize=(7, 4.2))

    bars = ax.bar(bins, counts, color=colors, edgecolor="white", linewidth=0.5, zorder=3)

    ax.set_xlabel("Detection frequency [times]")
    ax.set_ylabel("Number of unique pixels")
    ax.set_title(f"Hot Pixel Occurrence Frequency (N={n} measurements)")
    ax.grid(True, axis="y", alpha=0.3, linewidth=0.5)

    # x軸を整数ティックに
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    # 凡例を手動追加
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLOR_BAR, edgecolor="white", label="Transient"),
        Patch(facecolor=COLOR_FIXED_PIXEL, edgecolor="white",
              label=f"Fixed ({n}/{n})"),
    ]
    ax.legend(handles=legend_elements, loc="upper center", frameon=True)

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)

    print(f"[OK] 出現頻度ヒストグラムを保存しました: {out_path}")
    return out_path


def plot_hotpixel_count_timeseries(
    result: AnalysisResult,
    output_dir: str | Path = ".",
    interval_sec: float = 30.0,
    dpi: int = 300,
    filename: str = "hotpixel_count.png",
) -> Path:
    """各測定時点のホットピクセル総数の推移を折れ線グラフで出力する。

    温度上昇に伴うホットピクセル増加傾向の可視化に有用。

    Parameters
    ----------
    result : AnalysisResult
        analyzer.analyze_timeseries() の戻り値。
    output_dir : str or Path
        出力先ディレクトリ。
    interval_sec : float
        測定間隔（秒）。0 の場合はインデックス表記。
    dpi : int
        出力画像の解像度。
    filename : str
        出力ファイル名。

    Returns
    -------
    Path
        保存されたファイルのパス。
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / filename

    n = len(result.pixel_sets)

    if interval_sec > 0:
        x = np.array([interval_sec * i for i in range(n)]) / 60.0
        xlabel = "Elapsed time [min]"
    else:
        x = np.arange(n)
        xlabel = "Measurement index"

    fig, ax = plt.subplots(figsize=(7, 4.2))

    ax.plot(
        x, result.hot_pixel_counts,
        marker="^", color="#AA3377", linewidth=1.8, markersize=4, zorder=3,
    )

    ax.set_xlabel(xlabel)
    ax.set_ylabel("Hot pixel count")
    ax.set_title("Hot Pixel Count over Time")
    ax.grid(True, alpha=0.3, linewidth=0.5)

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)

    print(f"[OK] ホットピクセル数推移プロットを保存しました: {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    """コマンドラインからプロット生成を実行する。

    使用例::

        python plotter.py ../data/run_continuous
        python plotter.py ../data/run_continuous --output ../figures --dpi 300
        python plotter.py ../data/run_reboot --pattern "hp_reboot*.txt" --interval 0
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="ホットピクセル解析結果の可視化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
使用例:
  python plotter.py ../data/run_continuous
  python plotter.py ../data/run_continuous --output ../figures --dpi 300
  python plotter.py ../data/run_reboot --pattern "hp_reboot*.txt" --interval 0
""",
    )
    parser.add_argument(
        "data_dir",
        help="ホットピクセルファイルが格納されたディレクトリ",
    )
    parser.add_argument(
        "--pattern", default="hp_*.txt",
        help="ファイル名の glob パターン (default: hp_*.txt)",
    )
    parser.add_argument(
        "--output", "-o", default=".",
        help="グラフ画像の出力先ディレクトリ (default: カレントディレクトリ)",
    )
    parser.add_argument(
        "--interval", type=float, default=30.0,
        help="測定間隔（秒）。0 にするとインデックス表記 (default: 30)",
    )
    parser.add_argument(
        "--dpi", type=int, default=300,
        help="出力画像の解像度 (default: 300)",
    )
    args = parser.parse_args()

    _apply_style()

    try:
        result = analyze_timeseries(args.data_dir, pattern=args.pattern)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] {len(result.pixel_sets)} ファイルを読み込みました。")

    plot_jaccard_timeseries(
        result, output_dir=args.output,
        interval_sec=args.interval, dpi=args.dpi,
    )

    plot_frequency_histogram(
        result, output_dir=args.output, dpi=args.dpi,
    )

    plot_hotpixel_count_timeseries(
        result, output_dir=args.output,
        interval_sec=args.interval, dpi=args.dpi,
    )

    print("[INFO] 全グラフの生成が完了しました。")


if __name__ == "__main__":
    main()
