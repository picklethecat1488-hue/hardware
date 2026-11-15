attribute vec3 aInstancePos;
attribute vec3 aInstanceColor;

varying vec3 vWorldNormal;
varying vec3 vViewDir;
varying vec3 vColor;
varying float vWorldZ;

void main() {
  vec3 worldPos = position + aInstancePos;
  vec4 mvPos = modelViewMatrix * vec4(worldPos, 1.0);
  vWorldNormal = normalize(mat3(modelMatrix) * normal);
  vViewDir = normalize(-mvPos.xyz);
  vColor = aInstanceColor;
  vWorldZ = worldPos.z;
  gl_Position = projectionMatrix * mvPos;
}
