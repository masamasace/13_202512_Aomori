/**
 * response.js - 応答スペクトル機能（Newmark-β法で計算）
 */

let responsePeriodSlider = null;
let responseAccSlider = null;

// 対数スケールスライダー用のヘルパー関数
function logSliderToValueResp(sliderValue, minLog, maxLog) {
    return Math.pow(10, minLog + (maxLog - minLog) * sliderValue / 100);
}

function valueToLogSliderResp(value, minLog, maxLog) {
    return (Math.log10(value) - minLog) / (maxLog - minLog) * 100;
}

function formatLogValueResp(value) {
    if (value >= 100) return value.toFixed(0);
    if (value >= 10) return value.toFixed(1);
    if (value >= 1) return value.toFixed(2);
    if (value >= 0.1) return value.toFixed(3);
    return value.toExponential(1);
}

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

    // X軸（周期）範囲を取得
    const periodSliderValues = responsePeriodSlider ? responsePeriodSlider.get().map(Number) : [0, 100];
    const periodRange = [
        logSliderToValueResp(periodSliderValues[0], -2, 1.5),  // 0.01 - ~30 s
        logSliderToValueResp(periodSliderValues[1], -2, 1.5)
    ];

    // Y軸（応答加速度）範囲を取得
    const accSliderValues = responseAccSlider ? responseAccSlider.get().map(Number) : [0, 100];
    const accRange = [
        logSliderToValueResp(accSliderValues[0], 0, 4),   // 1 - 10000 gal
        logSliderToValueResp(accSliderValues[1], 0, 4)
    ];

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
                type: 'log',
                range: [Math.log10(accRange[0]), Math.log10(accRange[1])]
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

// 対数スケールスライダーを作成
function createLogSliderResp(elementId, minLog, maxLog, startMin, startMax, minLabelId, maxLabelId, onChange) {
    const sliderEl = document.getElementById(elementId);
    if (!sliderEl || typeof noUiSlider === 'undefined') return null;

    const slider = noUiSlider.create(sliderEl, {
        start: [
            valueToLogSliderResp(startMin, minLog, maxLog),
            valueToLogSliderResp(startMax, minLog, maxLog)
        ],
        connect: true,
        range: { 'min': 0, 'max': 100 },
        step: 1
    });

    slider.on('update', values => {
        const minVal = logSliderToValueResp(Number(values[0]), minLog, maxLog);
        const maxVal = logSliderToValueResp(Number(values[1]), minLog, maxLog);
        document.getElementById(minLabelId).textContent = formatLogValueResp(minVal);
        document.getElementById(maxLabelId).textContent = formatLogValueResp(maxVal);
    });

    slider.on('change', onChange);

    return slider;
}

// 応答スペクトルタブの初期化
function initResponse() {
    const select = document.getElementById('responseStationSelect');

    const onSliderChange = () => {
        const selected = Array.from(select.selectedOptions);
        if (selected.length > 0) {
            updateResponsePlot();
        }
    };

    // 周期スライダーの初期化（対数: 0.01 - ~30 s）
    responsePeriodSlider = createLogSliderResp(
        'responsePeriodSlider', -2, 1.5, 0.02, 10,
        'responsePeriodMin', 'responsePeriodMax', onSliderChange
    );

    // 応答加速度スライダーの初期化（対数: 1 - 10000 gal）
    responseAccSlider = createLogSliderResp(
        'responseAccSlider', 0, 4, 1, 10000,
        'responseAccMin', 'responseAccMax', onSliderChange
    );

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
