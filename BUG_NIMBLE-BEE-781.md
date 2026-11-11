# 🟢 `[BUG-NIMBLE-BEE-781]` Footprints render in front of bottom cover due to CAD view Z-ordering (cat_fountain)

- **UUID**: `934eb8ac-a282-42da-a0ee-a6fc6c4f876b`
- **ID**: `BUG-NIMBLE-BEE-781`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-11 21:50:54 UTC`
- **Resolved**: `2026-11-11 22:13:17 UTC`

#### Description

I see a Z ordering error here- looks like footprints are in front of the bottom cover

#### Reproduction Steps

1. python tools/scope.py cat_fountain/product:cad

#### Execution / Console Logs

```text
face 46 ignored
Unexpected error talking to the viewer:
Traceback (most recent call last):
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/site-packages/ocp_viewer_core/websocket.py", line 282, in _send
    with connect(f"{self.url}:{port}", close_timeout=0.05) as ws:
         ~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/site-packages/websockets/sync/client.py", line 249, in connect
    ws_uri = parse_uri(uri)
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/site-packages/websockets/uri.py", line 84, in parse_uri
    port = parsed.port or (443 if secure else 80)
           ^^^^^^^^^^^
  File "/Users/<username>/miniforge3/envs/cq/lib/python3.13/urllib/parse.py", line 182, in port
    raise ValueError(f"Port could not be cast to integer value as {port!r}")
ValueError: Port could not be cast to integer value as 'None'

CameraKeepWarning: reset_camera is set to KEEP. If shown objects are not visible use the 'resize' and a 'view' button
pybullet build time: Oct 20 2025 08:05:00
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: carrier_board/carrier_board [PCB]
  URL:    http://127.0.0.1:8003/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB
