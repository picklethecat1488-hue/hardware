# 🔴 `[BUG-JUMPING-APHID-570]` [carrier_board/carrier_board] Defect in PCB view

- **UUID**: `f616833a-1db1-4787-8936-4c87b44adb84`
- **ID**: `BUG-JUMPING-APHID-570`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `PCB`
- **Component**: `carrier_board`
- **Created**: `2026-11-12 20:49:35 UTC`

#### Description

Silkscreen text is mirrored horizontally (weird)?

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board:pcb

#### Execution / Console Logs

```text
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 16:54:42 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 16:54:42 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-11 16:54:58 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 16:55:23 [INFO] scope: Starting Scope workstation in foreground (PID 1549)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=product&subassembly=cad&mode=CAD (PID 1549).
2026-11-11 16:55:23 [INFO] scope: Background pre-warming geometry for carrier_board/product [CAD]...
2026-11-11 16:55:23 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [CAD] (subassembly: cad, step: None)...
2026-11-11 16:55:23 [WARNING] scope: Background pre-warming error for carrier_board/product: 'cad' is not a valid Section
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /?project=carrier_board&target=product&subassembly=cad&mode=CAD HTTP/1.1" 200 -
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 16:55:23 [INFO] scope: Loading geometry for carrier_board/product [CAD] (subassembly: cad, step: None)...
2026-11-11 16:55:23 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [CAD] (subassembly: cad, step: None)...
2026-11-11 16:55:23 [ERROR] scope: Failed to load geometry for /api/scope/load?project=carrier_board&target=product&subassembly=cad&mode=CAD after 0.01s: 'cad' is not a valid Section
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 545, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 171, in resolve
    target_info = self.parse(raw_target, action)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 72, in parse
    action = Section(action_str) if action_str else default_action
             ~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 727, in __call__
    return cls.__new__(cls, value)
           ~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 1204, in __new__
    raise ve_exc
ValueError: 'cad' is not a valid Section

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 278, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 547, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 171, in resolve
    target_info = self.parse(raw_target, action)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 72, in parse
    action = Section(action_str) if action_str else default_action
             ~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 727, in __call__
    return cls.__new__(cls, value)
           ~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 1204, in __new__
    raise ve_exc
ValueError: 'cad' is not a valid Section
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 16:55:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:23] "GET /api/scope/load?project=carrier_board&target=product&subassembly=cad&mode=CAD HTTP/1.1" 500 -
2026-11-11 16:55:29 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:29] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 16:55:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:30] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 16:55:30 [INFO] scope: Loading geometry for carrier_board/product [CAD] (subassembly: cad, step: None)...
2026-11-11 16:55:30 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [CAD] (subassembly: cad, step: None)...
2026-11-11 16:55:30 [ERROR] scope: Failed to load geometry for /api/scope/load?project=carrier_board&target=product&subassembly=cad&mode=CAD after 0.00s: 'cad' is not a valid Section
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 545, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 171, in resolve
    target_info = self.parse(raw_target, action)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 72, in parse
    action = Section(action_str) if action_str else default_action
             ~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 727, in __call__
    return cls.__new__(cls, value)
           ~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 1204, in __new__
    raise ve_exc
ValueError: 'cad' is not a valid Section

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 278, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 547, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 171, in resolve
    target_info = self.parse(raw_target, action)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 72, in parse
    action = Section(action_str) if action_str else default_action
             ~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 727, in __call__
    return cls.__new__(cls, value)
           ~~~~~~~~~~~^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/enum.py", line 1204, in __new__
    raise ve_exc
ValueError: 'cad' is not a valid Section
2026-11-11 16:55:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:30] "GET /api/scope/load?project=carrier_board&target=product&subassembly=cad&mode=CAD HTTP/1.1" 500 -
2026-11-11 16:55:34 [INFO] scope: Loading geometry for carrier_board/product [CAD] (subassembly: None, step: None)...
2026-11-11 16:55:34 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [CAD] (subassembly: None, step: None)...
2026-11-11 16:55:45 [INFO] scope.pipeline: Geometry carrier_board/product [CAD] tessellated in 10.84s (6 parts, 6 instances, bounds: {'xmin': -33.5, 'xmax': 36.0, 'ymin': -48.5, 'ymax': 87.75, 'zmin': -8.300000190734863, 'zmax': 17.8})
2026-11-11 16:55:45 [INFO] scope.pipeline: Persisted disk cache for carrier_board/product [CAD] in 10.89s (0.56 MB compressed)
2026-11-11 16:55:45 [INFO] scope: Successfully loaded geometry for carrier_board/product [CAD] in 10.89s
2026-11-11 16:55:45 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:55:45] "GET /api/scope/load?project=carrier_board&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 16:55:50 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 16:57:21 [INFO] scope: Starting Scope workstation in foreground (PID 2732)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM (PID 2732).
2026-11-11 16:57:22 [INFO] scope: Background pre-warming geometry for cat_fountain/wiring [DIAGRAM]...
2026-11-11 16:57:22 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-11 16:57:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:57:22] "GET /?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-11 16:57:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:57:22] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 16:57:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:57:22] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 16:57:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:57:22] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 16:57:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:57:22] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 16:57:22 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-11 16:57:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:57:22] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 16:58:16 [INFO] scope.pipeline: Geometry cat_fountain/wiring [DIAGRAM] tessellated in 54.18s (2 parts, 317 instances, bounds: {'xmin': -127.0, 'xmax': 122.0, 'ymin': -113.0, 'ymax': 112.0, 'zmin': -0.10000010000000134, 'zmax': 0.10000010000000134})
2026-11-11 16:58:16 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/wiring [DIAGRAM] in 54.40s (2.37 MB compressed)
2026-11-11 16:58:16 [INFO] scope: Background pre-warming completed for cat_fountain/wiring in 54.40s
2026-11-11 16:58:16 [INFO] scope: Successfully loaded geometry for cat_fountain/wiring [DIAGRAM] in 53.83s
2026-11-11 16:58:16 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:58:16] "GET /api/scope/load?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-11 16:59:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:06] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 16:59:09 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 16:59:39 [INFO] scope: Starting Scope workstation in foreground (PID 3982)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 3982).
2026-11-11 16:59:39 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-11 16:59:39 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 16:59:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:40] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 16:59:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:40] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 16:59:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:40] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 16:59:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:40] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 16:59:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:40] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 16:59:40 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 16:59:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:40] "GET /api/scope/projects HTTP/1.1" 200 -
face 46 ignored
2026-11-11 16:59:54 [INFO] scope.pipeline: Geometry cat_fountain/product [SIMULATE] tessellated in 14.75s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 16:59:54 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [SIMULATE] in 14.86s (1.32 MB compressed)
2026-11-11 16:59:54 [INFO] scope: Background pre-warming completed for cat_fountain/product in 14.86s
2026-11-11 16:59:54 [INFO] scope: Successfully loaded geometry for cat_fountain/product [SIMULATE] in 14.28s
2026-11-11 16:59:54 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:54] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
[2m2026-11-12T00:59:55.040572Z[0m [33m WARN[0m [2mre_log_encoding::rrd::frames[0m[2m:[0m Found data stream with Rerun version 0.42.0 which is newer than the local Rerun version (0.36.2). This file may contain data that is not compatible with this version of Rerun. Consider updating Rerun.
[2m2026-11-12T00:59:55.041378Z[0m [33m WARN[0m [2mre_sorbet::migrations[0m[2m:[0m Found Sorbet version 'v0.1.4' that is newer then current supported version 'v0.1.3'. Consider updating Rerun!
[2m2026-11-12T00:59:55.041397Z[0m [33m WARN[0m [2mre_sorbet::sorbet_schema[0m[2m:[0m Sorbet batch version mismatch. Expected 0.1.3, got "0.1.4"
2026-11-11 16:59:59 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:59:59] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-11 17:01:10 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:01:10] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 17:01:21 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 17:06:52 [INFO] scope: Starting Scope workstation in foreground (PID 8222)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 8222).
2026-11-11 17:06:53 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:06:53] "GET / HTTP/1.1" 200 -
2026-11-11 17:06:53 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:06:53] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 17:06:53 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:06:53] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 17:06:53 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:06:53] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 17:06:53 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:06:53] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 17:06:53 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:06:53] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 17:07:05 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 17:07:05 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.007s (1.32 MB compressed)
2026-11-11 17:07:05 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:07:05] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 17:07:05 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:07:05] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-11 17:08:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:08:18] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 17:08:21 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 17:08:21 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 17:08:55 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 17:09:57 [INFO] scope: Starting Scope workstation in foreground (PID 9643)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 9643).
2026-11-11 17:09:57 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:09:57] "GET / HTTP/1.1" 200 -
2026-11-11 17:09:57 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:09:57] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 17:09:57 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:09:57] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 17:09:57 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:09:57] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 17:09:57 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:09:57] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 17:09:57 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:09:57] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 17:10:03 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 17:10:03 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 17:10:38 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 35.47s (8 parts, 5860 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.405000023841858, 'zmax': 9.305})
2026-11-11 17:10:38 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [PCB] in 35.81s (2.87 MB compressed)
2026-11-11 17:10:38 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 35.81s
2026-11-11 17:10:39 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:10:39] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 17:12:02 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 17:12:02] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 17:12:04 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 17:30:23 [INFO] scope: Starting Scope workstation in foreground (PID 20638)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 20638).
2026-11-11 17:30:23 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 17:30:23 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.178s (2.87 MB compressed)
2026-11-11 17:30:23 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.18s
2026-11-11 17:36:45 [INFO] scope: Starting Scope workstation in foreground (PID 23167)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 23167).
2026-11-11 17:36:45 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 17:36:45 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 17:47:21 [INFO] scope: Starting Scope workstation in foreground (PID 30263)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 30263).
2026-11-11 17:47:21 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 17:47:21 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.174s (2.87 MB compressed)
2026-11-11 17:47:21 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.18s
2026-11-11 17:48:17 [INFO] scope: Starting Scope workstation in foreground (PID 30635)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 30635).
2026-11-11 17:48:17 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 17:48:17 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.175s (2.87 MB compressed)
2026-11-11 17:48:17 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.18s
2026-11-11 17:54:50 [INFO] scope: Starting Scope workstation in foreground (PID 33264)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 33264).
2026-11-11 17:54:50 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 17:54:50 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.221s (2.87 MB compressed)
2026-11-11 17:54:50 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.23s
2026-11-11 17:57:46 [INFO] scope: Starting Scope workstation in foreground (PID 34408)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 34408).
2026-11-11 17:57:46 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 17:57:47 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.141s (2.87 MB compressed)
2026-11-11 17:57:47 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-11 18:23:05 [INFO] scope: Starting Scope workstation in foreground (PID 39188)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 39188).
2026-11-11 18:23:05 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 18:23:05 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 19:46:48 [INFO] scope: Starting Scope workstation in foreground (PID 44799)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 44799).
2026-11-11 19:46:48 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 19:46:48 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 21:01:33 [INFO] scope: Starting Scope workstation in foreground (PID 46410)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 46410).
2026-11-11 21:01:34 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 21:01:34 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.145s (2.87 MB compressed)
2026-11-11 21:01:34 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.15s
2026-11-11 21:19:06 [INFO] scope: Starting Scope workstation in foreground (PID 47157)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 47157).
2026-11-11 21:19:06 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 21:19:06 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.147s (2.87 MB compressed)
2026-11-11 21:19:06 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.15s
2026-11-11 21:52:24 [INFO] scope: Starting Scope workstation in foreground (PID 51411)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 51411).
2026-11-11 21:52:24 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 21:52:24 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 23:03:28 [INFO] scope: Starting Scope workstation in foreground (PID 53044)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 53044).
2026-11-11 23:03:28 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 23:03:28 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.134s (2.87 MB compressed)
2026-11-11 23:03:28 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-12 00:51:29 [INFO] scope: Starting Scope workstation in foreground (PID 58406)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 58406).
2026-11-12 00:51:29 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 00:51:29 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.152s (2.87 MB compressed)
2026-11-12 00:51:29 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.15s
2026-11-12 01:48:21 [INFO] scope: Starting Scope workstation in foreground (PID 63454)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 63454).
2026-11-12 01:48:21 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 01:48:21 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 06:31:30 [INFO] scope: Starting Scope workstation in foreground (PID 90948)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 90948).
2026-11-12 06:31:31 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:31:31] "GET / HTTP/1.1" 200 -
2026-11-12 06:31:31 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:31:31] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 06:31:31 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:31:31] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 06:31:31 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:31:31] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 06:31:31 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:31:31] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 06:31:31 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:31:31] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 06:31:38 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 06:34:58 [INFO] scope: Starting Scope workstation in foreground (PID 92957)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 92957).
2026-11-12 06:34:58 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 06:34:58 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.135s (2.87 MB compressed)
2026-11-12 06:34:58 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.15s
2026-11-12 06:34:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:58] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 06:34:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:58] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 06:34:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:58] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 06:34:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:58] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 06:34:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:58] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 06:34:58 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 06:34:58 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.87 MB compressed)
2026-11-12 06:34:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:58] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 06:34:59 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:34:59] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 06:35:25 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 06:36:01 [INFO] scope: Starting Scope workstation in foreground (PID 93520)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM (PID 93520).
2026-11-12 06:36:01 [INFO] scope: Background pre-warming geometry for cat_fountain/wiring [DIAGRAM]...
2026-11-12 06:36:01 [INFO] scope.pipeline: Disk cache hit for cat_fountain/wiring [DIAGRAM] in 0.021s (2.37 MB compressed)
2026-11-12 06:36:01 [INFO] scope: Background pre-warming completed for cat_fountain/wiring in 0.03s
2026-11-12 06:36:01 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:01] "GET /?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 06:36:01 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:01] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 06:36:01 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:01] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 06:36:01 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:01] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 06:36:01 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:01] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 06:36:01 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 06:36:01 [INFO] scope: Delivered cached geometry for cat_fountain/wiring [DIAGRAM] in 0.000s (2.37 MB compressed)
2026-11-12 06:36:01 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:01] "GET /api/scope/load?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 06:36:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:36:02] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 06:37:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:37:38] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 06:37:42 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 06:38:14 [INFO] scope: Starting Scope workstation in foreground (PID 94621)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 94621).
2026-11-12 06:38:15 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-12 06:38:15 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.011s (1.32 MB compressed)
2026-11-12 06:38:15 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-12 06:38:15 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 06:38:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:38:15] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-12 06:38:36 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 06:39:18 [INFO] scope: Starting Scope workstation in foreground (PID 95141)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 95141).
2026-11-12 06:39:18 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 06:39:18 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.120s (2.87 MB compressed)
2026-11-12 06:39:18 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.13s
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 06:39:19 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 06:39:19 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.87 MB compressed)
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 06:39:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:39:19] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 06:41:48 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:41:48] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 06:42:52 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:42:52] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 06:43:10 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-12 06:43:10 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.009s (1.32 MB compressed)
2026-11-12 06:43:10 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:43:10] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 06:43:10 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:43:10] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-12 06:43:16 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:43:16] "POST /api/scope/open_rerun?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-12 06:46:44 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:46:44] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 06:47:04 [INFO] scope: Loading geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 06:47:04 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
face 46 ignored
2026-11-12 06:47:18 [INFO] scope.pipeline: Geometry cat_fountain/product [DIAGRAM] tessellated in 14.14s (2 parts, 16 instances, bounds: {'xmin': -134.10793296424515, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 128.61706314291132, 'zmin': -50.0, 'zmax': 197.60000038146973})
2026-11-12 06:47:18 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [DIAGRAM] in 14.25s (1.37 MB compressed)
2026-11-12 06:47:18 [INFO] scope: Successfully loaded geometry for cat_fountain/product [DIAGRAM] in 14.25s
2026-11-12 06:47:18 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:47:18] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 06:49:57 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 06:54:03 [INFO] scope: Starting Scope workstation in foreground (PID 2429)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 2429).
2026-11-12 06:54:03 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 06:54:04 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.125s (2.87 MB compressed)
2026-11-12 06:54:04 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-12 06:54:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:04] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 06:54:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:04] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 06:54:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:04] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 06:54:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:04] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 06:54:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:04] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 06:54:05 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 06:54:05 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.87 MB compressed)
2026-11-12 06:54:05 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:05] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 06:54:05 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:05] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 06:54:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 06:54:20] "GET /api/scope/open_kicad?project=carrier_board&target=carrier_board HTTP/1.1" 200 -
2026-11-12 06:54:50 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 07:46:27 [INFO] scope: Starting Scope workstation in foreground (PID 18763)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 18763).
2026-11-12 07:46:27 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 07:46:27 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 08:13:10 [INFO] scope: Starting Scope workstation in foreground (PID 24656)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 24656).
2026-11-12 08:13:10 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 08:13:10 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.175s (2.87 MB compressed)
2026-11-12 08:13:10 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.18s
2026-11-12 09:17:44 [INFO] scope: Starting Scope workstation in foreground (PID 26751)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 26751).
2026-11-12 09:17:44 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 09:17:44 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.103s (2.87 MB compressed)
2026-11-12 09:17:44 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.10s
2026-11-12 09:23:11 [INFO] scope: Starting Scope workstation in foreground (PID 28366)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 28366).
2026-11-12 09:23:12 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:12] "GET / HTTP/1.1" 200 -
2026-11-12 09:23:12 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:12] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 09:23:12 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:12] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 09:23:12 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:12] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 09:23:27 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 09:23:38 [INFO] scope: Starting Scope workstation in foreground (PID 28646)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 28646).
2026-11-12 09:23:39 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:39] "GET / HTTP/1.1" 200 -
2026-11-12 09:23:39 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:39] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 09:23:39 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:39] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 09:23:39 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:23:39] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 09:23:55 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 09:29:14 [INFO] scope: Starting Scope workstation in foreground (PID 30900)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 30900).
2026-11-12 09:29:14 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 09:29:15 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.127s (2.87 MB compressed)
2026-11-12 09:29:15 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.13s
2026-11-12 09:37:27 [INFO] scope: Starting Scope workstation in foreground (PID 37840)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 37840).
2026-11-12 09:37:27 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 09:37:28 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.184s (2.87 MB compressed)
2026-11-12 09:37:28 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.19s
2026-11-12 09:56:14 [INFO] scope: Starting Scope workstation in foreground (PID 46779)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 46779).
2026-11-12 09:56:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:15] "GET / HTTP/1.1" 200 -
2026-11-12 09:56:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:15] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 09:56:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:15] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 09:56:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:15] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 09:56:27 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 09:56:44 [INFO] scope: Starting Scope workstation in foreground (PID 47020)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 47020).
2026-11-12 09:56:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:45] "GET / HTTP/1.1" 200 -
2026-11-12 09:56:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:45] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 09:56:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:45] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 09:56:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:56:45] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 09:57:07 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 09:57:28 [INFO] scope: Starting Scope workstation in foreground (PID 47409)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 47409).
2026-11-12 09:57:28 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-12 09:57:28 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.012s (1.32 MB compressed)
2026-11-12 09:57:28 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-12 09:57:29 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:57:29] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 09:57:29 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:57:29] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 09:57:29 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:57:29] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 09:57:29 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 09:57:29] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 09:58:17 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 10:45:41 [INFO] scope: Starting Scope workstation in foreground (PID 64682)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 64682).
2026-11-12 10:45:41 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 10:45:41 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 10:45:48 [INFO] scope: Starting Scope workstation in foreground (PID 64717)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 64717).
2026-11-12 10:45:48 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 10:45:48 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 10:48:39 [INFO] scope: Starting Scope workstation in foreground (PID 65805)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 65805).
2026-11-12 10:48:39 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 10:48:39 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.153s (2.87 MB compressed)
2026-11-12 10:48:39 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.16s
2026-11-12 10:50:02 [INFO] scope: Starting Scope workstation in foreground (PID 66358)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 66358).
2026-11-12 10:50:02 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 10:50:02 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.151s (2.87 MB compressed)
2026-11-12 10:50:02 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.15s
2026-11-12 12:11:24 [INFO] scope: Starting Scope workstation in foreground (PID 83620)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 83620).
2026-11-12 12:11:24 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 12:11:24 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.162s (2.87 MB compressed)
2026-11-12 12:11:24 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.17s
2026-11-12 12:44:07 [INFO] scope: Starting Scope workstation in foreground (PID 85346)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 85346).
2026-11-12 12:44:07 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-12 12:44:07 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.015s (1.32 MB compressed)
2026-11-12 12:44:07 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.03s
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:44:08 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-12 12:44:08 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 12:44:08 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:08] "GET /api/scope/projects HTTP/1.1" 200 -
[2m2026-11-12T20:44:08.391799Z[0m [33m WARN[0m [2mre_log_encoding::rrd::frames[0m[2m:[0m Found data stream with Rerun version 0.42.0 which is newer than the local Rerun version (0.36.2). This file may contain data that is not compatible with this version of Rerun. Consider updating Rerun.
[2m2026-11-12T20:44:08.395294Z[0m [33m WARN[0m [2mre_sorbet::migrations[0m[2m:[0m Found Sorbet version 'v0.1.4' that is newer then current supported version 'v0.1.3'. Consider updating Rerun!
[2m2026-11-12T20:44:08.395602Z[0m [33m WARN[0m [2mre_sorbet::sorbet_schema[0m[2m:[0m Sorbet batch version mismatch. Expected 0.1.3, got "0.1.4"
2026-11-12 12:44:14 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:44:14] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-12 12:45:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:04] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 12:45:24 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 12:45:50 [INFO] scope: Starting Scope workstation in foreground (PID 86305)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM (PID 86305).
2026-11-12 12:45:50 [INFO] scope: Background pre-warming geometry for cat_fountain/wiring [DIAGRAM]...
2026-11-12 12:45:51 [INFO] scope.pipeline: Disk cache hit for cat_fountain/wiring [DIAGRAM] in 0.022s (2.37 MB compressed)
2026-11-12 12:45:51 [INFO] scope: Background pre-warming completed for cat_fountain/wiring in 0.03s
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:45:51 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 12:45:51 [INFO] scope: Delivered cached geometry for cat_fountain/wiring [DIAGRAM] in 0.007s (2.37 MB compressed)
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /api/scope/load?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 12:45:51 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:45:51] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 12:46:20 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 12:47:20 [INFO] scope: Starting Scope workstation in foreground (PID 87096)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 87096).
2026-11-12 12:47:20 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 12:47:20 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.124s (2.87 MB compressed)
2026-11-12 12:47:20 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.13s
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:47:21 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 12:47:21 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.87 MB compressed)
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 12:47:21 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:47:21] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 12:47:53 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 12:49:02 [INFO] scope: Starting Scope workstation in foreground (PID 87950)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 87950).
2026-11-12 12:49:02 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 12:49:03 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.126s (2.87 MB compressed)
2026-11-12 12:49:03 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:49:03 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 12:49:03 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.122s (2.87 MB compressed)
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 12:49:03 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:03] "GET /api/scope/projects HTTP/1.1" 200 -
```

#### Attachments & References

| Type | Filename | Description |
| :--- | :--- | :--- |
| `image/png` | [snapshot.png](attachments/BUG-JUMPING-APHID-570/snapshot.png) | 3D CAD/PCB annotated WebGL viewport snapshot |
| `text/plain` | [scope.log](attachments/BUG-JUMPING-APHID-570/scope.log) | Scope workstation execution logs |
