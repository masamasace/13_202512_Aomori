/**
 * signal.js - 信号処理モジュール（FFT、積分、スペクトル計算）
 */

// 処理済みデータのキャッシュ
const processedDataCache = {};

/**
 * FFT (Cooley-Tukey radix-2)
 * @param {number[]} real - 実部
 * @param {number[]} imag - 虚部
 * @param {boolean} inverse - 逆FFTの場合true
 */
function fft(real, imag, inverse = false) {
    const n = real.length;
    if (n <= 1) return;

    // ビット反転並べ替え
    let j = 0;
    for (let i = 0; i < n - 1; i++) {
        if (i < j) {
            [real[i], real[j]] = [real[j], real[i]];
            [imag[i], imag[j]] = [imag[j], imag[i]];
        }
        let k = n >> 1;
        while (k <= j) {
            j -= k;
            k >>= 1;
        }
        j += k;
    }

    // バタフライ演算
    const sign = inverse ? 1 : -1;
    for (let len = 2; len <= n; len <<= 1) {
        const halfLen = len >> 1;
        const angle = sign * 2 * Math.PI / len;
        const wReal = Math.cos(angle);
        const wImag = Math.sin(angle);

        for (let i = 0; i < n; i += len) {
            let curReal = 1, curImag = 0;
            for (let k = 0; k < halfLen; k++) {
                const evenIdx = i + k;
                const oddIdx = i + k + halfLen;

                const tReal = curReal * real[oddIdx] - curImag * imag[oddIdx];
                const tImag = curReal * imag[oddIdx] + curImag * real[oddIdx];

                real[oddIdx] = real[evenIdx] - tReal;
                imag[oddIdx] = imag[evenIdx] - tImag;
                real[evenIdx] += tReal;
                imag[evenIdx] += tImag;

                const newCurReal = curReal * wReal - curImag * wImag;
                curImag = curReal * wImag + curImag * wReal;
                curReal = newCurReal;
            }
        }
    }

    // 逆FFTの場合はNで割る
    if (inverse) {
        for (let i = 0; i < n; i++) {
            real[i] /= n;
            imag[i] /= n;
        }
    }
}

/**
 * 次の2のべき乗を取得
 */
function nextPowerOf2(n) {
    return Math.pow(2, Math.ceil(Math.log2(n)));
}

/**
 * 配列を2のべき乗サイズにゼロパディング
 */
function zeroPad(arr, targetLength) {
    const result = new Array(targetLength).fill(0);
    for (let i = 0; i < arr.length; i++) {
        result[i] = arr[i];
    }
    return result;
}

/**
 * ハイパスフィルタ（周波数領域）
 * @param {number[]} real - FFT結果の実部
 * @param {number[]} imag - FFT結果の虚部
 * @param {number} cutoffHz - カットオフ周波数
 * @param {number} df - 周波数分解能
 */
function applyHighpassFilter(real, imag, cutoffHz, df) {
    const n = real.length;
    const cutoffBin = Math.floor(cutoffHz / df);

    for (let i = 0; i < n; i++) {
        const bin = i <= n / 2 ? i : n - i;
        if (bin < cutoffBin) {
            // コサインテーパーで滑らかに減衰
            const ratio = bin / cutoffBin;
            const taper = 0.5 * (1 - Math.cos(Math.PI * ratio));
            real[i] *= taper;
            imag[i] *= taper;
        }
    }
}

/**
 * 加速度から速度への積分（FFT使用）
 * @param {number[]} acc - 加速度データ (gal)
 * @param {number} dt - サンプリング間隔 (s)
 * @param {number} highpassHz - ハイパスフィルタカットオフ (Hz)
 * @returns {number[]} 速度データ (cm/s)
 */
function integrateToVelocity(acc, dt, highpassHz = 0.1) {
    const n = acc.length;
    const nfft = nextPowerOf2(n * 2); // 2倍パディング

    // ゼロパディング
    const real = zeroPad(acc, nfft);
    const imag = new Array(nfft).fill(0);

    // FFT
    fft(real, imag, false);

    // 周波数領域で積分（1/(i*omega)を掛ける）
    const df = 1 / (nfft * dt);
    for (let i = 0; i < nfft; i++) {
        if (i === 0) {
            real[i] = 0;
            imag[i] = 0;
        } else {
            const freq = i <= nfft / 2 ? i * df : (i - nfft) * df;
            const omega = 2 * Math.PI * freq;
            // 1/(i*omega) = -i/omega
            const factor = 1 / omega;
            const newReal = imag[i] * factor;
            const newImag = -real[i] * factor;
            real[i] = newReal;
            imag[i] = newImag;
        }
    }

    // ハイパスフィルタ適用
    applyHighpassFilter(real, imag, highpassHz, df);

    // 逆FFT
    fft(real, imag, true);

    // 元のデータ長に切り詰め
    return real.slice(0, n);
}

