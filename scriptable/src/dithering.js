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
 *   - csfChromaWeight: 色差チャンネル減衰 (0.0=輝度のみ, 1.0=従来通り)
 */

/**
 * Floyd-Steinberg ディザリング（高速版）。
 * ペナルティなし時: LUT O(1) 検索
 * ペナルティあり時: Lab Euclidean距離 + ペナルティ
 *
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number[][]} palette - パレット [[r,g,b], ...]
 * @param {number} errorClamp - 誤差クランプ (0=無効)
 * @param {number} redPenalty - 赤ペナルティ係数
 * @param {number} yellowPenalty - 黄ペナルティ係数
 * @param {number} [csfChromaWeight=1.0] - 色差チャンネル減衰 (0.0=輝度のみ, 1.0=従来通り)
 * @returns {{data: Uint8ClampedArray, width: number, height: number}}
 */
function floydSteinbergDither(imageData, palette, errorClamp, redPenalty, yellowPenalty, csfChromaWeight) {
  palette = palette || EINK_PALETTE;
  errorClamp = errorClamp || 0;
  redPenalty = redPenalty || 0;
  yellowPenalty = yellowPenalty || 0;
  csfChromaWeight = csfChromaWeight ?? 1.0;

  const { data, width, height } = imageData;
  const usePenalty = redPenalty > 0 || yellowPenalty > 0;

  // Float32Array 作業バッファ (RGB のみ、3ch)
  const work = new Float32Array(width * height * 3);
  for (let i = 0; i < width * height; i++) {
    work[i * 3]     = data[i * 4];
    work[i * 3 + 1] = data[i * 4 + 1];
    work[i * 3 + 2] = data[i * 4 + 2];
  }

  // LUT構築（ペナルティなし用）
  const lut = buildDitherLut(palette);

  // パレットLab値を事前計算（ペナルティあり用）
  const palLab = usePenalty ? palette.map(c => rgbToLabFast(c[0], c[1], c[2])) : null;

  // FS拡散定数
  const W_R = 7 / 16, W_BL = 3 / 16, W_B = 5 / 16, W_BR = 1 / 16;

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (y * width + x) * 3;
      const oldR = work[idx], oldG = work[idx + 1], oldB = work[idx + 2];

      // 0-255 にクランプ
      const cr = Math.max(0, Math.min(255, Math.round(oldR)));
      const cg = Math.max(0, Math.min(255, Math.round(oldG)));
      const cb = Math.max(0, Math.min(255, Math.round(oldB)));

      // 最近色検索
      let palIdx;
      if (usePenalty) {
        const brightness = Math.max(0, Math.min(1,
          (0.2126 * cr + 0.7152 * cg + 0.0722 * cb) / 255
        ));
        palIdx = findNearestIndexLabEuclidean(
          cr, cg, cb, palette, palLab, redPenalty, yellowPenalty, brightness
        );
      } else {
        // LUT O(1) 検索
        palIdx = lut[(cr >> 2) * 4096 + (cg >> 2) * 64 + (cb >> 2)];
      }

      const nearest = palette[palIdx];
      const nR = nearest[0], nG = nearest[1], nB = nearest[2];
      work[idx] = nR;
      work[idx + 1] = nG;
      work[idx + 2] = nB;

      // 量子化誤差
      let errR = oldR - nR;
      let errG = oldG - nG;
      let errB = oldB - nB;

      // Error Clamping
      if (errorClamp > 0) {
        if (errR > errorClamp) errR = errorClamp; else if (errR < -errorClamp) errR = -errorClamp;
        if (errG > errorClamp) errG = errorClamp; else if (errG < -errorClamp) errG = -errorClamp;
        if (errB > errorClamp) errB = errorClamp; else if (errB < -errorClamp) errB = -errorClamp;
      }

      // CSF チャンネル重み付け (BT.709 opponent 色空間)
      if (csfChromaWeight < 1.0) {
        const errLum = 0.2126 * errR + 0.7152 * errG + 0.0722 * errB;
        let errRG = errR - errG;
        let errBY = 0.5 * (errR + errG) - errB;
        errRG *= csfChromaWeight;
        errBY *= csfChromaWeight;
        errR = errLum + 0.7513 * errRG + 0.0722 * errBY;
        errG = errLum - 0.2487 * errRG + 0.0722 * errBY;
        errB = errLum + 0.2513 * errRG - 0.9278 * errBY;
      }

      // Floyd-Steinberg 拡散
      if (x + 1 < width) {
        const ni = idx + 3;
        work[ni]     += errR * W_R;
        work[ni + 1] += errG * W_R;
        work[ni + 2] += errB * W_R;
      }
      if (y + 1 < height) {
        if (x - 1 >= 0) {
          const ni = idx + (width - 1) * 3;
          work[ni]     += errR * W_BL;
          work[ni + 1] += errG * W_BL;
          work[ni + 2] += errB * W_BL;
        }
        {
          const ni = idx + width * 3;
          work[ni]     += errR * W_B;
          work[ni + 1] += errG * W_B;
          work[ni + 2] += errB * W_B;
        }
        if (x + 1 < width) {
          const ni = idx + (width + 1) * 3;
          work[ni]     += errR * W_BR;
          work[ni + 1] += errG * W_BR;
          work[ni + 2] += errB * W_BR;
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
