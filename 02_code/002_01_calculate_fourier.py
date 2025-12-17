#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
002_01_calculate_fourier.py
加速度波形データからフーリエ振幅スペクトルを計算

入力: 01_data/02_seismic_formatted/{station}/waveform.csv
出力: 01_data/02_seismic_formatted/{station}/fourier_spectrum.csv
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Fourier Transform
# =============================================================================

def calculate_fourier_spectrum(data: np.ndarray, sampling_rate: float) -> tuple:
    """
    フーリエ振幅スペクトルを計算（地震工学標準の正規化）

    Parameters
    ----------
    data : np.ndarray
        時刻歴データ [gal]
    sampling_rate : float
        サンプリング周波数 [Hz]

    Returns
    -------
    freq : np.ndarray
        周波数 [Hz]
    amplitude : np.ndarray
        フーリエ振幅スペクトル [gal·s]
    """
    n = len(data)
    dt = 1.0 / sampling_rate

    # FFT計算（実数入力用）
    fft_result = np.fft.rfft(data)

    # 周波数軸
    freq = np.fft.rfftfreq(n, d=dt)

    # 振幅スペクトル（地震工学標準の正規化）
    # |F(f)| = |FFT| * dt * 2（片側スペクトル）
    amplitude = np.abs(fft_result) * dt * 2

    # DC成分とナイキスト周波数は2倍しない
    amplitude[0] /= 2
    if n % 2 == 0:
        amplitude[-1] /= 2

    return freq, amplitude


def process_station(station_dir: Path) -> bool:
    """
    1観測点のフーリエスペクトルを計算

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
    output_path = station_dir / "fourier_spectrum.csv"

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

        # 波形データ読み込み
        df = pd.read_csv(waveform_path)

        # 各成分のフーリエスペクトル計算
        freq, ns_amp = calculate_fourier_spectrum(df['NS'].values, sampling_rate)
        _, ew_amp = calculate_fourier_spectrum(df['EW'].values, sampling_rate)
        _, ud_amp = calculate_fourier_spectrum(df['UD'].values, sampling_rate)

        # 出力データフレーム作成
        out_df = pd.DataFrame({
            'frequency': freq,
            'NS': ns_amp,
            'EW': ew_amp,
            'UD': ud_amp
        })

        # CSV出力
        out_df.to_csv(output_path, index=False, float_format='%.6e')

        return True

    except Exception as e:
        logger.error(f"処理エラー ({station_dir.name}): {e}")
        return False


# =============================================================================
# Main
# =============================================================================

def main():
    """メインエントリポイント"""
    logger.info("フーリエスペクトル計算開始")
    logger.info(f"入力ディレクトリ: {INPUT_DIR}")

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
