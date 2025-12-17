#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地震計データをLeafletマップとしてHTML出力するスクリプト
summary_metadata.csvから動的にカラムを検出して色分け対応
"""

import numpy as np
import pandas as pd
import json
from pathlib import Path

# パス設定
BASE_DIR = Path(__file__).parent.parent
INPUT_CSV = BASE_DIR / "01_data/02_seismic_formatted/summary_metadata.csv"
OUTPUT_HTML = BASE_DIR / "03_output/seismic_map.html"

# 出力ディレクトリ作成
OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)

# CSVデータ読み込み（UTF-8）
df = pd.read_csv(INPUT_CSV, encoding='utf-8')

# 震度カラーマッピング（固定）
intensity_colors = {
    '1': '#F0F0FF',
    '2': '#00AAFF',
    '3': '#0041FF',
    '4': '#FAE696',
    '5弱': '#FFE600',
    '5強': '#FF9900',
    '6弱': '#FF2800',
    '6強': '#A50021',
    '7': '#B40068',
    '-': '#808080',
    '': '#808080'
}

# 数値カラムを動的に検出（lat, lon, height_m, sampling_rate_hz, duration_s除外）
exclude_cols = {'lat', 'lon', 'height_m', 'sampling_rate_hz', 'duration_s'}
numeric_cols = [col for col in df.select_dtypes(include=[np.number]).columns
                if col not in exclude_cols]

# 色分け設定を動的に生成
color_columns = {}

# 震度（カテゴリカル）
if 'intensity' in df.columns:
    color_columns['intensity'] = {
        'name': '震度',
        'type': 'category',
        'colors': intensity_colors
    }

# 数値カラム用の色（10段階: 青→白→赤）
# 安全=青, 中間=白, 危険=赤
color_palette_10 = [
    '#0000FF',  # 青 (最も安全)
    '#3333FF',
    '#6666FF',
    '#9999FF',
    '#CCCCFF',  # 薄い青→白
    '#FFCCCC',  # 白→薄い赤
    '#FF9999',
    '#FF6666',
    '#FF3333',
    '#FF0000',  # 赤 (最も危険)
]

# 各数値カラムに対してパーセンタイルベースで範囲設定（10段階）
for col in numeric_cols:
    values = df[col].dropna().abs()  # 絶対値を取る
    if len(values) == 0:
        continue

    # パーセンタイルで範囲を計算（10段階、上位に分解能を集中）
    percentiles = [0, 30, 50, 65, 75, 82, 88, 93, 97, 99, 100]
    thresholds = [np.percentile(values, p) for p in percentiles]

    ranges = []
    for i in range(len(thresholds) - 1):
        min_val = round(thresholds[i], 2)
        max_val = round(thresholds[i + 1], 2) if i < len(thresholds) - 2 else float('inf')
        ranges.append((min_val, max_val, color_palette_10[i]))

    color_columns[col] = {
        'name': col,
        'type': 'numeric',
        'ranges': ranges
    }

# NaNをnullに変換してJSON化
df_json = df.where(pd.notnull(df), None)
data_json = df_json.to_json(orient='records', force_ascii=False)

# セレクトボックスのオプション生成
select_options = '\n'.join([
    f'            <option value="{col}">{config["name"]}</option>'
    for col, config in color_columns.items()
])

# デフォルト選択カラム
default_col = 'intensity' if 'intensity' in color_columns else list(color_columns.keys())[0]

# HTMLテンプレート
html_template = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>地震計データマップ</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Hiragino Sans', 'Meiryo', sans-serif;
        }}
        #map {{
            height: calc(100vh - 60px);
            width: 100%;
        }}
        .control-panel {{
            height: 60px;
            background: #333;
            color: white;
            display: flex;
            align-items: center;
            padding: 0 20px;
            gap: 20px;
        }}
        .control-panel label {{
            font-size: 14px;
        }}
        .control-panel select {{
            padding: 8px 12px;
            font-size: 14px;
            border-radius: 4px;
            border: none;
        }}
        .legend {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
        }}
        .legend-title {{
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 4px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            margin-right: 8px;
            border-radius: 50%;
            border: 1px solid #333;
        }}
        .popup-content {{
            font-size: 12px;
        }}
        .popup-content h3 {{
            margin-bottom: 8px;
            color: #333;
        }}
        .popup-content table {{
            border-collapse: collapse;
            width: 100%;
        }}
        .popup-content td {{
            padding: 2px 5px;
            border-bottom: 1px solid #eee;
        }}
        .popup-content td:first-child {{
            font-weight: bold;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="control-panel">
        <label>色分け項目：</label>
        <select id="colorColumn">
{select_options}
        </select>
    </div>
    <div id="map"></div>

    <script>
        // データ
        const data = {data_json};

        // 色設定
        const colorConfig = {json.dumps(color_columns, ensure_ascii=False, default=str)};

        // 震度の色
        const intensityColors = {json.dumps(intensity_colors, ensure_ascii=False)};

        // マップ初期化
        const map = L.map('map').setView([40.5, 141.0], 6);

        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap contributors'
        }}).addTo(map);

        // マーカーレイヤー
        let markersLayer = L.layerGroup().addTo(map);

        // 凡例コントロール
        const legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function(map) {{
            this._div = L.DomUtil.create('div', 'legend');
            return this._div;
        }};
        legend.addTo(map);

        // 色取得関数
        function getColor(value, column) {{
            const config = colorConfig[column];
            if (!config) return '#808080';

            if (config.type === 'category') {{
                return intensityColors[value] || '#808080';
            }} else {{
                if (value === null || value === undefined) return '#808080';
                const absValue = Math.abs(value);  // 絶対値で判定
                for (const [min, max, color] of config.ranges) {{
                    if (absValue >= min && absValue < max) {{
                        return color;
                    }}
                }}
                return '#808080';
            }}
        }}

        // 凡例更新
        function updateLegend(column) {{
            const config = colorConfig[column];
            if (!config) return;

            let html = '<div class="legend-title">' + config.name + '</div>';

            if (config.type === 'category') {{
                for (const [key, color] of Object.entries(intensityColors)) {{
                    if (key === '') continue;
                    html += '<div class="legend-item">';
                    html += '<div class="legend-color" style="background:' + color + '"></div>';
                    html += '<span>' + key + '</span></div>';
                }}
            }} else {{
                for (const [min, max, color] of config.ranges) {{
                    const maxLabel = max === Infinity ? '+' : max;
                    html += '<div class="legend-item">';
                    html += '<div class="legend-color" style="background:' + color + '"></div>';
                    html += '<span>' + min + ' - ' + maxLabel + '</span></div>';
                }}
            }}

            legend._div.innerHTML = html;
        }}

        // ポップアップ内容を動的生成
        function createPopupContent(item) {{
            const excludeKeys = ['lat', 'lon'];
            let rows = '';

            for (const [key, value] of Object.entries(item)) {{
                if (excludeKeys.includes(key)) continue;
                if (value === null || value === undefined || value === '') continue;

                let displayValue = value;
                if (typeof value === 'number') {{
                    displayValue = Number.isInteger(value) ? value : value.toFixed(3);
                }}

                rows += `<tr><td>${{key}}</td><td>${{displayValue}}</td></tr>`;
            }}

            const title = item.station_name || item.station_code || 'Unknown';
            return `
                <div class="popup-content">
                    <h3>${{title}}</h3>
                    <table>${{rows}}</table>
                </div>
            `;
        }}

        // マーカー描画
        function drawMarkers(column) {{
            markersLayer.clearLayers();

            data.forEach(item => {{
                if (item.lat && item.lon) {{
                    const color = getColor(item[column], column);

                    const marker = L.circleMarker([item.lat, item.lon], {{
                        radius: 8,
                        fillColor: color,
                        color: '#333',
                        weight: 1,
                        opacity: 1,
                        fillOpacity: 0.8
                    }});

                    marker.bindPopup(createPopupContent(item));
                    markersLayer.addLayer(marker);
                }}
            }});

            updateLegend(column);
        }}

        // 初期描画
        document.getElementById('colorColumn').value = '{default_col}';
        drawMarkers('{default_col}');

        // セレクトボックス変更時
        document.getElementById('colorColumn').addEventListener('change', function() {{
            drawMarkers(this.value);
        }});
    </script>
</body>
</html>
'''

# HTML出力
with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_template)

print(f"HTMLファイルを出力しました: {OUTPUT_HTML}")
print(f"観測点数: {len(df)}")
print(f"色分け可能カラム: {list(color_columns.keys())}")