Desktop window closed; shutting down scope server...
Desktop window closed; shutting down scope server...
2026-11-10 17:00:35 [INFO] scope: Starting Scope workstation in foreground (PID 69913)...
2026-11-10 17:02:42 [INFO] scope: Starting Scope workstation in foreground (PID 71021)...
2026-11-10 17:06:40 [INFO] scope: Starting Scope workstation in foreground (PID 72380)...
2026-11-10 17:07:33 [INFO] scope: Starting Scope workstation in foreground (PID 72732)...
2026-11-10 17:09:33 [INFO] scope: Starting Scope workstation in foreground (PID 73413)...
2026-11-10 17:12:23 [INFO] scope: Starting Scope workstation in foreground (PID 74589)...
2026-11-10 17:13:04 [INFO] scope: Starting Scope workstation in foreground (PID 74860)...
2026-11-10 17:13:48 [INFO] scope: Starting Scope workstation in foreground (PID 75127)...
2026-11-10 17:15:03 [INFO] scope: Starting Scope workstation in foreground (PID 79193)...
2026-11-10 17:22:31 [INFO] scope: Starting Scope workstation in foreground (PID 86090)...
2026-11-10 17:22:36 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:22:36] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-10 17:22:36 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:22:36] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-10 17:22:36 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:22:36] "GET /static/common.css HTTP/1.1" 200 -
2026-11-10 17:22:36 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:22:36] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-10 17:22:36 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:22:36] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-10 17:23:25 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:23:25] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-10 17:23:25 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-10 17:23:25 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-10 17:23:43 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 17.96s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.3900000238418582, 'zmax': 9.29})
2026-11-10 17:23:43 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 17.97s
2026-11-10 17:23:43 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:23:43] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-10 17:23:45 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-10 17:23:45 [INFO] scope.pipeline: Cache hit for geometry carrier_board/carrier_board [PCB]
2026-11-10 17:23:45 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 0.00s
2026-11-10 17:23:45 [INFO] scope: 127.0.0.1 - - [10/Nov/2026 17:23:45] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-10 17:24:11 [INFO] scope: Starting Scope workstation in foreground (PID 86783)...
2026-11-10 17:25:02 [INFO] scope: Starting Scope workstation in foreground (PID 87181)...
2026-11-10 17:31:37 [INFO] scope: Starting Scope workstation in foreground (PID 89730)...
2026-11-10 17:32:33 [INFO] scope: Starting Scope workstation in foreground (PID 90113)...
2026-11-10 17:34:12 [INFO] scope: Starting Scope workstation in foreground (PID 90752)...
2026-11-10 17:36:02 [INFO] scope: Starting Scope workstation in foreground (PID 95085)...
2026-11-11 05:51:38 [INFO] scope: Starting Scope workstation in foreground (PID 20420)...
2026-11-11 05:51:40 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 05:51:40 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.033s (1.69 MB compressed)
2026-11-11 05:51:40 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.04s
2026-11-11 05:51:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:51:41] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:51:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:51:41] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 05:51:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:51:41] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 05:51:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:51:41] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 05:51:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:51:41] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 05:51:41 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 05:51:41 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (1.69 MB compressed)
2026-11-11 05:51:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:51:41] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:52:07 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:07] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 05:52:16 [INFO] scope: Loading geometry for cat_fountain/bottom_cover [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:16 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/bottom_cover [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:17 [INFO] scope.pipeline: Geometry cat_fountain/bottom_cover [PCB] tessellated in 1.49s (1 parts, 1 instances, bounds: {'xmin': -96.549560546875, 'xmax': 96.549560546875, 'ymin': -96.0307388305664, 'ymax': 96.48533630371094, 'zmin': 0.0, 'zmax': 4.0})
2026-11-11 05:52:17 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/bottom_cover [PCB] in 1.49s (0.04 MB compressed)
2026-11-11 05:52:17 [INFO] scope: Successfully loaded geometry for cat_fountain/bottom_cover [PCB] in 1.50s
2026-11-11 05:52:17 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:17] "GET /api/scope/load?project=cat_fountain&target=bottom_cover&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:52:21 [INFO] scope: Loading geometry for cat_fountain/product [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:21 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:24 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=PCB after 2.81s: No matching part targets found.
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 462, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 261, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 464, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.
2026-11-11 05:52:24 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:24] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=PCB HTTP/1.1" 500 -
2026-11-11 05:52:28 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:28] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 05:52:32 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:32] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 05:52:32 [INFO] scope: Loading geometry for cat_fountain/product [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:32 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:35 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=PCB after 3.01s: No matching part targets found.
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 462, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 261, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 464, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.
2026-11-11 05:52:35 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:35] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=PCB HTTP/1.1" 500 -
2026-11-11 05:52:57 [INFO] scope: Loading geometry for cat_fountain/product [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:57 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [PCB] (subassembly: None, step: None)...
2026-11-11 05:52:59 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=PCB after 2.76s: No matching part targets found.
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 462, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 261, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 464, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.
2026-11-11 05:52:59 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:52:59] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=PCB HTTP/1.1" 500 -
2026-11-11 05:53:09 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 05:53:09 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: carrier_board/carrier_board [PCB]
  URL:    http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB
