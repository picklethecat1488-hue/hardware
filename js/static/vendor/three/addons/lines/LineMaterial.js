/**
 * Wide-line shader material supporting physical pixel widths, world units, dashes, and clipping.
 *
 * Adapted from Three.js r184 addons (MIT License) with strict zero-globals
 * compliance, named constants, and JSDoc documentation.
 */

import { ShaderLib, ShaderMaterial, UniformsLib, UniformsUtils, Vector2 } from "../../three.module.js";

const DEFAULT_LINE_WIDTH = 1;
const DEFAULT_DASH_SCALE = 1;
const DEFAULT_DASH_SIZE = 1;
const DEFAULT_GAP_SIZE = 1;
const DEFAULT_RESOLUTION_PX = 1;

const LINE_VERTEX_SHADER = /* glsl */ `
  #include <common>
  #include <color_pars_vertex>
  #include <fog_pars_vertex>
  #include <logdepthbuf_pars_vertex>
  #include <clipping_planes_pars_vertex>

  uniform float linewidth;
  uniform vec2 resolution;

  attribute vec3 instanceStart;
  attribute vec3 instanceEnd;
  attribute vec3 instanceColorStart;
  attribute vec3 instanceColorEnd;

  #ifdef WORLD_UNITS
    varying vec4 worldPos;
    varying vec3 worldStart;
    varying vec3 worldEnd;
    #ifdef USE_DASH
      varying vec2 vUv;
    #endif
  #else
    varying vec2 vUv;
  #endif

  #ifdef USE_DASH
    uniform float dashScale;
    attribute float instanceDistanceStart;
    attribute float instanceDistanceEnd;
    varying float vLineDistance;
  #endif

  void trimSegment(const in vec4 start, inout vec4 end) {
    float a = projectionMatrix[2][2];
    float b = projectionMatrix[3][2];
    float nearEstimate = -0.5 * b / a;
    float alpha = (nearEstimate - start.z) / (end.z - start.z);
    end.xyz = mix(start.xyz, end.xyz, alpha);
  }

  void main() {
    #ifdef USE_COLOR
      vColor.xyz = (position.y < 0.5) ? instanceColorStart : instanceColorEnd;
    #endif

    #ifdef USE_DASH
      vLineDistance = (position.y < 0.5) ? dashScale * instanceDistanceStart : dashScale * instanceDistanceEnd;
      vUv = uv;
    #endif

    float aspect = resolution.x / resolution.y;

    vec4 start = modelViewMatrix * vec4(instanceStart, 1.0);
    vec4 end = modelViewMatrix * vec4(instanceEnd, 1.0);

    #ifdef WORLD_UNITS
      worldStart = start.xyz;
      worldEnd = end.xyz;
    #else
      vUv = uv;
    #endif

    bool perspective = (projectionMatrix[2][3] == -1.0);
    if (perspective) {
      if (start.z < 0.0 && end.z >= 0.0) {
        trimSegment(start, end);
      } else if (end.z < 0.0 && start.z >= 0.0) {
        trimSegment(end, start);
      }
    }

    vec4 clipStart = projectionMatrix * start;
    vec4 clipEnd = projectionMatrix * end;

    vec3 ndcStart = clipStart.xyz / clipStart.w;
    vec3 ndcEnd = clipEnd.xyz / clipEnd.w;

    vec2 dir = ndcEnd.xy - ndcStart.xy;
    dir.x *= aspect;
    float dirLen = length(dir);
    dir = (dirLen > 1e-6) ? (dir / dirLen) : vec2(1.0, 0.0);

    #ifdef WORLD_UNITS
      vec3 worldDir = normalize(end.xyz - start.xyz);
      vec3 tmpFwd = normalize(mix(start.xyz, end.xyz, 0.5));
      vec3 worldUp = normalize(cross(worldDir, tmpFwd));
      vec3 worldFwd = cross(worldDir, worldUp);
      worldPos = position.y < 0.5 ? start : end;

      float hw = linewidth * 0.5;
      worldPos.xyz += position.x < 0.0 ? hw * worldUp : -hw * worldUp;

      #ifndef USE_DASH
        worldPos.xyz += position.y < 0.5 ? -hw * worldDir : hw * worldDir;
        worldPos.xyz += worldFwd * hw;
        if (position.y > 1.0 || position.y < 0.0) {
          worldPos.xyz -= worldFwd * 2.0 * hw;
        }
      #endif

      vec4 clip = projectionMatrix * worldPos;
      vec3 clipPose = (position.y < 0.5) ? ndcStart : ndcEnd;
      clip.z = clipPose.z * clip.w;
    #else
      vec2 offset = vec2(dir.y, -dir.x);
      dir.x /= aspect;
      offset.x /= aspect;

      if (position.x < 0.0) {
        offset *= -1.0;
      }

      if (position.y < 0.0) {
        offset += -dir;
      } else if (position.y > 1.0) {
        offset += dir;
      }

      offset *= linewidth;
      offset /= resolution.y;

      vec4 clip = (position.y < 0.5) ? clipStart : clipEnd;
      offset *= clip.w;
      clip.xy += offset;
    #endif

    gl_Position = clip;

    vec4 mvPosition = (position.y < 0.5) ? start : end;

    #include <logdepthbuf_vertex>
    #include <clipping_planes_vertex>
    #include <fog_vertex>
  }
`;

