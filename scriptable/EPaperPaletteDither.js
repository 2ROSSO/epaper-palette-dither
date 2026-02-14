// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: deep-brown; icon-glyph: palette;
// share-sheet-inputs: file-url, image;
// always-run-in-app: true;

// EPaperPaletteDither.js — E-Ink 4色ディザリング for iPhone
//
// Usage:
//   1. Scriptableアプリで直接実行 → フォトライブラリから選択
//   2. 共有シートから画像を受け取り実行
//   3. Shortcuts から実行 (Script.setShortcutOutput)

// ===== 1. 画像取得 =====
let img;
if (args.images && args.images.length > 0) {
  // 共有シート / Shortcuts から Image として受け取り
  img = args.images[0];
} else if (args.fileURLs && args.fileURLs.length > 0) {
  // 共有シートから File URL として受け取り
  img = Image.fromFile(args.fileURLs[0]);
} else {
  // 直接実行: フォトライブラリから選択
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
const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>E-Paper Palette Dither</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --border: #0f3460;
    --accent: #e94560;
    --text: #e0e0e0;
    --text2: #a0a0a0;
    --btn: #0f3460;
    --btn-active: #e94560;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', sans-serif;
    font-size: 14px;
    background: var(--bg);
    color: var(--text);
    padding: 12px;
    padding-bottom: 80px;
    overscroll-behavior: none;
  }
  h1 {
    text-align: center;
    font-size: 18px;
    color: var(--accent);
    margin-bottom: 12px;
    font-weight: 600;
  }

  /* Preview canvases */
  .preview-container {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px;
    margin-bottom: 8px;
    text-align: center;
  }
  .preview-label {
    font-size: 11px;
    color: var(--text2);
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .preview-container canvas {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0 auto;
    background: #222;
    image-rendering: pixelated;
  }

  /* Controls */
  .control-section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
  }
  .control-row {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    gap: 8px;
  }
  .control-row:last-child { margin-bottom: 0; }
  .control-label {
    min-width: 72px;
    font-size: 12px;
    color: var(--text2);
    flex-shrink: 0;
  }
  .control-value {
    min-width: 48px;
    text-align: right;
    font-size: 12px;
    font-family: 'SF Mono', monospace;
    color: var(--accent);
  }

  /* Segmented buttons */
  .segmented {
    display: flex;
    flex: 1;
    gap: 2px;
    background: var(--bg);
    border-radius: 6px;
    padding: 2px;
  }
  .segmented button {
    flex: 1;
    padding: 6px 4px;
    font-size: 11px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--text2);
    cursor: pointer;
    transition: all 0.15s;
  }
  .segmented button.active {
    background: var(--btn-active);
    color: #fff;
    font-weight: 600;
  }

  /* Sliders */
  input[type=range] {
    -webkit-appearance: none;
    flex: 1;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    outline: none;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
  }

  /* Action buttons */
  .actions {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }
  .actions button {
    flex: 1;
    padding: 12px;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-secondary { background: var(--btn); color: var(--text); }
  .btn-save { background: #2e7d32; color: #fff; }
  .btn-primary:disabled, .btn-secondary:disabled, .btn-save:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Progress */
  #progress {
    display: none;
    text-align: center;
    padding: 16px;
    font-size: 13px;
    color: var(--accent);
  }
  #progress.visible { display: block; }

  /* Image info */
  .info {
    text-align: center;
    font-size: 11px;
    color: var(--text2);
    margin-bottom: 8px;
  }

  /* Hidden file input for browser testing */
  .file-input-wrapper {
    text-align: center;
    margin-bottom: 12px;
  }
  .file-input-wrapper label {
    display: inline-block;
    padding: 10px 24px;
    background: var(--btn);
    color: var(--text);
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
  }
  .file-input-wrapper input { display: none; }
</style>
</head>
<body>

<h1>E-Paper Palette Dither</h1>

<!-- For browser testing: file picker (hidden when in Scriptable) -->
<div class="file-input-wrapper" id="filePicker">
  <label>Load Image<input type="file" accept="image/*" id="fileInput"></label>
</div>

<div class="info" id="imageInfo">No image loaded</div>

<div class="preview-container">
  <div class="preview-label">Original</div>
  <canvas id="origCanvas" width="1" height="1"></canvas>
</div>

<div class="preview-container">
  <div class="preview-label">Dithered</div>
  <canvas id="ditherCanvas" width="1" height="1"></canvas>
</div>

<div id="progress">Converting...</div>

<!-- Target preset -->
<div class="control-section">
  <div class="control-row">
    <span class="control-label">Target:</span>
    <div class="segmented" id="presetBtns">
      <button data-w="296" data-h="128">2.9"</button>
      <button data-w="400" data-h="300" class="active">4.2"</button>
    </div>
  </div>

  <div class="control-row">
    <span class="control-label">Color:</span>
    <div class="segmented" id="colorBtns">
      <button data-mode="grayout">Gray</button>
      <button data-mode="antisat">AntiSat</button>
      <button data-mode="centroid">Cent</button>
      <button data-mode="illuminant" class="active">Illum</button>
    </div>
  </div>
</div>

<!-- Lab space toggle (only for AntiSat / Centroid) -->
<div class="control-section" id="labSection" style="display:none">
  <div class="control-row">
    <label><input type="checkbox" id="labCheckbox" checked> Lab space gamut mapping</label>
  </div>
</div>

<!-- Grayout strength (only for Grayout mode) -->
<div class="control-section" id="strengthSection" style="display:none">
  <div class="control-row">
    <span class="control-label">Strength:</span>
    <input type="range" id="strengthSlider" min="0" max="100" value="70">
    <span class="control-value" id="strengthValue">0.70</span>
  </div>
</div>

<!-- Illuminant params (only for Illuminant mode) -->
<div class="control-section" id="illuminantSection">
  <div class="control-row">
    <span class="control-label">Red:</span>
    <input type="range" id="illumRedSlider" min="0" max="100" value="100">
    <span class="control-value" id="illumRedValue">1.00</span>
  </div>
  <div class="control-row">
    <span class="control-label">Yellow:</span>
    <input type="range" id="illumYellowSlider" min="0" max="100" value="100">
    <span class="control-value" id="illumYellowValue">1.00</span>
  </div>
  <div class="control-row">
    <span class="control-label">White:</span>
    <input type="range" id="illumWhiteSlider" min="0" max="100" value="100">
    <span class="control-value" id="illumWhiteValue">1.00</span>
  </div>
</div>

<!-- Quality params -->
<div class="control-section">
  <div class="control-row">
    <span class="control-label">CSF:</span>
    <input type="range" id="csfSlider" min="0" max="100" value="60" step="5">
    <span class="control-value" id="csfValue">0.60</span>
  </div>
  <div class="control-row">
    <label><input type="checkbox" id="claheCheckbox"> CLAHE</label>
    <span class="control-label" style="min-width:36px">Clip:</span>
    <input type="range" id="clipSlider" min="100" max="400" value="200" step="10" disabled>
    <span class="control-value" id="clipValue">2.00</span>
  </div>
  <div class="control-row">
    <span class="control-label">ErrClamp:</span>
    <input type="range" id="errClampSlider" min="0" max="128" value="85">
    <span class="control-value" id="errClampValue">85</span>
  </div>
  <div class="control-row">
    <span class="control-label">RedPen:</span>
    <input type="range" id="redPenSlider" min="0" max="1000" value="0">
    <span class="control-value" id="redPenValue">0.0</span>
  </div>
  <div class="control-row">
    <span class="control-label">YellowPen:</span>
    <input type="range" id="yellowPenSlider" min="0" max="1000" value="0">
    <span class="control-value" id="yellowPenValue">0.0</span>
  </div>
</div>

<!-- Action buttons -->
<div class="control-section">
  <div class="actions">
    <button class="btn-primary" id="convertBtn" disabled>Convert</button>
    <button class="btn-secondary" id="gamutBtn" disabled>Gamut Only</button>
    <button class="btn-save" id="saveBtn" disabled>Save</button>
  </div>
</div>

<!-- Inline JS modules -->
<script>
// ===== color.js =====
const EINK_PALETTE = [
  [255, 255, 255],
  [0, 0, 0],
  [200, 0, 0],
  [255, 255, 0],
];

function srgbToLinear(c) {
  const v = c / 255.0;
  if (v <= 0.04045) return v / 12.92;
  return Math.pow((v + 0.055) / 1.055, 2.4);
}

function _labF(t) {
  const delta = 6.0 / 29.0;
  if (t > delta * delta * delta) return Math.pow(t, 1.0 / 3.0);
  return t / (3.0 * delta * delta) + 4.0 / 29.0;
}

function rgbToLab(r, g, b) {
  const rLin = srgbToLinear(r), gLin = srgbToLinear(g), bLin = srgbToLinear(b);
  const x = 0.4124564*rLin + 0.3575761*gLin + 0.1804375*bLin;
  const y = 0.2126729*rLin + 0.7151522*gLin + 0.0721750*bLin;
  const z = 0.0193339*rLin + 0.1191920*gLin + 0.9503041*bLin;
  const fx = _labF(x/0.95047), fy = _labF(y/1.0), fz = _labF(z/1.08883);
  return [116*fy-16, 500*(fx-fy), 200*(fy-fz)];
}

function _labFInv(t) {
  const delta = 6.0 / 29.0;
  if (t > delta) return t * t * t;
  return 3.0 * delta * delta * (t - 4.0 / 29.0);
}

function labToRgb(L, a, bStar) {
  const fy = (L + 16.0) / 116.0, fx = a / 500.0 + fy, fz = fy - bStar / 200.0;
  const x = 0.95047 * _labFInv(fx), y = 1.00000 * _labFInv(fy), z = 1.08883 * _labFInv(fz);
  const rLin = 3.2404542*x - 1.5371385*y - 0.4985314*z;
  const gLin = -0.9692660*x + 1.8760108*y + 0.0415560*z;
  const bLin = 0.0556434*x - 0.2040259*y + 1.0572252*z;
  function toSrgb(c){c=Math.max(0,Math.min(1,c));if(c<=0.0031308)return 12.92*c;return 1.055*Math.pow(c,1/2.4)-0.055;}
  return [Math.max(0,Math.min(255,Math.round(toSrgb(rLin)*255))),Math.max(0,Math.min(255,Math.round(toSrgb(gLin)*255))),Math.max(0,Math.min(255,Math.round(toSrgb(bLin)*255)))];
}

function ciede2000(lab1, lab2) {
  const [l1,a1,b1]=lab1, [l2,a2,b2]=lab2;
  const RAD=Math.PI/180, DEG=180/Math.PI;
  const c1Ab=Math.sqrt(a1*a1+b1*b1), c2Ab=Math.sqrt(a2*a2+b2*b2);
  const cAbMean=(c1Ab+c2Ab)/2, cAbMean7=Math.pow(cAbMean,7);
  const g=0.5*(1-Math.sqrt(cAbMean7/(cAbMean7+Math.pow(25,7))));
  const a1P=a1*(1+g), a2P=a2*(1+g);
  const c1P=Math.sqrt(a1P*a1P+b1*b1), c2P=Math.sqrt(a2P*a2P+b2*b2);
  let h1P=(Math.atan2(b1,a1P)*DEG)%360; if(h1P<0)h1P+=360;
  let h2P=(Math.atan2(b2,a2P)*DEG)%360; if(h2P<0)h2P+=360;
  const dLP=l2-l1, dCP=c2P-c1P;
  let dhP; if(c1P*c2P===0)dhP=0; else if(Math.abs(h2P-h1P)<=180)dhP=h2P-h1P;
  else if(h2P-h1P>180)dhP=h2P-h1P-360; else dhP=h2P-h1P+360;
  const dHP=2*Math.sqrt(c1P*c2P)*Math.sin(dhP/2*RAD);
  const lPM=(l1+l2)/2, cPM=(c1P+c2P)/2;
  let hPM; if(c1P*c2P===0)hPM=h1P+h2P; else if(Math.abs(h1P-h2P)<=180)hPM=(h1P+h2P)/2;
  else if(h1P+h2P<360)hPM=(h1P+h2P+360)/2; else hPM=(h1P+h2P-360)/2;
  const t=1-0.17*Math.cos((hPM-30)*RAD)+0.24*Math.cos(2*hPM*RAD)+0.32*Math.cos((3*hPM+6)*RAD)-0.20*Math.cos((4*hPM-63)*RAD);
  const lm50=(lPM-50)*(lPM-50);
  const sl=1+0.015*lm50/Math.sqrt(20+lm50), sc=1+0.045*cPM, sh=1+0.015*cPM*t;
  const cPM7=Math.pow(cPM,7), rc=2*Math.sqrt(cPM7/(cPM7+Math.pow(25,7)));
  const dTh=30*Math.exp(-Math.pow((hPM-275)/25,2));
  const rt=-Math.sin(2*dTh*RAD)*rc;
  return Math.sqrt(Math.pow(dLP/sl,2)+Math.pow(dCP/sc,2)+Math.pow(dHP/sh,2)+rt*(dCP/sc)*(dHP/sh));
}

function findNearestColor(r,g,b,palette,redPen,yellowPen,brightness) {
  palette=palette||EINK_PALETTE; redPen=redPen||0; yellowPen=yellowPen||0; brightness=brightness||0;
  const lab=rgbToLab(r,g,b); let best=palette[0], bestD=Infinity;
  for(const p of palette) {
    let d=ciede2000(lab,rgbToLab(p[0],p[1],p[2]));
    if(redPen>0&&p[0]>150&&p[1]<50&&p[2]<50)d+=redPen*brightness;
    if(yellowPen>0&&p[0]>200&&p[1]>200&&p[2]<50)d+=yellowPen*(1-brightness);
    if(d<bestD){bestD=d;best=p;}
  } return best;
}

// --- sRGB→Linear LUT & Lab高速変換 ---
const SRGB_TO_LINEAR_LUT=new Float64Array(256);
for(let i=0;i<256;i++){const v=i/255;SRGB_TO_LINEAR_LUT[i]=v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4);}
const _LAB_DELTA=6/29,_LAB_DELTA_SQ3=_LAB_DELTA*_LAB_DELTA*_LAB_DELTA,_LAB_DELTA_SQ3_INV=1/(3*_LAB_DELTA*_LAB_DELTA),_LAB_OFFSET=4/29,_XN_INV=1/0.95047,_ZN_INV=1/1.08883;
function rgbToLabFast(r,g,b){
  const rL=SRGB_TO_LINEAR_LUT[r],gL=SRGB_TO_LINEAR_LUT[g],bL=SRGB_TO_LINEAR_LUT[b];
  const xr=(0.4124564*rL+0.3575761*gL+0.1804375*bL)*_XN_INV,yr=0.2126729*rL+0.7151522*gL+0.0721750*bL,zr=(0.0193339*rL+0.1191920*gL+0.9503041*bL)*_ZN_INV;
  const fx=xr>_LAB_DELTA_SQ3?Math.pow(xr,1/3):xr*_LAB_DELTA_SQ3_INV+_LAB_OFFSET;
  const fy=yr>_LAB_DELTA_SQ3?Math.pow(yr,1/3):yr*_LAB_DELTA_SQ3_INV+_LAB_OFFSET;
  const fz=zr>_LAB_DELTA_SQ3?Math.pow(zr,1/3):zr*_LAB_DELTA_SQ3_INV+_LAB_OFFSET;
  return[116*fy-16,500*(fx-fy),200*(fy-fz)];
}

