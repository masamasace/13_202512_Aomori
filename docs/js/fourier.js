/**
 * fourier.js - フーリエスペクトル機能（FFTで計算）
 */

let fourierFreqSlider = null;
let fourierAmpSlider = null;

// 対数スケールスライダー用のヘルパー関数
function logSliderToValue(sliderValue, minLog, maxLog) {
    return Math.pow(10, minLog + (maxLog - minLog) * sliderValue / 100);
}

function valueToLogSlider(value, minLog, maxLog) {
    return (Math.log10(value) - minLog) / (maxLog - minLog) * 100;
}

function formatLogValue(value) {
    if (value >= 100) return value.toFixed(0);
    if (value >= 10) return value.toFixed(1);
    if (value >= 1) return value.toFixed(2);
    if (value >= 0.1) return value.toFixed(3);
    return value.toExponential(1);
}

// フーリエスペクトルデータをロード（signal.jsで計算）
async function loadFourierData(stationCode) {
    const processed = await getProcessedData(stationCode);
    if (!processed) {
        return null;
    }

    return processed.fourier;
}

// フーリエスペクトルプロットを更新
async function updateFourierPlot() {
    const select = document.getElementById('fourierStationSelect');
    const selectedStations = Array.from(select.selectedOptions).map(opt => opt.value);
    const component = document.getElementById('fourierComponent').value;

    if (selectedStations.length === 0) {
        Plotly.purge('fourierPlot');
        return;
    }

    // X軸（周波数）範囲を取得
    const freqSliderValues = fourierFreqSlider ? fourierFreqSlider.get().map(Number) : [0, 100];
    const freqRange = [
        logSliderToValue(freqSliderValues[0], -2, 2),  // 0.01 - 100 Hz
        logSliderToValue(freqSliderValues[1], -2, 2)
    ];

    // Y軸（振幅）範囲を取得
    const ampSliderValues = fourierAmpSlider ? fourierAmpSlider.get().map(Number) : [0, 100];
    const ampRange = [
        logSliderToValue(ampSliderValues[0], -4, 3),   // 0.0001 - 1000 gal·s
        logSliderToValue(ampSliderValues[1], -4, 3)
    ];

    showLoading(true);

    try {
        // データを並列ロード
        const loadPromises = selectedStations.map(code => loadFourierData(code));
        const fourierDataList = await Promise.all(loadPromises);

        const traces = [];

        selectedStations.forEach((code, i) => {
            if (!fourierDataList[i]) return;

            const stationName = stations[code]?.name || code;
            const data = fourierDataList[i];

            // 周波数範囲でフィルタ
            const filteredIndices = data.frequency
                .map((f, idx) => ({ f, idx }))
                .filter(item => item.f >= freqRange[0] && item.f <= freqRange[1])
                .map(item => item.idx);

            traces.push({
                x: filteredIndices.map(idx => data.frequency[idx]),
                y: filteredIndices.map(idx => data[component][idx]),
                type: 'scatter',
                mode: 'lines',
                name: stationName,
                line: { width: 1.5 }
            });
        });

        const layout = {
            xaxis: {
                title: '周波数 (Hz)',
                type: 'log',
                range: [Math.log10(freqRange[0]), Math.log10(freqRange[1])]
            },
            yaxis: {
                title: 'フーリエ振幅 (gal·s)',
                type: 'log',
                range: [Math.log10(ampRange[0]), Math.log10(ampRange[1])]
            },
            showlegend: true,
            legend: { orientation: 'h', y: -0.15 },
            margin: { l: 70, r: 20, t: 40, b: 80 }
        };

        Plotly.newPlot('fourierPlot', traces, layout, { responsive: true });

    } catch (error) {
        console.error('Failed to update fourier plot:', error);
    } finally {
        showLoading(false);
    }
}

// 対数スケールスライダーを作成
function createLogSlider(elementId, minLog, maxLog, startMin, startMax, minLabelId, maxLabelId, onChange) {
    const sliderEl = document.getElementById(elementId);
    if (!sliderEl || typeof noUiSlider === 'undefined') return null;

    const slider = noUiSlider.create(sliderEl, {
        start: [
            valueToLogSlider(startMin, minLog, maxLog),
            valueToLogSlider(startMax, minLog, maxLog)
        ],
        connect: true,
        range: { 'min': 0, 'max': 100 },
        step: 1
    });

    slider.on('update', values => {
        const minVal = logSliderToValue(Number(values[0]), minLog, maxLog);
        const maxVal = logSliderToValue(Number(values[1]), minLog, maxLog);
        document.getElementById(minLabelId).textContent = formatLogValue(minVal);
        document.getElementById(maxLabelId).textContent = formatLogValue(maxVal);
    });

    slider.on('change', onChange);

    return slider;
}

// フーリエタブの初期化
function initFourier() {
    const select = document.getElementById('fourierStationSelect');

    const onSliderChange = () => {
        const selected = Array.from(select.selectedOptions);
        if (selected.length > 0) {
            updateFourierPlot();
        }
    };

    // 周波数スライダーの初期化（対数: 0.01 - 100 Hz）
    fourierFreqSlider = createLogSlider(
        'fourierFreqSlider', -2, 2, 0.1, 20,
        'fourierFreqMin', 'fourierFreqMax', onSliderChange
    );

    // 振幅スライダーの初期化（対数: 0.1 - 10000 gal·s）
    fourierAmpSlider = createLogSlider(
        'fourierAmpSlider', -1, 5, 0.1, 10000,
        'fourierAmpMin', 'fourierAmpMax', onSliderChange
    );

    // 選択変更時のカウント更新
    select.addEventListener('change', () => {
        updateStationCount('fourierStationSelect', 'fourierStationCount');
    });

    // プロットボタン
    document.getElementById('fourierPlotBtn').addEventListener('click', updateFourierPlot);

    // クリアボタン
    document.getElementById('fourierClearBtn').addEventListener('click', () => {
        Array.from(select.options).forEach(opt => opt.selected = false);
        updateStationCount('fourierStationSelect', 'fourierStationCount');
        Plotly.purge('fourierPlot');
    });

    // 成分変更時
    document.getElementById('fourierComponent').addEventListener('change', () => {
        const selected = Array.from(select.selectedOptions);
        if (selected.length > 0) {
            updateFourierPlot();
        }
    });
}
