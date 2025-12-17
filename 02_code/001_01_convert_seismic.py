#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert_seismic.py
NIED/JMA地震波形データを統一フォーマットに変換

出力:
  - waveform.csv: datetime(ISO8601), NS, EW, UD (gal)
  - metadata.yml: 全メタデータ
"""

import re
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent
INPUT_DIR = BASE_DIR / "01_data" / "01_seismic"
OUTPUT_DIR = BASE_DIR / "01_data" / "02_seismic_formatted"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Peak Value Calculation
# =============================================================================

def calc_signed_peak(data: List[float]) -> float:
    """絶対値最大時の符号付き値を返す"""
    arr = np.array(data)
    abs_max_idx = np.argmax(np.abs(arr))
    return float(arr[abs_max_idx])


def calc_peak_horizontal(ns: List[float], ew: List[float]) -> float:
    """水平合成の最大値（常に正）"""
    ns_arr = np.array(ns)
    ew_arr = np.array(ew)
    combined = np.sqrt(ns_arr**2 + ew_arr**2)
    return float(np.max(combined))


def calc_peak_total(ns: List[float], ew: List[float], ud: List[float]) -> float:
    """3成分合成の最大値（常に正）"""
    ns_arr = np.array(ns)
    ew_arr = np.array(ew)
    ud_arr = np.array(ud)
    combined = np.sqrt(ns_arr**2 + ew_arr**2 + ud_arr**2)
    return float(np.max(combined))


# =============================================================================
# NIED Parser
# =============================================================================

def parse_nied_header(filepath: Path) -> Dict:
    """NIEDファイルヘッダーを解析"""
    metadata = {}
    with open(filepath, 'r', encoding='ascii') as f:
        lines = [f.readline() for _ in range(17)]

    # 18文字目以降が値
    metadata['origin_time'] = lines[0][18:].strip() or None
    metadata['eq_lat'] = lines[1][18:].strip() or None
    metadata['eq_lon'] = lines[2][18:].strip() or None
    metadata['eq_depth'] = lines[3][18:].strip() or None
    metadata['eq_mag'] = lines[4][18:].strip() or None
    metadata['station_code'] = lines[5][18:].strip()
    metadata['station_lat'] = float(lines[6][18:].strip())
    metadata['station_lon'] = float(lines[7][18:].strip())
    metadata['station_height'] = float(lines[8][18:].strip())
    metadata['record_time'] = lines[9][18:].strip()
    metadata['sampling_freq'] = int(lines[10][18:].replace('Hz', '').strip())
    metadata['duration'] = int(lines[11][18:].strip())
    metadata['direction'] = lines[12][18:].strip()

    # Scale Factor: "7845(gal)/8223790"
    scale_str = lines[13][18:].strip()
    match = re.match(r'(\d+)\(gal\)/(\d+)', scale_str)
    if match:
        metadata['scale_numerator'] = int(match.group(1))
        metadata['scale_denominator'] = int(match.group(2))
    else:
        raise ValueError(f"Invalid scale factor format: {scale_str}")

    metadata['max_acc'] = float(lines[14][18:].strip())
    metadata['last_correction'] = lines[15][18:].strip()

    return metadata


def parse_nied_data(filepath: Path, scale_num: int, scale_den: int) -> List[float]:
    """NIEDデータ部を読み込みgalに変換"""
    data = []
    scale = scale_num / scale_den

    with open(filepath, 'r', encoding='ascii') as f:
        # ヘッダー17行スキップ
        for _ in range(17):
            f.readline()

        for line in f:
            values = line.strip().split()
            for val in values:
                if val:
                    data.append(int(val) * scale)

    return data


def process_nied_station(base_name: str, components: Dict[str, Path], output_dir: Path) -> bool:
    """NIED観測点1つを処理"""
    try:
        # EWファイルからメタデータ取得
        ew_meta = parse_nied_header(components['.EW'])
        ns_meta = parse_nied_header(components['.NS'])
        ud_meta = parse_nied_header(components['.UD'])

        station_code = ew_meta['station_code']

        # データ読み込み
        ew_data = parse_nied_data(
            components['.EW'],
            ew_meta['scale_numerator'],
            ew_meta['scale_denominator']
        )
        ns_data = parse_nied_data(
            components['.NS'],
            ns_meta['scale_numerator'],
            ns_meta['scale_denominator']
        )
        ud_data = parse_nied_data(
            components['.UD'],
            ud_meta['scale_numerator'],
            ud_meta['scale_denominator']
        )

        # サンプル数確認
        num_samples = min(len(ew_data), len(ns_data), len(ud_data))
        ew_data = ew_data[:num_samples]
        ns_data = ns_data[:num_samples]
        ud_data = ud_data[:num_samples]

        # 時刻列生成
        datetimes = generate_datetime_series(
            ew_meta['record_time'],
            num_samples,
            ew_meta['sampling_freq']
        )

        # 出力ディレクトリ作成
        out_dir = output_dir / f"NIED_{station_code}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # waveform.csv出力
        df = pd.DataFrame({
            'datetime': datetimes,
            'NS': ns_data,
            'EW': ew_data,
            'UD': ud_data
        })
        df.to_csv(out_dir / 'waveform.csv', index=False)

        # 符号付き最大加速度を計算
        peak_ns = calc_signed_peak(ns_data)
        peak_ew = calc_signed_peak(ew_data)
        peak_ud = calc_signed_peak(ud_data)
        peak_h = calc_peak_horizontal(ns_data, ew_data)
        peak_total = calc_peak_total(ns_data, ew_data, ud_data)

        # metadata.yml作成
        metadata = {
            'source': 'NIED',
            'station': {
                'code': station_code,
                'lat': ew_meta['station_lat'],
                'lon': ew_meta['station_lon'],
                'height_m': ew_meta['station_height']
            },
            'record': {
                'start_time': datetimes[0],
                'end_time': datetimes[-1],
                'sampling_rate_hz': ew_meta['sampling_freq'],
                'duration_s': ew_meta['duration'],
                'num_samples': num_samples,
                'unit': 'gal (cm/s²)'
            },
            'max_acceleration': {
                'NS': round(peak_ns, 3),
                'EW': round(peak_ew, 3),
                'UD': round(peak_ud, 3),
                'H': round(peak_h, 3),
                'total': round(peak_total, 3)
            }
        }

        # 震源情報があれば追加
        if ew_meta['origin_time']:
            metadata['earthquake'] = {
                'origin_time': ew_meta['origin_time'],
                'lat': float(ew_meta['eq_lat']) if ew_meta['eq_lat'] else None,
                'lon': float(ew_meta['eq_lon']) if ew_meta['eq_lon'] else None,
                'depth_km': float(ew_meta['eq_depth']) if ew_meta['eq_depth'] else None,
                'magnitude': float(ew_meta['eq_mag']) if ew_meta['eq_mag'] else None
            }

        with open(out_dir / 'metadata.yml', 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return True

    except Exception as e:
        logger.error(f"NIED処理エラー ({base_name}): {e}")
        return False


# =============================================================================
# JMA Parser
# =============================================================================

def parse_jma_header(filepath: Path) -> Dict:
    """JMAファイルヘッダーを解析"""
    metadata = {}
    with open(filepath, 'r', encoding='cp932') as f:
        lines = [f.readline().strip() for _ in range(7)]

    # SITE CODE= 観測点名
    metadata['station_name'] = lines[0].split('=', 1)[1].strip()
    metadata['station_lat'] = float(lines[1].split('=')[1].strip())
    metadata['station_lon'] = float(lines[2].split('=')[1].strip())
    metadata['sampling_freq'] = int(lines[3].split('=')[1].replace('Hz', '').strip())
    metadata['unit'] = lines[4].split('=')[1].strip()

    # INITIAL TIME= 2025 12 08 23 15 30
    time_str = lines[5].split('=')[1].strip()
    parts = time_str.split()
    metadata['record_time'] = f"{parts[0]}/{parts[1]}/{parts[2]} {parts[3]}:{parts[4]}:{parts[5]}"

    return metadata


def parse_jma_data(filepath: Path) -> pd.DataFrame:
    """JMAデータ部を読み込み"""
    df = pd.read_csv(
        filepath,
        encoding='cp932',
        skiprows=7,
        header=None,
        names=['NS', 'EW', 'UD']
    )
    return df


def load_jma_max_csv(filepath: Path) -> Dict:
    """JMA max.csvを読み込み"""
    df = pd.read_csv(filepath, encoding='cp932', comment='#', header=None)

    # カラム名設定
    df.columns = [
        'station_id', 'station_name', 'lat', 'lon', 'intensity',
        'acc_ns', 'acc_ew', 'acc_ud', 'acc_total',
        'vel_ns', 'vel_ew', 'vel_ud', 'vel_total',
        'disp_ns', 'disp_ew', 'disp_ud', 'disp_total'
    ]

    # station_idをキーにした辞書
    return df.set_index('station_id').to_dict('index')


def process_jma_station(filepath: Path, max_lookup: Dict, output_dir: Path) -> bool:
    """JMA観測点1つを処理"""
    try:
        # ファイル名から観測点コード抽出: 4110120251208231530_acc.csv -> 41101
        filename = filepath.stem  # 4110120251208231530_acc
        station_code = filename.split('_')[0][:5]

        # ヘッダー解析
        meta = parse_jma_header(filepath)

        # データ読み込み
        df = parse_jma_data(filepath)
        num_samples = len(df)

        # 時刻列生成
        datetimes = generate_datetime_series(
            meta['record_time'],
            num_samples,
            meta['sampling_freq']
        )

        # 出力ディレクトリ作成
        out_dir = output_dir / f"JMA_{station_code}"
        out_dir.mkdir(parents=True, exist_ok=True)

        # waveform.csv出力
        ns_data = df['NS'].values.tolist()
        ew_data = df['EW'].values.tolist()
        ud_data = df['UD'].values.tolist()

        out_df = pd.DataFrame({
            'datetime': datetimes,
            'NS': ns_data,
            'EW': ew_data,
            'UD': ud_data
        })
        out_df.to_csv(out_dir / 'waveform.csv', index=False)

        # 符号付き最大加速度を計算
        peak_ns = calc_signed_peak(ns_data)
        peak_ew = calc_signed_peak(ew_data)
        peak_ud = calc_signed_peak(ud_data)
        peak_h = calc_peak_horizontal(ns_data, ew_data)
        peak_total = calc_peak_total(ns_data, ew_data, ud_data)

        # max.csvから追加情報取得
        max_info = max_lookup.get(int(station_code), {})

        # metadata.yml作成
        metadata = {
            'source': 'JMA',
            'station': {
                'code': station_code,
                'name': meta.get('station_name', max_info.get('station_name', '')),
                'lat': meta['station_lat'],
                'lon': meta['station_lon']
            },
            'record': {
                'start_time': datetimes[0],
                'end_time': datetimes[-1],
                'sampling_rate_hz': meta['sampling_freq'],
                'duration_s': round(num_samples / meta['sampling_freq'], 2),
                'num_samples': num_samples,
                'unit': meta['unit']
            }
        }

        # 震度
        if max_info.get('intensity'):
            metadata['intensity'] = str(max_info['intensity'])

        # 最大加速度（符号付き、波形から計算）
        metadata['max_acceleration'] = {
            'NS': round(peak_ns, 3),
            'EW': round(peak_ew, 3),
            'UD': round(peak_ud, 3),
            'H': round(peak_h, 3),
            'total': round(peak_total, 3)
        }

        # 最大速度・変位（max.csvから取得）
        if max_info:
            metadata['max_velocity'] = {
                'NS': max_info.get('vel_ns'),
                'EW': max_info.get('vel_ew'),
                'UD': max_info.get('vel_ud'),
                'total': max_info.get('vel_total')
            }
            metadata['max_displacement'] = {
                'NS': max_info.get('disp_ns'),
                'EW': max_info.get('disp_ew'),
                'UD': max_info.get('disp_ud'),
                'total': max_info.get('disp_total')
            }

        with open(out_dir / 'metadata.yml', 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        return True

    except Exception as e:
        logger.error(f"JMA処理エラー ({filepath.name}): {e}")
        return False


# =============================================================================
# Utility Functions
# =============================================================================

def generate_datetime_series(record_time: str, num_samples: int, sampling_freq: int = 100) -> List[str]:
    """ISO 8601形式の時刻列を生成"""
    # "2025/12/08 23:15:34" -> datetime
    start_dt = datetime.strptime(record_time, "%Y/%m/%d %H:%M:%S")

    # 0.01秒刻みでタイムスタンプ生成
    interval = timedelta(seconds=1/sampling_freq)
    timestamps = []

    for i in range(num_samples):
        dt = start_dt + i * interval
        # ISO 8601: "2025-12-08T23:15:34.000"
        timestamps.append(dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int((i % sampling_freq) * (1000 / sampling_freq)):03d}")

    return timestamps


# =============================================================================
# Main Processing
# =============================================================================

def process_all_nied(input_dir: Path, output_dir: Path) -> int:
    """全NIED観測点を処理"""
    acc_dir = input_dir / '01_NIED' / 'acc'

    if not acc_dir.exists():
        logger.warning(f"NIED directory not found: {acc_dir}")
        return 0

    # ファイルを観測点+日時でグループ化
    files = list(acc_dir.glob('*'))
    station_groups: Dict[str, Dict[str, Path]] = {}

    for f in files:
        if f.suffix.upper() in ['.EW', '.NS', '.UD']:
            base = f.stem  # e.g., "AKT00120251208231519"
            if base not in station_groups:
                station_groups[base] = {}
            station_groups[base][f.suffix.upper()] = f

    # 各観測点を処理
    success_count = 0
    for base, components in station_groups.items():
        if len(components) != 3:
            logger.warning(f"不完全なデータ: {base} ({len(components)}/3)")
            continue

        if process_nied_station(base, components, output_dir):
            success_count += 1

    return success_count


def process_all_jma(input_dir: Path, output_dir: Path) -> int:
    """全JMA観測点を処理"""
    jma_dir = input_dir / '02_JMA'
    acc_dir = jma_dir / 'acc'
    max_csv = jma_dir / 'max.csv'

    if not acc_dir.exists():
        logger.warning(f"JMA acc directory not found: {acc_dir}")
        return 0

    # max.csv読み込み
    max_lookup = {}
    if max_csv.exists():
        max_lookup = load_jma_max_csv(max_csv)
    else:
        logger.warning(f"max.csv not found: {max_csv}")

    # 各ファイルを処理
    success_count = 0
    for filepath in acc_dir.glob('*_acc.csv'):
        if process_jma_station(filepath, max_lookup, output_dir):
            success_count += 1

    return success_count


def flatten_metadata(meta: Dict) -> Dict:
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
        'acc_NS': meta.get('max_acceleration', {}).get('NS'),
        'acc_EW': meta.get('max_acceleration', {}).get('EW'),
        'acc_UD': meta.get('max_acceleration', {}).get('UD'),
        'acc_H': meta.get('max_acceleration', {}).get('H'),
        'acc_total': meta.get('max_acceleration', {}).get('total'),
    }
    return record


def generate_summary_csv(output_dir: Path) -> int:
    """全metadata.ymlを読み込んでsummary CSVを生成"""
    records = []

    for station_dir in sorted(output_dir.iterdir()):
        if not station_dir.is_dir():
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


def main():
    """メインエントリポイント"""
    logger.info("地震波形データ変換開始")
    logger.info(f"入力: {INPUT_DIR}")
    logger.info(f"出力: {OUTPUT_DIR}")

    # 出力ディレクトリ作成
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # NIED処理
    logger.info("NIED データ処理中...")
    nied_count = process_all_nied(INPUT_DIR, OUTPUT_DIR)
    logger.info(f"NIED: {nied_count} 観測点完了")

    # JMA処理
    logger.info("JMA データ処理中...")
    jma_count = process_all_jma(INPUT_DIR, OUTPUT_DIR)
    logger.info(f"JMA: {jma_count} 観測点完了")

    # サマリCSV生成
    logger.info("サマリCSV生成中...")
    summary_count = generate_summary_csv(OUTPUT_DIR)
    logger.info(f"summary_metadata.csv: {summary_count} 観測点")

    logger.info(f"変換完了: 合計 {nied_count + jma_count} 観測点")
    logger.info(f"出力ディレクトリ: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
