#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
004_01_calculate_response_spectrum.py
加速度波形から速度応答スペクトルを計算

入力: 01_data/02_seismic_formatted/{station}/waveform.csv
出力: 01_data/02_seismic_formatted/{station}/response_spectrum.csv
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "01_data" / "02_seismic_formatted"

# 応答スペクトル計算設定（ハードコード）
DAMPING_RATIO = 0.05  # 減衰定数 h
PERIOD_MIN = 0.02     # 最小周期 [s]
PERIOD_MAX = 10.0     # 最大周期 [s]
PERIOD_NUM = 100      # 周期の分割数（対数スケール）

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Response Spectrum Calculation (FFT Method)
# =============================================================================

def sdof_transfer_function(freq: np.ndarray, omega_n: float, h: float) -> np.ndarray:
    """
    1自由度系の伝達関数（変位/加速度）

    H(ω) = -1 / (ω_n² - ω² + 2ihω_nω)

    Parameters
    ----------
    freq : np.ndarray
        周波数配列 [Hz]
    omega_n : float
        固有角振動数 [rad/s]
    h : float
        減衰定数

    Returns
    -------
    np.ndarray
        伝達関数（複素数）
    """
    omega = 2 * np.pi * freq
    H = -1.0 / (omega_n**2 - omega**2 + 2j * h * omega_n * omega)
    return H


def calculate_response_fft(acc: np.ndarray, dt: float, period: float, h: float) -> tuple:
    """
    FFT法による1自由度系の応答計算

    Parameters
    ----------
    acc : np.ndarray
        加速度時刻歴 [gal]
    dt : float
        時間刻み [s]
    period : float
        固有周期 [s]
    h : float
        減衰定数

    Returns
    -------
    sd : float
        最大変位応答 [cm]
    sv : float
        最大速度応答 [cm/s]
    sa : float
        最大加速度応答 [gal]
    """
    if period == 0:
        sa = np.max(np.abs(acc))
        return 0.0, 0.0, sa

    n = len(acc)
    omega_n = 2 * np.pi / period

    # FFT（ゼロパディングで精度向上）
    n_fft = 2 ** int(np.ceil(np.log2(n)) + 1)  # 2倍パディング
    acc_fft = np.fft.rfft(acc, n=n_fft)
    freq = np.fft.rfftfreq(n_fft, d=dt)

    # 伝達関数
    H_disp = sdof_transfer_function(freq, omega_n, h)

    # 変位応答（周波数領域）
    disp_fft = acc_fft * H_disp

    # 速度応答 = iω * 変位
    omega = 2 * np.pi * freq
    vel_fft = 1j * omega * disp_fft

    # 絶対加速度応答 = 入力加速度 + 相対加速度
    # 相対加速度 = -ω² * 変位 - 2hωω_n * 速度（周波数領域では直接計算）
    abs_acc_fft = acc_fft + (-omega**2 * disp_fft - 2 * h * omega_n * vel_fft / (1j))
    # より簡潔に: 絶対加速度 = (1 + H * ω_n²) * 入力加速度 相当
    # ただし上記は近似になるので、変位と速度から計算
    # 相対加速度 = (iω)² * 変位 = -ω² * 変位
    rel_acc_fft = -omega**2 * disp_fft
    abs_acc_fft = acc_fft + rel_acc_fft

    # 逆FFT
    disp = np.fft.irfft(disp_fft, n=n_fft)[:n]
    vel = np.fft.irfft(vel_fft, n=n_fft)[:n]
    abs_acc_resp = np.fft.irfft(abs_acc_fft, n=n_fft)[:n]

    # 最大応答値
    sd = np.max(np.abs(disp))
    sv = np.max(np.abs(vel))
    sa = np.max(np.abs(abs_acc_resp))

    return sd, sv, sa


