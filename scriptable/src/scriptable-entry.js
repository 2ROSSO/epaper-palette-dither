// 4ColorDither.js — Scriptable entry point
// E-Ink 4色ディザリング for iPhone
//
// Usage:
//   1. Scriptableアプリで直接実行 → フォトライブラリから選択
//   2. 共有シートから画像を受け取り実行
//   3. Shortcuts から実行 (Script.setShortcutOutput)

// ===== 1. 画像取得 =====
let img;
if (args.images && args.images.length > 0) {
  img = args.images[0];
} else {
  img = await Photos.fromLibrary();
}

if (!img) {
  Script.complete();
  return;
}

// ===== 2. リサイズ (長辺1000px以下) =====
function resizeImage(image, maxWidth, maxHeight) {
  const size = image.size;
  const w = size.width;
  const h = size.height;

  if (w <= maxWidth && h <= maxHeight) {
    return image;
  }

  const scale = Math.min(maxWidth / w, maxHeight / h);
  const newW = Math.round(w * scale);
  const newH = Math.round(h * scale);

  const ctx = new DrawContext();
  ctx.size = new Size(newW, newH);
  ctx.opaque = true;
  ctx.respectScreenScale = false;
  ctx.drawImageInRect(image, new Rect(0, 0, newW, newH));
  return ctx.getImage();
}

const resized = resizeImage(img, 1000, 1000);
const base64 = Data.fromJPEG(resized, 0.92).toBase64String();

// ===== 3. WebView HTML =====
const html = `__HTML_CONTENT__`;

// ===== 4. WebView 起動 =====
const wv = new WebView();
await wv.loadHTML(html);

// 画像を注入
await wv.evaluateJavaScript(`loadBase64Image('${base64}')`);

// ユーザー操作を待機（WebView表示）
await wv.present(true);

// ===== 5. 結果取得・保存 =====
const result = await wv.evaluateJavaScript('getResult()');
if (result) {
  const imageData = Data.fromBase64String(result);
  const resultImage = Image.fromData(imageData);
  await Photos.save(resultImage);

  // Shortcuts対応
  Script.setShortcutOutput(resultImage);
}

Script.complete();