const LINE_FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 diffuse;
  uniform float opacity;
  uniform float linewidth;

  #ifdef USE_DASH
    uniform float dashOffset;
    uniform float dashSize;
    uniform float gapSize;
  #endif

  varying float vLineDistance;

  #ifdef WORLD_UNITS
    varying vec4 worldPos;
    varying vec3 worldStart;
    varying vec3 worldEnd;
    #ifdef USE_DASH
      varying vec2 vUv;
    #endif
  #else
    varying vec2 vUv;
  #endif

  #include <common>
  #include <color_pars_fragment>
  #include <fog_pars_fragment>
  #include <logdepthbuf_pars_fragment>
  #include <clipping_planes_pars_fragment>

  vec2 closestLineToLine(vec3 p1, vec3 p2, vec3 p3, vec3 p4) {
    vec3 p13 = p1 - p3;
    vec3 p43 = p4 - p3;
    vec3 p21 = p2 - p1;

    float d1343 = dot(p13, p43);
    float d4321 = dot(p43, p21);
    float d1321 = dot(p13, p21);
    float d4343 = dot(p43, p43);
    float d2121 = dot(p21, p21);

    float denom = d2121 * d4343 - d4321 * d4321;
    float numer = d1343 * d4321 - d1321 * d4343;

    float mua = clamp(numer / max(denom, 1e-8), 0.0, 1.0);
    float mub = clamp((d1343 + d4321 * mua) / max(d4343, 1e-8), 0.0, 1.0);
    return vec2(mua, mub);
  }

  void main() {
    float alpha = opacity;
    vec4 diffuseColor = vec4(diffuse, alpha);

    #include <clipping_planes_fragment>

    #ifdef USE_DASH
      if (vUv.y < -1.0 || vUv.y > 1.0) discard;
      if (mod(vLineDistance + dashOffset, dashSize + gapSize) > dashSize) discard;
    #endif

    #ifdef WORLD_UNITS
      vec3 rayEnd = normalize(worldPos.xyz) * 1e5;
      vec3 lineDir = worldEnd - worldStart;
      vec2 params = closestLineToLine(worldStart, worldEnd, vec3(0.0, 0.0, 0.0), rayEnd);

      vec3 p1 = worldStart + lineDir * params.x;
      vec3 p2 = rayEnd * params.y;
      float norm = length(p1 - p2) / linewidth;

      #ifndef USE_DASH
        #ifdef USE_ALPHA_TO_COVERAGE
          float dnorm = fwidth(norm);
          alpha = 1.0 - smoothstep(0.5 - dnorm, 0.5 + dnorm, norm);
        #else
          if (norm > 0.5) discard;
        #endif
      #endif
    #else
      #ifdef USE_ALPHA_TO_COVERAGE
        float a = vUv.x;
        float b = (vUv.y > 0.0) ? vUv.y - 1.0 : vUv.y + 1.0;
        float len2 = a * a + b * b;
        float dlen = fwidth(len2);
        if (abs(vUv.y) > 1.0) {
          alpha = 1.0 - smoothstep(1.0 - dlen, 1.0 + dlen, len2);
        }
      #else
        if (abs(vUv.y) > 1.0) {
          float a = vUv.x;
          float b = (vUv.y > 0.0) ? vUv.y - 1.0 : vUv.y + 1.0;
          if (a * a + b * b > 1.0) discard;
        }
      #endif
    #endif

    #include <logdepthbuf_fragment>
    #include <color_fragment>

    gl_FragColor = vec4(diffuseColor.rgb, alpha);

    #include <tonemapping_fragment>
    #include <colorspace_fragment>
    #include <fog_fragment>
    #include <premultiplied_alpha_fragment>
  }
