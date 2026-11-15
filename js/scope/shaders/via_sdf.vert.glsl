attribute vec4 aViaGeom; // (cx, cy, padRadiusMm, drillRadiusMm)
attribute float aViaHighlight;
uniform float uLayerZ;

varying vec2 vLocalMm;
varying float vPadRadius;
varying float vDrillRadius;
varying float vHighlight;

void main() {
  vec2 center = aViaGeom.xy;
  float padR = max(aViaGeom.z, 0.08);
  float margin = padR * 1.25 + 0.03;
  vec2 local = position.xy * 2.0 * margin;

  vLocalMm = local;
  vPadRadius = padR;
  vDrillRadius = aViaGeom.w;
  vHighlight = aViaHighlight;

  float zLift = aViaHighlight > 0.5 ? (uLayerZ >= 0.0 ? 0.018 : -0.018) : 0.0;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(center + local, uLayerZ + zLift, 1.0);
}
