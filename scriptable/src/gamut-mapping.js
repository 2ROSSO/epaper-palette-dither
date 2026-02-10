/**
 * gamut-mapping.js — ガマットマッピング4モード
 *
 * Python実装 (infrastructure/gamut_mapping.py) の忠実なJSポート。
 * Canvas ImageData (Uint8ClampedArray, RGBA) を直接操作。
 *
 * 4モード:
 *   1. Grayout — HSL脱彩度化
 *   2. Anti-Saturate — 四面体最近点射影 (Ericson)
 *   3. Centroid Clip — 重心レイキャスト
 *   4. Illuminant — 色温度シミュレーション
 */

// ========== HSL 変換 ==========

/**
 * RGB(0-255) → HSL (h: 0-1, s: max-min, l: 0-1)
 * s は明度正規化なしの max-min。
 */
function rgbToHsl(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  const l = (max + min) / 2;
  const s = d; // 明度正規化なし

  let h = 0;
  if (d > 0) {
    if (max === r) {
      h = ((g - b) / d) % 6;
    } else if (max === g) {
      h = (b - r) / d + 2;
    } else {
      h = (r - g) / d + 4;
    }
    h /= 6;
    h = ((h % 1) + 1) % 1;
  }

  return [h, s, l];
}

/**
 * HSL (h: 0-1, s: max-min, l: 0-1) → RGB(0-255)
 * s = max - min に対応した逆変換。
 */
function hslToRgb(h, s, l) {
  if (s === 0) {
    const v = Math.round(Math.min(1, Math.max(0, l)) * 255);
    return [v, v, v];
  }

  const p = s / 2;
  const maxC = l + p;
  const minC = l - p;
  const rng = maxC - minC;

  h = ((h % 1) + 1) % 1;
  const h6 = h * 6;

  let r, g, b;
  if (h6 < 1) {
    r = maxC; g = minC + rng * h6; b = minC;
  } else if (h6 < 2) {
    r = minC + rng * (2 - h6); g = maxC; b = minC;
  } else if (h6 < 3) {
    r = minC; g = maxC; b = minC + rng * (h6 - 2);
  } else if (h6 < 4) {
    r = minC; g = minC + rng * (4 - h6); b = maxC;
  } else if (h6 < 5) {
    r = minC + rng * (h6 - 4); g = minC; b = maxC;
  } else {
    r = maxC; g = minC; b = minC + rng * (6 - h6);
  }

  return [
    Math.max(0, Math.min(255, Math.round(Math.min(1, Math.max(0, r)) * 255))),
    Math.max(0, Math.min(255, Math.round(Math.min(1, Math.max(0, g)) * 255))),
    Math.max(0, Math.min(255, Math.round(Math.min(1, Math.max(0, b)) * 255))),
  ];
}

// ========== Grayout ==========

const DEFAULT_HUE_TOLERANCE = 60 / 360;

/**
 * パレットの有彩色の色相範囲を計算。
 * @param {number[][]} palette - [[r,g,b], ...]
 * @returns {[number, number]} [hMin, hRange]
 */
function _computePaletteHslRange(palette) {
  const hslList = palette.map(c => rgbToHsl(c[0], c[1], c[2]));

  // RGB重心
  const rSum = palette.reduce((s, c) => s + c[0], 0) / palette.length;
  const gSum = palette.reduce((s, c) => s + c[1], 0) / palette.length;
  const bSum = palette.reduce((s, c) => s + c[2], 0) / palette.length;
  const centerHsl = rgbToHsl(
    Math.max(0, Math.min(255, Math.round(rSum))),
    Math.max(0, Math.min(255, Math.round(gSum))),
    Math.max(0, Math.min(255, Math.round(bSum)))
  );
  const centerH = centerHsl[0];

  let hDistMin = 0, hDistMax = 0;
  for (const [h, s] of hslList) {
    if (s > 0.01) {
      let d = (h - centerH) % 1;
      if (d < 0) d += 1;
      if (d >= 0.5) d -= 1;
      hDistMin = Math.min(hDistMin, d);
      hDistMax = Math.max(hDistMax, d);
    }
  }

  const hMin = ((centerH + hDistMin) % 1 + 1) % 1;
  const hRange = hDistMax - hDistMin;
  return [hMin, hRange];
}

