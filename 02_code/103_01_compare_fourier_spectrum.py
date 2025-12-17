#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
複数地点のフーリエスペクトルを比較するインタラクティブHTMLを生成するスクリプト
Plotly.jsを使用し、CSVを動的に読み込んで描画
ローカルサーバー経由で動作
"""

import json
import yaml
import http.server
import socketserver
import webbrowser
import threading
from pathlib import Path

# パス設定
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "01_data/02_seismic_formatted"
OUTPUT_DIR = BASE_DIR / "03_output"
OUTPUT_HTML = OUTPUT_DIR / "fourier_spectrum_comparison.html"

# 出力ディレクトリ作成
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# サーバー設定
PORT = 8081


def load_station_metadata():
    """観測点のメタデータのみを読み込む"""
    stations = {}

    for station_dir in sorted(DATA_DIR.iterdir()):
        if not station_dir.is_dir():
            continue

        station_code = station_dir.name
        metadata_path = station_dir / "metadata.yml"
        fourier_path = station_dir / "fourier_spectrum.csv"

        if not metadata_path.exists() or not fourier_path.exists():
            continue

        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)

        stations[station_code] = {
            'name': metadata.get('station', {}).get('name', station_code),
            'lat': metadata.get('station', {}).get('lat'),
            'lon': metadata.get('station', {}).get('lon'),
            'intensity': metadata.get('intensity', '-'),
            'source': metadata.get('source', 'Unknown'),
            'max_acc': metadata.get('max_acceleration', {}).get('total'),
        }

    return stations


def generate_html(stations):
    """HTMLを生成（CSVは動的読み込み）"""

    stations_json = json.dumps(stations, ensure_ascii=False)

    # 震度順でソートしたリストを生成
    intensity_order = {'7': 0, '6強': 1, '6弱': 2, '5強': 3, '5弱': 4, '4': 5, '3': 6, '2': 7, '1': 8, '-': 9, '': 10}
    sorted_stations = sorted(
        stations.items(),
        key=lambda x: (intensity_order.get(x[1].get('intensity', '-'), 9), x[0])
    )

    # 観測点オプション生成
    station_options = '\n'.join([
        f'                        <option value="{code}">[{info.get("intensity", "-")}] {info.get("name", code)} ({code})</option>'
        for code, info in sorted_stations
    ])

    html_template = f'''<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>フーリエスペクトル比較ビューア</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/PapaParse/5.4.1/papaparse.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.7.1/nouislider.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/noUiSlider/15.7.1/nouislider.min.css">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Hiragino Sans', 'Meiryo', sans-serif;
            background: #f5f5f5;
        }}
        .control-panel {{
            background: #333;
            color: white;
            padding: 15px 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            align-items: flex-start;
        }}
        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .control-group label {{
            font-size: 12px;
            color: #ccc;
        }}
        .control-group select,
        .control-group button {{
            padding: 8px 12px;
            font-size: 14px;
            border-radius: 4px;
            border: none;
            min-width: 150px;
        }}
        .control-group select[multiple] {{
            min-height: 120px;
            min-width: 300px;
        }}
        .control-group button {{
            cursor: pointer;
            background: #4CAF50;
            color: white;
        }}
        .control-group button:hover {{
            background: #45a049;
        }}
        .control-group button.secondary {{
            background: #666;
        }}
        .control-group button.secondary:hover {{
            background: #555;
        }}
        .control-group button:disabled {{
            background: #999;
            cursor: not-allowed;
        }}
        #plot {{
            width: 100%;
            height: calc(100vh - 220px);
            background: white;
        }}
        .info-bar {{
            background: #444;
            color: #aaa;
            padding: 8px 20px;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
        }}
        .button-row {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .loading {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 20px 40px;
            border-radius: 8px;
            z-index: 1000;
            display: none;
        }}
        .loading.show {{
            display: block;
        }}
        .slider-group {{
            min-width: 280px;
        }}
        .slider-container {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 8px;
        }}
        .slider-label {{
            min-width: 50px;
            font-size: 12px;
            color: #ccc;
        }}
        .slider-wrapper {{
            flex: 1;
            padding: 0 10px;
        }}
        .slider-value {{
            min-width: 100px;
            font-size: 11px;
            text-align: right;
            color: #fff;
        }}
        .noUi-target {{
            background: #555;
            border: none;
            box-shadow: none;
        }}
        .noUi-connect {{
            background: #4CAF50;
        }}
        .noUi-handle {{
            background: #fff;
            border: none;
            box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        }}
        .noUi-handle:before, .noUi-handle:after {{
            display: none;
        }}
        .auto-checkbox {{
            display: flex;
            align-items: center;
            gap: 5px;
            margin-left: 10px;
        }}
        .auto-checkbox input {{
            width: 14px;
            height: 14px;
        }}
        .auto-checkbox label {{
            font-size: 11px;
            color: #ccc;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <div class="loading" id="loading">読み込み中...</div>
    <div class="control-panel">
        <div class="control-group">
            <label>観測点選択（Ctrl/Cmd+クリックで複数選択）</label>
            <select id="stationSelect" multiple>
{station_options}
            </select>
        </div>
        <div class="control-group">
            <label>成分</label>
            <select id="componentSelect">
                <option value="all">全成分 (NS/EW/UD)</option>
                <option value="NS">NS成分のみ</option>
                <option value="EW">EW成分のみ</option>
                <option value="UD">UD成分のみ</option>
            </select>
            <label style="margin-top: 10px;">表示形式</label>
            <select id="displayMode">
                <option value="subplot">サブプロット（縦並び）</option>
                <option value="overlay">オーバーレイ（重ね描き）</option>
            </select>
        </div>
        <div class="control-group slider-group">
            <label>軸範囲設定（対数スケール）</label>
            <div class="slider-container">
                <span class="slider-label">X軸:</span>
                <div class="slider-wrapper"><div id="xAxisSlider"></div></div>
                <span class="slider-value" id="xAxisValue">0.1 - 50 Hz</span>
            </div>
            <div class="slider-container">
                <span class="slider-label">Y軸:</span>
                <div class="slider-wrapper"><div id="yAxisSlider"></div></div>
                <span class="slider-value" id="yAxisValue">auto</span>
                <div class="auto-checkbox">
                    <input type="checkbox" id="yAxisAuto" checked>
                    <label for="yAxisAuto">auto</label>
                </div>
            </div>
        </div>
        <div class="control-group">
            <label>操作</label>
            <div class="button-row">
                <button id="updateBtn" onclick="updatePlot()">描画更新</button>
                <button class="secondary" onclick="clearSelection()">選択解除</button>
            </div>
            <label style="margin-top: 10px;">クイック選択</label>
            <div class="button-row">
                <button class="secondary" onclick="selectByIntensity('5強')">震度5強</button>
                <button class="secondary" onclick="selectByIntensity('5弱')">震度5弱</button>
                <button class="secondary" onclick="selectByIntensity('4')">震度4</button>
            </div>
        </div>
    </div>
    <div class="info-bar">
        <span id="stationCount">選択地点: 0</span>
        <span id="dataInfo">データポイント: -</span>
    </div>
    <div id="plot"></div>

    <script>
        // 観測点メタデータ
        const stations = {stations_json};

        // キャッシュされたスペクトルデータ
        const spectrumCache = {{}};

        // 成分の色設定
        const componentColors = {{
            'NS': '#1f77b4',
            'EW': '#ff7f0e',
            'UD': '#2ca02c',
        }};

        // 地点ごとの色パレット
        const stationColors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
        ];

        // スライダー設定
        const xAxisConfig = {{ min: 0.01, max: 100, startMin: 0.1, startMax: 50, unit: 'Hz' }};
        const yAxisConfig = {{ min: 0.001, max: 10000, startMin: 0.01, startMax: 1000, unit: 'gal·s' }};

        // 対数スケールスライダー初期化
        function createLogSlider(elementId, config, onChange) {{
            const slider = document.getElementById(elementId);
            noUiSlider.create(slider, {{
                start: [Math.log10(config.startMin), Math.log10(config.startMax)],
                connect: true,
                range: {{
                    'min': Math.log10(config.min),
                    'max': Math.log10(config.max)
                }},
                step: 0.01
            }});
            slider.noUiSlider.on('change', onChange);
            return slider;
        }}

        // スライダー値を取得（対数→実数変換）
        function getSliderValues(elementId) {{
            const slider = document.getElementById(elementId);
            const values = slider.noUiSlider.get();
            return [Math.pow(10, parseFloat(values[0])), Math.pow(10, parseFloat(values[1]))];
        }}

        // 数値をフォーマット
        function formatValue(val) {{
            if (val >= 100) return val.toFixed(0);
            if (val >= 10) return val.toFixed(1);
            if (val >= 1) return val.toFixed(2);
            if (val >= 0.1) return val.toFixed(2);
            if (val >= 0.01) return val.toFixed(3);
            return val.toExponential(1);
        }}

        // X軸スライダー更新時
        function onXAxisChange() {{
            const values = getSliderValues('xAxisSlider');
            document.getElementById('xAxisValue').textContent =
                `${{formatValue(values[0])}} - ${{formatValue(values[1])}} ${{xAxisConfig.unit}}`;
            updateAxisRange();
        }}

        // Y軸スライダー更新時
        function onYAxisChange() {{
            const yAuto = document.getElementById('yAxisAuto').checked;
            if (yAuto) {{
                document.getElementById('yAxisValue').textContent = 'auto';
            }} else {{
                const values = getSliderValues('yAxisSlider');
                document.getElementById('yAxisValue').textContent =
                    `${{formatValue(values[0])}} - ${{formatValue(values[1])}}`;
            }}
            updateAxisRange();
        }}

        // 軸範囲をグラフに適用
        function updateAxisRange() {{
            const plotDiv = document.getElementById('plot');
            if (!plotDiv.data || plotDiv.data.length === 0) return;

            const xValues = getSliderValues('xAxisSlider');
            const yAuto = document.getElementById('yAxisAuto').checked;
            const yValues = yAuto ? null : getSliderValues('yAxisSlider');

            const displayMode = document.getElementById('displayMode').value;

            if (displayMode === 'overlay') {{
                const update = {{
                    'xaxis.range': [Math.log10(xValues[0]), Math.log10(xValues[1])],
                }};
                if (!yAuto) {{
                    update['yaxis.range'] = [Math.log10(yValues[0]), Math.log10(yValues[1])];
                    update['yaxis.autorange'] = false;
                }} else {{
                    update['yaxis.autorange'] = true;
                }}
                Plotly.relayout('plot', update);
            }} else {{
                // サブプロットの場合、全てのX軸を更新
                const update = {{}};
                const numAxes = plotDiv.layout ? Object.keys(plotDiv.layout).filter(k => k.startsWith('xaxis')).length : 1;
                for (let i = 0; i < numAxes; i++) {{
                    const xKey = i === 0 ? 'xaxis' : `xaxis${{i + 1}}`;
                    const yKey = i === 0 ? 'yaxis' : `yaxis${{i + 1}}`;
                    update[`${{xKey}}.range`] = [Math.log10(xValues[0]), Math.log10(xValues[1])];
                    if (!yAuto) {{
                        update[`${{yKey}}.range`] = [Math.log10(yValues[0]), Math.log10(yValues[1])];
                        update[`${{yKey}}.autorange`] = false;
                    }} else {{
                        update[`${{yKey}}.autorange`] = true;
                    }}
                }}
                Plotly.relayout('plot', update);
            }}
        }}

        // スライダー初期化
        createLogSlider('xAxisSlider', xAxisConfig, onXAxisChange);
        createLogSlider('yAxisSlider', yAxisConfig, onYAxisChange);

        // Y軸autoチェックボックス
        document.getElementById('yAxisAuto').addEventListener('change', function() {{
            const ySlider = document.getElementById('yAxisSlider');
            if (this.checked) {{
                ySlider.setAttribute('disabled', true);
                document.getElementById('yAxisValue').textContent = 'auto';
            }} else {{
                ySlider.removeAttribute('disabled');
                onYAxisChange();
            }}
            updateAxisRange();
        }});

        // 初期表示
        onXAxisChange();
        onYAxisChange();

        // ローディング表示
        function showLoading(show) {{
            document.getElementById('loading').classList.toggle('show', show);
            document.getElementById('updateBtn').disabled = show;
        }}

        // 選択数更新
        function updateStationCount() {{
            const select = document.getElementById('stationSelect');
            const count = Array.from(select.selectedOptions).length;
            document.getElementById('stationCount').textContent = `選択地点: ${{count}}`;
        }}

        document.getElementById('stationSelect').addEventListener('change', updateStationCount);

        // 選択解除
        function clearSelection() {{
            const select = document.getElementById('stationSelect');
            Array.from(select.options).forEach(opt => opt.selected = false);
            updateStationCount();
            Plotly.purge('plot');
            document.getElementById('dataInfo').textContent = 'データポイント: -';
        }}

        // 震度で選択
        function selectByIntensity(intensity) {{
            const select = document.getElementById('stationSelect');
            Array.from(select.options).forEach(opt => {{
                const code = opt.value;
                const stationIntensity = stations[code]?.intensity;
                opt.selected = (stationIntensity === intensity);
            }});
            updateStationCount();
            updatePlot();
        }}

        // CSVを読み込む
        async function loadSpectrumData(stationCode) {{
            if (spectrumCache[stationCode]) {{
                return spectrumCache[stationCode];
            }}

            const url = `../01_data/02_seismic_formatted/${{stationCode}}/fourier_spectrum.csv`;

            return new Promise((resolve, reject) => {{
                Papa.parse(url, {{
                    download: true,
                    header: true,
                    dynamicTyping: true,
                    complete: function(results) {{
                        if (results.errors.length > 0) {{
                            console.warn(`Parse errors for ${{stationCode}}:`, results.errors);
                        }}

                        const data = results.data.filter(row => row.frequency !== undefined && row.frequency !== null);

                        if (data.length > 0) {{
                            const processed = {{
                                frequency: data.map(row => row.frequency),
                                NS: data.map(row => row.NS),
                                EW: data.map(row => row.EW),
                                UD: data.map(row => row.UD)
                            }};
                            spectrumCache[stationCode] = processed;
                            resolve(processed);
                        }} else {{
                            resolve(null);
                        }}
                    }},
                    error: function(error) {{
                        console.error(`Failed to load ${{url}}:`, error);
                        resolve(null);
                    }}
                }});
            }});
        }}

        // プロット更新
        async function updatePlot() {{
            const select = document.getElementById('stationSelect');
            const selectedStations = Array.from(select.selectedOptions).map(opt => opt.value);
            const displayMode = document.getElementById('displayMode').value;
            const componentSelect = document.getElementById('componentSelect').value;

            // スライダーから範囲取得
            const xRange = getSliderValues('xAxisSlider');
            const yAuto = document.getElementById('yAxisAuto').checked;
            const yRange = yAuto ? null : getSliderValues('yAxisSlider');

            if (selectedStations.length === 0) {{
                Plotly.purge('plot');
                document.getElementById('dataInfo').textContent = 'データポイント: -';
                return;
            }}

            showLoading(true);

            try {{
                // スペクトルデータを並列で読み込む
                const loadPromises = selectedStations.map(code => loadSpectrumData(code));
                const spectrumDataList = await Promise.all(loadPromises);

                // 表示する成分を決定
                const components = componentSelect === 'all' ? ['NS', 'EW', 'UD'] : [componentSelect];

                const traces = [];
                let totalPoints = 0;

                if (displayMode === 'subplot') {{
                    // サブプロット表示
                    const validStations = [];

                    selectedStations.forEach((stationCode, idx) => {{
                        const data = spectrumDataList[idx];
                        if (!data) return;
                        validStations.push({{ code: stationCode, data }});
                    }});

                    validStations.forEach((item, stationIdx) => {{
                        const {{ code: stationCode, data }} = item;
                        const stationInfo = stations[stationCode];
                        const stationName = stationInfo?.name || stationCode;

                        components.forEach((comp, compIdx) => {{
                            if (data[comp]) {{
                                totalPoints += data[comp].length;
                                traces.push({{
                                    x: data.frequency,
                                    y: data[comp],
                                    type: 'scatter',
                                    mode: 'lines',
                                    name: `${{stationName}} (${{comp}})`,
                                    line: {{
                                        color: componentColors[comp],
                                        width: 1
                                    }},
                                    xaxis: stationIdx === 0 ? 'x' : `x${{stationIdx + 1}}`,
                                    yaxis: stationIdx === 0 ? 'y' : `y${{stationIdx + 1}}`,
                                    legendgroup: stationCode,
                                    showlegend: compIdx === 0
                                }});
                            }}
                        }});
                    }});

                    // サブプロットのレイアウト
                    const numPlots = validStations.length;
                    const plotHeight = 1 / numPlots;
                    const gap = 0.02;

                    const layout = {{
                        title: 'フーリエスペクトル比較',
                        showlegend: true,
                        legend: {{ x: 1.02, y: 1 }},
                        margin: {{ l: 80, r: 150, t: 50, b: 50 }},
                    }};

                    validStations.forEach((item, idx) => {{
                        const stationInfo = stations[item.code];
                        const stationName = stationInfo?.name || item.code;
                        const intensity = stationInfo?.intensity || '-';

                        const yStart = 1 - (idx + 1) * plotHeight + gap / 2;
                        const yEnd = 1 - idx * plotHeight - gap / 2;

                        const xAxisKey = idx === 0 ? 'xaxis' : `xaxis${{idx + 1}}`;
                        const yAxisKey = idx === 0 ? 'yaxis' : `yaxis${{idx + 1}}`;

                        layout[yAxisKey] = {{
                            title: `[${{intensity}}] ${{stationName}}`,
                            type: 'log',
                            domain: [yStart, yEnd],
                            anchor: idx === 0 ? 'x' : `x${{idx + 1}}`
                        }};
                        if (!yAuto) {{
                            layout[yAxisKey].range = [Math.log10(yRange[0]), Math.log10(yRange[1])];
                            layout[yAxisKey].autorange = false;
                        }}

                        layout[xAxisKey] = {{
                            title: idx === numPlots - 1 ? '周波数 (Hz)' : '',
                            type: 'log',
                            range: [Math.log10(xRange[0]), Math.log10(xRange[1])],
                            domain: [0, 0.85],
                            anchor: idx === 0 ? 'y' : `y${{idx + 1}}`,
                            matches: 'x'
                        }};
                    }});

                    Plotly.react('plot', traces, layout, {{responsive: true}});

                }} else {{
                    // オーバーレイ表示
                    selectedStations.forEach((stationCode, stationIdx) => {{
                        const data = spectrumDataList[stationIdx];
                        if (!data) return;

                        const stationInfo = stations[stationCode];
                        const stationName = stationInfo?.name || stationCode;
                        const intensity = stationInfo?.intensity || '-';
                        const baseColor = stationColors[stationIdx % stationColors.length];

                        components.forEach((comp, compIdx) => {{
                            if (data[comp]) {{
                                totalPoints += data[comp].length;
                                const dashStyles = ['solid', 'dash', 'dot'];
                                traces.push({{
                                    x: data.frequency,
                                    y: data[comp],
                                    type: 'scatter',
                                    mode: 'lines',
                                    name: `[${{intensity}}] ${{stationName}} (${{comp}})`,
                                    line: {{
                                        color: baseColor,
                                        width: 1.5,
                                        dash: dashStyles[compIdx]
                                    }},
                                    legendgroup: stationCode
                                }});
                            }}
                        }});
                    }});

                    const layout = {{
                        title: 'フーリエスペクトル比較（オーバーレイ）',
                        xaxis: {{
                            title: '周波数 (Hz)',
                            type: 'log',
                            range: [Math.log10(xRange[0]), Math.log10(xRange[1])]
                        }},
                        yaxis: {{
                            title: 'フーリエ振幅 (gal·s)',
                            type: 'log'
                        }},
                        showlegend: true,
                        legend: {{ x: 1.02, y: 1 }},
                        margin: {{ l: 80, r: 200, t: 50, b: 50 }},
                        hovermode: 'x unified'
                    }};

                    if (!yAuto) {{
                        layout.yaxis.range = [Math.log10(yRange[0]), Math.log10(yRange[1])];
                        layout.yaxis.autorange = false;
                    }}

                    Plotly.react('plot', traces, layout, {{responsive: true}});
                }}

                document.getElementById('dataInfo').textContent = `データポイント: ${{totalPoints.toLocaleString()}}`;

            }} catch (error) {{
                console.error('Plot error:', error);
                alert('描画中にエラーが発生しました: ' + error.message);
            }} finally {{
                showLoading(false);
            }}
        }}

        // 初期化
        updateStationCount();
    </script>
</body>
</html>
'''
    return html_template


def run_server():
    """ローカルサーバーを起動"""
    handler = http.server.SimpleHTTPRequestHandler

    class CustomHandler(handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(BASE_DIR), **kwargs)

        def log_message(self, format, *args):
            print(f"[Server] {args[0]}")

    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"\nサーバー起動: http://localhost:{PORT}/03_output/fourier_spectrum_comparison.html")
        print("終了するには Ctrl+C を押してください\n")
        httpd.serve_forever()


def main():
    print("観測点メタデータを読み込み中...")
    stations = load_station_metadata()
    print(f"観測点数: {len(stations)}")

    print("HTMLを生成中...")
    html_content = generate_html(stations)

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTMLファイルを出力しました: {OUTPUT_HTML}")

    # ブラウザを開く
    url = f"http://localhost:{PORT}/03_output/fourier_spectrum_comparison.html"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # サーバー起動
    run_server()


if __name__ == '__main__':
    main()
