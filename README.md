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

## 技術スタック

- Python 3.12 / uv
- PyQt6 (GUI)
- Pillow (画像I/O)
- NumPy (数値計算)
- pytest + pytest-qt (テスト)