// --- LUT ---
const LUT_STEP=4,LUT_SIZE=64;
function buildDitherLut(palette){
  palette=palette||EINK_PALETTE;const palLab=palette.map(c=>rgbToLabFast(c[0],c[1],c[2]));const nPal=palette.length;
  const lut=new Uint8Array(LUT_SIZE*LUT_SIZE*LUT_SIZE);const half=LUT_STEP>>1;
  for(let ri=0;ri<LUT_SIZE;ri++){const r=ri*LUT_STEP+half;for(let gi=0;gi<LUT_SIZE;gi++){const g=gi*LUT_STEP+half;for(let bi=0;bi<LUT_SIZE;bi++){const b=bi*LUT_STEP+half;
    const lab=rgbToLabFast(r,g,b);const pL=lab[0],pa=lab[1],pb=lab[2];let bI=0,bD=Infinity;
    for(let p=0;p<nPal;p++){const dL=pL-palLab[p][0],da=pa-palLab[p][1],db=pb-palLab[p][2],d=dL*dL+da*da+db*db;if(d<bD){bD=d;bI=p;}}
    lut[ri*4096+gi*64+bi]=bI;}}}return lut;
}
function findNearestIndexLabEuclidean(r,g,b,palette,palLab,redPen,yellowPen,brightness){
  const lab=rgbToLabFast(r,g,b);const pL=lab[0],pa=lab[1],pb=lab[2];let bI=0,bD=Infinity;
  for(let i=0;i<palette.length;i++){const dL=pL-palLab[i][0],da=pa-palLab[i][1],db=pb-palLab[i][2];let d=Math.sqrt(dL*dL+da*da+db*db);
    const p=palette[i];if(redPen>0&&p[0]>150&&p[1]<50&&p[2]<50)d+=redPen*brightness;if(yellowPen>0&&p[0]>200&&p[1]>200&&p[2]<50)d+=yellowPen*(1-brightness);
    if(d<bD){bD=d;bI=i;}}return bI;
}

