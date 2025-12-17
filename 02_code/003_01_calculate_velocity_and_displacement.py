#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
003_01_calculate_velocity_and_displacement.py
加速度波形を4倍パディングFFT積分により速度・変位に変換

入力: 01_data/02_seismic_formatted/{station}/waveform.csv
出力:
  - velocity.csv: datetime, NS, EW, UD [cm/s]
  - displacement.csv: datetime, NS, EW, UD [cm]
  - metadata.yml: 最大速度・最大変位を追加
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import signal

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "01_data" / "02_seismic_formatted"

# 前処理設定（ハードコード）
BASELINE_WINDOW_SEC = 1.0  # 基線補正に使用する最初のデータ長 [秒]
HIGHPASS_FREQ = 0.1  # ハイパスフィルタカットオフ周波数 [Hz]
HIGHPASS_ORDER = 4   # バターワースフィルタ次数

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Signal Processing Functions
# =============================================================================

def apply_baseline_correction(data: np.ndarray, sampling_rate: float,
                              window_sec: float = BASELINE_WINDOW_SEC) -> np.ndarray:
    """
    基線補正（最初のwindow_sec秒間の平均値を除去）

    Parameters
    ----------
    data : np.ndarray
        入力データ
    sampling_rate : float
        サンプリング周波数 [Hz]
    window_sec : float
        基線決定に使用する最初のデータ長 [秒]

    Returns
    -------
    np.ndarray
        基線補正後のデータ
    """
    n_samples = int(window_sec * sampling_rate)
    n_samples = min(n_samples, len(data))  # データ長を超えないように
    baseline = np.mean(data[:n_samples])
    return data - baseline


def apply_highpass_filter(data: np.ndarray, sampling_rate: float,
                          cutoff: float = HIGHPASS_FREQ,
                          order: int = HIGHPASS_ORDER) -> np.ndarray:
    """
    バターワースハイパスフィルタ（ゼロ位相）

    Parameters
    ----------
    data : np.ndarray
        入力データ
    sampling_rate : float
        サンプリング周波数 [Hz]
    cutoff : float
        カットオフ周波数 [Hz]
    order : int
        フィルタ次数

    Returns
    -------
    np.ndarray
        フィルタ後のデータ
    """
    nyquist = sampling_rate / 2
    normalized_cutoff = cutoff / nyquist
    b, a = signal.butter(order, normalized_cutoff, btype='high')
    return signal.filtfilt(b, a, data)


def integrate_fft_padded(data: np.ndarray, sampling_rate: float,
                         pad_factor: int = 4) -> tuple:
    """
    4倍パディングFFT積分

    Parameters
    ----------
    data : np.ndarray
        加速度データ [gal]
    sampling_rate : float
        サンプリング周波数 [Hz]
    pad_factor : int
        パディング倍率

    Returns
    -------
    velocity : np.ndarray
        速度 [cm/s]
    displacement : np.ndarray
        変位 [cm]
    """
    n_original = len(data)
    n_padded = pad_factor * n_original
    dt = 1.0 / sampling_rate

    # ゼロパディング
    data_padded = np.zeros(n_padded)
    data_padded[:n_original] = data

    # FFT
    fft_acc = np.fft.rfft(data_padded)
    freq = np.fft.rfftfreq(n_padded, d=dt)

    # 角周波数
    omega = 2 * np.pi * freq
    omega[0] = 1.0  # DC成分のゼロ除算回避

    # 周波数領域での積分
    # 速度: V(f) = A(f) / (i * omega)
    # 変位: D(f) = V(f) / (i * omega)
    fft_vel = fft_acc / (1j * omega)
    fft_disp = fft_vel / (1j * omega)

    # DC成分をゼロに
    fft_vel[0] = 0
    fft_disp[0] = 0

    # 逆FFT
    velocity_padded = np.fft.irfft(fft_vel, n=n_padded)
    displacement_padded = np.fft.irfft(fft_disp, n=n_padded)

    # 元の長さにトリミング
    velocity = velocity_padded[:n_original]
    displacement = displacement_padded[:n_original]

    # 残留ドリフト補正（平均値除去）
    velocity = velocity - np.mean(velocity)
    displacement = displacement - np.mean(displacement)

    return velocity, displacement


def calc_signed_peak(data: np.ndarray) -> float:
    """絶対値最大時の符号付き値を返す"""
    abs_max_idx = np.argmax(np.abs(data))
    return float(data[abs_max_idx])


def calc_peak_horizontal(ns: np.ndarray, ew: np.ndarray) -> float:
    """水平合成の最大値"""
    combined = np.sqrt(ns**2 + ew**2)
    return float(np.max(combined))


def calc_peak_total(ns: np.ndarray, ew: np.ndarray, ud: np.ndarray) -> float:
    """3成分合成の最大値"""
    combined = np.sqrt(ns**2 + ew**2 + ud**2)
    return float(np.max(combined))


# =============================================================================
# Station Processing
# =============================================================================

