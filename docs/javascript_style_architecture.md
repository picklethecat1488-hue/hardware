# JavaScript Style, Zero-Globals & CAD Viewport Architecture

Architectural invariants, coding style standards, zero-globals isolation rules, HiDPI rendering requirements, and unit testing mandates for first-party and modifiable vendor JavaScript ES modules across the `hardware` and `firmware` repositories.

---

## 1. Canonical Single-Root Module Layout & Zero Inline Template JS

* **Single Canonical JS Directory**: All browser JavaScript ES modules live under a single root directory per repository:
  - `hardware`: `js/` (`js/core/`, `js/diff/`, `js/vcs/`, `js/review/`, `js/tracker/`, `js/scope/`, and `js/static/`)
  - `firmware`: `tools/js/` (`tools/js/core/`, `tools/js/diff/`, `tools/js/vcs/`, `tools/js/review/`, `tools/js/tracker/`, `tools/js/daemon/`, and `tools/js/static/`)
* **Unified Static Serving**: All workstation HTTP servers (`tools/forge.py`, `tools/scope.py`, `tools/host.py`, and review/tracker sub-servers) serve `/js/*` and `/static/*` from the canonical `js/` root via `http_static.py` with `Cache-Control: no-cache` and strict path-traversal containment.
* **Zero Inline JS & Zero HTML Event Attributes**: Jinja2 workstation templates (`.html.j2`) MUST contain:
  - **Zero** inline executable `<script>` logic blocks.
  - **Zero** inline HTML event handler attributes (`onclick="..."`, `onchange="..."`, `oninput="..."`, `onsubmit="..."`, etc.).
  - *(Exemption)*: Standalone single-file offline manufacturing artifacts such as `provider/templates/ibom.html.j2` that must open directly from `file://` with zero network/server dependencies remain self-contained.
* **Typed JSON Boot Payloads**: Server-rendered configuration must be serialized strictly via `<script id="app-boot-config" type="application/json">{{ boot_config | tojson }}</script>` (plus an optional `<script type="importmap">` JSON block) and parsed via `readBootConfig(ctx)` inside `<script type="module" src="/js/<app>/main.js"></script>`.

---

## 2. Strict Zero-Globals & `RuntimeContext` Accessor Mandate

* **No Ambient Browser Globals**: `.oxlintrc.json` explicitly omits `"browser"` from `env` and enforces `eslint(no-undef)` with `--deny-warnings`. Undeclared browser globals (`window`, `document`, `localStorage`, `sessionStorage`, `navigator`, `location`, `history`, `fetch`, `requestAnimationFrame`, `ResizeObserver`, `CustomEvent`, etc.) are compile/lint errors everywhere outside `runtime_context.js`.
* **Single Controlled Boundary (`js/core/runtime_context.js`)**:
  - `js/core/runtime_context.js` is the **sole** module permitted to touch `globalThis` (`/* oxlint-disable no-undef */` is restricted exclusively to that file).
  - Browser entrypoints (`main.js` / `*_app.js`) obtain the frozen platform capability object once via `getRuntimeContext()` and pass `ctx` explicitly into module constructors and helper functions.
  - Unit tests construct deterministic, isolated test doubles via `createMockRuntimeContext(overrides)` without mutating Node's `globalThis`.
* **Zero `window.*` Exports**: Modules must NEVER attach functions, singletons, or state onto `window.*` or `globalThis.*`. Bind UI interactions exclusively via `addEventListener` or delegated `data-action` handlers (`onDelegate`).

---

## 3. Code Style & Cleanliness Parity with Python & Rust

JavaScript modules are held to the exact same engineering rigor as Python and Rust production code:

* **Comprehensive JSDoc Documentation**: Write clear JSDoc (`/** ... */`) docstrings with `@param` and `@returns` annotations for all classes, methods, exported functions, and public properties.
* **Module-Level `ALL_CAPS` Constants & Frozen Enums**: Assign constant values (thresholds, tolerances, shader constants, keycodes, CSS class tokens, storage keys) to module-level `ALL_CAPS` `const` bindings rather than embedding inline magic numbers or strings. Represent structured mode/type sets with `Object.freeze({ ... })`.
* **Explicit Named Parameter Objects**: Instantiate controllers, renderers, and stateful services with explicit named options objects (`new PcbRenderer({ three: THREE, materialFactory })` or `initViewport({ ctx, canvas, onResize })`) rather than long positional argument lists or opaque object spreading.
* **No Dead Code or Backward-Compatibility Shims**: Unused variables, unreferenced exports, dead branches, unused function parameters, and legacy alias wrappers are strictly prohibited and rejected by `oxlint --deny-warnings` and `python tools/validate_js.py`.
* **Error Handling Guardrails**: Validate inputs, nullability, and array bounds explicitly rather than wrapping logic in generic `try/catch` blocks. Reserve `try/catch` strictly for external I/O boundaries (`ctx.fetch`, `JSON.parse` on untrusted payloads, `WebSocket`, storage quota errors) and never silently ignore errors with empty `catch {}` blocks.
* **Modifiable Vendor Code Compliance**: Any modifiable vendor ES modules checked into the repository (such as Three.js addons under `js/static/vendor/three/addons/**/*.js`) MUST adhere to the exact same zero-globals rules, JSDoc style, `ALL_CAPS` constants, and `oxlint --deny-warnings` checks as first-party code.

