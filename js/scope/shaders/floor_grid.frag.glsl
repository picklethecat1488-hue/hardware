precision highp float;

varying vec3 vWorldPos;
uniform float uMinorStep;
uniform float uMajorStep;
uniform float uFadeRadius;

float gridFactor(vec2 coord, float stepSize) {
  vec2 scaled = coord / stepSize;
  vec2 grid = abs(fract(scaled - 0.5) - 0.5) / max(fwidth(scaled), vec2(1e-4));
  float line = min(grid.x, grid.y);
  return 1.0 - min(line, 1.0);
}

void main() {
  float minor = gridFactor(vWorldPos.xy, uMinorStep);
  float major = gridFactor(vWorldPos.xy, uMajorStep);

  vec2 axisDist = abs(vWorldPos.xy) / max(fwidth(vWorldPos.xy), vec2(1e-4));
  float xAxis = 1.0 - min(axisDist.y, 1.0);
  float yAxis = 1.0 - min(axisDist.x, 1.0);

  float dist = length(vWorldPos.xy);
  float fade = 1.0 - smoothstep(uFadeRadius * 0.35, uFadeRadius, dist);

  vec3 color = vec3(0.24, 0.30, 0.39) * minor * 0.45;
  color = mix(color, vec3(0.38, 0.48, 0.62), major * 0.75);
  color = mix(color, vec3(0.92, 0.32, 0.32), xAxis * 0.85);
  color = mix(color, vec3(0.24, 0.82, 0.45), yAxis * 0.85);

  float alpha = max(max(minor * 0.28, major * 0.56), max(xAxis, yAxis) * 0.78) * fade;
  if (alpha < 0.01) discard;
  gl_FragColor = vec4(color, alpha);
}
