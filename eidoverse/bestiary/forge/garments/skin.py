"""SKINNING BY TRANSFER (HUMAN_PLAN §6.8: one weight field, transferred from the body, identical where the vertices
coincide). Each garment point takes the body's weights at its closest point on the skin: the three corner vertices'
four-influence weights blended by the barycentrics into one joint vector, the four largest kept, renormalised. Then
SMOOTHED over the garment's own surface a few steps where the cloth stands far from the skin (a bridge over a hollow
should move with its supports, not with the hollow), never at the skin's own stand-off.

THE CLOTH OFFSET: a garment point stands off the skin by its offset d along the skin's normal; under LBS that offset
shrinks inside a bending joint's crease. The gate (gates.py) measures it over the controller's clips; the cure here is
the weights' smoothing and the offset itself, nothing at runtime.

    J4, W4 = transfer(B, Vw_rest_points, P)        (P on the T rest)
    unpose(B, P_posed, J4, W4, mats) -> the T-rest points whose LBS lands on P_posed
"""
import numpy as np

from . import meshops as mo


def body_weights_dense(B):
    """skin_BODY's weights as a dense (n, joints) matrix (welded ids: the first copy's weights)"""
    D = np.zeros((len(B.V), len(B.jnames)))
    np.add.at(D, (np.repeat(np.arange(len(B.V)), 4), B.J4.ravel()), B.W4.ravel())
    return D


def top4(D):
    J = np.argsort(-D, axis=1)[:, :4]
    W = np.take_along_axis(D, J, axis=1)
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
    return J.astype(np.int64), W


def transfer(B, P, F=None, smooth_far=0.02, smooth_iters=12):
    """weights at P (T rest) from the body's closest skin points; smoothed over the garment (F) where P stands farther
    than smooth_far off the skin"""
    Vw, Fw, wid, rep = B.welded()
    D = body_weights_dense(B)[rep]
    q, t, bc, sd = mo.closest_on_mesh(Vw, Fw, P)
    W = np.einsum('nk,nkj->nj', bc, D[Fw[t]])
    if F is not None and smooth_iters:
        far = np.clip((np.abs(sd) - smooth_far) / smooth_far, 0.0, 1.0)
        L = mo.laplacian(P, F)
        for _ in range(smooth_iters):
            W = W + 0.5 * far[:, None] * (L @ W)
    J4, W4 = top4(W)
    return J4, W4, sd


def unpose(B, P, J4, W4, mats):
    return B.unlbs(P, J4, W4, mats)