---

## 4. Full Diff View Visibility & Cross-Repository Synchronization

* **Unminified Source & Zero `.js` VCS Exclusions**: Ship readable, unminified ES modules across `js/` (including `js/static/vendor/three/three.module.js` and `js/static/vendor/three/addons/*.js`). `GitEngine` (`provider/vcs/git_engine.py` / `tools/vcs/git_engine.py`) must maintain **zero `.js` or `.mjs` path exclusions** so every JavaScript module—including the 3D engine—is inspectable and reviewable line-by-line in Forge Diff View and Code Review.
* **Byte-for-Byte Cross-Repo Parity**: Shared workstation modules (`js/core/`, `js/diff/`, `js/vcs/`, `js/review/`, `js/tracker/`) and their corresponding unit test suites (`shared_*.test.mjs`, `runtime_context.test.mjs`) MUST remain byte-for-byte identical between `hardware/js/` and `firmware/tools/js/`. Any bug fix or enhancement in one repository must be mirrored immediately to the other.

---

## 5. Retina HiDPI, Crisp Typography & 60–120 FPS CAD/PCB/Sim Viewport

* **Never Use Document-Level CSS `zoom`**: Never set `document.documentElement.style.zoom` (which causes browsers to render `<canvas>` backing stores at fractional logical sizes and bilinearly upscale them). Drive HUD font and control scaling strictly via `--ui-scale` CSS custom properties (`js/core/ui_scale.js`).
* **Native Physical `devicePixelRatio` Backing Stores**:
  - Configure `THREE.WebGLRenderer` with `renderer.setPixelRatio(Math.min(ctx.devicePixelRatio || 1, 2))` and `preserveDrawingBuffer: false`.
  - Size 2D HUD/ruler/markup `<canvas>` backing stores to `Math.round(cssWidth * dpr)` × `Math.round(cssHeight * dpr)` and apply `ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0)` so vector strokes and text render crisp on Retina displays while hit-testing stays in CSS coordinates.
  - Update fat-line shaders (`LineSegments2` / `LineMaterial.resolution`) from `renderer.getDrawingBufferSize(vec2)` (physical pixels), never logical CSS pixels.
* **Coalesced Single-RAF Demand Rendering**: Never run an unconditional 60 Hz render loop when idle, and never invoke `renderer.render(...)` synchronously inside pointermove handlers or run offscreen `gl.readPixels` GPU stalls on hover. Schedule all redraws through a coalesced `Viewport.requestRender()` gate executing at most once per display refresh.
* **GPU Instancing, Standalone `.glsl` Shader Files & World-Space Simulation Voxels**:
  - Store all custom WebGL vertex and fragment shaders in dedicated `.glsl` files (`js/scope/shaders/*.vert.glsl`, `*.frag.glsl`) imported directly via ES module `import` rather than embedding inline GLSL template strings inside `.js` modules (`http_static.py` serves `.glsl` imports as ES modules in browsers, and `tests/js/glsl_loader.mjs` registers `node:module` hooks in unit tests).
  - Render PCB copper pads, traces, vias, and silkscreen glyphs via batched GPU `InstancedMesh` / SDF shaders (`js/scope/pcb_renderer.js`, $\le 8$ draw calls total) paired with an $O(1)$ uniform 2D spatial hash grid (`js/scope/pcb_spatial_index.js`) for sub-`0.1 ms` CPU hover/click picking.
  - Stream undecimated binary `float32` simulation particle frames (`positions_b64`) and render all fluid particles in a single `THREE.InstancedMesh` draw call (`js/scope/sim_renderer.js`) sized to exact world-space SPH grid spacing (`BoxGeometry(voxel_dx_mm, voxel_dx_mm, voxel_dx_mm)`).

---

## 6. Isolated Parallel Unit Testing & Pre-Commit Validation

* **Test Isolation**: All JavaScript unit tests live in `tests/js/*.test.mjs` (`hardware`) and `tools/tests/js/*.test.mjs` (`firmware`), completely separated from production modules under `js/`.
* **Parallel Execution**: Run the Node built-in test runner concurrently across CPU cores:
  ```bash
  node --test --test-concurrency=$(nproc 2>/dev/null || sysctl -n hw.ncpu || echo 4) tests/js/*.test.mjs
  ```
* **Functional Behavioral Testing Mandate**: JavaScript unit tests MUST exercise real module execution, DOM interactions (via `createMockRuntimeContext()`), binary decoding, camera math, spatial indexing, diff rendering, and state transitions. Never write tests that merely read `.js` or `.html.j2` files as strings to assert regex/token presence.
* **Unified Validator (`validate_js.py`)**: Always run `python tools/validate_js.py` (`hardware`) or `./tools/verify.sh` (`firmware`) before concluding any task to enforce `oxlint --deny-warnings`, zero-globals compliance outside `runtime_context.js`, zero inline template `on*="..."` attributes, valid JSON boot/importmap blocks, and parallel `node --test` pass rates.