// ===== gamut-mapping.js =====
const DEFAULT_HUE_TOLERANCE=60/360;

function rgbToHsl(r,g,b) {
  r/=255;g/=255;b/=255;
  const mx=Math.max(r,g,b),mn=Math.min(r,g,b),d=mx-mn,l=(mx+mn)/2,s=d;
  let h=0;
  if(d>0){if(mx===r)h=((g-b)/d)%6;else if(mx===g)h=(b-r)/d+2;else h=(r-g)/d+4;h/=6;h=((h%1)+1)%1;}
  return[h,s,l];
}

function hslToRgb(h,s,l) {
  if(s===0){const v=Math.round(Math.min(1,Math.max(0,l))*255);return[v,v,v];}
  const p=s/2,maxC=l+p,minC=l-p,rng=maxC-minC;
  h=((h%1)+1)%1;const h6=h*6;
  let r,g,b;
  if(h6<1){r=maxC;g=minC+rng*h6;b=minC;}
  else if(h6<2){r=minC+rng*(2-h6);g=maxC;b=minC;}
  else if(h6<3){r=minC;g=maxC;b=minC+rng*(h6-2);}
  else if(h6<4){r=minC;g=minC+rng*(4-h6);b=maxC;}
  else if(h6<5){r=minC+rng*(h6-4);g=minC;b=maxC;}
  else{r=maxC;g=minC;b=minC+rng*(6-h6);}
  return[Math.max(0,Math.min(255,Math.round(Math.min(1,Math.max(0,r))*255))),Math.max(0,Math.min(255,Math.round(Math.min(1,Math.max(0,g))*255))),Math.max(0,Math.min(255,Math.round(Math.min(1,Math.max(0,b))*255)))];
}

