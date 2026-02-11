# ARCHITECTURE.md — アーキテクチャ設計

## 概要
電子ペーパー（4色E-Ink: 白・黒・赤・黄）向けに、通常の画像をディザリング変換するGUIアプリケーション。

### ターゲットデバイス
**Santek EZ Sign NFC E-Paper Display（4色）**
- 2.9インチ: 296×128 ピクセル
- **4.2インチ: 400×300 ピクセル（主要ターゲット）**

## レイヤー構成

```
presentation (PyQt6 GUI)
    ↓ 依存
application (ユースケース・パイプライン)
    ↓ 依存
domain (アルゴリズム・モデル・Protocol)
    ↑ 依存しない（最内層）
infrastructure (Pillow, NumPy, ファイルI/O)
    → domain の Protocol を実装
```

### domain層
- 色定義・パレット（RGB値）
- ディザリングアルゴリズム（Protocol + Floyd-Steinberg実装）
- 画像ドメインモデル
- **外部ライブラリに依存しない（Pure Python + typing）**

### application層
- ディザリング実行ユースケース
- 画像変換パイプライン（リサイズ→色空間変換→ディザリング→出力）
- 進捗コールバック対応
- domain層のProtocolに依存（具体実装はDI）

### infrastructure層
- 画像I/O（Pillow: JPEG, PNG, BMP）
- 色空間変換（RGB↔LAB）
- domain層のProtocolを実装

### presentation層
- PyQt6 GUI
- メインウィンドウ（左右並列プレビュー）
- 画像ビューア（ドラッグ&ドロップ、ズーム・パン）
- パラメータ制御パネル
- application層のみに依存

## 依存関係ルール
- domain層は外部ライブラリに依存しない（Pure Python + typing）
- infrastructure層はdomain層のProtocolを実装
- application層はdomain層のProtocolに依存（具体実装はDI）
- presentation層はapplication層のみに依存

## 技術スタック
- Python 3.12 / uv
- PyQt6 (GUI)
- Pillow (画像I/O)
- NumPy (数値計算)
- pytest + pytest-qt (テスト)

## ディレクトリ構造
```
src/
└── epaper_palette_dither/
    ├── __init__.py
    ├── __main__.py
    ├── domain/
    │   ├── __init__.py
    │   ├── color.py
    │   ├── dithering.py
    │   └── image_model.py
    ├── application/
    │   ├── __init__.py
    │   ├── dither_service.py
    │   └── image_converter.py
    ├── infrastructure/
    │   ├── __init__.py
    │   ├── image_io.py
    │   └── color_space.py
    └── presentation/
        ├── __init__.py
        ├── main_window.py
        ├── image_viewer.py
        └── controls.py
```