face 46 ignored
2026-11-11 05:53:12 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 2.83s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 05:53:12 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 2.94s (1.32 MB compressed)
2026-11-11 05:53:12 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 2.94s
2026-11-11 05:53:12 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:53:12] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 05:54:05 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:54:05] "POST /api/scope/target_bug HTTP/1.1" 200 -
Desktop window closed; shutting down scope server...
2026-11-11 05:54:34 [INFO] scope: Starting Scope workstation in foreground (PID 21440)...
2026-11-11 05:54:36 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 05:54:36 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 05:54:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:54:37] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:54:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:54:37] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 05:54:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:54:37] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 05:54:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:54:37] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 05:54:37 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:54:37] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 05:54:37 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 05:55:09 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 32.92s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.3900000238418582, 'zmax': 9.29})
2026-11-11 05:55:09 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [PCB] in 33.09s (1.69 MB compressed)
2026-11-11 05:55:09 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 33.09s
2026-11-11 05:55:09 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 32.23s
2026-11-11 05:55:09 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:55:09] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:55:10 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:55:10] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 05:55:19 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 05:55:19 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (1.69 MB compressed)
2026-11-11 05:55:19 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:55:19] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:55:31 [INFO] scope: Loading geometry for carrier_board/carrier_board [SIMULATE] (subassembly: None, step: None)...
2026-11-11 05:55:31 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [SIMULATE] (subassembly: None, step: None)...
2026-11-11 05:55:42 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [SIMULATE] tessellated in 10.77s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.435000023841858, 'zmax': 9.335})
2026-11-11 05:55:42 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [SIMULATE] in 10.95s (1.73 MB compressed)
2026-11-11 05:55:42 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [SIMULATE] in 10.95s
2026-11-11 05:55:42 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:55:42] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 05:55:58 [INFO] scope: Loading geometry for cat_fountain/bottom_cover [SIMULATE] (subassembly: None, step: None)...
2026-11-11 05:55:58 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/bottom_cover [SIMULATE] (subassembly: None, step: None)...
2026-11-11 05:56:01 [INFO] scope.pipeline: Geometry cat_fountain/bottom_cover [SIMULATE] tessellated in 2.85s (1 parts, 1 instances, bounds: {'xmin': -96.549560546875, 'xmax': 96.549560546875, 'ymin': -96.0307388305664, 'ymax': 96.48533630371094, 'zmin': 0.0, 'zmax': 4.0})
2026-11-11 05:56:01 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/bottom_cover [SIMULATE] in 2.85s (0.04 MB compressed)
2026-11-11 05:56:01 [INFO] scope: Successfully loaded geometry for cat_fountain/bottom_cover [SIMULATE] in 2.85s
2026-11-11 05:56:01 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:56:01] "GET /api/scope/load?project=cat_fountain&target=bottom_cover&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 05:56:32 [INFO] scope: Loading geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 05:56:32 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 05:56:35 [INFO] scope.pipeline: Geometry cat_fountain/bottom_cover [CAD] tessellated in 2.76s (1 parts, 1 instances, bounds: {'xmin': -96.549560546875, 'xmax': 96.549560546875, 'ymin': -96.0307388305664, 'ymax': 96.48533630371094, 'zmin': 0.0, 'zmax': 4.0})
2026-11-11 05:56:35 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/bottom_cover [CAD] in 2.77s (0.04 MB compressed)
2026-11-11 05:56:35 [INFO] scope: Successfully loaded geometry for cat_fountain/bottom_cover [CAD] in 2.77s
2026-11-11 05:56:35 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:56:35] "GET /api/scope/load?project=cat_fountain&target=bottom_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 05:56:40 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 05:56:40 [INFO] scope: Delivered cached geometry for cat_fountain/product [CAD] in 0.013s (1.32 MB compressed)
2026-11-11 05:56:40 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:56:40] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 05:56:47 [INFO] scope: Loading geometry for cat_fountain/simulation [CAD] (subassembly: None, step: None)...
2026-11-11 05:56:47 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/simulation [CAD] (subassembly: None, step: None)...
2026-11-11 05:56:50 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=simulation&subassembly=&mode=CAD after 2.74s: No matching part targets found.
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 462, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching view targets found.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 261, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 464, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.
2026-11-11 05:56:50 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:56:50] "GET /api/scope/load?project=cat_fountain&target=simulation&subassembly=&mode=CAD HTTP/1.1" 500 -
2026-11-11 05:56:53 [INFO] scope: Loading geometry for cat_fountain/simulation [SIMULATE] (subassembly: None, step: None)...
2026-11-11 05:56:53 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/simulation [SIMULATE] (subassembly: None, step: None)...
2026-11-11 05:56:56 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=simulation&subassembly=&mode=SIMULATE after 2.77s: No matching part targets found.
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 462, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching view targets found.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 261, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 464, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.
2026-11-11 05:56:56 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:56:56] "GET /api/scope/load?project=cat_fountain&target=simulation&subassembly=&mode=SIMULATE HTTP/1.1" 500 -
2026-11-11 05:57:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:57:41] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 05:57:44 [INFO] scope: Loading geometry for cat_fountain/simulation [CAD] (subassembly: None, step: None)...
2026-11-11 05:57:44 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/simulation [CAD] (subassembly: None, step: None)...
2026-11-11 05:57:47 [ERROR] scope: Failed to load geometry for /api/scope/load?project=cat_fountain&target=simulation&subassembly=&mode=CAD after 2.71s: No matching part targets found.
Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 462, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, section)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching view targets found.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/<username>/gh/hardware/provider/scope/server.py", line 261, in do_GET
    payload = self.server.pipeline.load_geometry(
        project=project,
    ...<3 lines>...
        step_index=step,
    )
  File "/Users/<username>/gh/hardware/provider/scope/pipeline.py", line 464, in load_geometry
    parsed_targets = self.target_parser.resolve(full_target, Section.PART)
  File "/Users/<username>/gh/hardware/tools/target_parser.py", line 207, in resolve
    raise ValueError(msg)