function _computePaletteHslRange(palette) {
  const hslList=palette.map(c=>rgbToHsl(c[0],c[1],c[2]));
  const rS=palette.reduce((s,c)=>s+c[0],0)/palette.length;
  const gS=palette.reduce((s,c)=>s+c[1],0)/palette.length;
  const bS=palette.reduce((s,c)=>s+c[2],0)/palette.length;
  const cH=rgbToHsl(Math.max(0,Math.min(255,Math.round(rS))),Math.max(0,Math.min(255,Math.round(gS))),Math.max(0,Math.min(255,Math.round(bS))))[0];
  let hDMin=0,hDMax=0;
  for(const[h,s]of hslList){if(s>0.01){let d=((h-cH)%1+1)%1;if(d>=0.5)d-=1;hDMin=Math.min(hDMin,d);hDMax=Math.max(hDMax,d);}}
  return[((cH+hDMin)%1+1)%1,hDMax-hDMin];
}
function _hueDiff(h1,h2){let d=((h1-h2)%1+1)%1;return d<0.5?d:d-1;}
function _hueClip(hMin,hRange,hue){const r=hRange/2,c=(hMin+r)%1,d=_hueDiff(hue,c);if(d<-r)return((c-r)%1+1)%1;if(d>r)return((c+r)%1+1)%1;return hue;}

function gamutMapGrayout(imageData,strength,palette) {
  palette=palette||EINK_PALETTE;const{data,width,height}=imageData;const out=new Uint8ClampedArray(data.length);
  if(strength<=0){out.set(data);return{data:out,width,height};}
  strength=Math.min(strength,1);
  const[hMin,hRange]=_computePaletteHslRange(palette),hueTol=DEFAULT_HUE_TOLERANCE;
  for(let i=0;i<data.length;i+=4){
    const[h,s,l]=rgbToHsl(data[i],data[i+1],data[i+2]);
    const hC=_hueClip(hMin,hRange,h);
    let hDiff=Math.abs(((hC-h+0.5)%1+1)%1-0.5);
    const desat=hDiff>=hueTol?0:1-hDiff/hueTol;
    const nS=s*(1-strength*(1-desat));
    let nH=h+strength*(((hC-h+0.5)%1+1)%1-0.5);nH=((nH%1)+1)%1;
    const[r,g,b]=hslToRgb(nH,nS,l);
    out[i]=r;out[i+1]=g;out[i+2]=b;out[i+3]=255;
  }
  return{data:out,width,height};
}

function _buildTetrahedronFaces(verts) {
  const fi=[[1,2,3,0],[0,3,2,1],[0,1,3,2],[0,2,1,3]];
  const fV=[],fN=[];
  for(const[a,b,c,o]of fi){
    const v0=verts[a],v1=verts[b],v2=verts[c];fV.push([v0,v1,v2]);
    const e1=[v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2]],e2=[v2[0]-v0[0],v2[1]-v0[1],v2[2]-v0[2]];
    let n=[e1[1]*e2[2]-e1[2]*e2[1],e1[2]*e2[0]-e1[0]*e2[2],e1[0]*e2[1]-e1[1]*e2[0]];
    const len=Math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);if(len>1e-12)n=[n[0]/len,n[1]/len,n[2]/len];
    const to=[verts[o][0]-v0[0],verts[o][1]-v0[1],verts[o][2]-v0[2]];
    if(n[0]*to[0]+n[1]*to[1]+n[2]*to[2]>0)n=[-n[0],-n[1],-n[2]];
    fN.push(n);
  }
  return{faceVerts:fV,faceNormals:fN};
}

function _isInsideTetrahedron(p,fV,fN){for(let i=0;i<4;i++){const v=fV[i][0],n=fN[i];if((p[0]-v[0])*n[0]+(p[1]-v[1])*n[1]+(p[2]-v[2])*n[2]>1e-10)return false;}return true;}

function _closestPointOnTriangle(p,v0,v1,v2){
  const ab=[v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2]],ac=[v2[0]-v0[0],v2[1]-v0[1],v2[2]-v0[2]],ap=[p[0]-v0[0],p[1]-v0[1],p[2]-v0[2]];
  const d1=ab[0]*ap[0]+ab[1]*ap[1]+ab[2]*ap[2],d2=ac[0]*ap[0]+ac[1]*ap[1]+ac[2]*ap[2];
  if(d1<=0&&d2<=0)return[...v0];
  const bp=[p[0]-v1[0],p[1]-v1[1],p[2]-v1[2]],d3=ab[0]*bp[0]+ab[1]*bp[1]+ab[2]*bp[2],d4=ac[0]*bp[0]+ac[1]*bp[1]+ac[2]*bp[2];
  if(d3>=0&&d4<=d3)return[...v1];
  const vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0){const dn=d1-d3,s=Math.abs(dn)>1e-30?d1/dn:0;return[v0[0]+s*ab[0],v0[1]+s*ab[1],v0[2]+s*ab[2]];}
  const cp=[p[0]-v2[0],p[1]-v2[1],p[2]-v2[2]],d5=ab[0]*cp[0]+ab[1]*cp[1]+ab[2]*cp[2],d6=ac[0]*cp[0]+ac[1]*cp[1]+ac[2]*cp[2];
  if(d6>=0&&d5<=d6)return[...v2];
  const vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0){const dn=d2-d6,s=Math.abs(dn)>1e-30?d2/dn:0;return[v0[0]+s*ac[0],v0[1]+s*ac[1],v0[2]+s*ac[2]];}
  const va=d3*d6-d5*d4;if(va<=0&&(d4-d3)>=0&&(d5-d6)>=0){const dn=(d4-d3)+(d5-d6),s=Math.abs(dn)>1e-30?(d4-d3)/dn:0;const bc=[v2[0]-v1[0],v2[1]-v1[1],v2[2]-v1[2]];return[v1[0]+s*bc[0],v1[1]+s*bc[1],v1[2]+s*bc[2]];}
  const dm=va+vb+vc,sd=Math.abs(dm)>1e-30?dm:1,sI=vb/sd,tI=vc/sd;
  return[v0[0]+sI*ab[0]+tI*ac[0],v0[1]+sI*ab[1]+tI*ac[1],v0[2]+sI*ab[2]+tI*ac[2]];
}

function _projectToTetrahedronSurface(p,fV){
  let bD=Infinity,bP=[...p];
  for(let i=0;i<4;i++){const pr=_closestPointOnTriangle(p,fV[i][0],fV[i][1],fV[i][2]);const dx=p[0]-pr[0],dy=p[1]-pr[1],dz=p[2]-pr[2];const ds=dx*dx+dy*dy+dz*dz;if(ds<bD){bD=ds;bP=pr;}}
  return bP;
}