function _hueDiff(h1, h2) {
  let d = ((h1 - h2) % 1 + 1) % 1;
  return d < 0.5 ? d : d - 1;
}

function _hueClip(hMin, hRange, hue) {
  const radius = hRange / 2;
  const center = (hMin + radius) % 1;
  const d = _hueDiff(hue, center);
  if (d < -radius) return ((center - radius) % 1 + 1) % 1;
  if (d > radius) return ((center + radius) % 1 + 1) % 1;
  return hue;
}

/**
 * Grayout ガマットマッピング。
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number} strength - 0.0〜1.0
 * @param {number[][]} [palette] - パレット
 * @returns {{data: Uint8ClampedArray, width: number, height: number}}
 */
function gamutMapGrayout(imageData, strength, palette) {
  palette = palette || EINK_PALETTE;
  const { data, width, height } = imageData;
  const out = new Uint8ClampedArray(data.length);

  if (strength <= 0) {
    out.set(data);
    return { data: out, width, height };
  }
  strength = Math.min(strength, 1.0);

  const [hMin, hRange] = _computePaletteHslRange(palette);
  const hueTol = DEFAULT_HUE_TOLERANCE;

  for (let i = 0; i < data.length; i += 4) {
    const [h, s, l] = rgbToHsl(data[i], data[i+1], data[i+2]);

    // 色相クリップ
    const hClipped = _hueClip(hMin, hRange, h);

    // 色相差
    let hDiff = Math.abs(((hClipped - h + 0.5) % 1 + 1) % 1 - 0.5);

    // 脱彩度率
    const desaturation = hDiff >= hueTol ? 0 : 1 - hDiff / hueTol;
    const newS = s * (1 - strength * (1 - desaturation));

    // 色相ブレンド
    let newH = h + strength * (((hClipped - h + 0.5) % 1 + 1) % 1 - 0.5);
    newH = ((newH % 1) + 1) % 1;

    const [r, g, b] = hslToRgb(newH, newS, l);
    out[i] = r; out[i+1] = g; out[i+2] = b; out[i+3] = 255;
  }

  return { data: out, width, height };
}

// ========== Anti-Saturate (四面体最近点射影) ==========

/**
 * 四面体の面データを構築。
 * @param {number[][]} vertices - [[r,g,b], ...] 0-1スケール, 4頂点
 * @returns {{faceVerts: number[][][], faceNormals: number[][]}}
 */
function _buildTetrahedronFaces(vertices) {
  const faceIndices = [
    [1, 2, 3, 0],
    [0, 3, 2, 1],
    [0, 1, 3, 2],
    [0, 2, 1, 3],
  ];

  const faceVerts = [];
  const faceNormals = [];

  for (const [a, b, c, opp] of faceIndices) {
    const v0 = vertices[a], v1 = vertices[b], v2 = vertices[c];
    faceVerts.push([v0, v1, v2]);

    // 法線 = (v1-v0) x (v2-v0)
    const e1 = [v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]];
    const e2 = [v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]];
    let n = [
      e1[1]*e2[2] - e1[2]*e2[1],
      e1[2]*e2[0] - e1[0]*e2[2],
      e1[0]*e2[1] - e1[1]*e2[0],
    ];
    const len = Math.sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2]);
    if (len > 1e-12) {
      n = [n[0]/len, n[1]/len, n[2]/len];
    }

    // 外向きチェック
    const toOpp = [vertices[opp][0]-v0[0], vertices[opp][1]-v0[1], vertices[opp][2]-v0[2]];
    const dot = n[0]*toOpp[0] + n[1]*toOpp[1] + n[2]*toOpp[2];
    if (dot > 0) {
      n = [-n[0], -n[1], -n[2]];
    }

    faceNormals.push(n);
  }

  return { faceVerts, faceNormals };
}

