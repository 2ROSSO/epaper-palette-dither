/**
 * color.js — 色計算コア
 *
 * E-Ink 4色パレット定義、RGB→Lab変換、CIEDE2000色差、最近色検索。
 * Python実装 (domain/color.py) の忠実なJSポート。
 */

// --- E-Ink 4色パレット ---

const EINK_PALETTE = [
  [255, 255, 255], // White
  [0, 0, 0],       // Black
  [200, 0, 0],     // Red
  [255, 255, 0],   // Yellow
];

// --- RGB → Lab 変換 ---

/**
 * sRGBコンポーネント(0-255)をリニアRGBに変換。
 * @param {number} c - sRGB値 (0-255)
 * @returns {number} リニアRGB値
 */
function srgbToLinear(c) {
  const v = c / 255.0;
  if (v <= 0.04045) {
    return v / 12.92;
  }
  return Math.pow((v + 0.055) / 1.055, 2.4);
}

/**
 * Lab変換の補助関数。
 * @param {number} t
 * @returns {number}
 */
function _labF(t) {
  const delta = 6.0 / 29.0;
  if (t > delta * delta * delta) {
    return Math.pow(t, 1.0 / 3.0);
  }
  return t / (3.0 * delta * delta) + 4.0 / 29.0;
}

/**
 * Lab逆変換の補助関数（_labFの逆関数）。
 * @param {number} t
 * @returns {number}
 */
function _labFInv(t) {
  const delta = 6.0 / 29.0;
  if (t > delta) {
    return t * t * t;
  }
  return 3.0 * delta * delta * (t - 4.0 / 29.0);
}

/**
 * RGB(0-255)をCIE L*a*b*に変換。D65光源基準。
 * @param {number} r - Red (0-255)
 * @param {number} g - Green (0-255)
 * @param {number} b - Blue (0-255)
 * @returns {number[]} [L, a, b]
 */
function rgbToLab(r, g, b) {
  // sRGB → リニアRGB
  const rLin = srgbToLinear(r);
  const gLin = srgbToLinear(g);
  const bLin = srgbToLinear(b);

  // リニアRGB → XYZ (D65)
  const x = 0.4124564 * rLin + 0.3575761 * gLin + 0.1804375 * bLin;
  const y = 0.2126729 * rLin + 0.7151522 * gLin + 0.0721750 * bLin;
  const z = 0.0193339 * rLin + 0.1191920 * gLin + 0.9503041 * bLin;

  // D65 白色点
  const xn = 0.95047, yn = 1.00000, zn = 1.08883;

  // XYZ → L*a*b*
  const fx = _labF(x / xn);
  const fy = _labF(y / yn);
  const fz = _labF(z / zn);

  const L = 116.0 * fy - 16.0;
  const a = 500.0 * (fx - fy);
  const bStar = 200.0 * (fy - fz);

  return [L, a, bStar];
}

/**
 * CIE L*a*b* をRGB(0-255)に変換。D65光源基準。
 * Python lab_to_rgb_batch (color_space.py) の単ピクセル版。
 * @param {number} L - L* (0-100)
 * @param {number} a - a*
 * @param {number} bStar - b*
 * @returns {number[]} [R, G, B] (0-255, clamped)
 */
function labToRgb(L, a, bStar) {
  // Lab → XYZ
  const fy = (L + 16.0) / 116.0;
  const fx = a / 500.0 + fy;
  const fz = fy - bStar / 200.0;

  const x = 0.95047 * _labFInv(fx);
  const y = 1.00000 * _labFInv(fy);
  const z = 1.08883 * _labFInv(fz);

  // XYZ → リニアRGB
  const rLin =  3.2404542 * x - 1.5371385 * y - 0.4985314 * z;
  const gLin = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z;
  const bLin =  0.0556434 * x - 0.2040259 * y + 1.0572252 * z;

  // リニアRGB → sRGB
  function toSrgb(c) {
    c = Math.max(0, Math.min(1, c));
    if (c <= 0.0031308) return 12.92 * c;
    return 1.055 * Math.pow(c, 1.0 / 2.4) - 0.055;
  }

  return [
    Math.max(0, Math.min(255, Math.round(toSrgb(rLin) * 255))),
    Math.max(0, Math.min(255, Math.round(toSrgb(gLin) * 255))),
    Math.max(0, Math.min(255, Math.round(toSrgb(bLin) * 255))),
  ];
}

