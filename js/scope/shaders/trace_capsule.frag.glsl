precision highp float;

uniform vec3 uBaseColor;
uniform vec3 uHighlightColor;
uniform float uOpacity;

varying vec2 vLocalMm;
varying float vHalfLen;
varying float vRadius;
varying float vHighlight;

void main() {
  vec2 q = vec2(max(abs(vLocalMm.x) - vHalfLen, 0.0), abs(vLocalMm.y));
  float dist = length(q) - vRadius;
  float aa = max(fwidth(dist), 1e-4);
  float cov = 1.0 - smoothstep(-aa * 0.65, aa * 0.65, dist);
  if (cov <= 0.01) discard;

  vec3 col = mix(uBaseColor, uHighlightColor, clamp(vHighlight, 0.0, 1.0));
  if (vHighlight > 0.5) {
    float rim = 1.0 - smoothstep(0.0, aa * 2.2, abs(dist + vRadius * 0.18));
    col = mix(col, vec3(1.0, 1.0, 0.92), rim * 0.45);
  }
  gl_FragColor = vec4(col, cov * uOpacity);
}
