# Hot Pixel Characterization – Prophesee GenX320

> イベントカメラ（Prophesee GenX320）のホットピクセル固定・変動特性を定量的に調査するための実験・解析システム

## 概要

イベントカメラでは、ノイズ源となるホットピクセル（異常発振画素）が存在する。本プロジェクトでは、以下の2つの観点からホットピクセルの特性を調査する。

1. **連続駆動実験 (Continuous Run)**  
   電源投入後、30秒おきに30回（計15分間）ホットピクセルを測定し、時間経過（= 温度上昇）に伴う変化を観測する。

2. **再起動実験 (Reboot Cycle)**  
   カメラを再起動（電源サイクル）した直後にホットピクセルを測定し、起動間の再現性を確認する。

解析指標として **Jaccard 係数**（集合の類似度）および **出現頻度分析** を用い、ホットピクセルが「固定型」か「変動型」かを分類する。

---

## ディレクトリ構成

```text
hotpixel_characterization/
├── data/
│   ├── run_continuous/       # 連続駆動実験データ
│   └── run_reboot/           # 再起動実験データ
├── scripts/
│   ├── collect_data.sh       # データ収集スクリプト（半自動）
│   ├── analyzer.py           # Jaccard 解析・頻度カウントエンジン
│   └── plotter.py            # 論文品質グラフの可視化
├── requirements.txt          # Python 依存ライブラリ
└── README.md                 # 本ファイル
```

---

## セットアップ

### 前提条件

- **OS:** Ubuntu 22.04 LTS / Raspberry Pi OS 64-bit
- **Python:** 3.10 以上
- **Prophesee SDK (OpenEB / Metavision):** インストール済みで `metavision_active_pixel_detection` コマンドが利用可能
- **カメラ:** Prophesee GenX320 が USB 接続済み

### インストール

```bash
cd hotpixel_characterization
pip install -r requirements.txt
```

> [!NOTE]
> `SciencePlots` は論文風のグラフスタイルを提供するオプション依存です。インストールに失敗しても解析・可視化は正常に動作します。LaTeX がインストールされていない環境では SciencePlots の一部スタイルが使えない場合があります。

---

## 実験手順

### 事前準備

1. **遮光環境の構築**  
   - カメラのレンズキャップを装着するか、完全遮光ボックス内にカメラを設置する。
   - 環境光の漏れがないことを確認する（LED ランプ、画面反射等に注意）。

2. **暖機運転（ウォームアップ）**  
   - カメラを接続し、最低 **5分間** 通電した状態で待機する。
   - これにより、初期の急激な温度変化を避け、測定条件を安定させる。

3. **カメラ接続の確認**  
   ```bash
   # USB 接続の確認
   lsusb | grep -i prophesee

   # SDK がカメラを認識しているか確認
   metavision_viewer  # 映像が表示されることを確認したら Ctrl+C で終了
   ```

### 実験1: 連続駆動実験

30秒おきに30回、ホットピクセルを記録する。

```bash
cd hotpixel_characterization/scripts

# 30秒カウントダウン付き、30回測定
./collect_data.sh -n 30 -i 30 -d continuous
```

**操作フロー:**

1. スクリプトが `metavision_active_pixel_detection` を自動起動
2. GUI ウィンドウが開いたら、**スペースキー** を押して検出を実行
3. 検出完了後、GUI を閉じる（or 自動終了）
4. スクリプトが `result.txt` を検知し、タイムスタンプ付きでリネーム保存
5. 30秒カウントダウン後、次の測定へ
6. 全30回完了まで繰り返し

> [!TIP]
> `metavision_active_pixel_detection` が見つからない場合、スクリプトはダミーモードで動作し、手動で Enter を押して次に進むことができます。

### 実験2: 再起動実験

カメラの電源を切り→再投入した直後のホットピクセルを比較する。

```bash
./collect_data.sh -n 5 -i 0 -d reboot
```

**操作フロー:**

1. 初回測定を実施
2. **カメラの USB ケーブルを物理的に抜き、10秒待って再接続**
3. `lsusb` でカメラが再認識されたことを確認
4. Enter を押して次の測定を実行
5. 上記を必要回数繰り返す

> [!IMPORTANT]
> 再起動実験ではカウントダウンモード (`-i 0`) を推奨します。USB 再接続のタイミングは手動制御が必要です。

---

## 解析・可視化

### 解析の実行

```bash
cd hotpixel_characterization/scripts

# 連続駆動データの解析
python analyzer.py ../data/run_continuous

# 再起動データの解析
python analyzer.py ../data/run_reboot --pattern "hp_reboot*.txt"
```

**出力される解析結果:**
- 各時点のホットピクセル数
- Fixed-Baseline Jaccard 係数（初回基準の変化量）
- Adjacent-Step Jaccard 係数（隣接ステップ間の変化量）
- 出現頻度ヒストグラム（固定型 vs 変動型の分類）

### グラフの生成

```bash
# 連続駆動データのグラフ生成
python plotter.py ../data/run_continuous --output ../figures --dpi 300

# 再起動データのグラフ生成 (インデックス表記)
python plotter.py ../data/run_reboot --pattern "hp_reboot*.txt" --output ../figures --interval 0
```

**生成されるグラフ:**

| ファイル名 | 内容 |
|---|---|
| `jaccard_timeseries.png` | Fixed-Baseline / Adjacent-Step の Jaccard 係数推移 |
| `frequency_histogram.png` | ホットピクセル出現頻度の分布（固定型/変動型の二峰性） |
| `hotpixel_count.png` | ホットピクセル総数の時間推移 |

---

## 数理的背景

### Jaccard 係数 (Jaccard Index)

2つの有限集合 $A, B$ に対する Jaccard 係数は:

$$
J(A, B) = \frac{|A \cap B|}{|A \cup B|}
$$

- $J = 1.0$ : $A$ と $B$ が完全一致（全く同じホットピクセル集合）
- $J = 0.0$ : $A$ と $B$ に共通要素なし（完全に異なるピクセル集合）

高い Jaccard 係数はホットピクセルの「固定性」を示し、低い値は時間経過（温度変化）による変動を示唆する。

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| `metavision_active_pixel_detection` が見つからない | Prophesee SDK (OpenEB) の PATH を確認: `source /opt/prophesee/setup.bash` 等 |
| `result.txt` が生成されない | SDK のバージョンによりファイル出力パスが異なる。`-s` オプションでパスを明示指定 |
| グラフの文字が `□` になる | 日本語フォントが不足。`apt install fonts-noto-cjk` を実行 |
| SciencePlots エラー | `pip install SciencePlots` を再実行、または LaTeX をインストール: `apt install texlive-latex-extra` |

---

## 参考文献

- Prophesee SDK Documentation: [https://docs.prophesee.ai/](https://docs.prophesee.ai/)
- Jaccard, P. (1912). "The distribution of the flora in the alpine zone." *New Phytologist*, 11(2), 37-50.
