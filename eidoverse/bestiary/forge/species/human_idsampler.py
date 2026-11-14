"""HUMAN H2b: GNM's semantic IdentitySampler, our own numpy forward pass (the lead's H2b call 1: "start each sex from its
own mean face").

THE WEIGHTS: work/bestiary/research/human_web/gnm_semantic_sampler/identity_decoder_model.h5 (google/gnm, Apache-2.0,
pinned at commit abbad035; SOURCES.txt there), read as DATA by forge/h5lite.py; nothing upstream is imported or run.
THE MODEL (the file's own model_config, read as text, and asserted against the weights' shapes in load()): the decoder
of a conditional VAE, concat(z (64, standard normal), label (6)) -> Dense 64 relu -> Dense 128 relu -> Dense 256 relu ->
Dense 512 relu -> Dense 253 linear. The label is the one-hot gender (FEMALE 0, MALE 1) followed by the one-hot ethnicity
(MIDDLE_EASTERN 0, ASIAN 1, WHITE 2, BLACK 3); there is no age input. The output is GNM's whole identity vector, passed
unchanged to gnm(identity=...) upstream: head_000-169 (the skin), eyes_000-002 and teeth_000-079 (they move no skin
vertex: checked on gnm_head.npz, every eyes / teeth component is zero on the 12,466 skin vertices).

EACH SEX'S STATISTICS (sex_stats): the decoder's output over z ~ N(0, I) and the four ethnicity labels in EQUAL shares,
by Monte Carlo with a fixed seed: the MIXTURE's mean (the sex's mean face) and covariance (its spread, for the least
Mahalanobis conditioning in human_ref.condition_gnm). Equal shares mirror the body's MakeHuman macro targets, three races
a third each (human_pheno); the per-class means are kept for the report. The labels are one-hot (each class decoded as
trained), not the blended labels blend_identities feeds.

    load() -> dict of the layer arrays          decode(z, label) -> (n, 253)
    label(sex, ethnicity) -> (6,)               sex_stats(sex, n_per_class, seed) -> dict(mean, cov, class_means, ...)
"""
import json
import os

import numpy as np

from .. import h5lite
from . import human_ref as HR

VERSION = 'h2b-idsampler-1'
H5 = os.path.join(HR.WEB, 'gnm_semantic_sampler', 'identity_decoder_model.h5')
LAYERS = ('dense_4', 'dense_5', 'dense_6', 'dense_7', 'dense_8')
ACTIVATION = ('relu', 'relu', 'relu', 'relu', 'linear')
LATENT, N_GENDER, N_ETHNICITY, N_IDENTITY = 64, 2, 4, 253
GENDER = dict(F=0, M=1)
ETHNICITIES = ('middle_eastern', 'asian', 'white', 'black')
_W = {}


def load():
    """the decoder's kernels and biases (float64), checked against the file's model_config (layer order, units,
    activations, the two inputs and their concatenation order)"""
    if _W:
        return _W
    f = h5lite.H5File(H5)
    cfg = json.loads(f.attrs('/')['model_config'])['config']
    layers = {L['config']['name']: L for L in cfg['layers']}
    assert [x[0] for x in cfg['input_layers']] == ['latent_input', 'decoder_label_input'], cfg['input_layers']
    cat = layers['concatenate_1']['inbound_nodes'][0]
    assert [x[0] for x in cat] == ['latent_input', 'decoder_label_input'], 'the concatenation order changed'
    assert layers['latent_input']['config']['batch_input_shape'][-1] == LATENT
    assert layers['decoder_label_input']['config']['batch_input_shape'][-1] == N_GENDER + N_ETHNICITY
    prev = 'concatenate_1'
    n_in = LATENT + N_GENDER + N_ETHNICITY
    for name, act in zip(LAYERS, ACTIVATION):
        c = layers[name]['config']
        assert layers[name]['class_name'] == 'Dense' and c['activation'] == act and c['use_bias'], name
        assert layers[name]['inbound_nodes'][0][0][0] == prev, f'{name} does not follow {prev}'
        K = f.dataset(f'/model_weights/{name}/{name}/kernel:0').astype(np.float64)
        b = f.dataset(f'/model_weights/{name}/{name}/bias:0').astype(np.float64)
        assert K.shape == (n_in, c['units']) and b.shape == (c['units'],), (name, K.shape, b.shape)
        _W[name] = (K, b)
        prev, n_in = name, c['units']
    assert n_in == N_IDENTITY and [x[0] for x in cfg['output_layers']] == [LAYERS[-1]]
    return _W


def label(sex, ethnicity):
    """the decoder's 6-d condition: one-hot gender, then one-hot ethnicity (an index or a name of ETHNICITIES)"""
    e = ETHNICITIES.index(ethnicity) if isinstance(ethnicity, str) else int(ethnicity)
    v = np.zeros(N_GENDER + N_ETHNICITY)
    v[GENDER[sex]] = 1.0
    v[N_GENDER + e] = 1.0
    return v


def decode(z, lab):
    """GNM identity vectors (n, 253) for latents z (n, 64) and conditions lab (n, 6) or (6,)"""
    W = load()
    z = np.atleast_2d(np.asarray(z, np.float64))
    lab = np.broadcast_to(np.asarray(lab, np.float64), (len(z), N_GENDER + N_ETHNICITY))
    x = np.concatenate([z, lab], axis=1)
    for name, act in zip(LAYERS, ACTIVATION):
        K, b = W[name]
        x = x @ K + b
        if act == 'relu':
            x = np.maximum(x, 0.0)
    return x


def sex_stats(sex, n_per_class=25000, seed=2610, head_only=True):
    """the sex's mixture over the four ethnicity labels in equal shares: mean (the sex's mean face), cov, the per-class
    means, the samples' count; head_only keeps GNM's 170 head components (the only ones that move the skin)"""
    rng = np.random.default_rng(seed)
    k = HR.N_HEAD if head_only else N_IDENTITY
    means, s1, s2, n = [], np.zeros(k), np.zeros((k, k)), 0
    for e in range(N_ETHNICITY):
        z = rng.standard_normal((n_per_class, LATENT))
        C = decode(z, label(sex, e))[:, :k]
        means.append(C.mean(0))
        s1 += C.sum(0)
        s2 += C.T @ C
        n += len(C)
    mean = s1 / n
    cov = s2 / n - np.outer(mean, mean)
    return dict(sex=sex, mean=mean, cov=0.5 * (cov + cov.T), class_means=np.array(means), n=n, seed=seed,
                ethnicities=ETHNICITIES)
