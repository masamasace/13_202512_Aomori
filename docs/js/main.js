/**
 * main.js - メインロジック・タブ制御・データ管理
 */

// グローバル変数
let stations = {};
let dataCache = {};

// ローディング表示
function showLoading(show) {
    document.getElementById('loading').classList.toggle('show', show);
}

// 観測点データをロード
async function loadStations() {
    try {
        const response = await fetch('data/stations.json');
        stations = await response.json();
        console.log(`Loaded ${Object.keys(stations).length} stations`);
        return stations;
    } catch (error) {
        console.error('Failed to load stations:', error);
        return {};
    }
}

// 観測点リストを震度順にソート
function getSortedStationList() {
    const intensityOrder = {'7': 0, '6強': 1, '6弱': 2, '5強': 3, '5弱': 4, '4': 5, '3': 6, '2': 7, '1': 8};

    return Object.entries(stations)
        .map(([stationKey, data]) => ({
            ...data,
            code: stationKey,
            sortKey: intensityOrder[data.intensity] ?? 99
        }))
        .sort((a, b) => {
            if (a.sortKey !== b.sortKey) return a.sortKey - b.sortKey;
            return Math.abs(b.acc_total || 0) - Math.abs(a.acc_total || 0);
        });
}

// セレクトボックスにオプションを追加
function populateStationSelect(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;

    select.innerHTML = '';
    const sortedStations = getSortedStationList();

    sortedStations.forEach(station => {
        const option = document.createElement('option');
        option.value = station.code;
        const intensity = station.intensity || '-';
        option.textContent = `[${intensity}] ${station.name} (${station.code})`;
        select.appendChild(option);
    });
}

// CSVデータをロード（キャッシュ付き）
async function loadCSV(stationCode, filename) {
    const cacheKey = `${stationCode}/${filename}`;

    if (dataCache[cacheKey]) {
        return dataCache[cacheKey];
    }

    const url = `data/${stationCode}/${filename}`;

    return new Promise((resolve, reject) => {
        Papa.parse(url, {
            download: true,
            header: true,
            dynamicTyping: true,
            complete: function(results) {
                if (results.errors.length > 0) {
                    console.warn(`Parse warnings for ${cacheKey}:`, results.errors);
                }
                const data = results.data.filter(row => {
                    // 有効な行のみフィルタ
                    return Object.values(row).some(v => v !== null && v !== '');
                });
                dataCache[cacheKey] = data;
                resolve(data);
            },
            error: function(error) {
                console.error(`Failed to load ${cacheKey}:`, error);
                reject(error);
            }
        });
    });
}

// タブ切り替え
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            // ボタンのアクティブ状態を切り替え
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // パネルの表示を切り替え
            tabPanels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `tab-${targetTab}`) {
                    panel.classList.add('active');
                }
            });

            // タブ固有の初期化処理
            if (targetTab === 'map' && typeof initMap === 'function' && !window.mapInitialized) {
                initMap();
            }

            // Plotlyのリサイズ
            if (targetTab === 'waveform') {
                Plotly.Plots.resize('waveformPlot');
            } else if (targetTab === 'fourier') {
                Plotly.Plots.resize('fourierPlot');
            } else if (targetTab === 'response') {
                Plotly.Plots.resize('responsePlot');
            }
        });
    });
}

// 選択地点数の更新
function updateStationCount(selectId, countId) {
    const select = document.getElementById(selectId);
    const countEl = document.getElementById(countId);
    if (select && countEl) {
        const count = Array.from(select.selectedOptions).length;
        countEl.textContent = `選択地点: ${count}`;
    }
}

// アプリケーション初期化
async function initApp() {
    showLoading(true);

    try {
        // 観測点データをロード
        await loadStations();

        // 各タブのセレクトボックスを初期化
        populateStationSelect('waveformStationSelect');
        populateStationSelect('fourierStationSelect');
        populateStationSelect('responseStationSelect');

        // タブ切り替えを初期化
        initTabs();

        // 各モジュールの初期化
        if (typeof initMap === 'function') {
            initMap();
        }
        if (typeof initWaveform === 'function') {
            initWaveform();
        }
        if (typeof initFourier === 'function') {
            initFourier();
        }
        if (typeof initResponse === 'function') {
            initResponse();
        }

    } catch (error) {
        console.error('Initialization failed:', error);
    } finally {
        showLoading(false);
    }
}

// DOMContentLoaded時に初期化
document.addEventListener('DOMContentLoaded', initApp);

// ウィンドウリサイズ時の処理
window.addEventListener('resize', () => {
    // Plotlyグラフのリサイズ
    const activePanel = document.querySelector('.tab-panel.active');
    if (activePanel) {
        const plotEl = activePanel.querySelector('.plot-area');
        if (plotEl && plotEl.id) {
            Plotly.Plots.resize(plotEl.id);
        }
    }
});
