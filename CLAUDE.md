# CLAUDE.md — 開発ルール・規約

## ドキュメント参照
- 各種ライブラリやツールの使用前には、必ず公式ドキュメントを参照すること
- 公式ドキュメントの情報に基づいて実装し、非公式の情報のみに依存しない
- 使用するライブラリの対象バージョンに対応したドキュメントを参照すること

## パッケージ管理
- **uv** を使用してプロジェクト・依存関係を管理する
- `uv add` で依存追加、`uv run` でスクリプト実行
- `uv.lock` はコミット対象に含める

## ブランチ戦略
- **ブランチ作成時は、ベースブランチを `git pull` してリモートの最新状態を反映してから分岐する**
- **`wip/<feature>`**: 実装作業ブランチ。細切れにコミットしセーブポイントを増やす
- **`pr/<feature>`**: PR用クリーンブランチ。wip完了後に機能単位の段階的コミットで再構成
- wip/ブランチ完成時（pr/ブランチ作成直前）にテスト全通過を必須とする
- pr/ブランチの各コミットもテスト通過を必須条件とする
- **wip/ブランチは原則リモートにpushしない**（ローカル作業専用）。pushするのは pr/ブランチのみ
- wip/ブランチは作業の区切りごとに `wip2/`, `wip3/` ... とナンバリングを繰り上げて新ブランチを作成する。前のwipブランチはローカルのスナップショットとして残す

## マージルール
- **mainへの直接マージは禁止**。必ず pr/ ブランチからPR経由でマージする
- pr/ ブランチ完成後、mainへのマージ前にユーザーが手動で動作確認を行う
- ユーザーの動作確認・承認後にのみ、mainへのマージPRを作成できる
- マージ手順: wip/ → pr/（テスト全通過）→ ユーザー動作確認 → main へPR

## コミットルール
- wip/: 頻繁に小さくコミット（セーブポイント重視）
- pr/: PRを前提とした機能単位の段階的コミット
- **wipブランチ完成時（pr/ブランチ作成直前）にテスト全通過を必須とする**
- pr/ブランチの各コミット前にもテスト実行を必須とする

## テスト
- 機能実装時は必ずテストファイルを生成する
- wipブランチ完成時にテスト全通過を必須とする（pr/ブランチ作成のゲート条件）
- pr/ブランチでの各コミットでもテスト通過を条件とする
- `uv run pytest` でテスト実行

## コード設計
- クリーンアーキテクチャの原則に従う（domain / application / infrastructure / presentation）
- DI（依存性注入）を活用し、テスタビリティと拡張性を確保
- 機能実装後、サブ機能・サブ処理のヘルパー関数外出しを検討する
- 定期的に各機能の共通処理を `common` として抽出できないか検討する

## プランニング
- 機能実装の際は plan モードを必須とする
- GUIや3次元的な機能の指示出し時は、プラン段階でアスキーアートによる概略図を提示する

## GitHub リポジトリ
- プロジェクト開始時にリモートリポジトリを作成し、初期コミットを push すること
- リポジトリは **private** で作成する（`gh repo create --private`）

## ドキュメント・プロジェクト管理
- pr/ブランチ完了ごとに README.md および CLAUDE.md を更新する
- 機能追加依頼はタスク分解し、GitHub Issue として登録する
- 機能の優先順位は GitHub Projects（カンバン）で管理する

## プロジェクト構成
```
src/epaper_palette_dither/
├── domain/               # ドメイン層（Pure Python、外部依存なし）
│   ├── color.py              # RGB, EINK_PALETTE, CIEDE2000, find_nearest_color
│   ├── dithering.py          # Floyd-Steinberg 誤差拡散
│   └── image_model.py        # ColorMode(enum), DisplayPreset, ImageSpec
├── application/          # アプリケーション層（ユースケース）
│   ├── dither_service.py     # DitherService（ディザリング実行、ErrClamp/RedPen/YellowPen対応）
│   ├── image_converter.py    # ImageConverter（リサイズ→色処理→ディザ パイプライン、品質パラメータ管理）
│   └── reconvert_service.py  # ReconvertService（逆ディザリング: Blur→逆ガマット→自動輝度補正）
├── infrastructure/       # インフラ層（Pillow, NumPy, ファイルI/O）
│   ├── color_space.py        # sRGB⇔Linear, RGB⇔Lab バッチ変換
│   ├── gamut_mapping.py      # gamut_map, anti_saturate, anti_saturate_centroid, apply_illuminant
│   ├── inverse_gamut_mapping.py  # inverse_gamut_map, inverse_apply_illuminant
│   └── image_io.py           # load/save/resize/rotate
└── presentation/         # プレゼンテーション層（PyQt6 GUI）
    ├── controls.py           # ControlPanel（2段: 変換パラメータ + Reconvertパラメータ）
    ├── image_viewer.py       # ImageViewer（D&D対応画像表示）
    └── main_window.py        # MainWindow（3パネル並列 + ConvertWorker/ReconvertWorker）
```

## Scriptable (iPhone版)

### 構成
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
│   └── test-runner.html         # ブラウザテストランナー（46テスト）
└── README.md
```

### コマンド
- ビルド: `uv run python scriptable/build.py`
- テストベクトル再生成: `uv run python scriptable/tests/generate-vectors.py`
- JSテスト: `uv run python -m http.server 8765 --directory scriptable` → `http://localhost:8765/tests/test-runner.html`

### 注意事項
- Python実装の変更後は必ずテストベクトルを再生成し、JSテストの整合性を確認する
- `src/app.html` 編集後は `build.py` で `EPaperPaletteDither.js` を再生成する
- `EPaperPaletteDither.js` を直接編集しない（ビルド成果物）

## 主要な型・列挙
- `ColorMode`: Grayout / Anti-Saturation / Centroid Clip / Illuminant
- `DisplayPreset`: Santek 2.9" (296×128) / 4.2" (400×300)
- `ImageSpec`: target_width, target_height, keep_aspect_ratio, orientation_landscape

## コマンド
- テスト実行: `uv run pytest`
- アプリ起動: `uv run python -m epaper_palette_dither`
- Scriptableビルド: `uv run python scriptable/build.py`
- Scriptableテストベクトル再生成: `uv run python scriptable/tests/generate-vectors.py`