function _isInsideTetrahedron(p, faceVerts, faceNormals) {
  for (let i = 0; i < 4; i++) {
    const v0 = faceVerts[i][0];
    const n = faceNormals[i];
    const dx = p[0]-v0[0], dy = p[1]-v0[1], dz = p[2]-v0[2];
    if (dx*n[0] + dy*n[1] + dz*n[2] > 1e-10) return false;
  }
  return true;
}

/**
 * 三角形上の最近点 (Ericson, Real-Time Collision Detection)
 */
function _closestPointOnTriangle(p, v0, v1, v2) {
  const ab = [v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]];
  const ac = [v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]];
  const ap = [p[0]-v0[0], p[1]-v0[1], p[2]-v0[2]];

  const d1 = ab[0]*ap[0] + ab[1]*ap[1] + ab[2]*ap[2];
  const d2 = ac[0]*ap[0] + ac[1]*ap[1] + ac[2]*ap[2];

  if (d1 <= 0 && d2 <= 0) return [...v0]; // Region A

  const bp = [p[0]-v1[0], p[1]-v1[1], p[2]-v1[2]];
  const d3 = ab[0]*bp[0] + ab[1]*bp[1] + ab[2]*bp[2];
  const d4 = ac[0]*bp[0] + ac[1]*bp[1] + ac[2]*bp[2];

  if (d3 >= 0 && d4 <= d3) return [...v1]; // Region B

  const vc = d1*d4 - d3*d2;
  if (vc <= 0 && d1 >= 0 && d3 <= 0) {
    const denom = d1 - d3;
    const s = Math.abs(denom) > 1e-30 ? d1 / denom : 0;
    return [v0[0]+s*ab[0], v0[1]+s*ab[1], v0[2]+s*ab[2]]; // Region AB
  }

  const cp = [p[0]-v2[0], p[1]-v2[1], p[2]-v2[2]];
  const d5 = ab[0]*cp[0] + ab[1]*cp[1] + ab[2]*cp[2];
  const d6 = ac[0]*cp[0] + ac[1]*cp[1] + ac[2]*cp[2];

  if (d6 >= 0 && d5 <= d6) return [...v2]; // Region C

  const vb = d5*d2 - d1*d6;
  if (vb <= 0 && d2 >= 0 && d6 <= 0) {
    const denom = d2 - d6;
    const s = Math.abs(denom) > 1e-30 ? d2 / denom : 0;
    return [v0[0]+s*ac[0], v0[1]+s*ac[1], v0[2]+s*ac[2]]; // Region AC
  }

  const va = d3*d6 - d5*d4;
  if (va <= 0 && (d4-d3) >= 0 && (d5-d6) >= 0) {
    const denom = (d4-d3) + (d5-d6);
    const s = Math.abs(denom) > 1e-30 ? (d4-d3) / denom : 0;
    const bc = [v2[0]-v1[0], v2[1]-v1[1], v2[2]-v1[2]];
    return [v1[0]+s*bc[0], v1[1]+s*bc[1], v1[2]+s*bc[2]]; // Region BC
  }

  // Region ABC: 三角形内部
  const denom = va + vb + vc;
  const safeDenom = Math.abs(denom) > 1e-30 ? denom : 1;
  const sIn = vb / safeDenom;
  const tIn = vc / safeDenom;
  return [
    v0[0] + sIn*ab[0] + tIn*ac[0],
    v0[1] + sIn*ab[1] + tIn*ac[1],
    v0[2] + sIn*ab[2] + tIn*ac[2],
  ];
}

