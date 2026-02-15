# E-Paper Palette Dither

電子ペーパー（4色E-Ink: 白・黒・赤・黄）向けに、通常の画像をFloyd-Steinbergディザリングで変換するGUIアプリケーション。

## ターゲットデバイス

**Santek EZ Sign NFC E-Paper Display（4色）**
- 2.9インチ: 296×128 ピクセル
- 4.2インチ: 400×300 ピクセル（主要ターゲット）

## セットアップ

```bash
uv sync
```

## 使い方

```bash
uv run python -m epaper_palette_dither
```

## テスト

```bash
uv run pytest
```

## 機能

### ディザリング
- **Floyd-Steinbergディザリング**: Lab色差を使用した誤差拡散ディザリング
- **高速NumPy実装**: Lab ユークリッド距離＋LUTキャッシュによる高速ディザリング (`dither_array_fast`)

### カラーモード（色変換前処理）
4種類のカラーモードを切り替えて、ディザリング前の色変換方式を選択できる:

| モード | 方式 | 特徴 |
|--------|------|------|
| **Grayout** | HSL色相クリップ＋彩度低減 | パレット外の色相をグレー化。強度調整可能 |
| **Anti-Saturation** | 四面体最近点射影 | パレット凸包外の色を表面上の最近点に射影。色情報を最大限保持 |
| **Centroid Clip** | 重心方向レイキャスト | パレット重心から外部点へのレイで表面にクリップ。暖色寄りの結果 |
| **Illuminant** | 色付き照明シミュレーション | Red/Yellow光の合成で暖色バイアス。BT.709輝度補正＋白保持機能付き |

#### Illuminant モードの詳細
- **Red**: 赤光の強さ（デフォルト 1.00）
- **Yellow**: 黄光の強さ（デフォルト 1.00）
- **White**: 明部の白保持（デフォルト 1.00, 0.0=無効, 1.0=明部を完全保持）
- 内部で `Red光(1,0,0) + Yellow光(1,1,0)` を合成し RGB スケールに変換
- BT.709 輝度重みで自動正規化し、元画像の明るさを維持

### ディザリング品質調整
誤差拡散ディザリングの品質を制御するパラメータ:

| パラメータ | デフォルト | 範囲 | 効果 |
|-----------|-----------|------|------|
| **CSF** | 0.60 | 0.00–1.00 | 色差チャンネル減衰。誤差伝播を opponent 色空間で重み付けし知覚ノイズを低減（1.00=従来通り、0.00=輝度のみ伝播） |
| **ErrClamp** | 85 | 0–128 | 誤差拡散クランプ。値が小さいほどノイズ抑制が強い（0=無効） |
| **RedPen** | 0.0 | 0–100 | 明部での赤ペナルティ。Lab距離に加算し明部の赤ドットを抑制 |
| **YellowPen** | 0.0 | 0–100 | 暗部での黄ペナルティ。Lab距離に加算し暗部の黄ドットを抑制 |

#### CSF チャンネル重み付きの仕組み
Floyd-Steinberg の誤差伝播を BT.709 opponent 色空間（輝度 / 赤-緑 / 青-黄）に変換し、
色差チャンネル (赤-緑, 青-黄) の伝播量を CSF 値で減衰してから RGB に逆変換する。
人間の視覚系は高周波の色差に鈍感であるため、色差ノイズを選択的に抑制でき、
ディザパターンの知覚的な滑らかさが向上する。

### 明度リマッピング (CLAHE)
ガマットマッピング後・ディザリング前に L* チャンネルへ CLAHE（Contrast Limited Adaptive Histogram Equalization）を適用し、パレットの明度範囲を有効活用する。色域外の色同士の明度差を拡大し、ディザリング結果のコントラストを改善する。

| パラメータ | デフォルト | 範囲 | 効果 |
|-----------|-----------|------|------|
| **CLAHE** (チェックボックス) | OFF | ON/OFF | 明度リマッピングの有効/無効 |
| **Clip** | 2.00 | 1.00–4.00 | コントラスト制限係数。値が大きいほど均等化が強い |

### Reconvert（逆ディザリング）
ディザリング結果から元画像の近似復元を行う機能。ディザリングパラメータの効果確認に有用。

**処理パイプライン**:
1. **Gaussian Blur**: sRGB空間でディザパターンを平滑化し連続的な色調を復元
2. **逆ガマットマッピング**: Grayout/Illuminant モードの色変換を逆適用
3. **自動輝度補正**: リニア空間でBT.709輝度を比較し、逆変換による輝度変化を補正

| パラメータ | デフォルト | 範囲 | 効果 |
|-----------|-----------|------|------|
| **Blur** | 1 | 1–20 | ブラー半径。大きいほど滑らかだがディテール減少 |
| **Bright** | 1.00 | 0.50–2.00 | 手動明るさ調整（自動補正に乗算） |

### パラメータ自動最適化（Optimize）
Optuna TPE (Tree-structured Parzen Estimator) により、Convert パラメータを自動探索して元画像との類似度を最大化する。

- **評価指標**: PSNR・SSIM・Lab ΔE・S-CIELAB ΔE・Histogram Correlation の5メトリクス複合スコア
- **探索対象**: カラーモードに応じた Convert パラメータのみ（Reconvert は blur=1, bright=1.0 固定）
- **Trial 数**: Optimize ボタン右クリックで変更可能（25 / 50 / 100 / 200 / 500、初期値 50）
- **初期値**: 現在の UI パラメータを初期候補として登録（step にスナップ）
- **高速化**: S-CIELAB の Gaussian フィルタを scipy C 実装に置換し、参照画像の CSF フィルタ結果を trial 間でキャッシュ

