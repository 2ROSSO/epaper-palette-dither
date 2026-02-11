"""ビルドスクリプト: app.html を EPaperPaletteDither.js に埋め込む。

app.html の内容をテンプレートリテラルとして
EPaperPaletteDither.js の __HTML_CONTENT__ プレースホルダに挿入する。

Usage:
    uv run python scriptable/build.py
"""

from pathlib import Path


def main() -> None:
    root = Path(__file__).parent

    # app.html を読み込み
    html_path = root / "src" / "app.html"
    html_content = html_path.read_text(encoding="utf-8")

    # テンプレートリテラル内でバッククォートとドル記号をエスケープ
    html_escaped = html_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    # テンプレート読み込み（src/scriptable-entry.js をソースとして使用）
    template_path = root / "src" / "scriptable-entry.js"
    template = template_path.read_text(encoding="utf-8")

    # __HTML_CONTENT__ を置換
    output = template.replace("__HTML_CONTENT__", html_escaped)

    # 出力
    dist_path = root / "EPaperPaletteDither.js"
    dist_path.write_text(output, encoding="utf-8")

    print(f"Built: {dist_path}")
    print(f"  HTML: {len(html_content)} chars")
    print(f"  Output: {len(output)} chars")


if __name__ == "__main__":
    main()