ValueError: No matching part targets found.
2026-11-11 05:57:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:57:47] "GET /api/scope/load?project=cat_fountain&target=simulation&subassembly=&mode=CAD HTTP/1.1" 500 -
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: carrier_board/carrier_board [PCB]
  URL:    http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB
Desktop window closed; shutting down scope server...
2026-11-11 05:57:57 [INFO] scope: Starting Scope workstation in foreground (PID 22628)...
2026-11-11 05:57:59 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 05:57:59 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.037s (1.69 MB compressed)
2026-11-11 05:57:59 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.05s
2026-11-11 05:58:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:00] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:58:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:00] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 05:58:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:00] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 05:58:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:00] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 05:58:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:00] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 05:58:00 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 05:58:00 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.086s (1.69 MB compressed)
2026-11-11 05:58:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:00] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:58:25 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:25] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 05:58:29 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 05:58:29 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (1.69 MB compressed)
2026-11-11 05:58:29 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:58:29] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 05:59:20 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:59:20] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 05:59:41 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 05:59:41] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 06:00:11 [INFO] scope: Loading geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-11 06:00:11 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-11 06:00:22 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [CAD] tessellated in 10.34s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.435000023841858, 'zmax': 9.335})
2026-11-11 06:00:22 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [CAD] in 10.51s (1.73 MB compressed)
2026-11-11 06:00:22 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [CAD] in 10.51s
2026-11-11 06:00:22 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 06:00:22] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 06:01:07 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 06:01:07] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 06:01:14 [INFO] scope: Loading geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 06:01:14 [INFO] scope: Delivered cached geometry for cat_fountain/bottom_cover [CAD] in 0.005s (0.04 MB compressed)
2026-11-11 06:01:14 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 06:01:14] "GET /api/scope/load?project=cat_fountain&target=bottom_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 06:01:20 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 06:01:20 [INFO] scope: Delivered cached geometry for cat_fountain/product [CAD] in 0.004s (1.32 MB compressed)
2026-11-11 06:01:20 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 06:01:20] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 06:02:00 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 06:02:00] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-11 06:02:32 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 06:02:32] "POST /api/scope/target_bug HTTP/1.1" 200 -
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: carrier_board/carrier_board [PCB]
  URL:    http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB
