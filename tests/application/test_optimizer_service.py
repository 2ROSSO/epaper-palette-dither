"""optimizer_service モジュールのテスト。"""

from __future__ import annotations

import numpy as np
import pytest

from epaper_palette_dither.application.optimizer_service import (
    OptimizerService,
    OptimizeResult,
    ParamDef,
)
from epaper_palette_dither.domain.image_model import ColorMode, ImageSpec


def _make_white_image(h: int = 32, w: int = 32) -> np.ndarray:
    """白画像を生成（変化しない画像）。"""
    return np.full((h, w, 3), 255, dtype=np.uint8)


class TestGetParamDefs:
    """ColorMode別のパラメータ定義を検証。"""

    def test_illuminant_has_6_params(self) -> None:
        service = OptimizerService()
        defs = service.get_param_defs(ColorMode.ILLUMINANT)
        assert len(defs) == 6
        names = [d.name for d in defs]
        assert "illuminant_red" in names
        assert "illuminant_yellow" in names
        assert "illuminant_white" in names
        # Reconvert パラメータは探索対象外
        assert "blur_radius" not in names
        assert "brightness" not in names

    def test_grayout_has_4_params(self) -> None:
        service = OptimizerService()
        defs = service.get_param_defs(ColorMode.GRAYOUT)
        assert len(defs) == 4
        names = [d.name for d in defs]
        assert "gamut_strength" in names
        assert "illuminant_red" not in names

    def test_anti_saturation_has_3_params(self) -> None:
        service = OptimizerService()
        defs = service.get_param_defs(ColorMode.ANTI_SATURATION)
        assert len(defs) == 3

    def test_centroid_clip_has_3_params(self) -> None:
        service = OptimizerService()
        defs = service.get_param_defs(ColorMode.CENTROID_CLIP)
        assert len(defs) == 3

    def test_param_ranges_valid(self) -> None:
        """全 ParamDef の min < max かつ step > 0 を検証。"""
        service = OptimizerService()
        for mode in ColorMode:
            for pd in service.get_param_defs(mode):
                assert pd.min_val < pd.max_val, f"{pd.name}: min >= max"
                assert pd.coarse_step > 0, f"{pd.name}: coarse_step <= 0"
                assert pd.fine_step > 0, f"{pd.name}: fine_step <= 0"
                assert pd.coarse_step >= pd.fine_step, \
                    f"{pd.name}: coarse_step < fine_step"

    def test_no_reconvert_params_in_defs(self) -> None:
        """探索パラメータに blur_radius / brightness が含まれないこと。"""
        service = OptimizerService()
        reconvert_names = {"blur_radius", "brightness"}
        for mode in ColorMode:
            names = {pd.name for pd in service.get_param_defs(mode)}
            assert names.isdisjoint(reconvert_names), (
                f"{mode}: {names & reconvert_names} が探索対象に含まれている"
            )


class TestOptimize:
    """最適化の実行テスト。"""

    def test_white_image_returns_result(self) -> None:
        """白画像（変化しない）でも正常に結果が返ること。"""
        service = OptimizerService()
        img = _make_white_image(32, 32)
        spec = ImageSpec(target_width=32, target_height=32)
        initial = {
            "illuminant_red": 1.0,
            "illuminant_yellow": 1.0,
            "illuminant_white": 1.0,
            "error_clamp": 85,
            "red_penalty": 0.0,
            "yellow_penalty": 0.0,
        }

        result = service.optimize(
            img, spec, ColorMode.ILLUMINANT, initial, n_trials=5,
        )

        assert isinstance(result, OptimizeResult)
        assert result.best_score >= 0.0
        assert result.best_score <= 1.0
        assert len(result.log) > 0
        assert "composite" in result.metrics

    def test_result_includes_fixed_reconvert_params(self) -> None:
        """結果に固定 Reconvert パラメータが含まれること。"""
        service = OptimizerService()
        img = _make_white_image(16, 16)
        spec = ImageSpec(target_width=16, target_height=16)
        initial = {
            "error_clamp": 85,
            "red_penalty": 0.0,
            "yellow_penalty": 0.0,
        }

        result = service.optimize(
            img, spec, ColorMode.ANTI_SATURATION, initial, n_trials=5,
        )

        assert result.best_params["blur_radius"] == 1.0
        assert result.best_params["brightness"] == 1.0

    def test_cancelled_early_exit(self) -> None:
        """cancelled コールバックで早期中断できること。"""
        service = OptimizerService()
        img = _make_white_image(32, 32)
        spec = ImageSpec(target_width=32, target_height=32)
        initial = {
            "error_clamp": 85,
            "red_penalty": 0.0,
            "yellow_penalty": 0.0,
        }

        call_count = 0

        def cancel_after_2() -> bool:
            nonlocal call_count
            call_count += 1
            return call_count > 2

        result = service.optimize(
            img, spec, ColorMode.ANTI_SATURATION, initial,
            n_trials=100,
            cancelled=cancel_after_2,
        )

        assert isinstance(result, OptimizeResult)
        assert "Optuna TPE" in result.log[0]

    def test_progress_callback_called(self) -> None:
        """progress コールバックが呼ばれること。"""
        service = OptimizerService()
        img = _make_white_image(32, 32)
        spec = ImageSpec(target_width=32, target_height=32)
        initial = {
            "error_clamp": 85,
            "red_penalty": 0.0,
            "yellow_penalty": 0.0,
        }

        progress_calls: list[tuple[str, float]] = []

        result = service.optimize(
            img, spec, ColorMode.ANTI_SATURATION, initial,
            n_trials=5,
            progress=lambda msg, p: progress_calls.append((msg, p)),
        )

        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == "Complete"
        assert progress_calls[-1][1] == pytest.approx(1.0)

    def test_optuna_integration(self) -> None:
        """小画像で optimize() が Optuna で正常完了する。"""
        service = OptimizerService()
        rng = np.random.default_rng(42)
        img = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
        spec = ImageSpec(target_width=16, target_height=16)
        initial = {
            "error_clamp": 85,
            "red_penalty": 10.0,
            "yellow_penalty": 15.0,
        }

        result = service.optimize(
            img, spec, ColorMode.ANTI_SATURATION, initial,
            n_trials=10,
        )

        assert isinstance(result, OptimizeResult)
        assert result.best_score > 0.0
        assert any("Optuna TPE" in line for line in result.log)
        assert any("Top 5" in line for line in result.log)
        assert "error_clamp" in result.best_params

    def test_log_contains_fixed_params(self) -> None:
        """ログに固定パラメータ情報が含まれる。"""
        service = OptimizerService()
        img = _make_white_image(16, 16)
        spec = ImageSpec(target_width=16, target_height=16)
        initial = {
            "error_clamp": 85,
            "red_penalty": 0.0,
            "yellow_penalty": 0.0,
        }

        result = service.optimize(
            img, spec, ColorMode.ANTI_SATURATION, initial,
            n_trials=5,
        )

        log_text = "\n".join(result.log)
        assert "blur_radius = 1 (fixed)" in log_text
        assert "brightness = 1.00 (fixed)" in log_text
