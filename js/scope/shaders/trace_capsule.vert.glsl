attribute vec4 aTraceGeom;   // (x1, y1, x2, y2) in mm
attribute vec2 aTraceStyle;  // (widthMm, highlightFlag)
uniform float uLayerZ;

varying vec2 vLocalMm;
varying float vHalfLen;
varying float vRadius;
varying float vHighlight;

void main() {
  vec2 p1 = aTraceGeom.xy;
  vec2 p2 = aTraceGeom.zw;
  vec2 delta = p2 - p1;
  float segLen = max(length(delta), 1e-4);
  vec2 dir = delta / segLen;
  vec2 normal = vec2(-dir.y, dir.x);

  float radius = max(aTraceStyle.x * 0.5, 0.02);
  float halfLen = segLen * 0.5;
  float padMargin = radius * 1.35;

  // Unit quad position.xy is in [-0.5, +0.5]
  float along = position.x * 2.0 * (halfLen + padMargin);
  float across = position.y * 2.0 * padMargin;

  vec2 mid = (p1 + p2) * 0.5;
  vec2 worldXY = mid + dir * along + normal * across;

  vLocalMm = vec2(along, across);
  vHalfLen = halfLen;
  vRadius = radius;
  vHighlight = aTraceStyle.y;

  float zLift = aTraceStyle.y > 0.5 ? (uLayerZ >= 0.0 ? 0.012 : -0.012) : 0.0;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(worldXY, uLayerZ + zLift, 1.0);
}