function antiSaturate(imageData,palette) {
  palette=palette||EINK_PALETTE;const{data,width,height}=imageData;const out=new Uint8ClampedArray(data.length);
  const verts=palette.map(c=>[c[0]/255,c[1]/255,c[2]/255]);const{faceVerts:fV,faceNormals:fN}=_buildTetrahedronFaces(verts);
  for(let i=0;i<data.length;i+=4){const p=[data[i]/255,data[i+1]/255,data[i+2]/255];const r=_isInsideTetrahedron(p,fV,fN)?p:_projectToTetrahedronSurface(p,fV);
    out[i]=Math.max(0,Math.min(255,Math.round(r[0]*255)));out[i+1]=Math.max(0,Math.min(255,Math.round(r[1]*255)));out[i+2]=Math.max(0,Math.min(255,Math.round(r[2]*255)));out[i+3]=255;}
  return{data:out,width,height};
}

function _clipViaCentroid(p,cen,fV,fN){
  const dir=[p[0]-cen[0],p[1]-cen[1],p[2]-cen[2]];const dL=Math.sqrt(dir[0]*dir[0]+dir[1]*dir[1]+dir[2]*dir[2]);
  if(dL<1e-12)return _projectToTetrahedronSurface(p,fV);
  dir[0]/=dL;dir[1]/=dL;dir[2]/=dL;let bT=Infinity,bP=null;
  for(let i=0;i<4;i++){const v0=fV[i][0],n=fN[i];const dn=dir[0]*n[0]+dir[1]*n[1]+dir[2]*n[2];if(Math.abs(dn)<=1e-12)continue;
    const nm=(v0[0]-cen[0])*n[0]+(v0[1]-cen[1])*n[1]+(v0[2]-cen[2])*n[2];const t=nm/dn;if(t<=1e-10)continue;
    const hit=[cen[0]+t*dir[0],cen[1]+t*dir[1],cen[2]+t*dir[2]];
    const v1=fV[i][1],v2=fV[i][2],e1=[v1[0]-v0[0],v1[1]-v0[1],v1[2]-v0[2]],e2=[v2[0]-v0[0],v2[1]-v0[1],v2[2]-v0[2]],hp=[hit[0]-v0[0],hit[1]-v0[1],hit[2]-v0[2]];
    const d11=e1[0]*e1[0]+e1[1]*e1[1]+e1[2]*e1[2],d12=e1[0]*e2[0]+e1[1]*e2[1]+e1[2]*e2[2],d22=e2[0]*e2[0]+e2[1]*e2[1]+e2[2]*e2[2];
    const dh1=hp[0]*e1[0]+hp[1]*e1[1]+hp[2]*e1[2],dh2=hp[0]*e2[0]+hp[1]*e2[1]+hp[2]*e2[2];
    const iD=d11*d22-d12*d12;if(Math.abs(iD)<1e-30)continue;
    const u=(d22*dh1-d12*dh2)/iD,v=(d11*dh2-d12*dh1)/iD;
    if(u>=-1e-8&&v>=-1e-8&&u+v<=1+1e-8&&t<bT){bT=t;bP=hit;}}
  return bP||_projectToTetrahedronSurface(p,fV);
}

function antiSaturateCentroid(imageData,palette) {
  palette=palette||EINK_PALETTE;const{data,width,height}=imageData;const out=new Uint8ClampedArray(data.length);
  const verts=palette.map(c=>[c[0]/255,c[1]/255,c[2]/255]);const{faceVerts:fV,faceNormals:fN}=_buildTetrahedronFaces(verts);
  const cen=[verts.reduce((s,v)=>s+v[0],0)/4,verts.reduce((s,v)=>s+v[1],0)/4,verts.reduce((s,v)=>s+v[2],0)/4];
  for(let i=0;i<data.length;i+=4){const p=[data[i]/255,data[i+1]/255,data[i+2]/255];const r=_isInsideTetrahedron(p,fV,fN)?p:_clipViaCentroid(p,cen,fV,fN);
    out[i]=Math.max(0,Math.min(255,Math.round(r[0]*255)));out[i+1]=Math.max(0,Math.min(255,Math.round(r[1]*255)));out[i+2]=Math.max(0,Math.min(255,Math.round(r[2]*255)));out[i+3]=255;}
  return{data:out,width,height};
}

function antiSaturateLab(imageData,palette) {
  palette=palette||EINK_PALETTE;const{data,width,height}=imageData;const out=new Uint8ClampedArray(data.length);
  const labVerts=palette.map(c=>rgbToLab(c[0],c[1],c[2]));const{faceVerts:fV,faceNormals:fN}=_buildTetrahedronFaces(labVerts);
  for(let i=0;i<data.length;i+=4){const lab=rgbToLab(data[i],data[i+1],data[i+2]);const r=_isInsideTetrahedron(lab,fV,fN)?lab:_projectToTetrahedronSurface(lab,fV);
    const rgb=labToRgb(r[0],r[1],r[2]);out[i]=rgb[0];out[i+1]=rgb[1];out[i+2]=rgb[2];out[i+3]=255;}
  return{data:out,width,height};
}

function antiSaturateCentroidLab(imageData,palette) {
  palette=palette||EINK_PALETTE;const{data,width,height}=imageData;const out=new Uint8ClampedArray(data.length);
  const labVerts=palette.map(c=>rgbToLab(c[0],c[1],c[2]));const{faceVerts:fV,faceNormals:fN}=_buildTetrahedronFaces(labVerts);
  const cen=[labVerts.reduce((s,v)=>s+v[0],0)/4,labVerts.reduce((s,v)=>s+v[1],0)/4,labVerts.reduce((s,v)=>s+v[2],0)/4];
  for(let i=0;i<data.length;i+=4){const lab=rgbToLab(data[i],data[i+1],data[i+2]);const r=_isInsideTetrahedron(lab,fV,fN)?lab:_clipViaCentroid(lab,cen,fV,fN);
    const rgb=labToRgb(r[0],r[1],r[2]);out[i]=rgb[0];out[i+1]=rgb[1];out[i+2]=rgb[2];out[i+3]=255;}
  return{data:out,width,height};
}

