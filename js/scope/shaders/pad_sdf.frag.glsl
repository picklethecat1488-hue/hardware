precision highp float;

uniform vec3 uPadColor;
uniform vec3 uTestPointColor;
uniform vec3 uHighlightColor;
uniform vec3 uDrillColor;
uniform float uOpacity;

varying vec2 vLocalMm;
varying vec2 vHalfSize;
varying float vShapeCode;
varying float vDrillRadius;
varying float vIsTestPoint;
varying float vHighlight;

float sdRoundBox(vec2 p, vec2 b, float r) {
  vec2 q = abs(p) - b + vec2(r);
  return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}

void main() {
  float dist;
  float minHalf = min(vHalfSize.x, vHalfSize.y);
  if (vShapeCode > 0.5 && vShapeCode < 1.5) {
    // Circle
    dist = length(vLocalMm) - max(vHalfSize.x, vHalfSize.y);
  } else if (vShapeCode >= 1.5 && vShapeCode < 2.5) {
    // Sharp Rect (small chamfer for clean DFM edge)
    dist = sdRoundBox(vLocalMm, vHalfSize, minHalf * 0.06);
  } else if (vShapeCode >= 2.5) {
    // Stadium / Oval
    dist = sdRoundBox(vLocalMm, vHalfSize, minHalf);
  } else {
    // IPC-7351 RoundRect (25% corner radius capped at 0.25 mm)
    float cornerR = min(minHalf * 0.28, 0.25);
    dist = sdRoundBox(vLocalMm, vHalfSize, cornerR);
  }

  float aa = max(fwidth(dist), 1e-4);
  float outerAlpha = 1.0 - smoothstep(-aa * 0.65, aa * 0.65, dist);
  if (outerAlpha <= 0.01) discard;

  vec3 baseCol = mix(uPadColor, uTestPointColor, vIsTestPoint);
  vec3 copperCol = mix(baseCol, uHighlightColor, vHighlight);

  if (vDrillRadius > 0.005) {
    float holeDist = length(vLocalMm) - vDrillRadius;
    float holeMask = 1.0 - smoothstep(-aa * 0.65, aa * 0.65, holeDist);
    copperCol = mix(copperCol, uDrillColor, holeMask);
  }

  gl_FragColor = vec4(copperCol, outerAlpha * uOpacity);
}