/**
 * CIEDE2000色差を計算。
 * 参考: "The CIEDE2000 Color-Difference Formula" (Sharma et al., 2005)
 * @param {number[]} lab1 - [L, a, b]
 * @param {number[]} lab2 - [L, a, b]
 * @returns {number} CIEDE2000色差
 */
function ciede2000(lab1, lab2) {
  const [l1, a1, b1] = lab1;
  const [l2, a2, b2] = lab2;

  const RAD = Math.PI / 180.0;
  const DEG = 180.0 / Math.PI;

  // Step 1
  const c1Ab = Math.sqrt(a1 * a1 + b1 * b1);
  const c2Ab = Math.sqrt(a2 * a2 + b2 * b2);
  const cAbMean = (c1Ab + c2Ab) / 2.0;

  const cAbMean7 = Math.pow(cAbMean, 7);
  const g = 0.5 * (1.0 - Math.sqrt(cAbMean7 / (cAbMean7 + Math.pow(25.0, 7))));

  const a1Prime = a1 * (1.0 + g);
  const a2Prime = a2 * (1.0 + g);

  const c1Prime = Math.sqrt(a1Prime * a1Prime + b1 * b1);
  const c2Prime = Math.sqrt(a2Prime * a2Prime + b2 * b2);

  let h1Prime = (Math.atan2(b1, a1Prime) * DEG) % 360.0;
  if (h1Prime < 0) h1Prime += 360.0;
  let h2Prime = (Math.atan2(b2, a2Prime) * DEG) % 360.0;
  if (h2Prime < 0) h2Prime += 360.0;

  // Step 2: Delta値
  const deltaLPrime = l2 - l1;
  const deltaCPrime = c2Prime - c1Prime;

  let deltaHPrime;
  if (c1Prime * c2Prime === 0.0) {
    deltaHPrime = 0.0;
  } else if (Math.abs(h2Prime - h1Prime) <= 180.0) {
    deltaHPrime = h2Prime - h1Prime;
  } else if (h2Prime - h1Prime > 180.0) {
    deltaHPrime = h2Prime - h1Prime - 360.0;
  } else {
    deltaHPrime = h2Prime - h1Prime + 360.0;
  }

  const deltaHPrimeBig = 2.0 * Math.sqrt(c1Prime * c2Prime) *
    Math.sin((deltaHPrime / 2.0) * RAD);

  // Step 3: CIEDE2000
  const lPrimeMean = (l1 + l2) / 2.0;
  const cPrimeMean = (c1Prime + c2Prime) / 2.0;

  let hPrimeMean;
  if (c1Prime * c2Prime === 0.0) {
    hPrimeMean = h1Prime + h2Prime;
  } else if (Math.abs(h1Prime - h2Prime) <= 180.0) {
    hPrimeMean = (h1Prime + h2Prime) / 2.0;
  } else if (h1Prime + h2Prime < 360.0) {
    hPrimeMean = (h1Prime + h2Prime + 360.0) / 2.0;
  } else {
    hPrimeMean = (h1Prime + h2Prime - 360.0) / 2.0;
  }

  const t = 1.0
    - 0.17 * Math.cos((hPrimeMean - 30.0) * RAD)
    + 0.24 * Math.cos((2.0 * hPrimeMean) * RAD)
    + 0.32 * Math.cos((3.0 * hPrimeMean + 6.0) * RAD)
    - 0.20 * Math.cos((4.0 * hPrimeMean - 63.0) * RAD);

  const lm50sq = (lPrimeMean - 50.0) * (lPrimeMean - 50.0);
  const sl = 1.0 + 0.015 * lm50sq / Math.sqrt(20.0 + lm50sq);
  const sc = 1.0 + 0.045 * cPrimeMean;
  const sh = 1.0 + 0.015 * cPrimeMean * t;

  const cPrimeMean7 = Math.pow(cPrimeMean, 7);
  const rc = 2.0 * Math.sqrt(cPrimeMean7 / (cPrimeMean7 + Math.pow(25.0, 7)));
  const deltaTheta = 30.0 * Math.exp(
    -Math.pow((hPrimeMean - 275.0) / 25.0, 2)
  );
  const rt = -Math.sin((2.0 * deltaTheta) * RAD) * rc;

  return Math.sqrt(
    Math.pow(deltaLPrime / sl, 2) +
    Math.pow(deltaCPrime / sc, 2) +
    Math.pow(deltaHPrimeBig / sh, 2) +
    rt * (deltaCPrime / sc) * (deltaHPrimeBig / sh)
  );
}

