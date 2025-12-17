/**
 * map.js - Leaflet地図機能
 */

let map = null;
let markers = [];
window.mapInitialized = false;

// 震度に対応する色
const intensityColors = {
    '7': '#a50026',
    '6強': '#d73027',
    '6弱': '#f46d43',
    '5強': '#fdae61',
    '5弱': '#fee08b',
    '4': '#d9ef8b',
    '3': '#a6d96a',
    '2': '#66bd63',
    '1': '#1a9850',
    '-': '#999999'
};

// 数値カラースケール（加速度・速度用）
function getValueColor(value, minVal, maxVal) {
    if (value === null || value === undefined || isNaN(value)) {
        return '#999999';
    }

    // 対数スケールで正規化
    const logMin = Math.log10(Math.max(minVal, 0.1));
    const logMax = Math.log10(Math.max(maxVal, 1));
    const logVal = Math.log10(Math.max(Math.abs(value), 0.1));
    const ratio = Math.max(0, Math.min(1, (logVal - logMin) / (logMax - logMin)));

    // カラースケール（青→緑→黄→赤）
    const colors = [
        [26, 152, 80],   // 緑
        [166, 217, 106], // 黄緑
        [254, 224, 139], // 黄
        [253, 174, 97],  // オレンジ
        [244, 109, 67],  // 赤オレンジ
        [215, 48, 39],   // 赤
        [165, 0, 38]     // 暗赤
    ];

    const idx = ratio * (colors.length - 1);
    const i = Math.floor(idx);
    const t = idx - i;

    if (i >= colors.length - 1) {
        return `rgb(${colors[colors.length - 1].join(',')})`;
    }

    const r = Math.round(colors[i][0] + t * (colors[i + 1][0] - colors[i][0]));
    const g = Math.round(colors[i][1] + t * (colors[i + 1][1] - colors[i][1]));
    const b = Math.round(colors[i][2] + t * (colors[i + 1][2] - colors[i][2]));

    return `rgb(${r},${g},${b})`;
}

// マーカーを作成
function createMarker(station, colorColumn, minVal, maxVal) {
    let color;
    if (colorColumn === 'intensity') {
        color = intensityColors[station.intensity] || intensityColors['-'];
    } else {
        const value = Math.abs(station[colorColumn] || 0);
        color = getValueColor(value, minVal, maxVal);
    }

    const marker = L.circleMarker([station.lat, station.lon], {
        radius: 8,
        fillColor: color,
        color: '#333',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.9
    });

    // ポップアップ内容
    const popupContent = `
        <div class="popup-content">
            <h3>${station.name}</h3>
            <table>
                <tr><td>観測点</td><td>${station.code}</td></tr>
                <tr><td>震度</td><td>${station.intensity || '-'}</td></tr>
                <tr><td>水平加速度</td><td>${station.acc_H?.toFixed(1) || '-'} gal</td></tr>
                <tr><td>合成加速度</td><td>${station.acc_total?.toFixed(1) || '-'} gal</td></tr>
                <tr><td>水平速度</td><td>${station.vel_H?.toFixed(2) || '-'} cm/s</td></tr>
                <tr><td>合成速度</td><td>${station.vel_total?.toFixed(2) || '-'} cm/s</td></tr>
            </table>
        </div>
    `;
    marker.bindPopup(popupContent);

    return marker;
}

// 凡例を更新
function updateLegend(colorColumn) {
    const legendEl = document.getElementById('mapLegend');
    if (!legendEl) return;

    let html = '<div class="legend-title">';

    if (colorColumn === 'intensity') {
        html += '震度</div>';
        const intensityLevels = ['7', '6強', '6弱', '5強', '5弱', '4', '3', '2', '1'];
        intensityLevels.forEach(level => {
            html += `<div class="legend-item">
                <div class="legend-color" style="background:${intensityColors[level]}"></div>
                <span>${level}</span>
            </div>`;
        });
    } else {
        const labels = {
            'acc_H': '水平加速度 (gal)',
            'acc_total': '合成加速度 (gal)',
            'vel_H': '水平速度 (cm/s)',
            'vel_total': '合成速度 (cm/s)'
        };
        html += (labels[colorColumn] || colorColumn) + '</div>';

        // 凡例の値レベル
        const values = Object.values(stations).map(s => Math.abs(s[colorColumn] || 0)).filter(v => v > 0);
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);

        // 対数スケールでの凡例
        const levels = [1, 5, 10, 50, 100, 500, 1000].filter(v => v >= minVal * 0.5 && v <= maxVal * 2);
        levels.forEach(level => {
            html += `<div class="legend-item">
                <div class="legend-color" style="background:${getValueColor(level, minVal, maxVal)}"></div>
                <span>${level}</span>
            </div>`;
        });
    }

    legendEl.innerHTML = html;
}

// マーカーを更新
function updateMarkers() {
    const colorColumn = document.getElementById('mapColorColumn').value;

    // 既存マーカーを削除
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    // min/max値を計算（数値カラムの場合）
    let minVal = 0, maxVal = 100;
    if (colorColumn !== 'intensity') {
        const values = Object.values(stations).map(s => Math.abs(s[colorColumn] || 0)).filter(v => v > 0);
        minVal = Math.min(...values);
        maxVal = Math.max(...values);
    }

    // マーカーを追加
    Object.entries(stations).forEach(([code, station]) => {
        station.code = code;
        const marker = createMarker(station, colorColumn, minVal, maxVal);
        marker.addTo(map);
        markers.push(marker);
    });

    // 凡例を更新
    updateLegend(colorColumn);
}

// 地図を初期化
function initMap() {
    if (window.mapInitialized) return;

    // 地図を作成
    map = L.map('map').setView([40.5, 140.5], 7);

    // タイルレイヤーを追加
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // マーカーを追加
    updateMarkers();

    // イベントリスナー
    document.getElementById('mapColorColumn').addEventListener('change', updateMarkers);

    window.mapInitialized = true;
}
