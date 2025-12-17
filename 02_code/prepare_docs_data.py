#!/usr/bin/env python3
"""
GitHub Pages用データ準備スクリプト
- summary_metadata.csv → stations.json に変換
- 各観測点のCSVデータを docs/data/ にコピー
"""

import json
import shutil
from pathlib import Path
import pandas as pd

# パス設定
BASE_DIR = Path(__file__).parent.parent
SOURCE_DIR = BASE_DIR / "01_data" / "02_seismic_formatted"
DOCS_DATA_DIR = BASE_DIR / "docs" / "data"


def safe_value(val):
    """NaN/Infを適切に処理"""
    if pd.isna(val):
        return None
    if isinstance(val, float) and (val != val or val == float('inf') or val == float('-inf')):
        return None
    return val


def convert_metadata_to_json():
    """summary_metadata.csv を stations.json に変換"""
    csv_path = SOURCE_DIR / "summary_metadata.csv"
    df = pd.read_csv(csv_path)

    stations = {}
    for _, row in df.iterrows():
        station_code = f"{row['source']}_{row['station_code']}"
        # NIED観測点は名前がないので観測点コードを使用
        name = row["station_name"] if pd.notna(row["station_name"]) else station_code
        stations[station_code] = {
            "source": row["source"],
            "code": str(row["station_code"]),
            "name": name,
            "lat": safe_value(row["lat"]),
            "lon": safe_value(row["lon"]),
            "intensity": str(row["intensity"]) if pd.notna(row["intensity"]) else None,
            "acc_NS": safe_value(row["acc_NS"]),
            "acc_EW": safe_value(row["acc_EW"]),
            "acc_UD": safe_value(row["acc_UD"]),
            "acc_H": safe_value(row["acc_H"]),
            "acc_total": safe_value(row["acc_total"]),
            "vel_NS": safe_value(row["vel_NS"]),
            "vel_EW": safe_value(row["vel_EW"]),
            "vel_UD": safe_value(row["vel_UD"]),
            "vel_H": safe_value(row["vel_H"]),
            "vel_total": safe_value(row["vel_total"]),
            "disp_NS": safe_value(row["disp_NS"]),
            "disp_EW": safe_value(row["disp_EW"]),
            "disp_UD": safe_value(row["disp_UD"]),
            "disp_H": safe_value(row["disp_H"]),
            "disp_total": safe_value(row["disp_total"]),
        }

    output_path = DOCS_DATA_DIR / "stations.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(stations, f, ensure_ascii=False, indent=2)

    print(f"Created: {output_path} ({len(stations)} stations)")
    return stations


def copy_station_data(station_codes):
    """各観測点のCSVデータをコピー"""
    files_to_copy = ["waveform.csv"]
    copied_count = 0
    skipped_count = 0

    for station_code in station_codes:
        source_station_dir = SOURCE_DIR / station_code
        dest_station_dir = DOCS_DATA_DIR / station_code

        if not source_station_dir.exists():
            print(f"Warning: Source directory not found: {source_station_dir}")
            skipped_count += 1
            continue

        dest_station_dir.mkdir(parents=True, exist_ok=True)

        for filename in files_to_copy:
            source_file = source_station_dir / filename
            dest_file = dest_station_dir / filename

            if source_file.exists():
                shutil.copy2(source_file, dest_file)
                copied_count += 1
            else:
                print(f"Warning: File not found: {source_file}")

    print(f"Copied {copied_count} files, skipped {skipped_count} stations")


def main():
    print("Preparing data for GitHub Pages...")
    print(f"Source: {SOURCE_DIR}")
    print(f"Destination: {DOCS_DATA_DIR}")

    # docs/data ディレクトリを作成
    DOCS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # メタデータを変換
    stations = convert_metadata_to_json()

    # 各観測点のデータをコピー
    copy_station_data(list(stations.keys()))

    print("Done!")


if __name__ == "__main__":
    main()