| ColorMode | 探索パラメータ数 | 探索対象 |
|-----------|-----------------|----------|
| Illuminant | 9 | illuminant_red/yellow/white, csf_chroma_weight, error_clamp, red_penalty, yellow_penalty, lightness_remap, lightness_clip_limit |
| Grayout | 7 | gamut_strength, csf_chroma_weight, error_clamp, red_penalty, yellow_penalty, lightness_remap, lightness_clip_limit |
| Anti-Saturation / Centroid Clip | 6 | csf_chroma_weight, error_clamp, red_penalty, yellow_penalty, lightness_remap, lightness_clip_limit |

#### S-CIELAB 評価メトリクス
Optimizer の評価関数に Zhang & Wandell (1997) の S-CIELAB を導入。XYZ → Opponent 色空間で視覚系の空間周波数感度 (CSF) に基づくガウシアンフィルタを適用後に Lab ΔE を算出する。ディザリングパターンの高周波色差が空間ブラーで知覚的に消えるため、通常の Lab ΔE より人間の見え方に近い色差評価が可能。

| メトリクス | 重み | 説明 |
|-----------|------|------|
| SSIM | 0.30 | 構造的類似性 |
| S-CIELAB ΔE | 0.25 | 知覚的色差（空間CSFフィルタ後） |
| Lab ΔE | 0.20 | ピクセル単位色差 |
| PSNR | 0.15 | ピーク信号対雑音比 |
| Histogram Correlation | 0.10 | ヒストグラム相関 |

### GUI
- **3パネル並列表示**: Original / Dithered Preview / Reconverted を横並びで比較
- **ガマットのみプレビュー**: ディザリングなしでカラーモードの効果を確認
- **画像回転**: 元画像の90° CW回転（E-Paperの縦横切替用）
- **自動回転**: 縦長画像を読み込み時に自動で横向きに回転
- **ドラッグ&ドロップ**: 画像ファイルのD&D読み込み対応

## iPhone版 (Scriptable)

[Scriptable](https://apps.apple.com/app/scriptable/id1405459188) アプリを使ったiPhone版も利用可能。
デスクトップ版と同一のアルゴリズムをJavaScriptで再実装。

- `scriptable/EPaperPaletteDither.js` を Scriptable の Documents フォルダにコピーするだけで動作
- 共有シート / Shortcuts からも起動可能
- 詳細: [scriptable/README.md](scriptable/README.md)

## 技術スタック

### デスクトップ版
- Python 3.12 / uv
- PyQt6 (GUI)
- Pillow (画像I/O)
- NumPy (数値計算)
- SciPy (S-CIELAB Gaussian フィルタ高速化)
- Optuna (パラメータ自動最適化)
- pytest + pytest-qt (テスト)

### iPhone版 (Scriptable)
- Scriptable (iOS) + WebView
- Canvas API + Vanilla JavaScript
- 全アルゴリズムをPythonから忠実にポート

## プロジェクト構成

```
src/epaper_palette_dither/
├── domain/               # ドメイン層（Pure Python、外部依存なし）
│   ├── color.py              # RGB, パレット定義, CIEDE2000色差, RedPen/YellowPen
│   ├── dithering.py          # Floyd-Steinberg誤差拡散
│   └── image_model.py        # ColorMode, DisplayPreset, ImageSpec
├── application/          # アプリケーション層（ユースケース）
│   ├── dither_service.py     # ディザリングサービス（CSF重み付き誤差拡散、ErrClamp/RedPen/YellowPen対応）
│   ├── image_converter.py    # 変換パイプライン（リサイズ→色処理→ディザ、品質パラメータ管理）
│   ├── optimizer_service.py  # Optuna TPE 自動最適化（Convertパラメータ探索）
│   └── reconvert_service.py  # 逆ディザリング（Blur→逆ガマット→自動輝度補正）
├── infrastructure/       # インフラ層（Pillow, NumPy, ファイルI/O）
│   ├── color_space.py        # sRGB⇔Linear, RGB⇔Lab バッチ変換
│   ├── gamut_mapping.py      # Grayout, Anti-Saturation, Centroid Clip, Illuminant
│   ├── image_io.py           # 画像読込/保存/リサイズ/回転
│   ├── image_metrics.py      # PSNR, SSIM, Lab ΔE, S-CIELAB ΔE(scipy高速化+参照キャッシュ), Histogram Correlation, 複合スコア
│   ├── inverse_gamut_mapping.py  # Grayout/Illuminant の逆変換
│   └── lightness_remap.py    # CLAHE 明度リマッピング（L*チャンネル適応的ヒストグラム均等化）
└── presentation/         # プレゼンテーション層（PyQt6 GUI）
    ├── controls.py           # パラメータ制御パネル（2段構成: 変換 + Reconvert）
    ├── image_viewer.py       # 画像表示ウィジェット（D&D対応）
    └── main_window.py        # メインウィンドウ（3パネル + ワーカースレッド）

scriptable/                  # iPhone版 (Scriptable)
├── EPaperPaletteDither.js    # 配布用単一ファイル
├── build.py                 # ビルドスクリプト
├── src/                     # 開発用ソース
│   ├── scriptable-entry.js  # Scriptableエントリポイント（テンプレート）
│   ├── color.js             # 色計算コア
│   ├── gamut-mapping.js     # ガマットマッピング4モード
│   ├── dithering.js         # Floyd-Steinbergディザリング
│   └── app.html             # WebView UI
└── tests/                   # テスト
    ├── generate-vectors.py  # テストベクトル生成
    ├── test-vectors.json    # クロス言語テスト期待値
    └── test-runner.html     # ブラウザテストランナー
```

## 謝辞

- [Arrayfy](https://shapoco.github.io/arrayfy/) by [Shapoco](https://github.com/shapoco) — Grayout（HSL脱彩度化）方式の着想を参考にさせていただきました
