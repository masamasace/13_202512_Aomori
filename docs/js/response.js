/**
 * response.js - 応答スペクトル機能（Newmark-β法で計算）
 */

let responsePeriodSlider = null;

// 応答スペクトルデータをロード（signal.jsで計算）
async function loadResponseData(stationCode) {
    const processed = await getProcessedData(stationCode);
    if (!processed) {
        return null;
    }

    return processed.response;
}

// 応答スペクトルプロットを更新
async function updateResponsePlot() {
    const select = document.getElementById('responseStationSelect');
    const selectedStations = Array.from(select.selectedOptions).map(opt => opt.value);
    const component = document.getElementById('responseComponent').value;
    const damping = document.getElementById('responseDamping').value;

    if (selectedStations.length === 0) {
        Plotly.purge('responsePlot');
        return;
    }

    // 周期範囲を取得
    const periodRange = responsePeriodSlider ? responsePeriodSlider.get().map(Number) : [0.02, 10];

    showLoading(true);

    try {
        // データを並列ロード
        const loadPromises = selectedStations.map(code => loadResponseData(code));
        const responseDataList = await Promise.all(loadPromises);

        const traces = [];

        selectedStations.forEach((code, i) => {
            if (!responseDataList[i]) return;

            const stationName = stations[code]?.name || code;
            const data = responseDataList[i];

            // 周期範囲でフィルタ
            const filteredIndices = data.period
                .map((p, idx) => ({ p, idx }))
                .filter(item => item.p >= periodRange[0] && item.p <= periodRange[1])
                .map(item => item.idx);

            const yData = data[component][damping];

            traces.push({
                x: filteredIndices.map(idx => data.period[idx]),
                y: filteredIndices.map(idx => yData[idx]),
                type: 'scatter',
                mode: 'lines',
                name: stationName,
                line: { width: 1.5 }
            });
        });

        const dampingLabels = {
            'h005': '5%',
            'h010': '10%',
            'h020': '20%'
        };

        const layout = {
            title: `応答スペクトル比較 (${component}成分, 減衰${dampingLabels[damping]})`,
            xaxis: {
                title: '周期 (s)',
                type: 'log',
                range: [Math.log10(periodRange[0]), Math.log10(periodRange[1])]
            },
            yaxis: {
                title: '応答加速度 (gal)',
                type: 'log'
            },
            showlegend: true,
            legend: { orientation: 'h', y: -0.15 },
            margin: { l: 70, r: 20, t: 40, b: 80 }
        };

        Plotly.newPlot('responsePlot', traces, layout, { responsive: true });

    } catch (error) {
        console.error('Failed to update response plot:', error);
    } finally {
        showLoading(false);
    }
}

// 応答スペクトルタブの初期化
function initResponse() {
    const select = document.getElementById('responseStationSelect');

    // 周期スライダーの初期化
    const sliderEl = document.getElementById('responsePeriodSlider');
    if (sliderEl && typeof noUiSlider !== 'undefined') {
        responsePeriodSlider = noUiSlider.create(sliderEl, {
            start: [0.02, 10],
            connect: true,
            range: {
                'min': 0.01,
                'max': 20
            },
            step: 0.01,
            format: {
                to: value => value.toFixed(2),
                from: value => parseFloat(value)
            }
        });

        responsePeriodSlider.on('update', values => {
            document.getElementById('responsePeriodMin').textContent = values[0];
            document.getElementById('responsePeriodMax').textContent = values[1];
        });

        responsePeriodSlider.on('change', () => {
            const selected = Array.from(select.selectedOptions);
            if (selected.length > 0) {
                updateResponsePlot();
            }
        });
    }

    // 選択変更時のカウント更新
    select.addEventListener('change', () => {
        updateStationCount('responseStationSelect', 'responseStationCount');
    });

    // プロットボタン
    document.getElementById('responsePlotBtn').addEventListener('click', updateResponsePlot);

    // クリアボタン
    document.getElementById('responseClearBtn').addEventListener('click', () => {
        Array.from(select.options).forEach(opt => opt.selected = false);
        updateStationCount('responseStationSelect', 'responseStationCount');
        Plotly.purge('responsePlot');
    });

    // 成分・減衰定数変更時
    ['responseComponent', 'responseDamping'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            const selected = Array.from(select.selectedOptions);
            if (selected.length > 0) {
                updateResponsePlot();
            }
        });
    });
}
