// N8AO 2.0's neural denoise (n8ao@2.0.1: src/NeuralDenoise.js and the NEURAL_DENOISE block of
// src/PoissionBlur.js), ported from its GLSL generator to TSL for N8AONode. The model file is
// upstream's, verbatim. The layout checks, the folded feature normalisation, the layer order and
// the online-softmax attention follow upstream; upstream unrolls each layer row into a GLSL sum,
// here a row is the same int8 weights summed as vec4 dot products, times the tensor scale, plus
// the same bias.
import { abs, cross, dot, exp, float, inverseSqrt, log, max, vec3, vec4, } from "npm:three@0.184.0/tsl";
import model from "./NeuralDenoiseModel.json" with { type: "json" };
const MATRIX_LAYOUTS = [
    ['tapInputWeight', 'tapInputWeights', 8, 9],
    ['tapOutputWeight', 'tapOutputWeights', 8, 8],
    ['globalWeight', 'globalWeights', 8, 3],
    ['keyWeight', 'keyProjectionWeights', 8, 8],
    ['valueWeight', 'valueProjectionWeights', 8, 8],
    ['headWeight', 'headWeights', 8, 32],
    ['outputWeight', 'outputWeights', 1, 8]
];
const scale = (name) => {
    const value = model.quantization?.scales?.[name];
    if (!(value > 0) || !Number.isFinite(value)) {
        throw new Error(`The bundled N8AO neural model has no valid ${name} scale.`);
    }
    return value;
};
if (model.architecture !== 'attention-v3-int8'
    || model.formatVersion !== 3
    || model.quantization?.scheme !== 'symmetric-int8-per-tensor'
    || model.quantization?.zeroPoint !== 0
    || model.supportedDenoiseSamples?.join(',') !== '4,8,16'
    || MATRIX_LAYOUTS.some(([, field, rows, columns]) => (model[field]?.length !== rows * columns
        || model[field].some((value) => !Number.isInteger(value) || value < -127 || value > 127)))) {
    throw new Error('The bundled N8AO neural denoise model has an unsupported layout.');
}
const COMPONENTS = ['x', 'y', 'z', 'w'];
// One output row: tensorScale * (sum of weight * input) + bias. The inputs come as vec4 / vec3
// chunks in column order; columns past the chunks are folded into the bias (the tap input's
// constant feature).
const quantizedRow = (weights, row, width, chunks, tensorScale, bias) => {
    let sum = null;
    let column = 0;
    for (const chunk of chunks) {
        const w = weights.slice(row * width + column, row * width + column + chunk.length);
        column += chunk.length;
        if (w.every((value) => value === 0)) {
            continue;
        }
        const term = dot(chunk.length === 4 ? vec4(...w) : vec3(...w), chunk.node);
        sum = sum === null ? term : sum.add(term);
    }
    return float(tensorScale).mul(sum ?? float(0)).add(bias[row]);
};
const chunksOf = (token) => [{ node: token.lo, length: 4 }, { node: token.hi, length: 4 }];
const toToken = (rows, relu) => {
    const lo = vec4(rows[0], rows[1], rows[2], rows[3]);
    const hi = vec4(rows[4], rows[5], rows[6], rows[7]);
    return relu ? { lo: max(lo, vec4(0)), hi: max(hi, vec4(0)) } : { lo, hi };
};
const tokenLayer = (scaleName, weights, bias, relu) => {
    const tensorScale = scale(scaleName);
    return (input) => toToken(Array.from({ length: 8 }, (_, row) => quantizedRow(weights, row, 8, chunksOf(input), tensorScale, bias)), relu);
};
const foldedBias = (weights, bias, means, inverseStandardDeviations, rows, width, tensorScale, constantInputs = {}) => Array.from({ length: rows }, (_, row) => {
    let value = bias[row];
    for (let column = 0; column < width; column++) {
        const weight = weights[row * width + column] * tensorScale;
        value -= weight * inverseStandardDeviations[column] * means[column];
        if (Object.hasOwn(constantInputs, column)) {
            value += weight * inverseStandardDeviations[column] * constantInputs[column];
        }
    }
    return value;
});
const tapInputScale = scale('tapInputWeight');
const tapInputBias = foldedBias(model.tapInputWeights, model.tapInputBias, model.tapFeatureMean, model.tapFeatureInverseStandardDeviation, 8, 9, tapInputScale, { 8: 1 });
export function neuralTapInput(raw) {
    const scaledInput = {
        lo: raw.lo.mul(vec4(...model.tapFeatureInverseStandardDeviation.slice(0, 4))),
        hi: raw.hi.mul(vec4(...model.tapFeatureInverseStandardDeviation.slice(4, 8))),
    };
    return toToken(Array.from({ length: 8 }, (_, row) => quantizedRow(model.tapInputWeights, row, 9, chunksOf(scaledInput), tapInputScale, tapInputBias)), true);
}
export const neuralTapOutput = tokenLayer('tapOutputWeight', model.tapOutputWeights, model.tapOutputBias, true);
export const neuralKeyProject = tokenLayer('keyWeight', model.keyProjectionWeights, new Array(8).fill(0), false);
export const neuralValueProject = tokenLayer('valueWeight', model.valueProjectionWeights, new Array(8).fill(0), false);
const globalScale = scale('globalWeight');
const globalBias = foldedBias(model.globalWeights, model.globalBias, model.globalFeatureMean, model.globalFeatureInverseStandardDeviation, 8, 3, globalScale);
export function neuralEncodeGlobal(raw) {
    const scaledInput = raw.xyz.mul(vec3(...model.globalFeatureInverseStandardDeviation));
    return toToken(Array.from({ length: 8 }, (_, row) => quantizedRow(model.globalWeights, row, 3, [{ node: scaledInput, length: 3 }], globalScale, globalBias)), true);
}
export function neuralQueryScores(key) {
    const query = (index) => dot(vec4(...model.summaryQueries.slice(index * 8, index * 8 + 4)), key.lo)
        .add(dot(vec4(...model.summaryQueries.slice(index * 8 + 4, index * 8 + 8)), key.hi));
    return vec4(query(0), query(1), query(2), query(3));
}
const headScale = scale('headWeight');
export function neuralHead(summaryLo, summaryHi) {
    const chunks = [];
    for (let query = 0; query < 4; query++) {
        chunks.push({ node: summaryLo[query], length: 4 }, { node: summaryHi[query], length: 4 });
    }
    return toToken(Array.from({ length: 8 }, (_, row) => quantizedRow(model.headWeights, row, 32, chunks, headScale, model.headBias)), true);
}
export function neuralOutput(head) {
    return quantizedRow(model.outputWeights, 0, 8, chunksOf(head), scale('outputWeight'), [model.outputBias]);
}
const neuralSafeNormalize = (value, fallback) => {
    const lengthSquared = dot(value, value);
    return lengthSquared.greaterThan(1e-12).select(value.mul(inverseSqrt(lengthSquared)), fallback);
};
const asVars = (token) => ({ lo: token.lo.toVar(), hi: token.hi.toVar() });
// The per-pixel attention state of the neural blur (call inside the blur's Fn). encodeTap takes
// one non-background tap; finish adds the global token and returns the correction upstream adds
// to the bilateral result before clamping.
export function neuralDenoiseState(normal, radiusToUse, distanceFalloffToUse) {
    // neuralLocalFrame: transpose(mat3(tangent, bitangent, normal)) = dot with each axis
    const frameNormal = neuralSafeNormalize(normal, vec3(0, 0, 1)).toVar();
    const helper = abs(frameNormal.z).lessThan(0.999).select(vec3(0, 0, 1), vec3(0, 1, 0));
    const tangent = neuralSafeNormalize(cross(helper, frameNormal), vec3(1, 0, 0)).toVar();
    const bitangent = cross(frameNormal, tangent).toVar();
    const toLocal = (value) => vec3(dot(tangent, value), dot(bitangent, value), dot(frameNormal, value));
    const inverseRadius = float(1).div(max(radiusToUse, 1e-6)).toVar();
    const inverseDistance = float(1).div(max(distanceFalloffToUse, 1e-6)).toVar();
    const runningMaximum = vec4(-1e30).toVar();
    const runningDenominator = vec4(0).toVar();
    const runningSummaryLo = [0, 1, 2, 3].map(() => vec4(0).toVar());
    const runningSummaryHi = [0, 1, 2, 3].map(() => vec4(0).toVar());
    const consumeToken = (input) => {
        const token = asVars(input);
        const key = asVars(neuralKeyProject(token));
        const value = asVars(neuralValueProject(token));
        const score = neuralQueryScores(key).mul(0.3535533905932738).toVar();
        const newMaximum = max(runningMaximum, score).toVar();
        const oldScale = exp(runningMaximum.sub(newMaximum)).toVar();
        const newScale = exp(score.sub(newMaximum)).toVar();
        COMPONENTS.forEach((component, query) => {
            runningSummaryLo[query].assign(runningSummaryLo[query].mul(oldScale[component]).add(value.lo.mul(newScale[component])));
            runningSummaryHi[query].assign(runningSummaryHi[query].mul(oldScale[component]).add(value.hi.mul(newScale[component])));
        });
        runningDenominator.assign(runningDenominator.mul(oldScale).add(newScale));
        runningMaximum.assign(newMaximum);
    };
    const encodeRawTap = (raw) => {
        consumeToken(neuralTapOutput(asVars(neuralTapInput(raw))));
    };
    return {
        encodeRawTap,
        encodeTap(delta, sampleNormal, sampleOcclusion, tangentPlaneDistance) {
            const localDelta = toLocal(delta).mul(inverseRadius).toVar();
            const localNormal = toLocal(neuralSafeNormalize(sampleNormal, vec3(0, 0, 1))).toVar();
            encodeRawTap({
                lo: vec4(localDelta, localNormal.x),
                hi: vec4(localNormal.y, localNormal.z, sampleOcclusion, tangentPlaneDistance.mul(inverseDistance)),
            });
        },
        finish(baselineAO, worldRadius, distanceFalloff) {
            consumeToken(neuralEncodeGlobal(vec4(baselineAO, log(max(worldRadius, 1e-6)), log(max(distanceFalloff, 1e-6)), 0)));
            const inverseDenominator = vec4(1).div(max(runningDenominator, vec4(1e-12))).toVar();
            const head = neuralHead(runningSummaryLo.map((summary, query) => summary.mul(inverseDenominator[COMPONENTS[query]])), runningSummaryHi.map((summary, query) => summary.mul(inverseDenominator[COMPONENTS[query]])));
            return neuralOutput(asVars(head));
        },
    };
}
export { model as neuralDenoiseModel };
