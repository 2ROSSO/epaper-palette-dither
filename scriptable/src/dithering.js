/**
 * dithering.js — Floyd-Steinberg 誤差拡散ディザリング
 *
 * Python実装 (application/dither_service.py の dither_array_fast) の忠実なJSポート。
 * Canvas ImageData 形式で動作、Float32Array作業バッファ使用。
 *
 * パラメータ:
 *   - errorClamp: 誤差拡散クランプ値 (0=無効)
 *   - redPenalty: 明部での赤ペナルティ
 *   - yellowPenalty: 暗部での黄ペナルティ
 */

/**
 * Floyd-Steinberg ディザリング。
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number[][]} palette - パレット [[r,g,b], ...]
 * @param {number} errorClamp - 誤差クランプ (0=無効)
 * @param {number} redPenalty - 赤ペナルティ係数
 * @param {number} yellowPenalty - 黄ペナルティ係数
 * @returns {{data: Uint8ClampedArray, width: number, height: number}}
 */
function floydSteinbergDither(imageData, palette, errorClamp, redPenalty, yellowPenalty) {
  palette = palette || EINK_PALETTE;
  errorClamp = errorClamp || 0;
  redPenalty = redPenalty || 0;
  yellowPenalty = yellowPenalty || 0;

  const { data, width, height } = imageData;

  // Float32Array 作業バッファ (RGB のみ、3ch)
  const work = new Float32Array(width * height * 3);
  for (let i = 0; i < width * height; i++) {
    work[i * 3]     = data[i * 4];
    work[i * 3 + 1] = data[i * 4 + 1];
    work[i * 3 + 2] = data[i * 4 + 2];
  }

  // パレットのLab値を事前計算
  const paletteLab = palette.map(c => rgbToLab(c[0], c[1], c[2]));

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 3;
      const oldR = work[idx], oldG = work[idx + 1], oldB = work[idx + 2];

      // 0-255 にクランプ
      const cr = Math.max(0, Math.min(255, Math.round(oldR)));
      const cg = Math.max(0, Math.min(255, Math.round(oldG)));
      const cb = Math.max(0, Math.min(255, Math.round(oldB)));

      // 最近色検索
      let nearest;
      if (redPenalty > 0 || yellowPenalty > 0) {
        const brightness = Math.max(0, Math.min(1,
          (0.2126 * cr + 0.7152 * cg + 0.0722 * cb) / 255
        ));
        nearest = findNearestColor(cr, cg, cb, palette, redPenalty, yellowPenalty, brightness);
      } else {
        nearest = findNearestColor(cr, cg, cb, palette);
      }

      work[idx]     = nearest[0];
      work[idx + 1] = nearest[1];
      work[idx + 2] = nearest[2];

      // 量子化誤差
      let errR = oldR - nearest[0];
      let errG = oldG - nearest[1];
      let errB = oldB - nearest[2];

      // Error Clamping
      if (errorClamp > 0) {
        errR = Math.max(-errorClamp, Math.min(errorClamp, errR));
        errG = Math.max(-errorClamp, Math.min(errorClamp, errG));
        errB = Math.max(-errorClamp, Math.min(errorClamp, errB));
      }

      // Floyd-Steinberg 拡散
      //        [*] [7/16]
      //  [3/16] [5/16] [1/16]
      if (x + 1 < width) {
        const ni = idx + 3;
        work[ni]     += errR * 7 / 16;
        work[ni + 1] += errG * 7 / 16;
        work[ni + 2] += errB * 7 / 16;
      }
      if (y + 1 < height) {
        if (x - 1 >= 0) {
          const ni = idx + (width - 1) * 3;
          work[ni]     += errR * 3 / 16;
          work[ni + 1] += errG * 3 / 16;
          work[ni + 2] += errB * 3 / 16;
        }
        {
          const ni = idx + width * 3;
          work[ni]     += errR * 5 / 16;
          work[ni + 1] += errG * 5 / 16;
          work[ni + 2] += errB * 5 / 16;
        }
        if (x + 1 < width) {
          const ni = idx + (width + 1) * 3;
          work[ni]     += errR * 1 / 16;
          work[ni + 1] += errG * 1 / 16;
          work[ni + 2] += errB * 1 / 16;
        }
      }
    }
  }

  // 結果をImageData形式に変換
  const out = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i++) {
    out[i * 4]     = Math.max(0, Math.min(255, Math.round(work[i * 3])));
    out[i * 4 + 1] = Math.max(0, Math.min(255, Math.round(work[i * 3 + 1])));
    out[i * 4 + 2] = Math.max(0, Math.min(255, Math.round(work[i * 3 + 2])));
    out[i * 4 + 3] = 255;
  }

  return { data: out, width, height };
}

// Export for test and module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { floydSteinbergDither };
}