Desktop window closed; shutting down scope server...
2026-11-11 06:17:02 [INFO] scope: Starting Scope workstation in foreground (PID 29329)...
2026-11-11 06:18:05 [INFO] scope: Starting Scope workstation in foreground (PID 29710)...
2026-11-11 06:19:05 [INFO] scope: Starting Scope workstation in foreground (PID 30083)...
2026-11-11 06:22:07 [INFO] scope: Starting Scope workstation in foreground (PID 35052)...
2026-11-11 06:31:06 [INFO] scope: Starting Scope workstation in foreground (PID 39135)...
2026-11-11 10:06:59 [INFO] scope: Starting Scope workstation in foreground (PID 70576)...
2026-11-11 10:07:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:07:03] "GET / HTTP/1.1" 200 -
2026-11-11 10:07:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:07:03] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 10:07:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:07:03] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 10:07:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:07:03] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 10:07:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:07:03] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 10:08:17 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:08:17] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 10:08:18 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:08:18] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 10:08:18 [INFO] scope: Loading geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-11 10:08:18 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-11 10:08:33 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [CAD] tessellated in 15.11s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.435000023841858, 'zmax': 9.335})
2026-11-11 10:08:33 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [CAD] in 15.27s (1.73 MB compressed)
2026-11-11 10:08:33 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [CAD] in 15.28s
2026-11-11 10:08:33 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:08:33] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:08:44 [INFO] scope: Loading geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 10:08:44 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 10:08:47 [INFO] scope.pipeline: Geometry cat_fountain/bottom_cover [CAD] tessellated in 3.18s (1 parts, 1 instances, bounds: {'xmin': -96.549560546875, 'xmax': 96.549560546875, 'ymin': -96.0307388305664, 'ymax': 96.48533630371094, 'zmin': 0.0, 'zmax': 4.0})
2026-11-11 10:08:47 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/bottom_cover [CAD] in 3.19s (0.04 MB compressed)
2026-11-11 10:08:47 [INFO] scope: Successfully loaded geometry for cat_fountain/bottom_cover [CAD] in 3.19s
2026-11-11 10:08:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:08:47] "GET /api/scope/load?project=cat_fountain&target=bottom_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:08:54 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 10:08:54 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: / [CAD]
  URL:    http://127.0.0.1:8000/
face 46 ignored
2026-11-11 10:09:07 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 13.88s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 10:09:07 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 13.98s (1.32 MB compressed)
2026-11-11 10:09:07 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 13.98s
2026-11-11 10:09:08 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:09:08] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:09:21 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 10:09:21 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-11 10:09:23 [INFO] scope.pipeline: Geometry cat_fountain/product [SIMULATE] tessellated in 2.36s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 10:09:23 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [SIMULATE] in 2.46s (1.32 MB compressed)
2026-11-11 10:09:23 [INFO] scope: Successfully loaded geometry for cat_fountain/product [SIMULATE] in 2.46s
2026-11-11 10:09:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:09:23] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-11 10:11:34 [INFO] scope: Starting Scope workstation in foreground (PID 73301)...
2026-11-11 10:12:41 [INFO] scope: Starting Scope workstation in foreground (PID 74010)...
2026-11-11 10:12:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:12:44] "GET / HTTP/1.1" 200 -
2026-11-11 10:12:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:12:44] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 10:12:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:12:44] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 10:12:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:12:44] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 10:12:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:12:44] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 10:14:39 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:14:39] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-11 10:14:39 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:14:39] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 10:14:39 [INFO] scope: Loading geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-11 10:14:39 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-11 10:14:54 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [CAD] tessellated in 14.93s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.435000023841858, 'zmax': 9.335})
2026-11-11 10:14:54 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [CAD] in 15.10s (1.73 MB compressed)
2026-11-11 10:14:54 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [CAD] in 15.10s
2026-11-11 10:14:54 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:14:54] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:15:00 [INFO] scope: Loading geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 10:15:00 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/bottom_cover [CAD] (subassembly: None, step: None)...
2026-11-11 10:15:03 [INFO] scope.pipeline: Geometry cat_fountain/bottom_cover [CAD] tessellated in 2.99s (1 parts, 1 instances, bounds: {'xmin': -96.549560546875, 'xmax': 96.549560546875, 'ymin': -96.0307388305664, 'ymax': 96.48533630371094, 'zmin': 0.0, 'zmax': 4.0})
2026-11-11 10:15:03 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/bottom_cover [CAD] in 2.99s (0.04 MB compressed)
2026-11-11 10:15:03 [INFO] scope: Successfully loaded geometry for cat_fountain/bottom_cover [CAD] in 2.99s
2026-11-11 10:15:03 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:15:03] "GET /api/scope/load?project=cat_fountain&target=bottom_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:15:10 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 10:15:10 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: / [CAD]
  URL:    http://127.0.0.1:8000/
