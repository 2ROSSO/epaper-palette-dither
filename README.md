# 4-Color Dither for E-Paper

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
uv run python -m four_color_dither
```

## テスト

```bash
uv run pytest
```

## 機能

### ディザリング
- **Floyd-Steinbergディザリング**: CIEDE2000色差を使用した誤差拡散ディザリング
- **高速NumPy実装**: バッチ処理による高速ディザリング (`dither_array_fast`)

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
誤差拡散ディザリングの品質を制御する3つのパラメータ:

| パラメータ | デフォルト | 範囲 | 効果 |
|-----------|-----------|------|------|
| **ErrClamp** | 85 | 0–128 | 誤差拡散クランプ。値が小さいほどノイズ抑制が強い（0=無効） |
| **RedPen** | 10.0 | 0–100 | 明部での赤ペナルティ。CIEDE2000距離に加算し明部の赤ドットを抑制 |
| **YellowPen** | 15.0 | 0–100 | 暗部での黄ペナルティ。CIEDE2000距離に加算し暗部の黄ドットを抑制 |

### GUI
- **ガマットのみプレビュー**: ディザリングなしでカラーモードの効果を確認
- **画像回転**: 元画像の90° CW回転（E-Paperの縦横切替用）
- **ドラッグ&ドロップ**: 画像ファイルのD&D読み込み対応
- **左右並列プレビュー**: 元画像とディザリング結果を比較表示

## 技術スタック

- Python 3.12 / uv
- PyQt6 (GUI)
- Pillow (画像I/O)
- NumPy (数値計算)
- pytest + pytest-qt (テスト)

## プロジェクト構成

```
src/four_color_dither/
├── domain/           # ドメイン層（Pure Python、外部依存なし）
│   ├── color.py          # RGB, パレット定義, CIEDE2000色差
│   ├── dithering.py      # Floyd-Steinberg誤差拡散
│   └── image_model.py    # ColorMode, DisplayPreset, ImageSpec
├── application/      # アプリケーション層（ユースケース）
│   ├── dither_service.py # ディザリングサービス（ErrClamp/RedPen/YellowPen対応）
│   └── image_converter.py # 変換パイプライン（リサイズ→色処理→ディザ、品質パラメータ管理）
├── infrastructure/   # インフラ層（Pillow, NumPy, ファイルI/O）
│   ├── color_space.py    # Lab色空間バッチ変換
│   ├── gamut_mapping.py  # Grayout, Anti-Saturation, Centroid Clip, Illuminant
│   └── image_io.py       # 画像読込/保存/リサイズ/回転
└── presentation/     # プレゼンテーション層（PyQt6 GUI）
    ├── controls.py       # パラメータ制御パネル
    ├── image_viewer.py   # 画像表示ウィジェット（D&D対応）
    └── main_window.py    # メインウィンドウ
```

## 謝辞

- [Arrayfy](https://shapoco.github.io/arrayfy/) by [Shapoco](https://github.com/shapoco) — Grayout CSR・Anti-Saturation等のカラーモード設計を参考にさせていただきました