function _projectToTetrahedronSurface(p, faceVerts) {
  let bestDistSq = Infinity;
  let bestProj = [...p];

  for (let i = 0; i < 4; i++) {
    const proj = _closestPointOnTriangle(p, faceVerts[i][0], faceVerts[i][1], faceVerts[i][2]);
    const dx = p[0]-proj[0], dy = p[1]-proj[1], dz = p[2]-proj[2];
    const distSq = dx*dx + dy*dy + dz*dz;
    if (distSq < bestDistSq) {
      bestDistSq = distSq;
      bestProj = proj;
    }
  }

  return bestProj;
}

/**
 * Anti-Saturation ガマットマッピング。
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number[][]} palette
 * @returns {{data: Uint8ClampedArray, width: number, height: number}}
 */
function antiSaturate(imageData, palette) {
  palette = palette || EINK_PALETTE;
  const { data, width, height } = imageData;
  const out = new Uint8ClampedArray(data.length);

  const vertices = palette.map(c => [c[0]/255, c[1]/255, c[2]/255]);
  const { faceVerts, faceNormals } = _buildTetrahedronFaces(vertices);

  for (let i = 0; i < data.length; i += 4) {
    const p = [data[i]/255, data[i+1]/255, data[i+2]/255];

    let result;
    if (_isInsideTetrahedron(p, faceVerts, faceNormals)) {
      result = p;
    } else {
      result = _projectToTetrahedronSurface(p, faceVerts);
    }

    out[i]   = Math.max(0, Math.min(255, Math.round(result[0] * 255)));
    out[i+1] = Math.max(0, Math.min(255, Math.round(result[1] * 255)));
    out[i+2] = Math.max(0, Math.min(255, Math.round(result[2] * 255)));
    out[i+3] = 255;
  }

  return { data: out, width, height };
}

// ========== Centroid Clip (重心方向レイキャスト) ==========

function _clipViaCentroid(p, centroid, faceVerts, faceNormals) {
  const dir = [p[0]-centroid[0], p[1]-centroid[1], p[2]-centroid[2]];
  const dirLen = Math.sqrt(dir[0]*dir[0] + dir[1]*dir[1] + dir[2]*dir[2]);

  if (dirLen < 1e-12) {
    return _projectToTetrahedronSurface(p, faceVerts);
  }

  dir[0] /= dirLen; dir[1] /= dirLen; dir[2] /= dirLen;

  let bestT = Infinity;
  let bestPoint = null;

  for (let i = 0; i < 4; i++) {
    const v0 = faceVerts[i][0];
    const n = faceNormals[i];

    const denom = dir[0]*n[0] + dir[1]*n[1] + dir[2]*n[2];
    if (Math.abs(denom) <= 1e-12) continue;

    const numer = (v0[0]-centroid[0])*n[0] + (v0[1]-centroid[1])*n[1] + (v0[2]-centroid[2])*n[2];
    const t = numer / denom;
    if (t <= 1e-10) continue;

    // 交差点
    const hit = [
      centroid[0] + t*dir[0],
      centroid[1] + t*dir[1],
      centroid[2] + t*dir[2],
    ];

    // 三角形内判定（重心座標法）
    const v1 = faceVerts[i][1], v2 = faceVerts[i][2];
    const e1 = [v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2]];
    const e2 = [v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2]];
    const hp = [hit[0]-v0[0], hit[1]-v0[1], hit[2]-v0[2]];

    const dot11 = e1[0]*e1[0] + e1[1]*e1[1] + e1[2]*e1[2];
    const dot12 = e1[0]*e2[0] + e1[1]*e2[1] + e1[2]*e2[2];
    const dot22 = e2[0]*e2[0] + e2[1]*e2[1] + e2[2]*e2[2];
    const dotH1 = hp[0]*e1[0] + hp[1]*e1[1] + hp[2]*e1[2];
    const dotH2 = hp[0]*e2[0] + hp[1]*e2[1] + hp[2]*e2[2];

    const invDenom = dot11*dot22 - dot12*dot12;
    if (Math.abs(invDenom) < 1e-30) continue;

    const u = (dot22*dotH1 - dot12*dotH2) / invDenom;
    const v = (dot11*dotH2 - dot12*dotH1) / invDenom;

    if (u >= -1e-8 && v >= -1e-8 && u+v <= 1+1e-8) {
      if (t < bestT) {
        bestT = t;
        bestPoint = hit;
      }
    }
  }

  if (bestPoint === null) {
    return _projectToTetrahedronSurface(p, faceVerts);
  }
  return bestPoint;
}