face 46 ignored
2026-11-11 10:15:24 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 13.86s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 10:15:24 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 13.97s (1.32 MB compressed)
2026-11-11 10:15:24 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 13.97s
2026-11-11 10:15:24 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:15:24] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:16:21 [INFO] scope: Loading geometry for carrier_board/product [CAD] (subassembly: None, step: None)...
2026-11-11 10:16:21 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [CAD] (subassembly: None, step: None)...
2026-11-11 10:16:27 [INFO] scope.pipeline: Geometry carrier_board/product [CAD] tessellated in 5.64s (6 parts, 6 instances, bounds: {'xmin': -33.5, 'xmax': 36.0, 'ymin': -48.5, 'ymax': 87.75, 'zmin': -8.300000190734863, 'zmax': 17.8})
2026-11-11 10:16:27 [INFO] scope.pipeline: Persisted disk cache for carrier_board/product [CAD] in 5.69s (0.56 MB compressed)
2026-11-11 10:16:27 [INFO] scope: Successfully loaded geometry for carrier_board/product [CAD] in 5.69s
2026-11-11 10:16:27 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:16:27] "GET /api/scope/load?project=carrier_board&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-11 10:16:41 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 10:16:41 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 10:16:54 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 12.75s (8 parts, 2706 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -1.3900000238418582, 'zmax': 9.29})
2026-11-11 10:16:54 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [PCB] in 12.92s (1.69 MB compressed)
2026-11-11 10:16:54 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 12.93s
2026-11-11 10:16:55 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:16:55] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-11 10:17:51 [INFO] scope: Starting Scope workstation in foreground (PID 76898)...
2026-11-11 10:21:56 [INFO] scope: Starting Scope workstation in foreground (PID 79197)...
2026-11-11 10:23:42 [INFO] scope: Starting Scope workstation in foreground (PID 80335)...
2026-11-11 10:23:45 [INFO] scope: Starting Scope workstation in foreground (PID 80409)...
2026-11-11 10:25:02 [INFO] scope: Starting Scope workstation in foreground (PID 84769)...
2026-11-11 10:25:18 [INFO] scope: Starting Scope workstation in foreground (PID 85090)...
2026-11-11 10:25:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:25:23] "GET / HTTP/1.1" 200 -
2026-11-11 10:25:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:25:23] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 10:25:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:25:23] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 10:25:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:25:23] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 10:25:23 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 10:25:23] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
◈ SCOPE // CAD/PCB WORKSTATION ◈
  Target: (None - Select target via workstation UI)
  URL:    http://127.0.0.1:8000/
