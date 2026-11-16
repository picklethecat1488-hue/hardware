precision highp float;

uniform float uOpacity;
uniform vec3 uLightDirA;
uniform vec3 uLightDirB;

varying vec3 vWorldNormal;
varying vec3 vViewDir;
varying vec3 vColor;
varying float vWorldZ;

void main() {
  vec3 n = normalize(vWorldNormal);
  vec3 v = normalize(vViewDir);

  float diffA = max(dot(n, uLightDirA), 0.0);
  float diffB = max(dot(n, uLightDirB), 0.0);
  float hemi = n.z * 0.5 + 0.5;

  vec3 halfVec = normalize(uLightDirA + v);
  float spec = pow(max(dot(n, halfVec), 0.0), 36.0);
  float fresnel = pow(1.0 - max(dot(n, v), 0.0), 2.6);

  // Subtle elevation tint so upper fountain sheet & spout read vividly against deep pool
  float heightBoost = clamp((vWorldZ - 40.0) / 75.0, 0.0, 1.0);
  vec3 baseWater = mix(vColor * 0.86, mix(vColor, vec3(0.72, 0.93, 1.0), 0.32), heightBoost);

  vec3 shaded = baseWater * (0.38 + 0.52 * diffA + 0.22 * diffB + 0.18 * hemi)
              + vec3(0.88, 0.96, 1.0) * (spec * 0.34 + fresnel * 0.22);

  gl_FragColor = vec4(shaded, uOpacity);
}