/**
 * Centroid Clip ガマットマッピング。
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number[][]} palette
 * @returns {{data: Uint8ClampedArray, width: number, height: number}}
 */
function antiSaturateCentroid(imageData, palette) {
  palette = palette || EINK_PALETTE;
  const { data, width, height } = imageData;
  const out = new Uint8ClampedArray(data.length);

  const vertices = palette.map(c => [c[0]/255, c[1]/255, c[2]/255]);
  const { faceVerts, faceNormals } = _buildTetrahedronFaces(vertices);
  const centroid = [
    vertices.reduce((s,v) => s+v[0], 0) / 4,
    vertices.reduce((s,v) => s+v[1], 0) / 4,
    vertices.reduce((s,v) => s+v[2], 0) / 4,
  ];

  for (let i = 0; i < data.length; i += 4) {
    const p = [data[i]/255, data[i+1]/255, data[i+2]/255];

    let result;
    if (_isInsideTetrahedron(p, faceVerts, faceNormals)) {
      result = p;
    } else {
      result = _clipViaCentroid(p, centroid, faceVerts, faceNormals);
    }

    out[i]   = Math.max(0, Math.min(255, Math.round(result[0] * 255)));
    out[i+1] = Math.max(0, Math.min(255, Math.round(result[1] * 255)));
    out[i+2] = Math.max(0, Math.min(255, Math.round(result[2] * 255)));
    out[i+3] = 255;
  }

  return { data: out, width, height };
}

// ========== Illuminant ==========

/**
 * 色付き照明シミュレーション。
 * @param {{data: Uint8ClampedArray, width: number, height: number}} imageData
 * @param {number} rScale - R スケール
 * @param {number} gScale - G スケール
 * @param {number} bScale - B スケール
 * @param {number} whitePreserve - 白保持の強さ
 * @returns {{data: Uint8ClampedArray, width: number, height: number}}
 */
function applyIlluminant(imageData, rScale, gScale, bScale, whitePreserve) {
  const { data, width, height } = imageData;
  const out = new Uint8ClampedArray(data.length);

  // BT.709 輝度正規化
  const lumFactor = 0.2126 * rScale + 0.7152 * gScale + 0.0722 * bScale;
  const norm = lumFactor > 1e-12 ? 1.0 / lumFactor : 1.0;
  const sR = rScale * norm;
  const sG = gScale * norm;
  const sB = bScale * norm;

  for (let i = 0; i < data.length; i += 4) {
    const oR = data[i], oG = data[i+1], oB = data[i+2];

    let r = oR * sR;
    let g = oG * sG;
    let b = oB * sB;

    if (whitePreserve > 0) {
      const lum = (oR + oG + oB) / (3 * 255);
      const preserve = lum * lum * whitePreserve;
      r = r * (1 - preserve) + oR * preserve;
      g = g * (1 - preserve) + oG * preserve;
      b = b * (1 - preserve) + oB * preserve;
    }

    out[i]   = Math.max(0, Math.min(255, Math.floor(r + 0.5)));
    out[i+1] = Math.max(0, Math.min(255, Math.floor(g + 0.5)));
    out[i+2] = Math.max(0, Math.min(255, Math.floor(b + 0.5)));
    out[i+3] = 255;
  }

  return { data: out, width, height };
}

// Export for test and module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    rgbToHsl, hslToRgb, gamutMapGrayout, antiSaturate,
    antiSaturateCentroid, applyIlluminant,
  };
}