Desktop window closed; shutting down scope server...
2026-11-11 10:33:03 [INFO] scope: Starting Scope workstation in foreground (PID 89755)...
2026-11-11 10:33:07 [INFO] scope: Starting Scope workstation in foreground (PID 89809)...
2026-11-11 10:33:10 [INFO] scope: Starting Scope workstation in foreground (PID 89890)...
2026-11-11 10:34:14 [INFO] scope: Starting Scope workstation in foreground (PID 90362)...
2026-11-11 10:35:50 [INFO] scope: Starting Scope workstation in foreground (PID 94798)...
2026-11-11 11:10:50 [INFO] scope: Starting Scope workstation in foreground (PID 8246)...
2026-11-11 11:19:13 [INFO] scope: Starting Scope workstation in foreground (PID 13796)...
2026-11-11 11:19:25 [INFO] scope: Starting Scope workstation in foreground (PID 14193)...
2026-11-11 11:19:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:19:30] "GET / HTTP/1.1" 200 -
2026-11-11 11:19:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:19:30] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 11:19:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:19:30] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 11:19:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:19:30] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 11:19:30 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:19:30] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 14193).
Desktop window closed; shutting down scope server...
2026-11-11 11:24:44 [INFO] scope: Starting Scope workstation in foreground (PID 19903)...
2026-11-11 11:44:22 [INFO] scope: Starting Scope workstation in foreground (PID 33787)...
2026-11-11 11:44:25 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:44:25] "GET / HTTP/1.1" 200 -
2026-11-11 11:44:25 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:44:25] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 11:44:25 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:44:25] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 11:44:25 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:44:25] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 11:44:25 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:44:25] "GET /static/scope-icon.svg HTTP/1.1" 200 -
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 33787).
Desktop window closed; shutting down scope server...
2026-11-11 11:45:09 [INFO] scope: Starting Scope workstation in foreground (PID 34286)...
2026-11-11 11:45:11 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:11] "GET / HTTP/1.1" 200 -
2026-11-11 11:45:11 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:11] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 11:45:11 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:11] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 11:45:11 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:11] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 11:45:11 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:11] "GET /static/scope-icon.svg HTTP/1.1" 200 -
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 34286).
Desktop window closed; shutting down scope server...
2026-11-11 11:45:44 [INFO] scope: Starting Scope workstation in foreground (PID 34599)...
2026-11-11 11:45:46 [INFO] scope: Background pre-warming geometry for cat_fountain/product [CAD]...
2026-11-11 11:45:46 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: cad, step: None)...
2026-11-11 11:45:46 [WARNING] scope: Background pre-warming error for cat_fountain/product: 'cad' is not a valid Section
2026-11-11 11:45:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:47] "GET /?project=cat_fountain&target=product&subassembly=cad&mode=CAD HTTP/1.1" 200 -
2026-11-11 11:45:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:47] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 11:45:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:47] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 11:45:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:47] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 11:45:47 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 11:45:47] "GET /static/scope-icon.svg HTTP/1.1" 200 -
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=cad&mode=CAD (PID 34599).
Desktop window closed; shutting down scope server...
2026-11-11 11:51:01 [INFO] scope: Starting Scope workstation in foreground (PID 37048)...
2026-11-11 11:51:31 [INFO] scope: Starting Scope workstation in foreground (PID 37251)...
2026-11-11 12:03:24 [INFO] scope: Starting Scope workstation in foreground (PID 41866)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 41866).
2026-11-11 12:03:24 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 12:03:24 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.047s (1.71 MB compressed)
2026-11-11 12:03:24 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.05s
2026-11-11 12:03:53 [INFO] scope: Starting Scope workstation in foreground (PID 42060)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 42060).
2026-11-11 12:03:53 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 12:03:53 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.049s (1.71 MB compressed)
2026-11-11 12:03:53 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.05s
2026-11-11 12:15:30 [INFO] scope: Starting Scope workstation in foreground (PID 50781)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 50781).
2026-11-11 12:15:30 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 12:15:30 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.050s (1.71 MB compressed)
2026-11-11 12:15:30 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.05s
2026-11-11 12:16:55 [INFO] scope: Starting Scope workstation in foreground (PID 55177)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 55177).
2026-11-11 12:16:55 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 12:16:55 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.049s (1.71 MB compressed)
2026-11-11 12:16:55 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.05s
2026-11-11 12:20:35 [INFO] scope: Starting Scope workstation in foreground (PID 60260)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 60260).
2026-11-11 12:20:35 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-11 12:20:35 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-11 13:49:44 [INFO] scope: Starting Scope workstation in foreground (PID 92337)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 92337).
2026-11-11 13:49:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:49:44] "GET / HTTP/1.1" 200 -
2026-11-11 13:49:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:49:44] "GET /static/common.css HTTP/1.1" 200 -
2026-11-11 13:49:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:49:44] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-11 13:49:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:49:44] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-11 13:49:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:49:44] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-11 13:49:44 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:49:44] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-11 13:49:52 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-11 13:49:52 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
face 46 ignored
2026-11-11 13:50:07 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 14.81s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-11 13:50:07 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 14.92s (1.32 MB compressed)
2026-11-11 13:50:07 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 14.92s
2026-11-11 13:50:07 [INFO] scope: 127.0.0.1 - - [11/Nov/2026 13:50:07] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
```

#### Attached Commits

- `b3594b22`
- `e40dabc6`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:fd325d61 --> Inspect cat fountain assembled CAD view and verify bottom cover fully occludes internal PCB footprints from below | `python tools/scope.py cat_fountain/product:cad`

#### Resolution Notes

Set bottom_cover in manifest.yaml to fully opaque alpha 1.0 and updated three-cad-viewer MaterialFactory._createBaseProps to only set transparent: true when alpha < 1.0, preserving opaque depth-testing and resolving Z-ordering bleed.