function applyIlluminant(imageData,rS,gS,bS,wP) {
  const{data,width,height}=imageData;const out=new Uint8ClampedArray(data.length);
  const lF=0.2126*rS+0.7152*gS+0.0722*bS,nm=lF>1e-12?1/lF:1;
  const sR=rS*nm,sG=gS*nm,sB=bS*nm;
  for(let i=0;i<data.length;i+=4){const oR=data[i],oG=data[i+1],oB=data[i+2];
    let r=oR*sR,g=oG*sG,b=oB*sB;
    if(wP>0){const lum=(oR+oG+oB)/(3*255);const pr=lum*lum*wP;r=r*(1-pr)+oR*pr;g=g*(1-pr)+oG*pr;b=b*(1-pr)+oB*pr;}
    out[i]=Math.max(0,Math.min(255,Math.floor(r+0.5)));out[i+1]=Math.max(0,Math.min(255,Math.floor(g+0.5)));out[i+2]=Math.max(0,Math.min(255,Math.floor(b+0.5)));out[i+3]=255;}
  return{data:out,width,height};
}

// ===== lightness-remap.js =====
function claheChannel(channel,width,height,clipLimit,gridSize,minVal,maxVal,nBins){
  nBins=nBins||256;const result=new Float64Array(width*height);const valRange=maxVal-minVal;
  if(valRange<1e-10){result.set(channel);return result;}
  const scaled=new Float64Array(width*height);const scaleF=(nBins-1)/valRange;
  for(let i=0;i<scaled.length;i++){let v=(channel[i]-minVal)*scaleF;if(v<0)v=0;if(v>nBins-1)v=nBins-1;scaled[i]=v;}
  const rowStep=height/gridSize,colStep=width/gridSize;
  const cdfs=[];
  for(let gy=0;gy<gridSize;gy++){cdfs[gy]=[];
    const y0=Math.round(gy*rowStep);let y1=Math.round((gy+1)*rowStep);if(y1<=y0)y1=y0+1;
    for(let gx=0;gx<gridSize;gx++){
      const x0=Math.round(gx*colStep);let x1=Math.round((gx+1)*colStep);if(x1<=x0)x1=x0+1;
      const nPx=(y1-y0)*(x1-x0);const hist=new Float64Array(nBins);
      for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){let idx=Math.round(scaled[y*width+x]);if(idx<0)idx=0;if(idx>=nBins)idx=nBins-1;hist[idx]+=1.0;}
      const ac=clipLimit*nPx/nBins;let excess=0;for(let i=0;i<nBins;i++){if(hist[i]>ac){excess+=hist[i]-ac;hist[i]=ac;}}
      const rd=excess/nBins;for(let i=0;i<nBins;i++)hist[i]+=rd;
      const cdf=new Float64Array(nBins);cdf[0]=hist[0];for(let i=1;i<nBins;i++)cdf[i]=cdf[i-1]+hist[i];
      let cdfMin=0;for(let i=0;i<nBins;i++){if(cdf[i]>0){cdfMin=cdf[i];break;}}
      const denom=nPx-cdfMin;
      if(denom<1){for(let i=0;i<nBins;i++)cdf[i]=i;}else{for(let i=0;i<nBins;i++)cdf[i]=(cdf[i]-cdfMin)/denom*(nBins-1);}
      cdfs[gy][gx]=cdf;
    }
  }
  for(let y=0;y<height;y++){
    const gyF=(y+0.5)/rowStep-0.5;let gy0=Math.floor(gyF),gy1=gy0+1;const fy=gyF-gy0;
    gy0=Math.max(0,Math.min(gridSize-1,gy0));gy1=Math.max(0,Math.min(gridSize-1,gy1));
    for(let x=0;x<width;x++){
      const gxF=(x+0.5)/colStep-0.5;let gx0=Math.floor(gxF),gx1=gx0+1;const fx=gxF-gx0;
      gx0=Math.max(0,Math.min(gridSize-1,gx0));gx1=Math.max(0,Math.min(gridSize-1,gx1));
      const val=scaled[y*width+x];let idx=Math.floor(val);if(idx<0)idx=0;if(idx>nBins-2)idx=nBins-2;const frac=val-idx;
      const v00=cdfs[gy0][gx0][idx]*(1-frac)+cdfs[gy0][gx0][idx+1]*frac;
      const v01=cdfs[gy0][gx1][idx]*(1-frac)+cdfs[gy0][gx1][idx+1]*frac;
      const v10=cdfs[gy1][gx0][idx]*(1-frac)+cdfs[gy1][gx0][idx+1]*frac;
      const v11=cdfs[gy1][gx1][idx]*(1-frac)+cdfs[gy1][gx1][idx+1]*frac;
      const top=v00*(1-fx)+v01*fx,bot=v10*(1-fx)+v11*fx;
      result[y*width+x]=(top*(1-fy)+bot*fy)/(nBins-1)*valRange+minVal;
    }
  }
  return result;
}
function claheLightness(imageData,clipLimit,gridSize){
  gridSize=gridSize||8;const{data,width,height}=imageData;const n=width*height;
  const lCh=new Float64Array(n),aCh=new Float64Array(n),bCh=new Float64Array(n);
  for(let i=0;i<n;i++){const lab=rgbToLab(data[i*4],data[i*4+1],data[i*4+2]);lCh[i]=lab[0];aCh[i]=lab[1];bCh[i]=lab[2];}
  const lE=claheChannel(lCh,width,height,clipLimit,gridSize,0.0,100.0);
  for(let i=0;i<n;i++){let l=lE[i];if(l<0)l=0;if(l>100)l=100;lE[i]=l;}
  for(let i=0;i<n;i++){const rgb=labToRgb(lE[i],aCh[i],bCh[i]);data[i*4]=rgb[0];data[i*4+1]=rgb[1];data[i*4+2]=rgb[2];}
}