`;

UniformsLib.line = {
  worldUnits: { value: 1 },
  linewidth: { value: DEFAULT_LINE_WIDTH },
  resolution: { value: new Vector2(DEFAULT_RESOLUTION_PX, DEFAULT_RESOLUTION_PX) },
  dashOffset: { value: 0 },
  dashScale: { value: DEFAULT_DASH_SCALE },
  dashSize: { value: DEFAULT_DASH_SIZE },
  gapSize: { value: DEFAULT_GAP_SIZE },
};

ShaderLib.line = {
  uniforms: UniformsUtils.merge([UniformsLib.common, UniformsLib.fog, UniformsLib.line]),
  vertexShader: LINE_VERTEX_SHADER,
  fragmentShader: LINE_FRAGMENT_SHADER,
};

/**
 * ShaderMaterial for rendering crisp physical-pixel or world-space wide line segments.
 */
export class LineMaterial extends ShaderMaterial {
  /**
   * Construct a `LineMaterial`.
   *
   * @param {object} [parameters] - Initial material property overrides.
   */
  constructor(parameters) {
    super({
      type: "LineMaterial",
      uniforms: UniformsUtils.clone(ShaderLib.line.uniforms),
      vertexShader: ShaderLib.line.vertexShader,
      fragmentShader: ShaderLib.line.fragmentShader,
      clipping: true,
    });

    /**
     * Runtime type-guard flag.
     * @type {boolean}
     */
    this.isLineMaterial = true;
    this.setValues(parameters);
  }

  /**
   * Base diffuse color of the line segments.
   * @returns {import("../../three.module.js").Color}
   */
  get color() {
    return this.uniforms.diffuse.value;
  }

  set color(value) {
    this.uniforms.diffuse.value = value;
  }

  /**
   * Whether `linewidth` is interpreted in 3D world units rather than physical pixels.
   * @returns {boolean}
   */
  get worldUnits() {
    return "WORLD_UNITS" in this.defines;
  }

  set worldUnits(value) {
    const enabled = value === true;
    if (enabled !== this.worldUnits) {
      this.needsUpdate = true;
    }
    if (enabled) {
      this.defines.WORLD_UNITS = "";
    } else {
      delete this.defines.WORLD_UNITS;
    }
  }

  /**
   * Line thickness in physical drawing-buffer pixels (`worldUnits = false`) or world units (`true`).
   * @returns {number}
   */
  get linewidth() {
    return this.uniforms.linewidth.value;
  }

  set linewidth(value) {
    if (!this.uniforms.linewidth) {
      return;
    }
    this.uniforms.linewidth.value = value;
  }

  /**
   * Whether dashed segment rendering is enabled.
   * @returns {boolean}
   */
  get dashed() {
    return "USE_DASH" in this.defines;
  }

  set dashed(value) {
    const enabled = value === true;
    if (enabled !== this.dashed) {
      this.needsUpdate = true;
    }
    if (enabled) {
      this.defines.USE_DASH = "";
    } else {
      delete this.defines.USE_DASH;
    }
  }

  /**
   * Multiplier applied to cumulative line distance for dash patterning.
   * @returns {number}
   */
  get dashScale() {
    return this.uniforms.dashScale.value;
  }

  set dashScale(value) {
    this.uniforms.dashScale.value = value;
  }

  /**
   * Length of each visible dash segment.
   * @returns {number}
   */
  get dashSize() {
    return this.uniforms.dashSize.value;
  }

  set dashSize(value) {
    this.uniforms.dashSize.value = value;
  }

  /**
   * Phase offset along the dash cycle.
   * @returns {number}
   */
  get dashOffset() {
    return this.uniforms.dashOffset.value;
  }

  set dashOffset(value) {
    this.uniforms.dashOffset.value = value;
  }

  /**
   * Length of each gap between dashes.
   * @returns {number}
   */
  get gapSize() {
    return this.uniforms.gapSize.value;
  }

  set gapSize(value) {
    this.uniforms.gapSize.value = value;
  }

  /**
   * Alpha opacity in `[0, 1]`.
   * @returns {number}
   */
  get opacity() {
    return this.uniforms.opacity.value;
  }

  set opacity(value) {
    if (!this.uniforms) {
      return;
    }
    this.uniforms.opacity.value = value;
  }

  /**
   * Physical drawing-buffer dimensions `(widthPx, heightPx)` updated in `LineSegments2.onBeforeRender`.
   * @returns {Vector2}
   */
  get resolution() {
    return this.uniforms.resolution.value;
  }

  set resolution(value) {
    this.uniforms.resolution.value.copy(value);
  }

  /**
   * Whether MSAA alpha-to-coverage derivative antialiasing is active.
   * @returns {boolean}
   */
  get alphaToCoverage() {
    return "USE_ALPHA_TO_COVERAGE" in this.defines;
  }

  set alphaToCoverage(value) {
    if (!this.defines) {
      return;
    }
    const enabled = value === true;
    if (enabled !== this.alphaToCoverage) {
      this.needsUpdate = true;
    }
    if (enabled) {
      this.defines.USE_ALPHA_TO_COVERAGE = "";
    } else {
      delete this.defines.USE_ALPHA_TO_COVERAGE;
    }
  }
}
