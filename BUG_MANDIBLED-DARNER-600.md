# 🔴 `[BUG-MANDIBLED-DARNER-600]` [scope] Spout laminar lip splash at 3400 RPM

- **UUID**: `a454bd8c-72ce-40bb-889a-7ba5b217a0e6`
- **ID**: `BUG-MANDIBLED-DARNER-600`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `SIMULATION`
- **Component**: `cat_fountain`
- **Created**: `2026-11-16 02:24:14 UTC`

#### Description

Observed minor droplet shear along outer spout fillet during nominal SPH pumping cycle.

#### Reproduction Steps

1. python tools/scope.py cat_fountain/product --mode simulate

#### Execution / Console Logs

```text
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 13:16:38 [INFO] scope: Loading geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-14 13:16:38 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-14 13:16:43 [INFO] scope.pipeline: Geometry carrier_board/battery_cover [CAD] tessellated in 4.35s (1 parts, 1 instances, bounds: {'xmin': -31.899999618530273, 'xmax': 10.399999618530273, 'ymin': -30.399999618530273, 'ymax': 23.899999618530273, 'zmin': 0.0, 'zmax': 7.0})
2026-11-14 13:16:43 [INFO] scope.pipeline: Persisted disk cache for carrier_board/battery_cover [CAD] in 4.35s (0.01 MB compressed)
2026-11-14 13:16:43 [INFO] scope: Successfully loaded geometry for carrier_board/battery_cover [CAD] in 4.35s
2026-11-14 13:16:43 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:43] "GET /api/scope/load?project=carrier_board&target=battery_cover&mode=CAD HTTP/1.1" 200 -
2026-11-14 13:16:57 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-14 13:16:57 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.009s (0.03 MB compressed)
2026-11-14 13:16:57 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:57] "GET /api/scope/load?project=carrier_board&target=carrier_board&mode=PCB HTTP/1.1" 200 -
2026-11-14 13:18:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:18:45] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:19:17 [INFO] scope: Loading geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-14 13:19:17 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-14 13:19:49 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [CAD] tessellated in 32.14s (8 parts, 5860 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.4500000238418582, 'zmax': 9.35})
2026-11-14 13:19:49 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [CAD] in 32.51s (2.89 MB compressed)
2026-11-14 13:19:49 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [CAD] in 32.52s
2026-11-14 13:19:50 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:19:50] "GET /api/scope/load?project=carrier_board&target=carrier_board&mode=CAD HTTP/1.1" 200 -
2026-11-14 13:21:32 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:21:32] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:22:22 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:22:22] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:22:58 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:22:58] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:23:09 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-14 13:23:09 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
face 46 ignored
2026-11-14 13:23:23 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 14.29s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-14 13:23:23 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 14.40s (1.32 MB compressed)
2026-11-14 13:23:23 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 14.40s
2026-11-14 13:23:23 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:23:23] "GET /api/scope/load?project=cat_fountain&target=product&mode=CAD HTTP/1.1" 200 -
2026-11-14 13:23:43 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-14 13:23:43 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.010s (1.32 MB compressed)
2026-11-14 13:23:43 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:23:43] "GET /api/scope/load?project=cat_fountain&target=product&mode=SIMULATE HTTP/1.1" 200 -
2026-11-14 13:23:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:23:45] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-14 13:24:32 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:24:32] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:24:34 [INFO] scope: Loading geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-14 13:24:34 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
face 46 ignored
2026-11-14 13:24:36 [INFO] scope.pipeline: Geometry cat_fountain/product [DIAGRAM] tessellated in 2.27s (2 parts, 16 instances, bounds: {'xmin': -134.10793296424515, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 128.61706314291132, 'zmin': -50.0, 'zmax': 197.60000038146973})
2026-11-14 13:24:36 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [DIAGRAM] in 2.38s (1.37 MB compressed)
2026-11-14 13:24:36 [INFO] scope: Successfully loaded geometry for cat_fountain/product [DIAGRAM] in 2.38s
2026-11-14 13:24:36 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:24:36] "GET /api/scope/load?project=cat_fountain&target=product&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 13:25:01 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:25:01] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:25:09 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-14 13:25:09 [INFO] scope: Delivered cached geometry for cat_fountain/wiring [DIAGRAM] in 0.009s (2.37 MB compressed)
2026-11-14 13:25:09 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:25:09] "GET /api/scope/load?project=cat_fountain&target=wiring&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 13:25:35 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:25:35] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-14 13:26:06 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-14 14:39:28 [INFO] scope: Starting Scope workstation in foreground (PID 84229)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 84229).
2026-11-14 14:39:28 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 14:39:28 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.03 MB compressed)
2026-11-14 14:39:28 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.00s
2026-11-14 17:17:22 [INFO] scope: Starting Scope workstation in foreground (PID 82350)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 82350).
2026-11-14 17:17:22 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 17:17:22 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-14 17:18:49 [INFO] scope: Starting Scope workstation in foreground (PID 93918)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 93918).
2026-11-14 17:18:49 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 17:18:49 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-14 17:21:10 [INFO] scope: Starting Scope workstation in foreground (PID 11443)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 11443).
2026-11-14 17:21:10 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 17:21:10 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-14 17:29:39 [INFO] scope: Starting Scope workstation in foreground (PID 83369)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 83369).
2026-11-14 17:29:39 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 17:29:39 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.08 MB compressed)
2026-11-14 17:29:39 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.00s
2026-11-14 17:57:57 [INFO] scope: Starting Scope workstation in foreground (PID 56142)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 56142).
2026-11-14 17:57:57 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 17:57:57 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.005s (0.08 MB compressed)
2026-11-14 17:57:57 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.01s
2026-11-14 18:10:15 [INFO] scope: Starting Scope workstation in foreground (PID 72093)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 72093).
2026-11-14 18:10:15 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 18:10:15 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.003s (0.08 MB compressed)
2026-11-14 18:10:15 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.01s
2026-11-14 18:26:46 [INFO] scope: Starting Scope workstation in foreground (PID 13280)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 13280).
2026-11-14 18:26:46 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 18:26:46 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.08 MB compressed)
2026-11-14 18:26:46 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.01s
2026-11-14 18:55:34 [INFO] scope: Starting Scope workstation in foreground (PID 73162)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 73162).
2026-11-14 18:55:34 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 18:55:34 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.08 MB compressed)
2026-11-14 18:55:34 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.00s
2026-11-14 18:59:46 [INFO] scope: Starting Scope workstation in foreground (PID 78638)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM (PID 78638).
2026-11-14 18:59:46 [INFO] scope: Background pre-warming geometry for cat_fountain/wiring [DIAGRAM]...
2026-11-14 18:59:46 [INFO] scope.pipeline: Disk cache hit for cat_fountain/wiring [DIAGRAM] in 0.031s (2.37 MB compressed)
2026-11-14 18:59:46 [INFO] scope: Background pre-warming completed for cat_fountain/wiring in 0.05s
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 18:59:47 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-14 18:59:47 [INFO] scope: Delivered cached geometry for cat_fountain/wiring [DIAGRAM] in 0.000s (2.37 MB compressed)
2026-11-14 18:59:47 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 18:59:47] "GET /api/scope/load?project=cat_fountain&target=wiring&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 19:00:16 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-14 19:01:18 [INFO] scope: Starting Scope workstation in foreground (PID 80007)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=DIAGRAM (PID 80007).
2026-11-14 19:01:19 [INFO] scope: Background pre-warming geometry for cat_fountain/product [DIAGRAM]...
2026-11-14 19:01:19 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /?project=cat_fountain&target=product&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 19:01:20 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:20] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:01:21] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 19:01:21 [INFO] scope: Loading geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-14 19:01:38 [INFO] scope: Starting Scope workstation in foreground (PID 80251)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 80251).
2026-11-14 19:01:38 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-14 19:01:38 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.08 MB compressed)
2026-11-14 19:01:38 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.01s
2026-11-14 19:07:44 [INFO] scope: Starting Scope workstation in foreground (PID 83388)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=DIAGRAM (PID 83388).
2026-11-14 19:07:44 [INFO] scope: Background pre-warming geometry for cat_fountain/product [DIAGRAM]...
2026-11-14 19:07:44 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [DIAGRAM] in 0.012s (1.37 MB compressed)
2026-11-14 19:07:44 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /?project=cat_fountain&target=product&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 19:07:45 [INFO] scope: Loading geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-14 19:07:45 [INFO] scope: Delivered cached geometry for cat_fountain/product [DIAGRAM] in 0.000s (1.37 MB compressed)
2026-11-14 19:07:45 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:07:45] "GET /api/scope/load?project=cat_fountain&target=product&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-14 19:07:53 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-14 19:08:36 [INFO] scope: Starting Scope workstation in foreground (PID 83965)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 83965).
2026-11-14 19:08:36 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-14 19:08:36 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.012s (1.32 MB compressed)
2026-11-14 19:08:36 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 19:08:37 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-14 19:08:37 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-14 19:08:37 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:37] "GET /api/scope/load?project=cat_fountain&target=product&mode=SIMULATE HTTP/1.1" 200 -
2026-11-14 19:08:38 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:08:38] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-14 19:08:55 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-14 19:09:30 [INFO] scope: Starting Scope workstation in foreground (PID 84502)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=CAD (PID 84502).
2026-11-14 19:09:31 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [CAD]...
2026-11-14 19:09:31 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:09:31] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 19:09:31 [INFO] scope: Loading geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-14 19:10:04 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [CAD] tessellated in 33.07s (8 parts, 5860 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.4500000238418582, 'zmax': 9.35})
2026-11-14 19:10:04 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [CAD] in 33.43s (2.89 MB compressed)
2026-11-14 19:10:04 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [CAD] in 32.70s
2026-11-14 19:10:04 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 33.43s
2026-11-14 19:10:04 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:10:04] "GET /api/scope/load?project=carrier_board&target=carrier_board&mode=CAD HTTP/1.1" 200 -
2026-11-14 19:10:19 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-14 19:10:19 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.004s (0.08 MB compressed)
2026-11-14 19:10:19 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:10:19] "GET /api/scope/load?project=carrier_board&target=carrier_board&mode=PCB HTTP/1.1" 200 -
2026-11-14 19:10:24 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-14 19:12:10 [INFO] scope: Starting Scope workstation in foreground (PID 85976)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=product&subassembly=&mode=PCB (PID 85976).
2026-11-14 19:12:10 [INFO] scope: Background pre-warming geometry for carrier_board/product [PCB]...
2026-11-14 19:12:10 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [PCB] (subassembly: None, step: None)...
2026-11-14 19:12:10 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:10] "GET /?project=carrier_board&target=product&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-14 19:12:10 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:10] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 19:12:10 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:10] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 19:12:10 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:10] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:12:11 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:11] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:12:12 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:12] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:12:12 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:12] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:12:12 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:12] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-14 19:12:12 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:12] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-14 19:12:12 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:12] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-14 19:12:12 [INFO] scope: Loading geometry for carrier_board/product [PCB] (subassembly: None, step: None)...
2026-11-14 19:12:19 [INFO] scope.pipeline: Geometry carrier_board/product [PCB] tessellated in 9.68s (1 parts, 1 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -0.755, 'zmax': 0.7549999904632568})
2026-11-14 19:12:19 [INFO] scope.pipeline: Persisted disk cache for carrier_board/product [PCB] in 9.68s (0.03 MB compressed)
2026-11-14 19:12:19 [INFO] scope: Background pre-warming completed for carrier_board/product in 9.68s
2026-11-14 19:12:19 [INFO] scope: Successfully loaded geometry for carrier_board/product [PCB] in 7.29s
2026-11-14 19:12:19 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 19:12:19] "GET /api/scope/load?project=carrier_board&target=product&mode=PCB HTTP/1.1" 200 -
2026-11-14 19:13:36 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-15 01:34:28 [INFO] scope: Starting Scope workstation in foreground (PID 13604)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 13604).
2026-11-15 01:34:28 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-15 01:34:28 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.08 MB compressed)
2026-11-15 01:34:28 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.01s
2026-11-15 16:04:48 [INFO] scope: Starting Scope workstation in foreground (PID 63742)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 63742).
2026-11-15 16:04:48 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-15 16:04:48 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-15 16:17:14 [INFO] scope: Starting Scope workstation in foreground (PID 71750)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 71750).
2026-11-15 16:17:14 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-15 16:17:14 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.08 MB compressed)
2026-11-15 16:17:14 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.00s
2026-11-15 16:44:11 [INFO] scope: Starting Scope workstation in foreground (PID 90365)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 90365).
2026-11-15 16:44:12 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-15 16:44:12 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.004s (0.08 MB compressed)
2026-11-15 16:44:12 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.01s
2026-11-15 18:21:03 [INFO] scope: Starting Scope workstation in foreground (PID 22961)...
2026-11-15 18:21:03 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:03] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /?project=exhaust_manifolds&target=part_positions&mode=CAD HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /static/common.css HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: Loading geometry for exhaust_manifolds/part_positions [CAD] (subassembly: None, step: None)...
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /static/scope-favicon.ico HTTP/1.1" 200 -
2026-11-15 18:21:12 [INFO] scope: Delivered cached geometry for exhaust_manifolds/part_positions [CAD] in 0.005s (3.16 MB compressed)
2026-11-15 18:21:12 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:21:12] "GET /api/scope/load?project=exhaust_manifolds&target=part_positions&mode=CAD HTTP/1.1" 200 -
2026-11-15 18:22:05 [INFO] scope: Loading geometry for cat_fountain/bowl [CAD] (subassembly: None, step: None)...
2026-11-15 18:22:05 [INFO] scope: Delivered cached geometry for cat_fountain/bowl [CAD] in 0.010s (0.87 MB compressed)
2026-11-15 18:22:05 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:22:05] "GET /api/scope/load?project=cat_fountain&target=bowl&mode=CAD HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /?project=cat_fountain&target=bowl&mode=CAD HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /static/common.css HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/pcb_renderer.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/ruler_tool.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/viewport.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/dom.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/static/vendor/three/addons/lines/LineSegments2.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/static/vendor/three/addons/lines/LineSegmentsGeometry.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/fuzzy_search.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/static/vendor/three/three.module.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/static/vendor/three/addons/lines/LineMaterial.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/core/sanitize.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/static/vendor/three/addons/controls/OrbitControls.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/pcb_spatial_index.js HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/floor_grid.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/fluid_particle.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/floor_grid.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/fluid_particle.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/pad_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/trace_capsule.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/via_sdf.frag.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/pad_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/via_sdf.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /js/scope/shaders/trace_capsule.vert.glsl HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /static/scope-favicon.ico HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-15 18:23:01 [INFO] scope: Loading geometry for cat_fountain/bowl [CAD] (subassembly: None, step: None)...
2026-11-15 18:23:01 [INFO] scope: Delivered cached geometry for cat_fountain/bowl [CAD] in 0.000s (0.87 MB compressed)
2026-11-15 18:23:01 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:01] "GET /api/scope/load?project=cat_fountain&target=bowl&mode=CAD HTTP/1.1" 200 -
2026-11-15 18:23:07 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-15 18:23:07 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.006s (0.08 MB compressed)
2026-11-15 18:23:07 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:07] "GET /api/scope/load?project=carrier_board&target=carrier_board&mode=PCB HTTP/1.1" 200 -
2026-11-15 18:23:37 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-15 18:23:37 [INFO] scope: Delivered cached geometry for cat_fountain/wiring [DIAGRAM] in 0.006s (2.37 MB compressed)
2026-11-15 18:23:37 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:37] "GET /api/scope/load?project=cat_fountain&target=wiring&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-15 18:23:50 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-15 18:23:50 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.003s (1.32 MB compressed)
2026-11-15 18:23:50 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:50] "GET /api/scope/load?project=cat_fountain&target=product&mode=SIMULATE HTTP/1.1" 200 -
2026-11-15 18:23:53 [INFO] scope: 127.0.0.1 - - [15/Nov/2026 18:23:53] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
```

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `image/png` | [snapshot.png](attachments/BUG-MANDIBLED-DARNER-600/snapshot.png) | 3D CAD/PCB annotated WebGL viewport snapshot |
| `text/plain` | [scope.log](attachments/BUG-MANDIBLED-DARNER-600/scope.log) | Scope workstation execution logs |