// ===== dithering.js =====
function floydSteinbergDither(imageData,palette,errClamp,redPen,yellowPen,csfChromaWeight) {
  palette=palette||EINK_PALETTE;errClamp=errClamp||0;redPen=redPen||0;yellowPen=yellowPen||0;csfChromaWeight=csfChromaWeight??1.0;
  const{data,width,height}=imageData;const usePen=redPen>0||yellowPen>0;
  const work=new Float32Array(width*height*3);
  for(let i=0;i<width*height;i++){work[i*3]=data[i*4];work[i*3+1]=data[i*4+1];work[i*3+2]=data[i*4+2];}
  const lut=buildDitherLut(palette);
  const palLab=usePen?palette.map(c=>rgbToLabFast(c[0],c[1],c[2])):null;
  for(let y=0;y<height;y++){for(let x=0;x<width;x++){
    const idx=(y*width+x)*3;const oR=work[idx],oG=work[idx+1],oB=work[idx+2];
    const cr=Math.max(0,Math.min(255,Math.round(oR))),cg=Math.max(0,Math.min(255,Math.round(oG))),cb=Math.max(0,Math.min(255,Math.round(oB)));
    let pI;if(usePen){const br=Math.max(0,Math.min(1,(0.2126*cr+0.7152*cg+0.0722*cb)/255));pI=findNearestIndexLabEuclidean(cr,cg,cb,palette,palLab,redPen,yellowPen,br);}
    else pI=lut[(cr>>2)*4096+(cg>>2)*64+(cb>>2)];
    const nr=palette[pI];work[idx]=nr[0];work[idx+1]=nr[1];work[idx+2]=nr[2];
    let eR=oR-nr[0],eG=oG-nr[1],eB=oB-nr[2];
    if(errClamp>0){if(eR>errClamp)eR=errClamp;else if(eR<-errClamp)eR=-errClamp;if(eG>errClamp)eG=errClamp;else if(eG<-errClamp)eG=-errClamp;if(eB>errClamp)eB=errClamp;else if(eB<-errClamp)eB=-errClamp;}
    if(csfChromaWeight<1.0){const eLum=0.2126*eR+0.7152*eG+0.0722*eB;let eRG=eR-eG;let eBY=0.5*(eR+eG)-eB;eRG*=csfChromaWeight;eBY*=csfChromaWeight;eR=eLum+0.7513*eRG+0.0722*eBY;eG=eLum-0.2487*eRG+0.0722*eBY;eB=eLum+0.2513*eRG-0.9278*eBY;}
    if(x+1<width){const ni=idx+3;work[ni]+=eR*0.4375;work[ni+1]+=eG*0.4375;work[ni+2]+=eB*0.4375;}
    if(y+1<height){if(x-1>=0){const ni=idx+(width-1)*3;work[ni]+=eR*0.1875;work[ni+1]+=eG*0.1875;work[ni+2]+=eB*0.1875;}
      {const ni=idx+width*3;work[ni]+=eR*0.3125;work[ni+1]+=eG*0.3125;work[ni+2]+=eB*0.3125;}
      if(x+1<width){const ni=idx+(width+1)*3;work[ni]+=eR*0.0625;work[ni+1]+=eG*0.0625;work[ni+2]+=eB*0.0625;}}
  }}
  const out=new Uint8ClampedArray(width*height*4);
  for(let i=0;i<width*height;i++){out[i*4]=Math.max(0,Math.min(255,Math.round(work[i*3])));out[i*4+1]=Math.max(0,Math.min(255,Math.round(work[i*3+1])));out[i*4+2]=Math.max(0,Math.min(255,Math.round(work[i*3+2])));out[i*4+3]=255;}
  return{data:out,width,height};
}
</script>