def calculate_response_spectrum(acc: np.ndarray, dt: float, periods: np.ndarray,
                                h: float = DAMPING_RATIO) -> dict:
    """
    応答スペクトルを計算（FFT法）

    Parameters
    ----------
    acc : np.ndarray
        加速度時刻歴 [gal]
    dt : float
        時間刻み [s]
    periods : np.ndarray
        周期配列 [s]
    h : float
        減衰定数

    Returns
    -------
    dict
        SD, SV, SA, pSV（擬似速度応答）の配列
    """
    sd_arr = np.zeros(len(periods))
    sv_arr = np.zeros(len(periods))
    sa_arr = np.zeros(len(periods))

    for i, T in enumerate(periods):
        sd, sv, sa = calculate_response_fft(acc, dt, T, h)
        sd_arr[i] = sd
        sv_arr[i] = sv
        sa_arr[i] = sa

    # 擬似速度応答 pSV = omega * SD = (2π/T) * SD
    psv_arr = np.zeros(len(periods))
    nonzero_idx = periods > 0
    psv_arr[nonzero_idx] = (2 * np.pi / periods[nonzero_idx]) * sd_arr[nonzero_idx]

    return {
        'SD': sd_arr,
        'SV': sv_arr,
        'SA': sa_arr,
        'pSV': psv_arr
    }


# =============================================================================
# Station Processing
# =============================================================================

def process_station(station_dir: Path) -> bool:
    """
    1観測点の応答スペクトルを計算

    Parameters
    ----------
    station_dir : Path
        観測点ディレクトリ

    Returns
    -------
    bool
        処理成功/失敗
    """
    waveform_path = station_dir / "waveform.csv"
    metadata_path = station_dir / "metadata.yml"
    output_path = station_dir / "response_spectrum.csv"

    if not waveform_path.exists():
        logger.warning(f"waveform.csv not found: {station_dir.name}")
        return False

    try:
        # メタデータ読み込み
        sampling_rate = 100  # デフォルト値
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)
                sampling_rate = metadata.get('record', {}).get('sampling_rate_hz', 100)

        dt = 1.0 / sampling_rate

        # 波形データ読み込み
        df = pd.read_csv(waveform_path)

        # 周期配列（対数スケール）
        periods = np.logspace(np.log10(PERIOD_MIN), np.log10(PERIOD_MAX), PERIOD_NUM)

        # 各成分の応答スペクトル計算
        results = {}
        for comp in ['NS', 'EW', 'UD']:
            acc = df[comp].values
            resp = calculate_response_spectrum(acc, dt, periods, DAMPING_RATIO)
            results[comp] = resp

        # 水平合成（SRSS: Square Root of Sum of Squares）
        results['H'] = {
            'SD': np.sqrt(results['NS']['SD']**2 + results['EW']['SD']**2),
            'SV': np.sqrt(results['NS']['SV']**2 + results['EW']['SV']**2),
            'SA': np.sqrt(results['NS']['SA']**2 + results['EW']['SA']**2),
            'pSV': np.sqrt(results['NS']['pSV']**2 + results['EW']['pSV']**2)
        }

        # 出力データフレーム作成（速度応答スペクトルSV）
        out_df = pd.DataFrame({
            'period': periods,
            'NS': results['NS']['SV'],
            'EW': results['EW']['SV'],
            'UD': results['UD']['SV'],
            'H': results['H']['SV']
        })

        # CSV出力
        out_df.to_csv(output_path, index=False, float_format='%.6e')

        return True

    except Exception as e:
        logger.error(f"処理エラー ({station_dir.name}): {e}")
        import traceback
        traceback.print_exc()
        return False


# =============================================================================
# Main
# =============================================================================

def main():
    """メインエントリポイント"""
    logger.info("速度応答スペクトル計算開始")
    logger.info(f"入力ディレクトリ: {INPUT_DIR}")
    logger.info(f"減衰定数: {DAMPING_RATIO}")
    logger.info(f"周期範囲: {PERIOD_MIN} - {PERIOD_MAX} s ({PERIOD_NUM}点)")

    if not INPUT_DIR.exists():
        logger.error(f"入力ディレクトリが存在しません: {INPUT_DIR}")
        return

    # 全観測点ディレクトリを処理
    success_count = 0
    fail_count = 0

    for station_dir in sorted(INPUT_DIR.iterdir()):
        if not station_dir.is_dir():
            continue
        if station_dir.name.startswith('.'):
            continue

        if process_station(station_dir):
            success_count += 1
            logger.info(f"完了: {station_dir.name}")
        else:
            fail_count += 1

    logger.info(f"処理完了: 成功 {success_count}, 失敗 {fail_count}")


if __name__ == "__main__":
    main()
