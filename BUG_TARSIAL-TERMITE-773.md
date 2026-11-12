# 🔴 `[BUG-TARSIAL-TERMITE-773]` CAD and PCB targets fail to render due to :cad target parsing error, PCB frustum backface culling, viewer resize bug, and scope.lock reuse block

- **UUID**: `6a4a5316-242c-4b8f-b520-73300d26e1ff`
- **ID**: `BUG-TARSIAL-TERMITE-773`
- **Status**: `OPEN`
- **Severity**: `CRITICAL`
- **Category**: `CAD`
- **Component**: `scope`

#### Description

1. parse_target_string does not strip ':cad' or '/cad' suffixes, setting subassembly='cad' and failing with ValueError: 'cad' is not a valid Section (HTTP 500) on all *:cad targets. 2. setupPcbOrientation inverts OrthographicCamera top/bottom (cam.top < 0), flipping NDC winding to CW while Three.js WebGLRenderer keeps gl.frontFace(gl.CCW), backface-culling 100% of PCB top surfaces. 3. resizeViewport calls viewer.resize(w, h) (which resets zoom to 1.0 and ignores dimensions) instead of viewer.resizeCadView(w, 0, h, true), and unrendered viewer getters throw TypeError. 4. tools/scope.py exits early without switching targets when build/scope.lock is active, and Dashboard _handle_run_command does not propagate sys.executable PATH.