/**
 * パレットから最も近い色をCIEDE2000で検索。
 * @param {number} r - Red (0-255)
 * @param {number} g - Green (0-255)
 * @param {number} b - Blue (0-255)
 * @param {number[][]} palette - パレット色配列 [[r,g,b], ...]
 * @param {number} redPenalty - 赤ペナルティ係数 (0=無効)
 * @param {number} yellowPenalty - 黄ペナルティ係数 (0=無効)
 * @param {number} brightness - 正規化輝度 (0.0〜1.0)
 * @returns {number[]} 最近パレット色 [r, g, b]
 */
function findNearestColor(r, g, b, palette, redPenalty, yellowPenalty, brightness) {
  palette = palette || EINK_PALETTE;
  redPenalty = redPenalty || 0.0;
  yellowPenalty = yellowPenalty || 0.0;
  brightness = brightness || 0.0;

  const lab = rgbToLab(r, g, b);
  let bestColor = palette[0];
  let bestDist = Infinity;

  for (const p of palette) {
    let dist = ciede2000(lab, rgbToLab(p[0], p[1], p[2]));

    // 赤パレット色 (R>150, G<50, B<50) に明度ベースのペナルティ
    if (redPenalty > 0.0 && p[0] > 150 && p[1] < 50 && p[2] < 50) {
      dist += redPenalty * brightness;
    }
    // 黄パレット色 (R>200, G>200, B<50) に暗部ベースのペナルティ
    if (yellowPenalty > 0.0 && p[0] > 200 && p[1] > 200 && p[2] < 50) {
      dist += yellowPenalty * (1.0 - brightness);
    }

    if (dist < bestDist) {
      bestDist = dist;
      bestColor = p;
    }
  }

  return bestColor;
}

// --- sRGB → Linear LUT (256エントリ事前計算) ---

const SRGB_TO_LINEAR_LUT = new Float64Array(256);
for (let i = 0; i < 256; i++) {
  const v = i / 255.0;
  SRGB_TO_LINEAR_LUT[i] = v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
}

// --- Lab変換定数 ---
const _LAB_DELTA = 6.0 / 29.0;
const _LAB_DELTA_SQ3 = _LAB_DELTA * _LAB_DELTA * _LAB_DELTA;
const _LAB_DELTA_SQ3_INV = 1.0 / (3.0 * _LAB_DELTA * _LAB_DELTA);
const _LAB_OFFSET = 4.0 / 29.0;
const _XN_INV = 1.0 / 0.95047;
const _ZN_INV = 1.0 / 1.08883;

/**
 * RGB(0-255) → Lab インライン高速変換。
 * rgbToLabと同じ結果だがLUTベースで高速。
 * @param {number} r - Red (0-255, integer)
 * @param {number} g - Green (0-255, integer)
 * @param {number} b - Blue (0-255, integer)
 * @returns {number[]} [L, a, b]
 */
function rgbToLabFast(r, g, b) {
  const rLin = SRGB_TO_LINEAR_LUT[r];
  const gLin = SRGB_TO_LINEAR_LUT[g];
  const bLin = SRGB_TO_LINEAR_LUT[b];

  const xr = (0.4124564 * rLin + 0.3575761 * gLin + 0.1804375 * bLin) * _XN_INV;
  const yr = 0.2126729 * rLin + 0.7151522 * gLin + 0.0721750 * bLin;
  const zr = (0.0193339 * rLin + 0.1191920 * gLin + 0.9503041 * bLin) * _ZN_INV;

  const fx = xr > _LAB_DELTA_SQ3 ? Math.pow(xr, 1.0 / 3.0) : xr * _LAB_DELTA_SQ3_INV + _LAB_OFFSET;
  const fy = yr > _LAB_DELTA_SQ3 ? Math.pow(yr, 1.0 / 3.0) : yr * _LAB_DELTA_SQ3_INV + _LAB_OFFSET;
  const fz = zr > _LAB_DELTA_SQ3 ? Math.pow(zr, 1.0 / 3.0) : zr * _LAB_DELTA_SQ3_INV + _LAB_OFFSET;

  return [116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)];
}


