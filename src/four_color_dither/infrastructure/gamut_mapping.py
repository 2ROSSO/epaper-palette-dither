"""ガマットマッピング（ディザリング前処理）。

パレット外の色をHSL色空間で表現可能な範囲に圧縮する。
パレット範囲外の色相を脱彩度化（Grayout方式）し、
HSL明度を保存することで青→中間グレー等、構造を維持する。

Grayout方式の着想元: Arrayfy (https://github.com/shapoco/arrayfy)
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt

from four_color_dither.domain.color import RGB

# デフォルトの色相許容幅（0〜1スケール、1=360°）
_DEFAULT_HUE_TOLERANCE = 60.0 / 360.0


def _rgb_to_hsl_batch(
    rgb_array: npt.NDArray[np.uint8],
) -> npt.NDArray[np.float64]:
    """RGB配列をHSL色空間に一括変換。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)

    Returns:
        (H, W, 3) の float64 配列 (H: 0〜1, S: 0〜1, L: 0〜1)
    """
    rgb = rgb_array.astype(np.float64) / 255.0
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    d = max_c - min_c

    # Lightness
    l = (max_c + min_c) / 2.0

    # Saturation: 明度正規化なしの s = max - min を使用
    # （標準HSLのように明度で割らないため、S と L が独立に扱える）
    s = d.copy()

    # Hue
    h = np.zeros_like(r)
    mask_nonzero = d > 0

    mask_r = mask_nonzero & (max_c == r)
    mask_g = mask_nonzero & (max_c == g) & ~mask_r
    mask_b = mask_nonzero & (max_c == b) & ~mask_r & ~mask_g

    h[mask_r] = ((g[mask_r] - b[mask_r]) / d[mask_r]) % 6.0
    h[mask_g] = (b[mask_g] - r[mask_g]) / d[mask_g] + 2.0
    h[mask_b] = (r[mask_b] - g[mask_b]) / d[mask_b] + 4.0

    h /= 6.0
    h = h % 1.0  # 0〜1に正規化

    return np.stack([h, s, l], axis=-1)


def _hsl_to_rgb_batch(
    hsl_array: npt.NDArray[np.float64],
) -> npt.NDArray[np.uint8]:
    """HSL配列をRGBに一括変換。

    s = max - min（明度正規化なし）に対応した逆変換。

    Args:
        hsl_array: (H, W, 3) の float64 配列 (H, S, L)

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    h = hsl_array[:, :, 0]
    s = hsl_array[:, :, 1]
    l = hsl_array[:, :, 2]

    # 無彩色マスク
    achromatic = s == 0

    p = s / 2.0
    max_c = l + p
    min_c = l - p

    h6 = (h - np.floor(h)) * 6.0

    r = np.where(achromatic, l, np.zeros_like(l))
    g = np.where(achromatic, l, np.zeros_like(l))
    b = np.where(achromatic, l, np.zeros_like(l))

    rng = max_c - min_c

    # h6 < 1: r=max, g=min+rng*h6, b=min
    mask = ~achromatic & (h6 < 1)
    r = np.where(mask, max_c, r)
    g = np.where(mask, min_c + rng * h6, g)
    b = np.where(mask, min_c, b)

    # 1 <= h6 < 2: r=min+rng*(2-h6), g=max, b=min
    mask = ~achromatic & (h6 >= 1) & (h6 < 2)
    r = np.where(mask, min_c + rng * (2.0 - h6), r)
    g = np.where(mask, max_c, g)
    b = np.where(mask, min_c, b)

    # 2 <= h6 < 3: r=min, g=max, b=min+rng*(h6-2)
    mask = ~achromatic & (h6 >= 2) & (h6 < 3)
    r = np.where(mask, min_c, r)
    g = np.where(mask, max_c, g)
    b = np.where(mask, min_c + rng * (h6 - 2.0), b)

    # 3 <= h6 < 4: r=min, g=min+rng*(4-h6), b=max
    mask = ~achromatic & (h6 >= 3) & (h6 < 4)
    r = np.where(mask, min_c, r)
    g = np.where(mask, min_c + rng * (4.0 - h6), g)
    b = np.where(mask, max_c, b)

    # 4 <= h6 < 5: r=min+rng*(h6-4), g=min, b=max
    mask = ~achromatic & (h6 >= 4) & (h6 < 5)
    r = np.where(mask, min_c + rng * (h6 - 4.0), r)
    g = np.where(mask, min_c, g)
    b = np.where(mask, max_c, b)

    # 5 <= h6: r=max, g=min, b=min+rng*(6-h6)
    mask = ~achromatic & (h6 >= 5)
    r = np.where(mask, max_c, r)
    g = np.where(mask, min_c, g)
    b = np.where(mask, min_c + rng * (6.0 - h6), b)

    rgb = np.stack([r, g, b], axis=-1)
    rgb = np.clip(rgb, 0.0, 1.0)
    return np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _hue_diff(h1: npt.NDArray[np.float64], h2: float) -> npt.NDArray[np.float64]:
    """符号付き色相差（-0.5〜+0.5）。0〜1スケール。"""
    d = (h1 - h2) % 1.0
    return np.where(d < 0.5, d, d - 1.0)


