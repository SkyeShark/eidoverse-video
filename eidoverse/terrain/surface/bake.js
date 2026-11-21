// Port of blender/eidoblend/terrain/surface/bake.py at d67f19e (in progress: the kernel loader first).

/** The eleven kernels transcribed from Blender's surface/kernels/*.glsl (surface/kernels/<name>.wgsl), named as
 * Blender's twins register them ('surface_<name>'), marked as Blender kernels for the dispatch log. */
export const KERNELS = ['blur', 'upsample2', 'field_normal', 'crest', 'phacelle', 'cavity', 'carry_src', 'streak', 'fill',
    'pin_inflow', 'route_colour'];
export const PREFIX = 'surface_';

/** A surface kernel on runner R: surface/kernels/<name>.wgsl (a Blender one, KERNELS) or surface/kernels/port/<name>.wgsl
 * (the port's own: numpy code of bake.py moved to the GPU), compiled once per runner. */
export function kernel(R, name) {
    const blender = KERNELS.includes(name);
    const url = new URL(`kernels/${blender ? '' : 'port/'}${name}.wgsl`, import.meta.url);
    return R.kernel(PREFIX + name, { url, blender });
}
