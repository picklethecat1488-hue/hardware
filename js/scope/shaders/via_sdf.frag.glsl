precision highp float;

uniform vec3 uViaColor;
uniform vec3 uHighlightColor;
uniform vec3 uDrillColor;
uniform float uOpacity;

varying vec2 vLocalMm;
varying float vPadRadius;
varying float vDrillRadius;
varying float vHighlight;

void main() {
  float r = length(vLocalMm);
  float outerDist = r - vPadRadius;
  float aa = max(fwidth(r), 1e-4);
  float outerCov = 1.0 - smoothstep(-aa * 0.65, aa * 0.65, outerDist);
  if (outerCov <= 0.01) discard;

  vec3 ringCol = mix(uViaColor, uHighlightColor, vHighlight);
  float innerDist = r - vDrillRadius;
  float holeMask = 1.0 - smoothstep(-aa * 0.65, aa * 0.65, innerDist);
  vec3 finalCol = mix(ringCol, uDrillColor, holeMask);

  gl_FragColor = vec4(finalCol, outerCov * uOpacity);
}