def process_station(station_dir: Path) -> bool:
    """
    1観測点の速度・変位を計算

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
    velocity_path = station_dir / "velocity.csv"
    displacement_path = station_dir / "displacement.csv"

    if not waveform_path.exists():
        logger.warning(f"waveform.csv not found: {station_dir.name}")
        return False

    try:
        # メタデータ読み込み
        sampling_rate = 100  # デフォルト値
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)
                sampling_rate = metadata.get('record', {}).get('sampling_rate_hz', 100)

        # 波形データ読み込み
        df = pd.read_csv(waveform_path)
        datetimes = df['datetime'].values

        # 各成分の処理
        results = {}
        for comp in ['NS', 'EW', 'UD']:
            acc = df[comp].values

            # 前処理
            acc = apply_baseline_correction(acc, sampling_rate)
            acc = apply_highpass_filter(acc, sampling_rate)

            # FFT積分
            vel, disp = integrate_fft_padded(acc, sampling_rate)

            results[comp] = {'velocity': vel, 'displacement': disp}

        # velocity.csv出力
        vel_df = pd.DataFrame({
            'datetime': datetimes,
            'NS': results['NS']['velocity'],
            'EW': results['EW']['velocity'],
            'UD': results['UD']['velocity']
        })
        vel_df.to_csv(velocity_path, index=False)

        # displacement.csv出力
        disp_df = pd.DataFrame({
            'datetime': datetimes,
            'NS': results['NS']['displacement'],
            'EW': results['EW']['displacement'],
            'UD': results['UD']['displacement']
        })
        disp_df.to_csv(displacement_path, index=False)

        # 最大値計算
        vel_ns = results['NS']['velocity']
        vel_ew = results['EW']['velocity']
        vel_ud = results['UD']['velocity']
        disp_ns = results['NS']['displacement']
        disp_ew = results['EW']['displacement']
        disp_ud = results['UD']['displacement']

        # metadata.yml更新
        metadata['max_velocity_calculated'] = {
            'NS': round(calc_signed_peak(vel_ns), 3),
            'EW': round(calc_signed_peak(vel_ew), 3),
            'UD': round(calc_signed_peak(vel_ud), 3),
            'H': round(calc_peak_horizontal(vel_ns, vel_ew), 3),
            'total': round(calc_peak_total(vel_ns, vel_ew, vel_ud), 3)
        }

        metadata['max_displacement_calculated'] = {
            'NS': round(calc_signed_peak(disp_ns), 3),
            'EW': round(calc_signed_peak(disp_ew), 3),
            'UD': round(calc_signed_peak(disp_ud), 3),
            'H': round(calc_peak_horizontal(disp_ns, disp_ew), 3),
            'total': round(calc_peak_total(disp_ns, disp_ew, disp_ud), 3)
        }

        metadata['integration_params'] = {
            'method': 'FFT with 4x padding',
            'baseline_window_sec': BASELINE_WINDOW_SEC,
            'highpass_cutoff_hz': HIGHPASS_FREQ,
            'highpass_order': HIGHPASS_ORDER
        }

        with open(metadata_path, 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return True

    except Exception as e:
        logger.error(f"処理エラー ({station_dir.name}): {e}")
        return False


# =============================================================================
# Summary CSV Generation
# =============================================================================

def flatten_metadata(meta: dict) -> dict:
    """metadata.ymlの内容をフラット化してCSV用の辞書に変換"""
    record = {
        'source': meta.get('source'),
        'station_code': meta.get('station', {}).get('code'),
        'station_name': meta.get('station', {}).get('name', ''),
        'lat': meta.get('station', {}).get('lat'),
        'lon': meta.get('station', {}).get('lon'),
        'height_m': meta.get('station', {}).get('height_m'),
        'start_time': meta.get('record', {}).get('start_time'),
        'duration_s': meta.get('record', {}).get('duration_s'),
        'sampling_rate_hz': meta.get('record', {}).get('sampling_rate_hz'),
        'intensity': meta.get('intensity', ''),
        # 加速度
        'acc_NS': meta.get('max_acceleration', {}).get('NS'),
        'acc_EW': meta.get('max_acceleration', {}).get('EW'),
        'acc_UD': meta.get('max_acceleration', {}).get('UD'),
        'acc_H': meta.get('max_acceleration', {}).get('H'),
        'acc_total': meta.get('max_acceleration', {}).get('total'),
        # 速度（計算値）
        'vel_NS': meta.get('max_velocity_calculated', {}).get('NS'),
        'vel_EW': meta.get('max_velocity_calculated', {}).get('EW'),
        'vel_UD': meta.get('max_velocity_calculated', {}).get('UD'),
        'vel_H': meta.get('max_velocity_calculated', {}).get('H'),
        'vel_total': meta.get('max_velocity_calculated', {}).get('total'),
        # 変位（計算値）
        'disp_NS': meta.get('max_displacement_calculated', {}).get('NS'),
        'disp_EW': meta.get('max_displacement_calculated', {}).get('EW'),
        'disp_UD': meta.get('max_displacement_calculated', {}).get('UD'),
        'disp_H': meta.get('max_displacement_calculated', {}).get('H'),
        'disp_total': meta.get('max_displacement_calculated', {}).get('total'),
    }
    return record


def generate_summary_csv(output_dir: Path) -> int:
    """全metadata.ymlを読み込んでsummary CSVを生成"""
    records = []

    for station_dir in sorted(output_dir.iterdir()):
        if not station_dir.is_dir():
            continue
        if station_dir.name.startswith('.'):
            continue
        meta_path = station_dir / 'metadata.yml'
        if meta_path.exists():
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = yaml.safe_load(f)
            records.append(flatten_metadata(meta))

    if records:
        df = pd.DataFrame(records)
        df.to_csv(output_dir / 'summary_metadata.csv', index=False, encoding='utf-8')

    return len(records)


# =============================================================================
# Main
# =============================================================================

def main():
    """メインエントリポイント"""
    logger.info("速度・変位計算開始")
    logger.info(f"入力ディレクトリ: {INPUT_DIR}")
    logger.info(f"基線補正ウィンドウ: {BASELINE_WINDOW_SEC} 秒")
    logger.info(f"ハイパスフィルタ: {HIGHPASS_FREQ} Hz, {HIGHPASS_ORDER}次")

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

    # サマリCSV更新
    logger.info("summary_metadata.csv 更新中...")
    summary_count = generate_summary_csv(INPUT_DIR)
    logger.info(f"summary_metadata.csv: {summary_count} 観測点")


if __name__ == "__main__":
    main()
