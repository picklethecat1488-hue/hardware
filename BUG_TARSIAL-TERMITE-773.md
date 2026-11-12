# 🟢 `[BUG-TARSIAL-TERMITE-773]` CAD and PCB targets fail to render due to :cad target parsing error, PCB frustum backface culling, viewer resize bug, and scope.lock reuse block

- **UUID**: `6a4a5316-242c-4b8f-b520-73300d26e1ff`
- **ID**: `BUG-TARSIAL-TERMITE-773`
- **Status**: `RESOLVED`
- **Severity**: `CRITICAL`
- **Category**: `CAD`
- **Component**: `scope`
- **Created**: `2026-11-12 18:51:22 UTC`
- **Resolved**: `2026-11-12 20:54:36 UTC`

#### Description

1. parse_target_string does not strip ':cad' or '/cad' suffixes, setting subassembly='cad' and failing with ValueError: 'cad' is not a valid Section (HTTP 500) on all *:cad targets. 2. setupPcbOrientation inverts OrthographicCamera top/bottom (cam.top < 0), flipping NDC winding to CW while Three.js WebGLRenderer keeps gl.frontFace(gl.CCW), backface-culling 100% of PCB top surfaces. 3. resizeViewport calls viewer.resize(w, h) (which resets zoom to 1.0 and ignores dimensions) instead of viewer.resizeCadView(w, 0, h, true), and unrendered viewer getters throw TypeError. 4. tools/scope.py exits early without switching targets when build/scope.lock is active, and Dashboard _handle_run_command does not propagate sys.executable PATH.

#### Attached Commits

- `2e54b87d`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:6804407a --> Verify CAD target loads and renders cleanly with :cad suffix | `python tools/scope.py cat_fountain/product:cad`
- [ ] <!-- task:615d421d --> Verify PCB target renders non-culled top/bottom copper, components, and accurate entity picking | `python tools/scope.py carrier_board/carrier_board:pcb`

#### Resolution Notes

Fixed :cad//cad suffix parsing in parse_target_string and normalized mode specifiers in ScopeGeometryPipeline, replaced negative OrthographicCamera frustum with Y-mirrored rootGroup.scale.set(1, -1, 1) to eliminate WebGL backface culling while preserving KiCad +Y downward orientation and accurate picking/net highlights, prioritized resizeCadView over zoom-resetting viewer.resize, guarded unrendered viewer getters, and updated ScopeTool/Dashboard demo runner to cleanly switch running targets.
