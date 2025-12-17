/**
 * fourier.js - フーリエスペクトル機能（FFTで計算）
 */

let fourierFreqSlider = null;

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

    // 周波数範囲を取得
    const freqRange = fourierFreqSlider ? fourierFreqSlider.get().map(Number) : [0.1, 50];

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
            title: `フーリエスペクトル比較 (${component}成分)`,
            xaxis: {
                title: '周波数 (Hz)',
                type: 'log',
                range: [Math.log10(freqRange[0]), Math.log10(freqRange[1])]
            },
            yaxis: {
                title: 'フーリエ振幅 (gal・s)',
                type: 'log'
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

// フーリエタブの初期化
function initFourier() {
    const select = document.getElementById('fourierStationSelect');

    // 周波数スライダーの初期化
    const sliderEl = document.getElementById('fourierFreqSlider');
    if (sliderEl && typeof noUiSlider !== 'undefined') {
        fourierFreqSlider = noUiSlider.create(sliderEl, {
            start: [0.1, 50],
            connect: true,
            range: {
                'min': 0.01,
                'max': 100
            },
            step: 0.01,
            format: {
                to: value => value.toFixed(2),
                from: value => parseFloat(value)
            }
        });

        fourierFreqSlider.on('update', values => {
            document.getElementById('fourierFreqMin').textContent = values[0];
            document.getElementById('fourierFreqMax').textContent = values[1];
        });

        fourierFreqSlider.on('change', () => {
            const selected = Array.from(select.selectedOptions);
            if (selected.length > 0) {
                updateFourierPlot();
            }
        });
    }

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