def _hue_clip(
    h_min: float, h_range: float, hue: npt.NDArray[np.float64]
) -> npt.NDArray[np.float64]:
    """色相を指定範囲にクリップ。"""
    radius = h_range / 2.0
    center = (h_min + radius) % 1.0
    d = _hue_diff(hue, center)
    clipped = np.where(
        d < -radius,
        (center - radius) % 1.0,
        np.where(d > radius, (center + radius) % 1.0, hue),
    )
    return clipped % 1.0


def _compute_palette_hsl_range(
    palette: Sequence[RGB],
) -> tuple[float, float]:
    """パレットの有彩色の色相範囲を計算。

    RGB重心の色相を中心に、有彩色パレットの色相の広がりを測定する。

    Returns:
        (h_min, h_range) 0〜1スケール
    """
    hsl_list = []
    for c in palette:
        rgb = np.array([[[c.r, c.g, c.b]]], dtype=np.uint8)
        hsl = _rgb_to_hsl_batch(rgb)
        hsl_list.append((hsl[0, 0, 0], hsl[0, 0, 1], hsl[0, 0, 2]))

    # RGB重心から色相中心を求める
    r_sum = sum(c.r for c in palette) / len(palette)
    g_sum = sum(c.g for c in palette) / len(palette)
    b_sum = sum(c.b for c in palette) / len(palette)
    center_rgb = np.array([[[r_sum, g_sum, b_sum]]], dtype=np.float64)
    center_rgb = np.clip(center_rgb, 0, 255).astype(np.uint8)
    center_hsl = _rgb_to_hsl_batch(center_rgb)
    center_h = float(center_hsl[0, 0, 0])

    # 有彩色のみ色相距離を測定
    h_dist_min = 0.0
    h_dist_max = 0.0
    for h, s, _l in hsl_list:
        if s > 0.01:  # 有彩色のみ
            d = float(_hue_diff(np.array([h]), center_h)[0])
            h_dist_min = min(h_dist_min, d)
            h_dist_max = max(h_dist_max, d)

    h_min = (center_h + h_dist_min) % 1.0
    h_range = h_dist_max - h_dist_min

    return h_min, h_range


# ---------------------------------------------------------------------------
# Anti-Saturation（凸包クリッピング）
# ---------------------------------------------------------------------------


