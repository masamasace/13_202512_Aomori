/**
 * waveform.js - 波形比較機能（FFTによる速度・変位計算）
 */

const waveformUnits = {
    'acceleration': 'gal',
    'velocity': 'cm/s',
    'displacement': 'cm'
};

const waveformNames = {
    'acceleration': '加速度',
    'velocity': '速度',
    'displacement': '変位'
};

// 波形データをロード（signal.jsのgetProcessedDataを使用）
async function loadWaveformData(stationCode, waveformType) {
    const processed = await getProcessedData(stationCode);
    if (!processed) {
        return null;
    }

    return processed.waveforms[waveformType];
}

// 波形プロットを更新
async function updateWaveformPlot() {
    const select = document.getElementById('waveformStationSelect');
    const selectedStations = Array.from(select.selectedOptions).map(opt => opt.value);
    const waveformType = document.getElementById('waveformType').value;
    const displayMode = document.getElementById('waveformDisplayMode').value;
    const componentSelect = document.getElementById('waveformComponent').value;

    if (selectedStations.length === 0) {
        Plotly.purge('waveformPlot');
        document.getElementById('waveformDataInfo').textContent = 'データポイント: -';
        return;
    }

    showLoading(true);
    console.log('displayMode:', displayMode, '| selectedStations:', selectedStations.length);

    try {
        // データを並列ロード
        const loadPromises = selectedStations.map(code => loadWaveformData(code, waveformType));
        const waveformDataList = await Promise.all(loadPromises);

        // 表示成分
        const components = componentSelect === 'all' ? ['NS', 'EW', 'UD'] : [componentSelect];
        const componentColors = { 'NS': '#e41a1c', 'EW': '#377eb8', 'UD': '#4daf4a' };

        const traces = [];
        const unit = waveformUnits[waveformType];
        let totalPoints = 0;

        if (displayMode === 'subplot') {
            // サブプロット表示
            const validStations = [];
            selectedStations.forEach((code, i) => {
                if (waveformDataList[i]) {
                    validStations.push({ code, data: waveformDataList[i] });
                }
            });
            console.log('Subplot mode: validStations =', validStations.length);

            validStations.forEach((station, stationIdx) => {
                components.forEach((comp, compIdx) => {
                    const yaxis = stationIdx === 0 ? 'y' : `y${stationIdx + 1}`;
                    traces.push({
                        x: station.data.time,
                        y: station.data[comp],
                        type: 'scatter',
                        mode: 'lines',
                        name: `${stations[station.code]?.name || station.code} (${comp})`,
                        line: { color: componentColors[comp], width: 1 },
                        yaxis: yaxis
                    });
                    totalPoints += station.data.time.length;
                });
            });

            // レイアウト（サブプロット）
            const numStations = validStations.length;
            const height = Math.max(0.8 / numStations, 0.1);
            const gap = 0.02;

            const layout = {
                title: `${waveformNames[waveformType]}波形比較`,
                showlegend: true,
                legend: { orientation: 'h', y: -0.1 },
                xaxis: { title: '時間 (s)' },
                margin: { l: 60, r: 20, t: 40, b: 60 }
            };

            validStations.forEach((station, i) => {
                const domain = [1 - (i + 1) * (height + gap), 1 - i * (height + gap) - gap];
                if (i === 0) {
                    layout.yaxis = {
                        title: `${unit}`,
                        domain: domain
                    };
                } else {
                    layout[`yaxis${i + 1}`] = {
                        title: `${unit}`,
                        domain: domain,
                        anchor: 'x'
                    };
                }
            });

            Plotly.newPlot('waveformPlot', traces, layout, { responsive: true });

        } else {
            // 重ね合わせ表示
            selectedStations.forEach((code, i) => {
                if (!waveformDataList[i]) return;

                const stationName = stations[code]?.name || code;
                components.forEach(comp => {
                    traces.push({
                        x: waveformDataList[i].time,
                        y: waveformDataList[i][comp],
                        type: 'scatter',
                        mode: 'lines',
                        name: `${stationName} (${comp})`,
                        line: { width: 1 }
                    });
                    totalPoints += waveformDataList[i].time.length;
                });
            });

            const layout = {
                title: `${waveformNames[waveformType]}波形比較`,
                xaxis: { title: '時間 (s)' },
                yaxis: { title: `${waveformNames[waveformType]} (${unit})` },
                showlegend: true,
                legend: { orientation: 'h', y: -0.15 },
                margin: { l: 60, r: 20, t: 40, b: 80 }
            };

            Plotly.newPlot('waveformPlot', traces, layout, { responsive: true });
        }

        document.getElementById('waveformDataInfo').textContent = `データポイント: ${totalPoints.toLocaleString()}`;

    } catch (error) {
        console.error('Failed to update waveform plot:', error);
    } finally {
        showLoading(false);
    }
}

// 波形タブの初期化
function initWaveform() {
    const select = document.getElementById('waveformStationSelect');

    // 選択変更時のカウント更新
    select.addEventListener('change', () => {
        updateStationCount('waveformStationSelect', 'waveformStationCount');
    });

    // プロットボタン
    document.getElementById('waveformPlotBtn').addEventListener('click', updateWaveformPlot);

    // クリアボタン
    document.getElementById('waveformClearBtn').addEventListener('click', () => {
        Array.from(select.options).forEach(opt => opt.selected = false);
        updateStationCount('waveformStationSelect', 'waveformStationCount');
        Plotly.purge('waveformPlot');
        document.getElementById('waveformDataInfo').textContent = 'データポイント: -';
    });

    // 波形種別・成分・表示モード変更時
    ['waveformType', 'waveformComponent', 'waveformDisplayMode'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            const selected = Array.from(select.selectedOptions);
            if (selected.length > 0) {
                updateWaveformPlot();
            }
        });
    });
}
