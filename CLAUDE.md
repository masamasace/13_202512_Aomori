# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Field survey research project for December 2025 Aomori (青森) earthquake event analysis.

## Directory Structure

- `01_data/` - Raw and processed data
  - `01_seismic/01_NIED/` - NIED (防災科学技術研究所) seismic waveform data
  - `01_seismic/02_JMA/` - JMA (気象庁) seismic intensity data
  - `02_seismic_formatted/` - Unified format data (waveform.csv + metadata.yml per station)
- `02_code/` - Analysis scripts and notebooks
- `03_output/` - Generated outputs (HTML maps, figures)

## Data Handling

- CSV files from JMA are encoded in **Shift-JIS (CP932)**. When reading with Python:
  ```python
  pd.read_csv(filepath, encoding='cp932')
  ```
- JMA seismic intensity data (`level.csv`) contains observation station data with columns for station ID, location, earthquake timing, and intensity values

## Data Conventions

- **Signed peak acceleration**: metadata.yml stores signed values (e.g., -130.159 gal) representing the value at the time of absolute maximum
- **Visualization**: When displaying/coloring by acceleration values, always use **absolute values** for comparison and color mapping

## Data Sources

- NIED K-NET/KiK-net: https://www.kyoshin.bosai.go.jp/
- JMA Seismic Intensity Database: https://www.data.jma.go.jp/svd/eqdb/data/shindo/
