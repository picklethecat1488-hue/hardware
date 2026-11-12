# 🔴 `[BUG-SHINING-HOVERFLY-298]` Simulation water particles shimmer/motion blur and STEPS/SCALE playback control text overlap

- **UUID**: `3707fc5c-39a2-48c2-89a9-73c07ca08d9c`
- **ID**: `BUG-SHINING-HOVERFLY-298`
- **Status**: `OPEN`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-12 01:01:10 UTC`
- **Rejected**: `2026-11-12 14:39:06 UTC`

#### Description

Water particles in simulation view appear shimmery, and it is difficult to see the water motion over time. The “STEPS/SCALE” text in the playback control are also overlapping

#### Reproduction Steps

1. python tools/scope.py cat_fountain/product:simulate

#### Execution / Console Logs

```text
2026-11-11 14:02:47 [INFO] scope: Successfully loaded geometry for exhaust_manifolds/driver [CAD] in 2.89s
2026-11-11 14:02:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:02:47] "GET /api/scope/load?project=exhaust_manifolds&target=driver&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 14:03:01 [INFO] scope: Loading geometry for exhaust_manifolds/part_positions [CAD] (subassembly: None, step: None)...
2026-11-11 14:03:01 [INFO] scope.pipeline: Resolving and compiling geometry for exhaust_manifolds/part_positions [CAD] (subassembly: None, step: None)...
2026-11-11 14:03:07 [INFO] scope.pipeline: Geometry exhaust_manifolds/part_positions [CAD] tessellated in 5.40s (49 parts, 49 instances, bounds: {'xmin': 145.0, 'xmax': 950.0, 'ymin': -32.0, 'ymax': 390.0, 'zmin': 145.0, 'zmax': 532.5})
2026-11-11 14:03:07 [INFO] scope.pipeline: Persisted disk cache for exhaust_manifolds/part_positions [CAD] in 5.64s (3.16 MB compressed)
2026-11-11 14:03:07 [INFO] scope: Successfully loaded geometry for exhaust_manifolds/part_positions [CAD] in 5.64s
2026-11-11 14:03:07 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:03:07] "GET /api/scope/load?project=exhaust_manifolds&target=part_positions&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 14:03:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:03:40] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 14:03:52 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:03:52] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 14:03:52 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:03:52] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 14:03:52 [INFO] scope: Loading geometry for exhaust_manifolds/part_positions [CAD] (subassembly: None, step: None)...
2026-11-11 14:03:52 [INFO] scope.pipeline: Resolving and compiling geometry for exhaust_manifolds/part_positions [CAD] (subassembly: None, step: None)...
2026-11-11 14:03:55 [INFO] scope.pipeline: Geometry exhaust_manifolds/part_positions [CAD] tessellated in 2.37s (49 parts, 49 instances, bounds: {'xmin': 145.0, 'xmax': 950.0, 'ymin': -32.0, 'ymax': 390.0, 'zmin': 145.0, 'zmax': 532.5})
2026-11-11 14:03:55 [INFO] scope.pipeline: Persisted disk cache for exhaust_manifolds/part_positions [CAD] in 2.61s (3.16 MB compressed)
2026-11-11 14:03:55 [INFO] scope: Successfully loaded geometry for exhaust_manifolds/part_positions [CAD] in 2.61s
2026-11-11 14:03:55 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:03:55] "GET /api/scope/load?project=exhaust_manifolds&target=part_positions&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 14:04:17 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 14:04:17 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 14:04:19 [INFO] scope.pipeline: Geometry cat_fountain/product [SIMULATE] tessellated in 2.43s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 14:04:19 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [SIMULATE] in 2.53s (1.32 MB compressed)
2026-11-11 14:04:19 [INFO] scope: Successfully loaded geometry for cat_fountain/product [SIMULATE] in 2.53s
2026-11-11 14:04:20 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:04:20] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 14:06:16 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 14:06:16] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 14:06:40 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 14:14:26 [INFO] scope: Starting Scope workstation in foreground (PID 7786)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 7786).
2026-11-11 14:14:26 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 14:14:26 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 14:35:23 [INFO] scope: Starting Scope workstation in foreground (PID 15551)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 15551).
2026-11-11 14:35:23 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 14:35:23 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.093s (2.87 MB compressed)
2026-11-11 14:35:23 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.09s
2026-11-11 14:40:42 [INFO] scope: Starting Scope workstation in foreground (PID 17616)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 17616).
2026-11-11 14:40:42 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 14:40:43 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.158s (2.87 MB compressed)
2026-11-11 14:40:43 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.16s
2026-11-11 14:46:02 [INFO] scope: Starting Scope workstation in foreground (PID 19589)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 19589).
2026-11-11 14:46:02 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 14:46:02 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.144s (2.87 MB compressed)
2026-11-11 14:46:02 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.15s
2026-11-11 14:49:01 [INFO] scope: Starting Scope workstation in foreground (PID 24556)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 24556).
2026-11-11 14:49:01 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 14:49:01 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.204s (2.87 MB compressed)
2026-11-11 14:49:01 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.21s
2026-11-11 15:03:48 [INFO] scope: Starting Scope workstation in foreground (PID 31166)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 31166).
2026-11-11 15:03:48 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-11 15:03:48 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.012s (1.32 MB compressed)
2026-11-11 15:03:48 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:03:49 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 15:03:49 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:03:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:03:49] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:05:20 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:20] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 15:05:22 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 15:05:37 [INFO] scope: Starting Scope workstation in foreground (PID 32043)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 32043).
2026-11-11 15:05:37 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-11 15:05:37 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.011s (1.32 MB compressed)
2026-11-11 15:05:37 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:05:37 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 15:05:37 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:05:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:05:37] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:06:06 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 15:06:06 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-11 15:06:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:06:06] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:08:59 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 15:09:32 [INFO] scope: Starting Scope workstation in foreground (PID 34036)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 34036).
2026-11-11 15:09:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:33] "GET / HTTP/1.1" 200 -
2026-11-11 15:09:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:33] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:09:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:33] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:09:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:33] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:09:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:33] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:09:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:33] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:09:41 [INFO] scope: Loading geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-11 15:09:41 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-11 15:09:45 [INFO] scope.pipeline: Geometry carrier_board/battery_cover [CAD] tessellated in 4.12s (1 parts, 1 instances, bounds: {'xmin': -31.899999618530273, 'xmax': 10.399999618530273, 'ymin': -30.399999618530273, 'ymax': 23.899999618530273, 'zmin': 0.0, 'zmax': 7.0})
2026-11-11 15:09:45 [INFO] scope.pipeline: Persisted disk cache for carrier_board/battery_cover [CAD] in 4.13s (0.01 MB compressed)
2026-11-11 15:09:45 [INFO] scope: Successfully loaded geometry for carrier_board/battery_cover [CAD] in 4.13s
2026-11-11 15:09:45 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:09:45] "GET /api/scope/load?project=carrier_board&target=battery_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 15:09:54 [INFO] scope: Loading geometry for carrier_board/product [CAD] (subassembly: None, step: None)...
2026-11-11 15:09:54 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [CAD] (subassembly: None, step: None)...
2026-11-11 15:10:02 [INFO] scope.pipeline: Geometry carrier_board/product [CAD] tessellated in 8.16s (6 parts, 6 instances, bounds: {'xmin': -33.5, 'xmax': 36.0, 'ymin': -48.5, 'ymax': 87.75, 'zmin': -8.300000190734863, 'zmax': 17.8})
2026-11-11 15:10:02 [INFO] scope.pipeline: Persisted disk cache for carrier_board/product [CAD] in 8.21s (0.56 MB compressed)
2026-11-11 15:10:02 [INFO] scope: Successfully loaded geometry for carrier_board/product [CAD] in 8.21s
2026-11-11 15:10:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:10:03] "GET /api/scope/load?project=carrier_board&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 15:11:29 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:11:29] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 15:11:40 [INFO] scope: Loading geometry for exhaust_manifolds/part_positions [CAD] (subassembly: None, step: None)...
2026-11-11 15:11:40 [INFO] scope: Delivered cached geometry for exhaust_manifolds/part_positions [CAD] in 0.003s (3.16 MB compressed)
2026-11-11 15:11:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:11:40] "GET /api/scope/load?project=exhaust_manifolds&target=part_positions&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 15:11:59 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-11 15:11:59 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-11 15:12:49 [INFO] scope.pipeline: Geometry cat_fountain/wiring [DIAGRAM] tessellated in 49.88s (321 parts, 186 instances, bounds: {'xmin': -127.0, 'xmax': 122.0, 'ymin': -113.0, 'ymax': 112.0, 'zmin': -0.10000010000000134, 'zmax': 0.10000010000000134})
2026-11-11 15:12:49 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/wiring [DIAGRAM] in 49.89s (0.07 MB compressed)
2026-11-11 15:12:49 [INFO] scope: Successfully loaded geometry for cat_fountain/wiring [DIAGRAM] in 49.89s
2026-11-11 15:12:49 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:12:49] "GET /api/scope/load?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-11 15:13:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:13:47] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 15:14:15 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 15:14:58 [INFO] scope: Starting Scope workstation in foreground (PID 36674)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=cad&mode=CAD (PID 36674).
2026-11-11 15:14:58 [INFO] scope: Background pre-warming geometry for cat_fountain/product [CAD]...
2026-11-11 15:14:58 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: cad, step: None)...
2026-11-11 15:14:58 [WARNING] scope: Background pre-warming error for cat_fountain/product: 'cad' is not a valid Section
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /?project=cat_fountain&target=product&subassembly=cad&mode=CAD HTTP/1.1" 200 -
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:14:58 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: cad, step: None)...
2026-11-11 15:14:58 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: cad, step: None)...
2026-11-11 15:14:58 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=product&subassembly=cad&mode=CAD after 0.00s: 'cad' is not a valid Section
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 537, in load_geometry
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
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 539, in load_geometry
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
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:14:58 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:14:58] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=cad&mode=CAD HTTP/1.1" 500 -
2026-11-11 15:15:15 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:15:15] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 15:15:16 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:15:16] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:15:16 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: cad, step: None)...
2026-11-11 15:15:16 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: cad, step: None)...
2026-11-11 15:15:16 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=product&subassembly=cad&mode=CAD after 0.00s: 'cad' is not a valid Section
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 537, in load_geometry
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
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 539, in load_geometry
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
2026-11-11 15:15:16 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:15:16] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=cad&mode=CAD HTTP/1.1" 500 -
2026-11-11 15:15:21 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 15:15:21 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
face 46 ignored
2026-11-11 15:15:36 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 14.21s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 15:15:36 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 14.32s (1.32 MB compressed)
2026-11-11 15:15:36 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 14.32s
2026-11-11 15:15:36 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:15:36] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 15:15:41 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 15:16:05 [INFO] scope: Starting Scope workstation in foreground (PID 37258)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 37258).
2026-11-11 15:16:05 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 15:16:05 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 15:16:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:06] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 15:16:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:06] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:16:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:06] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:16:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:06] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:16:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:06] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:16:06 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 15:16:06 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:06] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:16:41 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 35.43s (8 parts, 5858 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.3900000238418582, 'zmax': 9.29})
2026-11-11 15:16:41 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [PCB] in 35.77s (2.87 MB compressed)
2026-11-11 15:16:41 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 35.77s
2026-11-11 15:16:41 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 34.83s
2026-11-11 15:16:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:16:41] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 15:21:20 [INFO] scope: Starting Scope workstation in foreground (PID 39982)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 39982).
2026-11-11 15:21:20 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-11 15:21:20 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 15:21:21 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:21] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:21:21 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:21] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:21:21 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:21] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:21:21 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:21] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:21:21 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:21] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:21:22 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 15:21:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:22] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:21:22 [INFO] scope: Starting Scope workstation in foreground (PID 39995)...
➜ Scope workstation running at http://127.0.0.1:8001/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 39995).
2026-11-11 15:21:22 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 15:21:22 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.253s (2.87 MB compressed)
2026-11-11 15:21:22 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.26s
face 46 ignored
2026-11-11 15:21:42 [INFO] scope.pipeline: Geometry cat_fountain/product [SIMULATE] tessellated in 21.85s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 15:21:42 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [SIMULATE] in 21.97s (1.32 MB compressed)
2026-11-11 15:21:42 [INFO] scope: Background pre-warming completed for cat_fountain/product in 21.97s
2026-11-11 15:21:42 [INFO] scope: Successfully loaded geometry for cat_fountain/product [SIMULATE] in 20.65s
2026-11-11 15:21:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:21:42] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 15:22:45 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:22:45] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 15:22:47 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 15:28:42 [INFO] scope: Starting Scope workstation in foreground (PID 44934)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 44934).
2026-11-11 15:28:42 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 15:28:42 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.157s (2.87 MB compressed)
2026-11-11 15:28:42 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.16s
2026-11-11 15:30:08 [INFO] scope: Starting Scope workstation in foreground (PID 49535)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 49535).
2026-11-11 15:30:08 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 15:30:08 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.187s (2.87 MB compressed)
2026-11-11 15:30:08 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.19s
2026-11-11 15:39:43 [INFO] scope: Starting Scope workstation in foreground (PID 60098)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 60098).
2026-11-11 15:39:43 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 15:39:43 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.183s (2.87 MB compressed)
2026-11-11 15:39:43 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.19s
2026-11-11 15:40:14 [INFO] scope: Starting Scope workstation in foreground (PID 60418)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 60418).
2026-11-11 15:40:15 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:15] "GET / HTTP/1.1" 200 -
2026-11-11 15:40:15 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:15] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 15:40:15 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:15] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 15:40:15 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:15] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 15:40:16 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:16] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 15:40:17 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:17] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 15:40:27 [INFO] scope: Loading geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-11 15:40:27 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-11 15:40:36 [INFO] scope.pipeline: Geometry carrier_board/battery_cover [CAD] tessellated in 9.24s (1 parts, 1 instances, bounds: {'xmin': -31.899999618530273, 'xmax': 10.399999618530273, 'ymin': -30.399999618530273, 'ymax': 23.899999618530273, 'zmin': 0.0, 'zmax': 7.0})
2026-11-11 15:40:36 [INFO] scope.pipeline: Persisted disk cache for carrier_board/battery_cover [CAD] in 9.24s (0.01 MB compressed)
2026-11-11 15:40:36 [INFO] scope: Successfully loaded geometry for carrier_board/battery_cover [CAD] in 9.24s
2026-11-11 15:40:36 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 15:40:36] "GET /api/scope/load?project=carrier_board&target=battery_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 15:41:44 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 16:06:28 [INFO] scope: Starting Scope workstation in foreground (PID 71461)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 71461).
2026-11-11 16:06:28 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 16:06:28 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 16:09:55 [INFO] scope: Starting Scope workstation in foreground (PID 76603)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 76603).
2026-11-11 16:09:55 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 16:09:56 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.178s (2.87 MB compressed)
2026-11-11 16:09:56 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.18s
2026-11-11 16:20:54 [INFO] scope: Starting Scope workstation in foreground (PID 81306)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 81306).
2026-11-11 16:20:54 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 16:20:54 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 16:42:00 [INFO] scope: Starting Scope workstation in foreground (PID 90710)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 90710).
2026-11-11 16:42:00 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 16:42:00 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.136s (2.87 MB compressed)
2026-11-11 16:42:00 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-11 16:47:11 [INFO] scope: Starting Scope workstation in foreground (PID 96799)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 96799).
2026-11-11 16:47:11 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 16:47:11 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 16:50:43 [INFO] scope: Starting Scope workstation in foreground (PID 98674)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 98674).
2026-11-11 16:50:43 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 16:50:43 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.249s (2.87 MB compressed)
2026-11-11 16:50:43 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.27s
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 16:50:44 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 16:50:44 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.87 MB compressed)
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 16:50:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:50:44] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 16:52:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:52:30] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 16:52:42 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 16:53:18 [INFO] scope: Starting Scope workstation in foreground (PID 243)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 243).
2026-11-11 16:53:18 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-11 16:53:18 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.015s (1.32 MB compressed)
2026-11-11 16:53:18 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 16:53:18 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.008s (1.32 MB compressed)
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 16:53:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:18] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-11 16:53:51 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:53:51] "POST /api/scope/open_rerun?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-11 16:54:17 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-11 16:54:41 [INFO] scope: Starting Scope workstation in foreground (PID 1080)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 1080).
2026-11-11 16:54:41 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-11 16:54:42 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.039s (1.32 MB compressed)
2026-11-11 16:54:42 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.04s
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 16:54:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 16:54:42] "GET /static/common.css HTTP/1.1" 200 -
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
```

#### Attached Commits

- `d845247c`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:3707fc5c --> Open cat fountain simulation in Scope SIMULATE mode, verify fluid particles render with circular soft sprite texture and velocity-based color grading without shimmer, verify playback controls and step readout do not overlap at any scale, and verify Save .rrd button downloads the recording | `python tools/scope.py cat_fountain/product:simulate`
- [ ] <!-- task:08e83f11 --> Verify fluid simulation particles smooth blending and hydrodynamic motion blur streamlines with clean STEPS/SCALE badge | `python tools/scope.py cat_fountain/product:simulate`

#### Resolution Notes

Eliminate particle shimmer with circular soft sprite and velocity color ramp, fix playback control overlap with nowrap layout, add Save .rrd button, and genericize rerun events

-I still see shimmering, I think the particles are too small. Can you repro this on the CLI?

#### Rejection Feedback

Eliminate particle shimmer with circular soft sprite and velocity color ramp, fix playback control overlap with nowrap layout, add Save .rrd button, and genericize rerun events

-I still see shimmering, I think the particles are too small. Can you repro this on the CLI?
