# E-Paper Palette Dither for Scriptable (iPhone)

Scriptable (iOS) の WebView を使った E-Ink 4色ディザリングアプリ。
デスクトップ版（Python/PyQt6）と同一のアルゴリズムを JavaScript で再実装。

## 導入方法

### 必要なもの
- iPhone（iOS 14以降）
- [Scriptable](https://apps.apple.com/app/scriptable/id1405459188)（App Store、無料）

### インストール手順

#### 方法1: iCloud Drive 経由（推奨）
1. PC/Mac で `scriptable/EPaperPaletteDither.js` を iCloud Drive にコピー
2. コピー先: `iCloud Drive/Scriptable/EPaperPaletteDither.js`
3. Scriptable アプリを開くとスクリプトが自動で表示される

#### 方法2: コピー＆ペースト
1. iPhone で Scriptable アプリを開く
2. 右上の「+」で新規スクリプトを作成
3. スクリプト名を `EPaperPaletteDither` に変更
4. `scriptable/EPaperPaletteDither.js` の内容を全選択してペースト
5. 右上の「Done」で保存

## 使い方

### 基本的な流れ
1. 画像を選択（フォトライブラリまたは共有シート）
2. WebView UI でパラメータを調整（デフォルト: 4.2" / Illuminant）
3. 「Convert」ボタンでディザリング実行
4. 「Save」ボタン → WebView を閉じるとフォトライブラリに保存

### 起動方法

#### Scriptable アプリから直接実行
1. Scriptable アプリを開く
2. `EPaperPaletteDither` をタップ
3. フォトライブラリから画像を選択
4. パラメータ調整 → Convert → Save

#### 共有シートから起動
1. 写真アプリや Safari 等で画像を表示
2. 共有ボタン → 「Scriptable」を選択
3. `EPaperPaletteDither` をタップ
4. パラメータ調整 → Convert → Save

#### Shortcuts（ショートカット）連携
1. ショートカットアプリで新規ショートカットを作成
2. 「Run Script」アクションを追加
3. スクリプト名: `EPaperPaletteDither`
4. 入力に画像を渡すと自動処理
5. 出力: ディザリング済み画像

## 機能

### カラーモード（色変換前処理）
E-Inkパレット（白・黒・赤・黄）の4色に変換する前に、元画像の色を前処理する4つのモード:

| モード | 説明 |
|--------|------|
| **Gray** | パレット外の色相をグレー化（HSL脱彩度化）。Strength スライダーで強度調整 |
| **AntiSat** | パレット4色が張る四面体の表面に最近点射影。色情報を最大限保持 |
| **Cent** | 四面体の重心からレイキャストして表面にクリップ。暖色寄りの結果 |
| **Illum** | 赤/黄の色付き照明シミュレーション。Red/Yellow/White で調整 |

### ディザリング品質パラメータ

| パラメータ | デフォルト | 効果 |
|-----------|-----------|------|
| **ErrClamp** | 85 | 誤差拡散の上限。小さいほどノイズ抑制（0=無効） |
| **RedPen** | 10.0 | 明るい部分での赤ドット出現を抑制 |
| **YellowPen** | 15.0 | 暗い部分での黄ドット出現を抑制 |

### 自動回転
縦長の写真を横長のE-Paperターゲット（2.9"/4.2"）に変換する際、自動で90°回転してフィットさせます。

### ターゲットプリセット

| プリセット | 解像度 | 用途 |
|-----------|--------|------|
| **2.9"** | 296×128 | Santek 2.9インチ E-Paper |
| **4.2"** | 400×300 | Santek 4.2インチ E-Paper（デフォルト） |

### ボタン

| ボタン | 動作 |
|--------|------|
| **Convert** | カラーモード処理 + Floyd-Steinbergディザリングを実行 |
| **Gamut Only** | カラーモード処理のみ（ディザリングなし）。色変換の効果確認用 |
| **Save** | 結果画像を保持し、WebView を閉じるとフォトライブラリに保存 |

## 開発

### ファイル構成

```
scriptable/
├── EPaperPaletteDither.js              # 配布用（HTML埋め込み済み単一ファイル）
├── build.py                     # ビルドスクリプト
├── src/
│   ├── scriptable-entry.js      # Scriptableエントリポイント（テンプレート）
│   ├── color.js                 # 色計算: Lab, CIEDE2000, findNearestColor
│   ├── gamut-mapping.js         # ガマットマッピング4モード
│   ├── dithering.js             # Floyd-Steinberg + パラメータ
│   └── app.html                 # WebView UI（ブラウザでもテスト可能）
├── tests/
│   ├── generate-vectors.py      # Python→JSON テストベクトル生成
│   ├── test-vectors.json        # クロス言語テスト期待値
│   └── test-runner.html         # ブラウザテストランナー
└── README.md
```

### ビルド

`src/app.html` を編集した後、配布用ファイルを再生成:

```bash
uv run python scriptable/build.py
```

`src/scriptable-entry.js`（Scriptable API部分）と `src/app.html`（WebView UI + 全JSモジュール）を結合して `EPaperPaletteDither.js` を生成します。

### テスト

#### テストベクトル再生成
Python実装の変更後:

```bash
uv run python scriptable/tests/generate-vectors.py
```

#### JSテスト実行（ローカルサーバー）
```bash
uv run python -m http.server 8765 --directory scriptable
# ブラウザで http://localhost:8765/tests/test-runner.html を開く
```

色計算・ガマットマッピング・ディザリングの各関数が Python実装と一致するかを自動検証（46テスト）。

#### ブラウザでのE2Eテスト
```bash
# 上記サーバー起動中に http://localhost:8765/src/app.html を開く
```

ファイルピッカーで画像を読み込み、全モード・パラメータの動作確認が可能。

## アルゴリズム

デスクトップ版（Python）の忠実なJavaScriptポート:

- **色計算**: sRGB→Lab変換（D65光源）、CIEDE2000色差、BT.709輝度ベースのペナルティ付き最近色検索
- **ガマットマッピング**: Grayout（HSL脱彩度化）、Anti-Saturation（Ericsonの最近点アルゴリズム）、Centroid Clip（重心レイキャスト）、Illuminant（BT.709輝度補正付き色温度シミュレーション）
- **ディザリング**: Floyd-Steinberg誤差拡散（7/16, 3/16, 5/16, 1/16）+ ErrClamp/RedPen/YellowPen

## パフォーマンス

- 400×300画像: 約2〜5秒（iPhone 12以降）
- 296×128画像: 約1〜2秒
- iPhone写真（4032×3024）はScriptable側でDrawContextリサイズ（長辺1000px以下）後、WebView内でターゲットサイズに縮小
- パレットLab値は事前計算（4色分のみ）で高速化