/**
 * 速度から変位への積分（FFT使用）
 */
function integrateToDisplacement(vel, dt, highpassHz = 0.1) {
    return integrateToVelocity(vel, dt, highpassHz);
}

/**
 * 加速度データを処理して速度・変位を計算
 * @param {Object} accData - {time, NS, EW, UD}
 * @param {number} dt - サンプリング間隔
 * @returns {Object} {acceleration, velocity, displacement}
 */
function processAccelerationData(accData, dt) {
    const result = {
        acceleration: {
            time: accData.time,
            NS: accData.NS,
            EW: accData.EW,
            UD: accData.UD
        },
        velocity: {
            time: accData.time,
            NS: integrateToVelocity(accData.NS, dt),
            EW: integrateToVelocity(accData.EW, dt),
            UD: integrateToVelocity(accData.UD, dt)
        },
        displacement: {
            time: accData.time,
            NS: null,
            EW: null,
            UD: null
        }
    };

    // 速度から変位を計算
    result.displacement.NS = integrateToDisplacement(result.velocity.NS, dt);
    result.displacement.EW = integrateToDisplacement(result.velocity.EW, dt);
    result.displacement.UD = integrateToDisplacement(result.velocity.UD, dt);

    return result;
}

/**
 * フーリエスペクトルを計算
 * @param {number[]} signal - 時系列データ
 * @param {number} dt - サンプリング間隔
 * @returns {Object} {frequency, amplitude}
 */
function computeFourierSpectrum(signal, dt) {
    const n = signal.length;
    const nfft = nextPowerOf2(n);

    // ゼロパディング
    const real = zeroPad(signal, nfft);
    const imag = new Array(nfft).fill(0);

    // FFT
    fft(real, imag, false);

    // 周波数と振幅を計算（片側スペクトル）
    const df = 1 / (nfft * dt);
    const numFreqs = Math.floor(nfft / 2) + 1;
    const frequency = [];
    const amplitude = [];

    for (let i = 0; i < numFreqs; i++) {
        frequency.push(i * df);
        // 振幅スペクトル（両側→片側の補正係数2、ただしDC成分とナイキスト周波数は1）
        const scale = (i === 0 || i === nfft / 2) ? 1 : 2;
        const amp = Math.sqrt(real[i] * real[i] + imag[i] * imag[i]) / nfft * scale * dt;
        amplitude.push(amp);
    }

    return { frequency, amplitude };
}

/**
 * 3成分のフーリエスペクトルを計算
 */
function computeFourierSpectrumAll(accData, dt) {
    const nsSpec = computeFourierSpectrum(accData.NS, dt);
    const ewSpec = computeFourierSpectrum(accData.EW, dt);
    const udSpec = computeFourierSpectrum(accData.UD, dt);

    return {
        frequency: nsSpec.frequency,
        NS: nsSpec.amplitude,
        EW: ewSpec.amplitude,
        UD: udSpec.amplitude
    };
}

/**
 * 単自由度系の応答を計算（Newmark-β法）
 * @param {number[]} acc - 入力加速度 (gal)
 * @param {number} dt - サンプリング間隔 (s)
 * @param {number} T - 固有周期 (s)
 * @param {number} h - 減衰定数
 * @returns {number} 最大応答加速度 (gal)
 */
function computeSDOFResponse(acc, dt, T, h) {
    if (T === 0) {
        return Math.max(...acc.map(Math.abs));
    }

    const omega = 2 * Math.PI / T;
    const omega2 = omega * omega;
    const n = acc.length;

    // Newmark-β法のパラメータ（平均加速度法）
    const beta = 0.25;
    const gamma = 0.5;

    // 係数計算
    const c1 = 1 / (beta * dt * dt);
    const c2 = gamma / (beta * dt);
    const c3 = 1 / (beta * dt);
    const c4 = 1 / (2 * beta) - 1;
    const c5 = dt * (gamma / (2 * beta) - 1);
    const c6 = gamma / beta - 1;

    const keff = omega2 + c1 + 2 * h * omega * c2;

    let u = 0;      // 変位
    let v = 0;      // 速度
    let a = -acc[0]; // 加速度（相対）

    let maxAbsAcc = Math.abs(acc[0]);

    for (let i = 1; i < n; i++) {
        const peff = -acc[i] + c1 * u + c3 * v + c4 * a + 2 * h * omega * (c2 * u + c6 * v + c5 * a);

        const uNew = peff / keff;
        const vNew = c2 * (uNew - u) - c6 * v - c5 * a;
        const aNew = c1 * (uNew - u) - c3 * v - c4 * a;

        u = uNew;
        v = vNew;
        a = aNew;

        // 絶対加速度 = 相対加速度 + 入力加速度
        const absAcc = Math.abs(a + acc[i]);
        if (absAcc > maxAbsAcc) {
            maxAbsAcc = absAcc;
        }
    }

    return maxAbsAcc;
}

