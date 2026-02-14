/**
 * lightness-remap.js — CLAHE 明度リマッピング
 *
 * L* チャンネルに Contrast Limited Adaptive Histogram Equalization を適用し、
 * パレットの明度範囲を有効活用する。
 * Python実装 (infrastructure/lightness_remap.py) の忠実なJSポート。
 */

/**
 * 単チャンネルに対する CLAHE 実装。
 *
 * @param {Float64Array|number[]} channel - (H*W) フラット配列
 * @param {number} width - 画像幅
 * @param {number} height - 画像高さ
 * @param {number} clipLimit - コントラスト制限係数 (1.0=弱い, 4.0=強い)
 * @param {number} gridSize - グリッド分割数
 * @param {number} minVal - チャンネルの最小値
 * @param {number} maxVal - チャンネルの最大値
 * @param {number} [nBins=256] - ヒストグラムのビン数
 * @returns {Float64Array} CLAHE 適用後のフラット配列
 */
function claheChannel(channel, width, height, clipLimit, gridSize, minVal, maxVal, nBins) {
  nBins = nBins || 256;

  const result = new Float64Array(width * height);
  const valRange = maxVal - minVal;
  if (valRange < 1e-10) {
    result.set(channel);
    return result;
  }

  // 値を [0, nBins-1] にスケーリング
  const scaled = new Float64Array(width * height);
  const scaleF = (nBins - 1) / valRange;
  for (let i = 0; i < scaled.length; i++) {
    let v = (channel[i] - minVal) * scaleF;
    if (v < 0) v = 0;
    if (v > nBins - 1) v = nBins - 1;
    scaled[i] = v;
  }

  // グリッド境界
  const rowStep = height / gridSize;
  const colStep = width / gridSize;

  // 各グリッドブロックの CDF を事前計算
  // cdfs[gy][gx] = Float64Array(nBins)
  const cdfs = [];
  for (let gy = 0; gy < gridSize; gy++) {
    cdfs[gy] = [];
    const y0 = Math.round(gy * rowStep);
    let y1 = Math.round((gy + 1) * rowStep);
    if (y1 <= y0) y1 = y0 + 1;

    for (let gx = 0; gx < gridSize; gx++) {
      const x0 = Math.round(gx * colStep);
      let x1 = Math.round((gx + 1) * colStep);
      if (x1 <= x0) x1 = x0 + 1;

      const nPixels = (y1 - y0) * (x1 - x0);

      // ヒストグラム
      const hist = new Float64Array(nBins);
      for (let y = y0; y < y1; y++) {
        for (let x = x0; x < x1; x++) {
          let idx = Math.round(scaled[y * width + x]);
          if (idx < 0) idx = 0;
          if (idx >= nBins) idx = nBins - 1;
          hist[idx] += 1.0;
        }
      }

      // クリッピング
      const actualClip = clipLimit * nPixels / nBins;
      let excess = 0.0;
      for (let i = 0; i < nBins; i++) {
        if (hist[i] > actualClip) {
          excess += hist[i] - actualClip;
          hist[i] = actualClip;
        }
      }

      // 超過分を均等再分配
      const redistrib = excess / nBins;
      for (let i = 0; i < nBins; i++) {
        hist[i] += redistrib;
      }

      // CDF
      const cdf = new Float64Array(nBins);
      cdf[0] = hist[0];
      for (let i = 1; i < nBins; i++) {
        cdf[i] = cdf[i - 1] + hist[i];
      }

      let cdfMin = 0;
      for (let i = 0; i < nBins; i++) {
        if (cdf[i] > 0) { cdfMin = cdf[i]; break; }
      }

      const denom = nPixels - cdfMin;
      if (denom < 1.0) {
        for (let i = 0; i < nBins; i++) {
          cdf[i] = i;
        }
      } else {
        for (let i = 0; i < nBins; i++) {
          cdf[i] = (cdf[i] - cdfMin) / denom * (nBins - 1);
        }
      }

      cdfs[gy][gx] = cdf;
    }
  }

  // バイリニア補間で全ピクセルをリマッピング
  for (let y = 0; y < height; y++) {
    const gyF = (y + 0.5) / rowStep - 0.5;
    let gy0 = Math.floor(gyF);
    let gy1 = gy0 + 1;
    const fy = gyF - gy0;
    if (gy0 < 0) gy0 = 0;
    if (gy0 >= gridSize) gy0 = gridSize - 1;
    if (gy1 < 0) gy1 = 0;
    if (gy1 >= gridSize) gy1 = gridSize - 1;

    for (let x = 0; x < width; x++) {
      const gxF = (x + 0.5) / colStep - 0.5;
      let gx0 = Math.floor(gxF);
      let gx1 = gx0 + 1;
      const fx = gxF - gx0;
      if (gx0 < 0) gx0 = 0;
      if (gx0 >= gridSize) gx0 = gridSize - 1;
      if (gx1 < 0) gx1 = 0;
      if (gx1 >= gridSize) gx1 = gridSize - 1;

      const val = scaled[y * width + x];
      let idx = Math.floor(val);
      if (idx < 0) idx = 0;
      if (idx > nBins - 2) idx = nBins - 2;
      const frac = val - idx;

      // 4ブロックの CDF を線形補間
      const v00 = cdfs[gy0][gx0][idx] * (1 - frac) + cdfs[gy0][gx0][idx + 1] * frac;
      const v01 = cdfs[gy0][gx1][idx] * (1 - frac) + cdfs[gy0][gx1][idx + 1] * frac;
      const v10 = cdfs[gy1][gx0][idx] * (1 - frac) + cdfs[gy1][gx0][idx + 1] * frac;
      const v11 = cdfs[gy1][gx1][idx] * (1 - frac) + cdfs[gy1][gx1][idx + 1] * frac;

      // バイリニア補間
      const top = v00 * (1 - fx) + v01 * fx;
      const bot = v10 * (1 - fx) + v11 * fx;
      const mapped = top * (1 - fy) + bot * fy;

      result[y * width + x] = mapped / (nBins - 1) * valRange + minVal;
    }
  }

  return result;
}

