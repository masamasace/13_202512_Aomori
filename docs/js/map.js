/**
 * map.js - Leaflet地図機能
 */

let map = null;
let markers = [];
window.mapInitialized = false;

// 震度に対応する色（1が白、6弱以上が赤）
const intensityColors = {
    '7': '#a50026',
    '6強': '#d73027',
    '6弱': '#f46d43',
    '5強': '#fdae61',
    '5弱': '#fee08b',
    '4': '#ffffbf',
    '3': '#e0e0e0',
    '2': '#f0f0f0',
    '1': '#ffffff',
    '-': '#999999'
};

// 加速度の閾値と色（白→赤、gal単位）
const accThresholds = [20, 40, 60, 80, 100, 150, 200, 250, 300, 400, 500, 600];
const accMinDisplay = 20;  // 表示最小値

// 速度の閾値と色（白→赤、cm/s単位、加速度の1/5）
const velThresholds = [4, 8, 12, 16, 20, 30, 40, 50, 60, 80, 100, 120];
const velMinDisplay = 2;   // 表示最小値

// 閾値に基づいて白→赤の色を取得
function getThresholdColor(value, thresholds) {
    if (value === null || value === undefined || isNaN(value)) {
        return null;
    }

    const absValue = Math.abs(value);

    // 閾値のどの位置にあるか計算
    let ratio = 0;
    for (let i = 0; i < thresholds.length; i++) {
        if (absValue < thresholds[i]) {
            if (i === 0) {
                ratio = absValue / thresholds[0];
            } else {
                const prevThresh = thresholds[i - 1];
                const currThresh = thresholds[i];
                ratio = (i + (absValue - prevThresh) / (currThresh - prevThresh)) / thresholds.length;
            }
            break;
        }
        if (i === thresholds.length - 1) {
            ratio = 1;
        }
    }

    // 白(255,255,255)から赤(165,0,38)へのグラデーション
    const r = Math.round(255 - ratio * (255 - 165));
    const g = Math.round(255 - ratio * 255);
    const b = Math.round(255 - ratio * (255 - 38));

    return `rgb(${r},${g},${b})`;
}

// マーカーを作成（表示条件を満たさない場合はnullを返す）
function createMarker(station, colorColumn) {
    let color;
    const value = station[colorColumn];

    if (colorColumn === 'intensity') {
        color = intensityColors[station.intensity] || intensityColors['-'];
    } else if (colorColumn === 'acc_H' || colorColumn === 'acc_total') {
        // 加速度：20gal以上のみ表示
        const absValue = Math.abs(value || 0);
        if (absValue < accMinDisplay) {
            return null;  // 表示しない
        }
        color = getThresholdColor(value, accThresholds);
    } else if (colorColumn === 'vel_H' || colorColumn === 'vel_total') {
        // 速度：2cm/s以上のみ表示
        const absValue = Math.abs(value || 0);
        if (absValue < velMinDisplay) {
            return null;  // 表示しない
        }
        color = getThresholdColor(value, velThresholds);
    } else {
        color = '#999999';
    }

    if (!color) {
        return null;
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
                <div class="legend-color" style="background:${intensityColors[level]}; border: 1px solid #ccc;"></div>
                <span>${level}</span>
            </div>`;
        });
    } else if (colorColumn === 'acc_H' || colorColumn === 'acc_total') {
        const labels = {
            'acc_H': '水平加速度 (gal)',
            'acc_total': '合成加速度 (gal)'
        };
        html += (labels[colorColumn] || colorColumn) + '</div>';

        // 加速度の凡例（主要な閾値を表示）
        const legendThresholds = [20, 40, 60, 100, 150, 200, 300, 400, 600];
        legendThresholds.forEach(level => {
            html += `<div class="legend-item">
                <div class="legend-color" style="background:${getThresholdColor(level, accThresholds)}; border: 1px solid #ccc;"></div>
                <span>${level}</span>
            </div>`;
        });
    } else if (colorColumn === 'vel_H' || colorColumn === 'vel_total') {
        const labels = {
            'vel_H': '水平速度 (cm/s)',
            'vel_total': '合成速度 (cm/s)'
        };
        html += (labels[colorColumn] || colorColumn) + '</div>';

        // 速度の凡例（主要な閾値を表示）
        const legendThresholds = [4, 8, 12, 20, 30, 40, 60, 80, 120];
        legendThresholds.forEach(level => {
            html += `<div class="legend-item">
                <div class="legend-color" style="background:${getThresholdColor(level, velThresholds)}; border: 1px solid #ccc;"></div>
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

    // マーカーを追加（閾値以上の観測点のみ）
    let displayCount = 0;
    Object.entries(stations).forEach(([code, station]) => {
        station.code = code;
        const marker = createMarker(station, colorColumn);
        if (marker) {
            marker.addTo(map);
            markers.push(marker);
            displayCount++;
        }
    });

    console.log(`Displaying ${displayCount} / ${Object.keys(stations).length} stations for ${colorColumn}`);

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
