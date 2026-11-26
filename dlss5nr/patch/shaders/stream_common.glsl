// The arithmetic of `dlss5vk run --stream`'s temporal passes (stream_*.comp, src/main.cpp runStream): the CPU path of
// `run --list` (HistoryImage and the composite of runRun) operation for operation, so the two give the same numbers. Every float is `precise` (no contraction, no reassociation), every division is the IEEE
// quotient (divRn below: GLSL's `/` is an approximate reciprocal on this hardware), and the half conversions are
// spelled on the bits.
#ifndef STREAM_COMMON_GLSL
#define STREAM_COMMON_GLSL

#extension GL_EXT_shader_explicit_arithmetic_types : require
#extension GL_GOOGLE_include_directive : require
#include "common.glsl"

// a / b rounded to nearest even, for b > 0 and a quotient in the normal range (every division of the warp). The
// approximate reciprocal and one correction give a faithful quotient q (one of the two floats either side of a / b);
// its remainder a - b q is then exact under fma, and so is the other candidate's: the nearer one is the IEEE quotient.
// (A quotient of two floats is never exactly halfway between two floats, so there is no tie to break.)
float divRn(float a, float b) {
  precise float y = 1.0 / b;
  precise float q = a * y;
  precise float r = fma(-b, q, a);
  q = fma(r, y, q);
  r = fma(-b, q, a);
  if (r == 0.0 || q == 0.0) return q;
  const uint bits = floatBitsToUint(q);
  const float other = uintBitsToFloat((r > 0.0) == (q > 0.0) ? bits + 1u : bits - 1u);   // the float on a / b's side
  precise float r2 = fma(-b, other, a);
  return abs(r2) < abs(r) ? other : q;
}

// IEEE binary16 bits -> f32, exact, subnormals included (num::f16ToF32).
float halfBitsToFloat(uint bits) {
  const uint sign = (bits & 0x8000u) << 16u, exponent = (bits >> 10u) & 0x1fu, mantissa = bits & 0x3ffu;
  if (exponent == 0u) return uintBitsToFloat(sign | floatBitsToUint(float(mantissa) * uintBitsToFloat(0x33800000u)));
  if (exponent == 31u) return uintBitsToFloat(sign | 0x7f800000u | (mantissa << 13u));
  return uintBitsToFloat(sign | ((exponent + 112u) << 23u) | (mantissa << 13u));
}

// f32 -> binary16 bits truncated toward zero (main.cpp's truncateHalf before its f16ToF32; exact for a value on the grid).
uint truncateHalfBits(float value) {
  const uint bits = floatBitsToUint(value);
  const uint signBit = (bits >> 16u) & 0x8000u, exponent = (bits >> 23u) & 0xffu, mantissa = bits & 0x7fffffu;
  if (exponent == 0xffu) return signBit | (mantissa != 0u ? 0x7e00u : 0x7c00u);
  const int halfExponent = int(exponent) - 112;
  if (halfExponent >= 31) return signBit | 0x7c00u;
  if (halfExponent <= 0) return halfExponent < -10 ? signBit : signBit | ((mantissa | 0x800000u) >> uint(14 - halfExponent));
  return signBit | (uint(halfExponent) << 10u) | (mantissa >> 13u);
}

float truncateHalf(float value) { return halfBitsToFloat(truncateHalfBits(value)); }

#endif