/**
 * L* チャンネルに CLAHE を適用。
 * imageData を in-place で書き換える。
 *
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number} clipLimit - コントラスト制限 (1.0=弱い, 4.0=強い)
 * @param {number} [gridSize=8] - CLAHE グリッドサイズ
 */
function claheLightness(imageData, clipLimit, gridSize) {
  gridSize = gridSize || 8;
  const { data, width, height } = imageData;
  const n = width * height;

  // RGB → Lab (L* チャンネル抽出)
  const lChannel = new Float64Array(n);
  const aChannel = new Float64Array(n);
  const bChannel = new Float64Array(n);

  for (let i = 0; i < n; i++) {
    const lab = rgbToLab(data[i * 4], data[i * 4 + 1], data[i * 4 + 2]);
    lChannel[i] = lab[0];
    aChannel[i] = lab[1];
    bChannel[i] = lab[2];
  }

  // L* に CLAHE 適用
  const lEnhanced = claheChannel(lChannel, width, height, clipLimit, gridSize, 0.0, 100.0);

  // L* をクランプ
  for (let i = 0; i < n; i++) {
    let l = lEnhanced[i];
    if (l < 0.0) l = 0.0;
    if (l > 100.0) l = 100.0;
    lEnhanced[i] = l;
  }

  // Lab → RGB (in-place)
  for (let i = 0; i < n; i++) {
    const rgb = labToRgb(lEnhanced[i], aChannel[i], bChannel[i]);
    data[i * 4] = rgb[0];
    data[i * 4 + 1] = rgb[1];
    data[i * 4 + 2] = rgb[2];
  }
}

// Export for test and module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { claheChannel, claheLightness };
}