<!-- App logic -->
<script>
(function() {
  // State
  let sourceImage = null;       // HTMLImageElement (original)
  let targetW = 400, targetH = 300;
  let colorMode = 'illuminant';
  let resultBase64 = null;

  // DOM refs
  const origCanvas = document.getElementById('origCanvas');
  const ditherCanvas = document.getElementById('ditherCanvas');
  const origCtx = origCanvas.getContext('2d');
  const ditherCtx = ditherCanvas.getContext('2d');
  const progressEl = document.getElementById('progress');
  const infoEl = document.getElementById('imageInfo');
  const convertBtn = document.getElementById('convertBtn');
  const gamutBtn = document.getElementById('gamutBtn');
  const saveBtn = document.getElementById('saveBtn');

  // Lab checkbox ref
  const labCheckbox = document.getElementById('labCheckbox');

  // Slider refs
  const strengthSlider = document.getElementById('strengthSlider');
  const strengthValue = document.getElementById('strengthValue');
  const illumRedSlider = document.getElementById('illumRedSlider');
  const illumYellowSlider = document.getElementById('illumYellowSlider');
  const illumWhiteSlider = document.getElementById('illumWhiteSlider');
  const illumRedValue = document.getElementById('illumRedValue');
  const illumYellowValue = document.getElementById('illumYellowValue');
  const illumWhiteValue = document.getElementById('illumWhiteValue');
  const csfSlider = document.getElementById('csfSlider');
  const csfValueEl = document.getElementById('csfValue');
  const claheCheckbox = document.getElementById('claheCheckbox');
  const clipSlider = document.getElementById('clipSlider');
  const clipValueEl = document.getElementById('clipValue');
  const errClampSlider = document.getElementById('errClampSlider');
  const redPenSlider = document.getElementById('redPenSlider');
  const yellowPenSlider = document.getElementById('yellowPenSlider');
  const errClampValue = document.getElementById('errClampValue');
  const redPenValue = document.getElementById('redPenValue');
  const yellowPenValue = document.getElementById('yellowPenValue');

  // ===== Preset buttons =====
  document.getElementById('presetBtns').addEventListener('click', e => {
    if (!e.target.dataset.w) return;
    document.querySelectorAll('#presetBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    targetW = parseInt(e.target.dataset.w);
    targetH = parseInt(e.target.dataset.h);
    if (sourceImage) showOriginal();
  });

  // ===== Color mode buttons =====
  document.getElementById('colorBtns').addEventListener('click', e => {
    if (!e.target.dataset.mode) return;
    document.querySelectorAll('#colorBtns button').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    colorMode = e.target.dataset.mode;

    // Show/hide mode-specific controls
    document.getElementById('strengthSection').style.display = colorMode === 'grayout' ? '' : 'none';
    document.getElementById('labSection').style.display = (colorMode === 'antisat' || colorMode === 'centroid') ? '' : 'none';
    document.getElementById('illuminantSection').style.display = colorMode === 'illuminant' ? '' : 'none';
  });

  // ===== Slider handlers =====
  strengthSlider.oninput = () => { strengthValue.textContent = (strengthSlider.value / 100).toFixed(2); };
  illumRedSlider.oninput = () => { illumRedValue.textContent = (illumRedSlider.value / 100).toFixed(2); };
  illumYellowSlider.oninput = () => { illumYellowValue.textContent = (illumYellowSlider.value / 100).toFixed(2); };
  illumWhiteSlider.oninput = () => { illumWhiteValue.textContent = (illumWhiteSlider.value / 100).toFixed(2); };
  csfSlider.oninput = () => { csfValueEl.textContent = (csfSlider.value / 100).toFixed(2); };
  clipSlider.oninput = () => { clipValueEl.textContent = (clipSlider.value / 100).toFixed(2); };
  claheCheckbox.onchange = () => { clipSlider.disabled = !claheCheckbox.checked; };
  errClampSlider.oninput = () => { errClampValue.textContent = errClampSlider.value; };
  redPenSlider.oninput = () => { redPenValue.textContent = (redPenSlider.value / 10).toFixed(1); };
  yellowPenSlider.oninput = () => { yellowPenValue.textContent = (yellowPenSlider.value / 10).toFixed(1); };

  // ===== File input (browser testing) =====
  document.getElementById('fileInput').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => loadImageFromDataURL(ev.target.result);
    reader.readAsDataURL(file);
  });

  // ===== Image loading =====
  function loadImageFromDataURL(dataUrl) {
    const img = new Image();
    img.onload = () => {
      sourceImage = img;
      convertBtn.disabled = false;
      gamutBtn.disabled = false;
      showOriginal();
    };
    img.src = dataUrl;
  }

  // Called from Scriptable: inject base64 image
  window.loadBase64Image = function(base64) {
    document.getElementById('filePicker').style.display = 'none';
    loadImageFromDataURL('data:image/jpeg;base64,' + base64);
  };

  function showOriginal() {
    let srcW = sourceImage.width, srcH = sourceImage.height;

    // 縦長画像 + 横長ターゲット → 自動90° CW回転
    const needsRotate = (srcH > srcW) && (targetW > targetH);

    if (needsRotate) {
      // 回転後の論理サイズ
      srcW = sourceImage.height;
      srcH = sourceImage.width;
    }

    // Resize to target while maintaining aspect ratio
    const scale = Math.min(targetW / srcW, targetH / srcH);
    const w = Math.round(srcW * scale);
    const h = Math.round(srcH * scale);

    origCanvas.width = w;
    origCanvas.height = h;

    if (needsRotate) {
      origCtx.save();
      origCtx.translate(w, 0);
      origCtx.rotate(Math.PI / 2);
      origCtx.drawImage(sourceImage, 0, 0, h, w);
      origCtx.restore();
    } else {
      origCtx.drawImage(sourceImage, 0, 0, w, h);
    }

    ditherCanvas.width = w;
    ditherCanvas.height = h;
    ditherCtx.fillStyle = '#222';
    ditherCtx.fillRect(0, 0, w, h);

    const rotateLabel = needsRotate ? ' (rotated)' : '';
    infoEl.textContent = \`\${sourceImage.width}x\${sourceImage.height} → \${w}x\${h}\${rotateLabel}\`;
    saveBtn.disabled = true;
    resultBase64 = null;
  }

  // ===== Processing =====
  function getParams() {
    return {
      strength: strengthSlider.value / 100,
      illumRed: illumRedSlider.value / 100,
      illumYellow: illumYellowSlider.value / 100,
      illumWhite: illumWhiteSlider.value / 100,
      csfChromaWeight: csfSlider.value / 100,
      lightnessRemap: claheCheckbox.checked,
      lightnessClipLimit: clipSlider.value / 100,
      errClamp: parseInt(errClampSlider.value),
      redPen: redPenSlider.value / 10,
      yellowPen: yellowPenSlider.value / 10,
    };
  }

  function applyColorProcessing(imgData, params) {
    switch (colorMode) {
      case 'antisat':
        return labCheckbox.checked ? antiSaturateLab(imgData, EINK_PALETTE)
                                   : antiSaturate(imgData, EINK_PALETTE);
      case 'centroid':
        return labCheckbox.checked ? antiSaturateCentroidLab(imgData, EINK_PALETTE)
                                   : antiSaturateCentroid(imgData, EINK_PALETTE);
      case 'illuminant': {
        const rScale = params.illumRed + params.illumYellow;
        const gScale = params.illumYellow;
        return applyIlluminant(imgData, rScale, gScale, 0, params.illumWhite);
      }
      default:
        return gamutMapGrayout(imgData, params.strength, EINK_PALETTE);
    }
  }

  function processAsync(ditherEnabled) {
    if (!sourceImage) return;

    const params = getParams();
    progressEl.classList.add('visible');
    convertBtn.disabled = true;
    gamutBtn.disabled = true;

    // Use setTimeout to allow UI update
    setTimeout(() => {
      try {
        // Get resized original
        const w = origCanvas.width, h = origCanvas.height;
        const srcData = origCtx.getImageData(0, 0, w, h);

        // Color processing
        const mapped = applyColorProcessing(
          { data: srcData.data, width: w, height: h },
          params
        );

        // CLAHE lightness remap
        if (params.lightnessRemap) {
          claheLightness(mapped, params.lightnessClipLimit);
        }

        let result;
        if (ditherEnabled) {
          result = floydSteinbergDither(
            mapped, EINK_PALETTE, params.errClamp, params.redPen, params.yellowPen, params.csfChromaWeight
          );
        } else {
          result = mapped;
        }

        // Draw result
        const outData = ditherCtx.createImageData(w, h);
        outData.data.set(result.data);
        ditherCtx.putImageData(outData, 0, 0);

        // Store result as base64
        resultBase64 = ditherCanvas.toDataURL('image/png').split(',')[1];
        saveBtn.disabled = false;
      } catch (err) {
        progressEl.textContent = 'Error: ' + err.message;
        console.error(err);
      } finally {
        progressEl.classList.remove('visible');
        convertBtn.disabled = false;
        gamutBtn.disabled = false;
      }
    }, 50);
  }

  convertBtn.addEventListener('click', () => processAsync(true));
  gamutBtn.addEventListener('click', () => processAsync(false));

  // ===== Save =====
  saveBtn.addEventListener('click', () => {
    if (!resultBase64) return;

    // In Scriptable context, notify via completion handler
    if (window.webkit && window.webkit.messageHandlers) {
      window.webkit.messageHandlers.scriptable.postMessage(resultBase64);
      return;
    }

    // Browser fallback: download
    const link = document.createElement('a');
    link.download = 'dithered.png';
    link.href = 'data:image/png;base64,' + resultBase64;
    link.click();
  });

  // ===== Scriptable result getter =====
  window.getResult = function() {
    return resultBase64;
  };

})();
</script>
</body>
</html>
`;

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

  // Shortcuts対応（通常実行時はスキップ）
  try { Script.setShortcutOutput(resultImage); } catch (e) {}
}

Script.complete();
