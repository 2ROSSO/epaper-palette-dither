"""パラメータ自動最適化サービス。

Optuna TPE (Tree-structured Parzen Estimator) で Convert パラメータを
自動探索し、元画像との類似度を最大化する。
Reconvert パラメータ（blur_radius, brightness）は固定値。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
import numpy.typing as npt
import optuna

from epaper_palette_dither.domain.color import EINK_PALETTE, RGB
from epaper_palette_dither.domain.image_model import ColorMode, ImageSpec
from epaper_palette_dither.application.dither_service import DitherService
from epaper_palette_dither.application.image_converter import ImageConverter
from epaper_palette_dither.application.reconvert_service import ReconvertService
from epaper_palette_dither.infrastructure.image_io import resize_image
from epaper_palette_dither.infrastructure.image_metrics import compute_composite_score


@dataclass
class ParamDef:
    """探索パラメータの定義。"""

    name: str
    min_val: float
    max_val: float
    coarse_step: float
    fine_step: float
    is_int: bool = False


@dataclass
class OptimizeResult:
    """最適化の結果。"""

    best_params: dict[str, float]
    best_score: float
    metrics: dict[str, float]
    log: list[str] = field(default_factory=list)


# Reconvert 固定パラメータ
_RECONVERT_BLUR_RADIUS = 1
_RECONVERT_BRIGHTNESS = 1.0


def _apply_converter_params(
    converter: ImageConverter,
    params: dict[str, float],
    color_mode: ColorMode,
) -> None:
    """ImageConverter のプロパティに params の値を反映。"""
    converter.color_mode = color_mode
    converter.gamut_strength = params.get("gamut_strength", 0.7)
    converter.illuminant_red = params.get("illuminant_red", 1.0)
    converter.illuminant_yellow = params.get("illuminant_yellow", 1.0)
    converter.illuminant_white = params.get("illuminant_white", 1.0)
    converter.error_clamp = int(params.get("error_clamp", 85))
    converter.red_penalty = params.get("red_penalty", 0.0)
    converter.yellow_penalty = params.get("yellow_penalty", 0.0)
    converter.csf_chroma_weight = params.get("csf_chroma_weight", 0.6)


def _suggest_params(
    trial: optuna.Trial,
    param_defs: list[ParamDef],
) -> dict[str, float]:
    """Optuna Trial からパラメータ候補を生成。"""
    params: dict[str, float] = {}
    for pd in param_defs:
        if pd.is_int:
            params[pd.name] = float(
                trial.suggest_int(pd.name, int(pd.min_val), int(pd.max_val), step=int(pd.fine_step))
            )
        else:
            params[pd.name] = trial.suggest_float(
                pd.name, pd.min_val, pd.max_val, step=pd.fine_step,
            )
    return params


class OptimizerService:
    """Optuna TPE ベースのパラメータ最適化。"""

    def get_param_defs(self, color_mode: ColorMode) -> list[ParamDef]:
        """ColorMode に応じた探索パラメータ定義を返す。"""
        common = [
            ParamDef("error_clamp", 0, 128, 32, 8, is_int=True),
            ParamDef("red_penalty", 0.0, 100.0, 20, 5),
            ParamDef("yellow_penalty", 0.0, 100.0, 20, 5),
            ParamDef("csf_chroma_weight", 0.0, 1.0, 0.2, 0.05),
        ]

        if color_mode == ColorMode.ILLUMINANT:
            return [
                ParamDef("illuminant_red", 0.0, 1.0, 0.2, 0.05),
                ParamDef("illuminant_yellow", 0.0, 1.0, 0.2, 0.05),
                ParamDef("illuminant_white", 0.0, 1.0, 0.2, 0.05),
                *common,
            ]

        if color_mode == ColorMode.GRAYOUT:
            return [
                ParamDef("gamut_strength", 0.0, 1.0, 0.2, 0.05),
                *common,
            ]

        # ANTI_SATURATION / CENTROID_CLIP
        return list(common)

    def optimize(
        self,
        source_image: npt.NDArray[np.uint8],
        spec: ImageSpec,
        color_mode: ColorMode,
        initial_params: dict[str, float],
        palette: Sequence[RGB] = EINK_PALETTE,
        n_trials: int = 50,
        progress: Callable[[str, float], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> OptimizeResult:
        """パラメータを自動最適化。

        Args:
            source_image: 元画像 (H, W, 3) uint8
            spec: 変換仕様
            color_mode: 使用する ColorMode
            initial_params: 現在のUIパラメータ
            palette: カラーパレット
            n_trials: Optuna の試行回数
            progress: 進捗コールバック (message, 0.0-1.0)
            cancelled: キャンセル判定コールバック

        Returns:
            OptimizeResult
        """
        param_defs = self.get_param_defs(color_mode)

        # Optuna ログ抑制
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        # 事前リサイズ（1回だけ）
        pre_resized = resize_image(
            source_image, spec.target_width, spec.target_height, spec.keep_aspect_ratio,
        )
        reference = pre_resized

        # インスタンス再利用
        converter = ImageConverter(DitherService(), palette)
        reconvert_service = ReconvertService()

        eval_count = 0

        def evaluate(params: dict[str, float]) -> float:
            nonlocal eval_count
            eval_count += 1

            _apply_converter_params(converter, params, color_mode)
            dithered = converter.convert_pre_resized(pre_resized)

            reconverted = reconvert_service.reconvert_array(
                dithered,
                blur_radius=_RECONVERT_BLUR_RADIUS,
                color_mode=color_mode,
                gamut_strength=params.get("gamut_strength", 0.7),
                illuminant_red=params.get("illuminant_red", 1.0),
                illuminant_yellow=params.get("illuminant_yellow", 1.0),
                illuminant_white=params.get("illuminant_white", 1.0),
                palette=palette,
                brightness=_RECONVERT_BRIGHTNESS,
            )

            metrics = compute_composite_score(reference, reconverted)
            return metrics["composite"]

        # Optuna Study
        def objective(trial: optuna.Trial) -> float:
            params = _suggest_params(trial, param_defs)
            return evaluate(params)

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
        )

        # 初期値を最初の候補として登録（step に合わせてスナップ）
        enqueue_params: dict[str, float | int] = {}
        for pd in param_defs:
            if pd.name in initial_params:
                val = initial_params[pd.name]
                if pd.is_int:
                    step = int(pd.fine_step)
                    snapped = int(round((val - pd.min_val) / step) * step + pd.min_val)
                    snapped = max(int(pd.min_val), min(int(pd.max_val), snapped))
                    enqueue_params[pd.name] = snapped
                else:
                    step = pd.fine_step
                    snapped = round((val - pd.min_val) / step) * step + pd.min_val
                    snapped = max(pd.min_val, min(pd.max_val, snapped))
                    enqueue_params[pd.name] = snapped
        study.enqueue_trial(enqueue_params)

        def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
            if cancelled and cancelled():
                study.stop()
            if progress:
                pct = (trial.number + 1) / n_trials
                score_str = f"{trial.value:.4f}" if trial.value is not None else "N/A"
                progress(
                    f"Trial {trial.number + 1}/{n_trials}: {score_str}",
                    min(pct, 0.95),
                )

        study.optimize(objective, n_trials=n_trials, callbacks=[callback])

        # 結果構築
        best_trial = study.best_trial
        best_params: dict[str, float] = {}
        for pd in param_defs:
            best_params[pd.name] = best_trial.params[pd.name]
        # Reconvert 固定値も結果に含める（UIに反映するため）
        best_params["blur_radius"] = float(_RECONVERT_BLUR_RADIUS)
        best_params["brightness"] = _RECONVERT_BRIGHTNESS

        # best_trial のパラメータで再評価して正確なメトリクスを取得
        _apply_converter_params(converter, best_params, color_mode)
        final_dithered = converter.convert_pre_resized(pre_resized)
        final_reconverted = reconvert_service.reconvert_array(
            final_dithered,
            blur_radius=_RECONVERT_BLUR_RADIUS,
            color_mode=color_mode,
            gamut_strength=best_params.get("gamut_strength", 0.7),
            illuminant_red=best_params.get("illuminant_red", 1.0),
            illuminant_yellow=best_params.get("illuminant_yellow", 1.0),
            illuminant_white=best_params.get("illuminant_white", 1.0),
            palette=palette,
            brightness=_RECONVERT_BRIGHTNESS,
        )
        best_metrics_final = compute_composite_score(reference, final_reconverted)

        # ログ
        log: list[str] = []
        completed = len(study.trials)
        log.append(f"=== Optuna TPE ({completed} trials, {eval_count} evaluations) ===")
        log.append(
            f"Best trial: #{best_trial.number}, "
            f"composite={best_trial.value:.4f}"
        )
        log.append(
            f"  PSNR={best_metrics_final['psnr']:.2f} "
            f"SSIM={best_metrics_final['ssim']:.4f} "
            f"LabDE={best_metrics_final['lab_de']:.2f} "
            f"S-CIELAB={best_metrics_final['scielab_de']:.2f} "
            f"Hist={best_metrics_final['hist_corr']:.4f}"
        )
        for pd in param_defs:
            log.append(f"  {pd.name} = {best_params[pd.name]:.2f}")
        log.append(f"  blur_radius = {_RECONVERT_BLUR_RADIUS} (fixed)")
        log.append(f"  brightness = {_RECONVERT_BRIGHTNESS:.2f} (fixed)")

        # Top 5 trials
        log.append("")
        sorted_trials = sorted(
            study.trials,
            key=lambda t: t.value if t.value is not None else float("-inf"),
            reverse=True,
        )
        top = sorted_trials[:5]
        top_strs = [f"#{t.number}: {t.value:.4f}" for t in top if t.value is not None]
        log.append(f"Top 5: {', '.join(top_strs)}")

        if progress:
            progress("Complete", 1.0)

        return OptimizeResult(
            best_params=best_params,
            best_score=best_trial.value,
            metrics=best_metrics_final,
            log=log,
        )
