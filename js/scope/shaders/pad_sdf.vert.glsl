attribute vec4 aPadTransform; // (cx, cy, w, h) in mm
attribute vec4 aPadParams;    // (rotRad, shapeCode, drillRadiusMm, flags: +1=testPoint, +2=highlight)
uniform float uLayerZ;

varying vec2 vLocalMm;
varying vec2 vHalfSize;
varying float vShapeCode;
varying float vDrillRadius;
varying float vIsTestPoint;
varying float vHighlight;

void main() {
  vec2 center = aPadTransform.xy;
  vec2 halfSize = max(aPadTransform.zw * 0.5, vec2(0.025));
  float rot = aPadParams.x;
  float c = cos(rot);
  float s = sin(rot);

  vec2 margin = halfSize * 1.22 + vec2(0.04);
  vec2 local = position.xy * 2.0 * margin;
  vec2 rotated = vec2(local.x * c - local.y * s, local.x * s + local.y * c);

  float flags = aPadParams.w;
  float highlight = flags >= 1.5 ? 1.0 : 0.0;
  float isTp = mod(floor(flags + 0.1), 2.0);

  vLocalMm = local;
  vHalfSize = halfSize;
  vShapeCode = aPadParams.y;
  vDrillRadius = aPadParams.z;
  vIsTestPoint = isTp;
  vHighlight = highlight;

  float zLift = highlight > 0.5 ? (uLayerZ >= 0.0 ? 0.015 : -0.015) : 0.0;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(center + rotated, uLayerZ + zLift, 1.0);
}
