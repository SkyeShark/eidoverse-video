// human_visemes.js — THE TALK'S VISEMES SMOOTHED (H4b face builder, 11-02), for the human's face driver: a viseme track
// as voicebox writes it ({fps, frames: [{aa, ih, ou, ee, oh}]}, one viseme per frame, mostly at 1, its consonants as
// 0.07-0.25 dips) is a STEP function, and fed raw to the face (the H4 films: x0.68 with no attack or release) the jaw
// opened 8-12 deg in one frame and shut in the next (the H4 check: frames 208-211, 218-220, 226-227). Real lips move
// smoothly and ahead of the sound:
//   * ANTICIPATION: the target at time t is the track's frame at t + LEAD (the articulators lead the acoustic onset; the
//     house's own claudesona_face.js makeVisemeTrack leads by 50 ms);
//   * ATTACK and RELEASE: each channel through a critically damped two-stage filter (two first-order lags in cascade, no
//     overshoot, no kink at the onset), its time constant the attack's while the input is above the state and the
//     release's below; ATTACK / RELEASE are the 10 -> 90 % times of a step (3.36 tau). Measured on a public-domain talking
//     head (h4b/face/probes/s01_speech.py + s02_series_look.py, the woman's address: 28 lip gestures in 12 s, the outer lip
//     height's 10 -> 90 % rise p50 81 ms (p25 54, p75 141), fall p50 79 ms (p25 29, p75 190));
//   * COARTICULATION falls out of it: neighbours overlap where one fades while the next rises, and a short consonant dip
//     closes the mouth only part way, as in the video;
//   * the channels' sum is capped at 1 so two overlapping visemes never open the jaw past either alone.
// Time-based (the track is simulated once at SIM_HZ and read by linear interpolation), so it holds at any frame rate.
//
//   const S = smoothVisemes(track, { gain: 0.68 });     // once
//   const w = S.at(tLine);                                // per frame: {aa, ih, ou, ee, oh}, tLine = t - the line's start
export const VISEMES = ['aa', 'ih', 'ou', 'ee', 'oh'];

export function smoothVisemes(track, { lead = 0.05, attack = 0.075, release = 0.095, gain = 0.68, simHz = 240 } = {}) {
    const fps = track.fps || 30;
    const frames = track.frames || [];
    const dur = frames.length / fps + 0.6;
    const n = Math.ceil(dur * simHz) + 1;
    const dt = 1.0 / simHz;
    const tauA = attack / 3.36, tauR = release / 3.36;
    const out = {};
    for (const k of VISEMES) out[k] = new Float32Array(n);
    const target = (k, t) => {
        const f = Math.floor((t + lead) * fps);
        return f >= 0 && f < frames.length ? (frames[f][k] || 0) : 0;
    };
    for (const k of VISEMES) {
        let s1 = 0, s2 = 0;
        const o = out[k];
        for (let i = 0; i < n; i++) {
            const x = target(k, i * dt);
            const a1 = 1.0 - Math.exp(-dt / (x > s1 ? tauA : tauR));
            s1 += (x - s1) * a1;
            const a2 = 1.0 - Math.exp(-dt / (s1 > s2 ? tauA : tauR));
            s2 += (s1 - s2) * a2;
            o[i] = s2;
        }
    }
    // the sum capped at 1
    for (let i = 0; i < n; i++) {
        let s = 0;
        for (const k of VISEMES) s += out[k][i];
        if (s > 1.0) for (const k of VISEMES) out[k][i] /= s;
    }
    return {
        duration: dur,
        at(t) {
            const w = {};
            const x = t * simHz;
            const i0 = Math.floor(x);
            for (const k of VISEMES) {
                if (i0 < 0 || i0 >= n - 1) { w[k] = 0; continue; }
                const f = x - i0;
                w[k] = gain * (out[k][i0] * (1 - f) + out[k][i0 + 1] * f);
            }
            return w;
        },
    };
}
