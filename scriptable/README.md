# 4-Color Dither for Scriptable (iPhone)

Scriptable (iOS) の WebView を使った E-Ink 4色ディザリングアプリ。
デスクトップ版（Python/PyQt6）と同一のアルゴリズムを JavaScript で再実装。

## セットアップ

1. App Store から [Scriptable](https://apps.apple.com/app/scriptable/id1405459188) をインストール
2. `4ColorDither.js` を Scriptable の Documents フォルダにコピー
   - iCloud Drive: `Scriptable/4ColorDither.js`
   - または Scriptable アプリ内で新規スクリプトを作成し、内容をペースト

## 使い方

### 直接実行
1. Scriptable アプリを開く
2. `4ColorDither` をタップ
3. フォトライブラリから画像を選択
4. パラメータ調整 → Convert → Save

### 共有シートから
1. 写真アプリ等で画像を選択
2. 共有 → Scriptable → 4ColorDither
3. パラメータ調整 → Convert → Save

### Shortcuts 連携
1. ショートカットアプリで「Run Script」アクションを追加
2. スクリプト名: `4ColorDither`
3. 入力: 画像
4. 出力: ディザリング済み画像（`Script.setShortcutOutput`）

## UIコントロール

| コントロール | 説明 |
|-------------|------|
| **Target** | 出力解像度プリセット（2.9" = 296x128, 4.2" = 400x300） |
| **Color** | カラーモード（Gray / AntiSat / Cent / Illum） |
| **Strength** | Grayoutモードの強度（0.00〜1.00） |
| **Red/Yellow/White** | Illuminantモードのパラメータ |
| **ErrClamp** | 誤差拡散クランプ（0=無効, 85=デフォルト） |
| **RedPen** | 明部での赤ペナルティ（10.0=デフォルト） |
| **YellowPen** | 暗部での黄ペナルティ（15.0=デフォルト） |
| **Convert** | ガマットマッピング + ディザリング実行 |
| **Gamut Only** | ガマットマッピングのみ（ディザリングなし） |
| **Save** | 結果をフォトライブラリに保存 |

## 開発

### ファイル構成

```
scriptable/
├── 4ColorDither.js          # 配布用（HTML埋め込み済み単一ファイル）
├── build.py                 # app.html → 4ColorDither.js 埋め込みビルド
├── src/
│   ├── color.js             # 色計算: Lab, CIEDE2000, findNearestColor
│   ├── gamut-mapping.js     # ガマットマッピング4モード
│   ├── dithering.js         # Floyd-Steinberg + パラメータ
│   └── app.html             # WebView UI（ブラウザでもテスト可能）
├── tests/
│   ├── generate-vectors.py  # Python→JSON テストベクトル生成
│   ├── test-vectors.json    # クロス言語テスト期待値
│   └── test-runner.html     # ブラウザテストランナー
└── README.md
```

### ビルド

app.html を編集した後、配布用ファイルを再生成:

```bash
uv run python scriptable/build.py
```

### テスト

#### テストベクトル再生成
Python実装の変更後:

```bash
uv run python scriptable/tests/generate-vectors.py
```

#### JSテスト実行
`scriptable/tests/test-runner.html` をブラウザで開く。
色計算・ガマットマッピング・ディザリングの各関数が
Python実装と一致するかを自動検証。

#### ブラウザでのE2Eテスト
`scriptable/src/app.html` をブラウザで直接開き、
ファイルピッカーで画像を読み込んで動作確認可能。

## アルゴリズム

デスクトップ版（Python）の忠実なJavaScriptポート:

- **色計算**: sRGB→Lab変換、CIEDE2000色差、ペナルティ付き最近色検索
- **ガマットマッピング**: Grayout（HSL脱彩度化）、Anti-Saturation（四面体最近点射影）、Centroid Clip（重心レイキャスト）、Illuminant（色温度シミュレーション）
- **ディザリング**: Floyd-Steinberg誤差拡散 + ErrClamp/RedPen/YellowPen

## パフォーマンス

- 400x300画像: 約2-5秒（iPhone 12以降）
- 写真（4032x3024）はScriptable側で1000px以下にリサイズ後、WebView内でターゲットサイズに縮小