def _build_tetrahedron_faces(
    vertices: npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """四面体の面データと外向き法線を構築。

    Args:
        vertices: (4, 3) — 四面体の4頂点 (RGB 0-1)

    Returns:
        face_vertices: (4, 3, 3) — 各面の3頂点
        face_normals: (4, 3) — 各面の外向き法線（正規化済み）
    """
    # 面のインデックス: 各面は頂点3つ、残り1つが対向頂点
    face_indices = [
        (1, 2, 3, 0),
        (0, 3, 2, 1),
        (0, 1, 3, 2),
        (0, 2, 1, 3),
    ]

    face_verts = np.zeros((4, 3, 3), dtype=np.float64)
    face_normals = np.zeros((4, 3), dtype=np.float64)

    for i, (a, b, c, opp) in enumerate(face_indices):
        v0, v1, v2 = vertices[a], vertices[b], vertices[c]
        face_verts[i] = [v0, v1, v2]

        # 法線 = (v1 - v0) x (v2 - v0)
        normal = np.cross(v1 - v0, v2 - v0)
        norm_len = np.linalg.norm(normal)
        if norm_len > 1e-12:
            normal = normal / norm_len

        # 外向きチェック: 対向頂点から面への方向と法線が逆向きになるべき
        to_opp = vertices[opp] - v0
        if np.dot(normal, to_opp) > 0:
            normal = -normal

        face_normals[i] = normal

    return face_verts, face_normals


def _is_inside_tetrahedron(
    points: npt.NDArray[np.float64],
    face_vertices: npt.NDArray[np.float64],
    face_normals: npt.NDArray[np.float64],
) -> npt.NDArray[np.bool_]:
    """点群が四面体の内部にあるか判定（NumPyベクトル化）。

    Args:
        points: (N, 3) — 判定対象の点群
        face_vertices: (4, 3, 3) — 各面の3頂点
        face_normals: (4, 3) — 各面の外向き法線

    Returns:
        (N,) — True なら内部
    """
    inside = np.ones(points.shape[0], dtype=np.bool_)

    for i in range(4):
        v0 = face_vertices[i, 0]  # (3,)
        # 点から面の頂点へのベクトルと法線のドット積
        diff = points - v0[np.newaxis, :]  # (N, 3)
        dot = np.sum(diff * face_normals[i][np.newaxis, :], axis=1)  # (N,)
        # 外向き法線と同方向 = 外部
        inside &= dot <= 1e-10

    return inside


def _closest_point_on_triangle(
    points: npt.NDArray[np.float64],
    v0: npt.NDArray[np.float64],
    v1: npt.NDArray[np.float64],
    v2: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """点群から三角形上の最近点を求める（NumPyベクトル化）。

    参考: Real-Time Collision Detection (Ericson, 2004)

    Args:
        points: (N, 3)
        v0, v1, v2: (3,) — 三角形の3頂点

    Returns:
        (N, 3) — 各点に対する三角形上の最近点
    """
    ab = v1 - v0  # (3,)
    ac = v2 - v0  # (3,)
    ap = points - v0[np.newaxis, :]  # (N, 3)

    d1 = np.sum(ap * ab[np.newaxis, :], axis=1)  # (N,)
    d2 = np.sum(ap * ac[np.newaxis, :], axis=1)  # (N,)

    # 初期値: v0
    result = np.tile(v0, (points.shape[0], 1))  # (N, 3)
    region = np.full(points.shape[0], -1, dtype=np.int32)

    # Region A: v0 が最近点
    mask_a = (d1 <= 0) & (d2 <= 0)
    region[mask_a] = 0  # already v0

    bp = points - v1[np.newaxis, :]  # (N, 3)
    d3 = np.sum(bp * ab[np.newaxis, :], axis=1)
    d4 = np.sum(bp * ac[np.newaxis, :], axis=1)

    # Region B: v1 が最近点
    mask_b = (d3 >= 0) & (d4 <= d3) & (region < 0)
    result[mask_b] = v1
    region[mask_b] = 1

    # Region AB: 辺 v0-v1 上
    vc = d1 * d4 - d3 * d2
    mask_ab = (vc <= 0) & (d1 >= 0) & (d3 <= 0) & (region < 0)
    denom_ab = d1 - d3
    s_ab = np.where(np.abs(denom_ab) > 1e-30, d1 / denom_ab, 0.0)
    result[mask_ab] = (
        v0[np.newaxis, :] + s_ab[mask_ab, np.newaxis] * ab[np.newaxis, :]
    )
    region[mask_ab] = 2

    cp = points - v2[np.newaxis, :]
    d5 = np.sum(cp * ab[np.newaxis, :], axis=1)
    d6 = np.sum(cp * ac[np.newaxis, :], axis=1)

    # Region C: v2 が最近点
    mask_c = (d6 >= 0) & (d5 <= d6) & (region < 0)
    result[mask_c] = v2
    region[mask_c] = 3

    # Region AC: 辺 v0-v2 上
    vb = d5 * d2 - d1 * d6
    mask_ac = (vb <= 0) & (d2 >= 0) & (d6 <= 0) & (region < 0)
    denom_ac = d2 - d6
    s_ac = np.where(np.abs(denom_ac) > 1e-30, d2 / denom_ac, 0.0)
    result[mask_ac] = (
        v0[np.newaxis, :] + s_ac[mask_ac, np.newaxis] * ac[np.newaxis, :]
    )
    region[mask_ac] = 4

    # Region BC: 辺 v1-v2 上
    va = d3 * d6 - d5 * d4
    mask_bc = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0) & (region < 0)
    denom_bc = (d4 - d3) + (d5 - d6)
    s_bc = np.where(np.abs(denom_bc) > 1e-30, (d4 - d3) / denom_bc, 0.0)
    result[mask_bc] = (
        v1[np.newaxis, :]
        + s_bc[mask_bc, np.newaxis] * (v2 - v1)[np.newaxis, :]
    )
    region[mask_bc] = 5

    # Region ABC: 三角形内部（面への射影）
    mask_inside = region < 0
    denom_bary = va + vb + vc
    safe_denom = np.where(np.abs(denom_bary) > 1e-30, denom_bary, 1.0)
    s_in = vb / safe_denom
    t_in = vc / safe_denom
    result[mask_inside] = (
        v0[np.newaxis, :]
        + s_in[mask_inside, np.newaxis] * ab[np.newaxis, :]
        + t_in[mask_inside, np.newaxis] * ac[np.newaxis, :]
    )

    return result


def _project_to_tetrahedron_surface(
    points: npt.NDArray[np.float64],
    face_vertices: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """外部点を四面体表面上の最近点に射影する。

    Args:
        points: (N, 3) — 外部点
        face_vertices: (4, 3, 3) — 各面の3頂点

    Returns:
        (N, 3) — 四面体表面上の最近点
    """
    best_dist_sq = np.full(points.shape[0], np.inf, dtype=np.float64)
    best_proj = np.copy(points)

    for i in range(4):
        v0 = face_vertices[i, 0]
        v1 = face_vertices[i, 1]
        v2 = face_vertices[i, 2]

        proj = _closest_point_on_triangle(points, v0, v1, v2)
        diff = points - proj
        dist_sq = np.sum(diff * diff, axis=1)

        closer = dist_sq < best_dist_sq
        best_dist_sq[closer] = dist_sq[closer]
        best_proj[closer] = proj[closer]

    return best_proj


def _clip_via_centroid(
    points: npt.NDArray[np.float64],
    centroid: npt.NDArray[np.float64],
    face_vertices: npt.NDArray[np.float64],
    face_normals: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """重心からのレイキャストで外部点を四面体表面にクリップ。

    レイ: origin=centroid, direction=normalize(P - centroid)
    各面について交差判定し、最小 t > 0 の交差点を採用する。

    Args:
        points: (N, 3) — 外部点
        centroid: (3,) — 四面体重心
        face_vertices: (4, 3, 3) — 各面の3頂点
        face_normals: (4, 3) — 各面の外向き法線

    Returns:
        (N, 3) — 四面体表面上のクリップ結果
    """
    n = points.shape[0]
    directions = points - centroid[np.newaxis, :]  # (N, 3)
    dir_norms = np.linalg.norm(directions, axis=1, keepdims=True)  # (N, 1)

    # 重心と一致する点はフォールバック対象
    degenerate = (dir_norms[:, 0] < 1e-12)
    safe_norms = np.where(dir_norms > 1e-12, dir_norms, 1.0)
    directions = directions / safe_norms  # (N, 3)

    best_t = np.full(n, np.inf, dtype=np.float64)
    best_point = np.copy(points)

    for i in range(4):
        v0 = face_vertices[i, 0]  # (3,)
        normal = face_normals[i]   # (3,)

        # レイと面の交差: t = dot(v0 - centroid, normal) / dot(direction, normal)
        denom = np.sum(directions * normal[np.newaxis, :], axis=1)  # (N,)
        numer = np.dot(v0 - centroid, normal)  # scalar

        # denom ≈ 0 → レイが面と平行
        valid = np.abs(denom) > 1e-12
        t = np.where(valid, numer / np.where(valid, denom, 1.0), np.inf)

        # t > 0 のみ（重心から外向き方向）
        valid &= t > 1e-10

        # 交差点を計算（無効な t を 0 に置換して NaN/Inf 回避）
        safe_t = np.where(valid, t, 0.0)
        hit = centroid[np.newaxis, :] + safe_t[:, np.newaxis] * directions  # (N, 3)

        # 三角形内判定（重心座標法）
        v1 = face_vertices[i, 1]
        v2 = face_vertices[i, 2]
        edge1 = v1 - v0  # (3,)
        edge2 = v2 - v0  # (3,)
        h_pts = hit - v0[np.newaxis, :]  # (N, 3)

        dot11 = np.dot(edge1, edge1)
        dot12 = np.dot(edge1, edge2)
        dot22 = np.dot(edge2, edge2)
        dot_h1 = np.sum(h_pts * edge1[np.newaxis, :], axis=1)
        dot_h2 = np.sum(h_pts * edge2[np.newaxis, :], axis=1)

        inv_denom = dot11 * dot22 - dot12 * dot12
        if abs(inv_denom) < 1e-30:
            continue
        inv_denom = 1.0 / inv_denom

        u = (dot22 * dot_h1 - dot12 * dot_h2) * inv_denom
        v = (dot11 * dot_h2 - dot12 * dot_h1) * inv_denom

        in_tri = valid & (u >= -1e-8) & (v >= -1e-8) & (u + v <= 1.0 + 1e-8)

        # best_t より小さい t で三角形内ならば更新
        better = in_tri & (t < best_t)
        best_t[better] = t[better]
        best_point[better] = hit[better]

    # ヒットしなかった点 or 縮退点 → 最近点射影にフォールバック
    no_hit = (best_t == np.inf) | degenerate
    if np.any(no_hit):
        fallback_pts = points[no_hit]
        best_point[no_hit] = _project_to_tetrahedron_surface(
            fallback_pts, face_vertices,
        )

    return best_point


def anti_saturate(
    rgb_array: npt.NDArray[np.uint8],
    palette: Sequence[RGB],
) -> npt.NDArray[np.uint8]:
    """Anti-Saturation ガマットマッピング（凸包クリッピング方式）。

    パレット4色が張る四面体の外側にある色のみ
    グレー軸方向に四面体表面まで移動させる。
    色相方向の情報を可能な限り保存する。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)
        palette: パレット色のシーケンス（4色）

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    h, w = rgb_array.shape[:2]

    # パレット頂点を正規化 RGB (0-1)
    vertices = np.array(
        [[c.r / 255.0, c.g / 255.0, c.b / 255.0] for c in palette],
        dtype=np.float64,
    )

    # 四面体構築
    face_verts, face_normals = _build_tetrahedron_faces(vertices)

    # 全ピクセルを (N, 3) にフラット化
    pixels = rgb_array.reshape(-1, 3).astype(np.float64) / 255.0

    # 内部/外部判定
    inside = _is_inside_tetrahedron(pixels, face_verts, face_normals)

    # 外部ピクセルのみ処理
    outside_mask = ~inside
    outside_indices = np.where(outside_mask)[0]

    if outside_indices.size > 0:
        outside_pts = pixels[outside_indices]

        # 四面体表面上の最近点に射影
        projected = _project_to_tetrahedron_surface(outside_pts, face_verts)

        pixels[outside_indices] = projected

    # 0-255 に変換
    result = np.clip(pixels * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return result.reshape(h, w, 3)


def anti_saturate_centroid(
    rgb_array: npt.NDArray[np.uint8],
    palette: Sequence[RGB],
) -> npt.NDArray[np.uint8]:
    """Centroid Clip ガマットマッピング（重心方向レイキャスト方式）。

    パレット4色が張る四面体の重心から外部点方向にレイキャストし、
    表面との交差点にクリップする。重心はグレー軸上にないため、
    色のある面に交差しやすく、色情報が保持される。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)
        palette: パレット色のシーケンス（4色）

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    h, w = rgb_array.shape[:2]

    # パレット頂点を正規化 RGB (0-1)
    vertices = np.array(
        [[c.r / 255.0, c.g / 255.0, c.b / 255.0] for c in palette],
        dtype=np.float64,
    )

    # 四面体構築
    face_verts, face_normals = _build_tetrahedron_faces(vertices)
    centroid = vertices.mean(axis=0)

    # 全ピクセルを (N, 3) にフラット化
    pixels = rgb_array.reshape(-1, 3).astype(np.float64) / 255.0

    # 内部/外部判定
    inside = _is_inside_tetrahedron(pixels, face_verts, face_normals)

    # 外部ピクセルのみ処理
    outside_mask = ~inside
    outside_indices = np.where(outside_mask)[0]

    if outside_indices.size > 0:
        outside_pts = pixels[outside_indices]

        # 重心からのレイキャストで表面にクリップ
        clipped = _clip_via_centroid(
            outside_pts, centroid, face_verts, face_normals,
        )

        pixels[outside_indices] = clipped

    # 0-255 に変換
    result = np.clip(pixels * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return result.reshape(h, w, 3)


def gamut_map(
    rgb_array: npt.NDArray[np.uint8],
    palette: Sequence[RGB],
    strength: float = 0.7,
) -> npt.NDArray[np.uint8]:
    """ガマットマッピング前処理（HSL Grayout方式）。

    パレットの色相範囲外の色を脱彩度化（グレー化）する。
    HSL明度が保存されるため、青→中間グレーとなり構造が残る。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)
        palette: パレット色のシーケンス
        strength: マッピング強度 (0.0=無効, 1.0=最大)

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    if strength <= 0.0:
        return rgb_array.copy()

    strength = min(strength, 1.0)

    # パレットの色相範囲を計算
    h_min, h_range = _compute_palette_hsl_range(palette)
    hue_tolerance = _DEFAULT_HUE_TOLERANCE

    # RGB → HSL
    hsl = _rgb_to_hsl_batch(rgb_array)
    h = hsl[:, :, 0]
    s = hsl[:, :, 1]

    # 色相をパレット範囲にクリップ
    h_clipped = _hue_clip(h_min, h_range, h)

    # クリップ前後の色相差（絶対値）
    h_diff = np.abs(_hue_diff(h_clipped, 0.0) - _hue_diff(h, 0.0))
    # hue_diffを再計算（wrap-aroundを正しく処理）
    h_diff = np.abs(
        ((h_clipped - h + 0.5) % 1.0) - 0.5
    )

    # 彩度の調整
    # 色相差 >= tolerance → 完全脱彩度化
    # 色相差 < tolerance → 比例的に彩度を低減
    desaturation = np.where(
        h_diff >= hue_tolerance,
        0.0,
        1.0 - h_diff / hue_tolerance,
    )
    # strength を適用
    new_s = s * (1.0 - strength * (1.0 - desaturation))

    # クリップされた色相を適用
    # strength=1.0なら完全にクリップ色相に、0なら元の色相のまま
    new_h = h + strength * (((h_clipped - h + 0.5) % 1.0) - 0.5)
    new_h = new_h % 1.0

    # 新しいHSL配列を構成（明度は保存）
    new_hsl = np.stack([new_h, new_s, hsl[:, :, 2]], axis=-1)

    # HSL → RGB
    return _hsl_to_rgb_batch(new_hsl)


def apply_illuminant(
    rgb_array: npt.NDArray[np.uint8],
    r_scale: float = 1.0,
    g_scale: float = 0.7,
    b_scale: float = 0.1,
    white_preserve: float = 0.0,
) -> npt.NDArray[np.uint8]:
    """色付き照明シミュレーション（輝度補正・白保持付き）。

    RGB各チャンネルにスケール係数を乗算し、暖色系バイアスを掛ける。
    輝度（BT.709）が元画像と同等になるよう自動補正する。
    white_preserve > 0 の場合、明るいピクセルほど元の色を保持する。

    Args:
        rgb_array: (H, W, 3) の uint8 配列 (RGB)
        r_scale: R チャンネルのスケール係数 (0.0〜1.0)
        g_scale: G チャンネルのスケール係数 (0.0〜1.0)
        b_scale: B チャンネルのスケール係数 (0.0〜1.0)
        white_preserve: 白保持の強さ (0.0=無効, 1.0=明部を完全保持)

    Returns:
        (H, W, 3) の uint8 配列 (RGB)
    """
    original = rgb_array.astype(np.float64)

    # BT.709 輝度重み
    lum_factor = 0.2126 * r_scale + 0.7152 * g_scale + 0.0722 * b_scale
    norm = 1.0 / lum_factor if lum_factor > 1e-12 else 1.0
    scales = np.array(
        [r_scale * norm, g_scale * norm, b_scale * norm], dtype=np.float64,
    )
    illuminated = original * scales[np.newaxis, np.newaxis, :]

    if white_preserve > 0.0:
        # 元ピクセルの輝度 (0〜1) を二乗し、白付近だけ効くカーブにする
        lum = np.mean(original, axis=-1) / 255.0  # (H, W)
        preserve = (lum * lum) * white_preserve    # (H, W)
        preserve = preserve[:, :, np.newaxis]      # (H, W, 1)
        illuminated = illuminated * (1.0 - preserve) + original * preserve

    return np.clip(illuminated + 0.5, 0, 255).astype(np.uint8)