/**
 * 応答スペクトルを計算
 * @param {number[]} acc - 加速度データ (gal)
 * @param {number} dt - サンプリング間隔 (s)
 * @param {number[]} periods - 周期配列 (s)
 * @param {number[]} dampingRatios - 減衰定数配列
 * @returns {Object} {period, responses: {h005: [], h010: [], h020: []}}
 */
function computeResponseSpectrum(acc, dt, periods, dampingRatios = [0.05, 0.10, 0.20]) {
    const responses = {};
    const dampingKeys = ['h005', 'h010', 'h020'];

    dampingRatios.forEach((h, idx) => {
        responses[dampingKeys[idx]] = periods.map(T => computeSDOFResponse(acc, dt, T, h));
    });

    return {
        period: periods,
        responses
    };
}

/**
 * 3成分の応答スペクトルを計算
 */
function computeResponseSpectrumAll(accData, dt) {
    // 対数等間隔の周期配列を生成
    const periods = [];
    const logMin = Math.log10(0.02);
    const logMax = Math.log10(10);
    const numPoints = 100;

    for (let i = 0; i < numPoints; i++) {
        const logT = logMin + (logMax - logMin) * i / (numPoints - 1);
        periods.push(Math.pow(10, logT));
    }

    return {
        period: periods,
        NS: {
            h005: periods.map(T => computeSDOFResponse(accData.NS, dt, T, 0.05)),
            h010: periods.map(T => computeSDOFResponse(accData.NS, dt, T, 0.10)),
            h020: periods.map(T => computeSDOFResponse(accData.NS, dt, T, 0.20))
        },
        EW: {
            h005: periods.map(T => computeSDOFResponse(accData.EW, dt, T, 0.05)),
            h010: periods.map(T => computeSDOFResponse(accData.EW, dt, T, 0.10)),
            h020: periods.map(T => computeSDOFResponse(accData.EW, dt, T, 0.20))
        },
        UD: {
            h005: periods.map(T => computeSDOFResponse(accData.UD, dt, T, 0.05)),
            h010: periods.map(T => computeSDOFResponse(accData.UD, dt, T, 0.10)),
            h020: periods.map(T => computeSDOFResponse(accData.UD, dt, T, 0.20))
        }
    };
}

/**
 * 加速度データをロードして全ての処理済みデータを取得（キャッシュ付き）
 * @param {string} stationCode - 観測点コード
 * @returns {Object} {waveforms, fourier, response}
 */
async function getProcessedData(stationCode) {
    // キャッシュ確認
    if (processedDataCache[stationCode]) {
        return processedDataCache[stationCode];
    }

    // 加速度データをロード
    const rawData = await loadCSV(stationCode, 'waveform.csv');
    if (!rawData || rawData.length === 0) {
        return null;
    }

    // サンプリング間隔を計算
    const t0 = new Date(rawData[0].datetime).getTime();
    const t1 = new Date(rawData[1].datetime).getTime();
    const dt = (t1 - t0) / 1000; // 秒

    // 時刻配列を作成
    const startTime = t0;
    const accData = {
        time: rawData.map(row => (new Date(row.datetime).getTime() - startTime) / 1000),
        NS: rawData.map(row => row.NS),
        EW: rawData.map(row => row.EW),
        UD: rawData.map(row => row.UD)
    };

    // 波形データを処理（加速度→速度→変位）
    const waveforms = processAccelerationData(accData, dt);

    // フーリエスペクトルを計算
    const fourier = computeFourierSpectrumAll(accData, dt);

    // 応答スペクトルを計算
    const response = computeResponseSpectrumAll(accData, dt);

    // キャッシュに保存
    const result = { waveforms, fourier, response, dt };
    processedDataCache[stationCode] = result;

    return result;
}

/**
 * キャッシュをクリア
 */
function clearProcessedDataCache() {
    Object.keys(processedDataCache).forEach(key => delete processedDataCache[key]);
}