// --- LUT (ルックアップテーブル) ---

const LUT_STEP = 4;
const LUT_SIZE = 64; // 256 / LUT_STEP

/**
 * RGB→パレットインデックスの3D LUTを構築。
 * Lab Euclidean距離で最近色を決定。ペナルティなし。
 *
 * @param {number[][]} palette - パレット [[r,g,b], ...]
 * @returns {Uint8Array} 64³ のフラット配列。インデックス = (r>>2)*64*64 + (g>>2)*64 + (b>>2)
 */
function buildDitherLut(palette) {
  palette = palette || EINK_PALETTE;
  const palLab = palette.map(c => rgbToLabFast(c[0], c[1], c[2]));
  const nPal = palette.length;
  const lut = new Uint8Array(LUT_SIZE * LUT_SIZE * LUT_SIZE);
  const half = LUT_STEP >> 1; // 2

  for (let ri = 0; ri < LUT_SIZE; ri++) {
    const r = ri * LUT_STEP + half;
    for (let gi = 0; gi < LUT_SIZE; gi++) {
      const g = gi * LUT_STEP + half;
      for (let bi = 0; bi < LUT_SIZE; bi++) {
        const b = bi * LUT_STEP + half;
        const lab = rgbToLabFast(r, g, b);
        const pL = lab[0], pa = lab[1], pb = lab[2];

        let bestIdx = 0, bestDist = Infinity;
        for (let p = 0; p < nPal; p++) {
          const dL = pL - palLab[p][0];
          const da = pa - palLab[p][1];
          const db = pb - palLab[p][2];
          const dist = dL * dL + da * da + db * db;
          if (dist < bestDist) { bestDist = dist; bestIdx = p; }
        }
        lut[ri * LUT_SIZE * LUT_SIZE + gi * LUT_SIZE + bi] = bestIdx;
      }
    }
  }
  return lut;
}

/**
 * Lab Euclidean距離 + ペナルティで最近色インデックスを検索。
 * ペナルティあり時のディザリングループ用。
 *
 * @param {number} r - Red (0-255, integer)
 * @param {number} g - Green (0-255, integer)
 * @param {number} b - Blue (0-255, integer)
 * @param {number[][]} palette - パレット
 * @param {number[][]} palLab - パレットLab値 (事前計算済み)
 * @param {number} redPenalty - 赤ペナルティ係数
 * @param {number} yellowPenalty - 黄ペナルティ係数
 * @param {number} brightness - 正規化輝度 (0.0-1.0)
 * @returns {number} パレットインデックス
 */
function findNearestIndexLabEuclidean(r, g, b, palette, palLab, redPenalty, yellowPenalty, brightness) {
  const lab = rgbToLabFast(r, g, b);
  const pL = lab[0], pa = lab[1], pb = lab[2];
  let bestIdx = 0, bestDist = Infinity;

  for (let i = 0; i < palette.length; i++) {
    const dL = pL - palLab[i][0];
    const da = pa - palLab[i][1];
    const db = pb - palLab[i][2];
    let dist = Math.sqrt(dL * dL + da * da + db * db);

    const p = palette[i];
    if (redPenalty > 0 && p[0] > 150 && p[1] < 50 && p[2] < 50) {
      dist += redPenalty * brightness;
    }
    if (yellowPenalty > 0 && p[0] > 200 && p[1] > 200 && p[2] < 50) {
      dist += yellowPenalty * (1.0 - brightness);
    }

    if (dist < bestDist) { bestDist = dist; bestIdx = i; }
  }
  return bestIdx;
}

// Export for test and module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    EINK_PALETTE, srgbToLinear, rgbToLab, rgbToLabFast, labToRgb, ciede2000,
    findNearestColor, findNearestIndexLabEuclidean,
    buildDitherLut, LUT_STEP, LUT_SIZE,
  };
}
