# 🟢 `[BUG-MOTTLED-BUMBLEBEE-555]` [carrier_board/carrier_board] Defect Summary

- **UUID**: `12e7f183-6646-4931-80f4-e6611dc800d2`
- **ID**: `BUG-MOTTLED-BUMBLEBEE-555`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `carrier_board`
- **Created**: `2026-11-14 21:22:58 UTC`
- **Resolved**: `2026-11-15 03:10:31 UTC`

#### Description

Silkscreens for designators and labeling is mirrored horizontally

#### Reproduction Steps

1. python tools/scope.py carrier_board/carrier_board

#### Execution / Console Logs

```text
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
2026-11-12 12:49:35 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:49:35] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 12:50:05 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:50:05] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 12:50:40 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 12:52:45 [INFO] scope: Starting Scope workstation in foreground (PID 90079)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 90079).
2026-11-12 12:52:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:45] "GET / HTTP/1.1" 200 -
2026-11-12 12:52:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:45] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:52:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:45] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:52:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:45] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:52:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:45] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:52:45 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:45] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 12:52:48 [INFO] scope: Loading geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-12 12:52:48 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-12 12:52:52 [INFO] scope.pipeline: Geometry carrier_board/battery_cover [CAD] tessellated in 4.19s (1 parts, 1 instances, bounds: {'xmin': -31.899999618530273, 'xmax': 10.399999618530273, 'ymin': -30.399999618530273, 'ymax': 23.899999618530273, 'zmin': 0.0, 'zmax': 7.0})
2026-11-12 12:52:52 [INFO] scope.pipeline: Persisted disk cache for carrier_board/battery_cover [CAD] in 4.19s (0.01 MB compressed)
2026-11-12 12:52:52 [INFO] scope: Successfully loaded geometry for carrier_board/battery_cover [CAD] in 4.19s
2026-11-12 12:52:52 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:52:52] "GET /api/scope/load?project=carrier_board&target=battery_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-12 12:53:05 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 12:53:37 [INFO] scope: Starting Scope workstation in foreground (PID 90545)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=CAD (PID 90545).
2026-11-12 12:53:37 [INFO] scope: Background pre-warming geometry for cat_fountain/product [CAD]...
2026-11-12 12:53:37 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-12 12:53:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:38] "GET /?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-12 12:53:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:38] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:53:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:38] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:53:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:38] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:53:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:38] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:53:38 [INFO] scope: Loading geometry for cat_fountain/product [CAD] (subassembly: None, step: None)...
2026-11-12 12:53:38 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:38] "GET /api/scope/projects HTTP/1.1" 200 -
face 46 ignored
2026-11-12 12:53:52 [INFO] scope.pipeline: Geometry cat_fountain/product [CAD] tessellated in 15.07s (20 parts, 20 instances, bounds: {'xmin': -109.29315948486328, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 109.29315948486328, 'zmin': 0.0, 'zmax': 117.60000038146973})
2026-11-12 12:53:52 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [CAD] in 15.17s (1.32 MB compressed)
2026-11-12 12:53:52 [INFO] scope: Background pre-warming completed for cat_fountain/product in 15.17s
2026-11-12 12:53:52 [INFO] scope: Successfully loaded geometry for cat_fountain/product [CAD] in 14.59s
2026-11-12 12:53:52 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:52] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-12 12:53:58 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-12 12:53:58 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.005s (1.32 MB compressed)
2026-11-12 12:53:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:58] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 12:53:58 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:53:58] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-12 12:53:59 [INFO] scope: Loading geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 12:53:59 [INFO] scope.pipeline: Resolving and compiling geometry for cat_fountain/product [DIAGRAM] (subassembly: None, step: None)...
face 46 ignored
2026-11-12 12:54:01 [INFO] scope.pipeline: Geometry cat_fountain/product [DIAGRAM] tessellated in 2.08s (2 parts, 16 instances, bounds: {'xmin': -134.10793296424515, 'xmax': 109.29315948486328, 'ymin': -99.97997283935547, 'ymax': 128.61706314291132, 'zmin': -50.0, 'zmax': 197.60000038146973})
2026-11-12 12:54:02 [INFO] scope.pipeline: Persisted disk cache for cat_fountain/product [DIAGRAM] in 2.18s (1.37 MB compressed)
2026-11-12 12:54:02 [INFO] scope: Successfully loaded geometry for cat_fountain/product [DIAGRAM] in 2.19s
2026-11-12 12:54:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:02] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 12:54:15 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 12:54:24 [INFO] scope: Starting Scope workstation in foreground (PID 90909)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 90909).
2026-11-12 12:54:24 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 12:54:25 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.110s (2.87 MB compressed)
2026-11-12 12:54:25 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.12s
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 12:54:25 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 12:54:25 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.87 MB compressed)
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 12:54:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 12:54:25] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 12:54:32 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 13:37:31 [INFO] scope: Starting Scope workstation in foreground (PID 10724)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 10724).
2026-11-12 13:37:31 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 13:37:31 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.206s (2.87 MB compressed)
2026-11-12 13:37:31 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.21s
2026-11-12 14:10:03 [INFO] scope: Starting Scope workstation in foreground (PID 27508)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 27508).
2026-11-12 14:10:03 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 14:10:03 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.123s (2.87 MB compressed)
2026-11-12 14:10:03 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.13s
2026-11-12 14:20:06 [INFO] scope: Starting Scope workstation in foreground (PID 31611)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 31611).
2026-11-12 14:20:06 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 14:20:06 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 14:27:08 [INFO] scope: Starting Scope workstation in foreground (PID 34772)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 34772).
2026-11-12 14:27:08 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 14:27:09 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.127s (2.86 MB compressed)
2026-11-12 14:27:09 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 14:27:09 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 14:27:09 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.86 MB compressed)
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 14:27:09 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 14:27:09] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 14:27:51 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 14:50:20 [INFO] scope: Starting Scope workstation in foreground (PID 43306)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 43306).
2026-11-12 14:50:21 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 14:50:21 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.129s (2.86 MB compressed)
2026-11-12 14:50:21 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.13s
2026-11-12 15:01:01 [INFO] scope: Starting Scope workstation in foreground (PID 50999)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 50999).
2026-11-12 15:01:01 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 15:01:01 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.155s (2.86 MB compressed)
2026-11-12 15:01:01 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.16s
2026-11-12 15:05:25 [INFO] scope: Starting Scope workstation in foreground (PID 56249)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 56249).
2026-11-12 15:05:25 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 15:05:25 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.182s (2.86 MB compressed)
2026-11-12 15:05:25 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.19s
2026-11-12 15:43:46 [INFO] scope: Starting Scope workstation in foreground (PID 65074)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM (PID 65074).
2026-11-12 15:43:46 [INFO] scope: Background pre-warming geometry for cat_fountain/wiring [DIAGRAM]...
2026-11-12 15:43:46 [INFO] scope.pipeline: Disk cache hit for cat_fountain/wiring [DIAGRAM] in 0.024s (2.37 MB compressed)
2026-11-12 15:43:46 [INFO] scope: Background pre-warming completed for cat_fountain/wiring in 0.03s
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 15:43:47 [INFO] scope: Loading geometry for cat_fountain/wiring [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 15:43:47 [INFO] scope: Delivered cached geometry for cat_fountain/wiring [DIAGRAM] in 0.000s (2.37 MB compressed)
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /api/scope/load?project=cat_fountain&target=wiring&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 15:43:47 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:43:47] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 15:44:36 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 15:45:14 [INFO] scope: Starting Scope workstation in foreground (PID 65826)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 65826).
2026-11-12 15:45:14 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 15:45:15 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.124s (2.86 MB compressed)
2026-11-12 15:45:15 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 15:45:15 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 15:45:15 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.86 MB compressed)
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 15:45:15 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:15] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 15:45:54 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:45:54] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 15:46:31 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 15:47:18 [INFO] scope: Starting Scope workstation in foreground (PID 66903)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=cat_fountain&target=product&subassembly=&mode=SIMULATE (PID 66903).
2026-11-12 15:47:18 [INFO] scope: Background pre-warming geometry for cat_fountain/product [SIMULATE]...
2026-11-12 15:47:18 [INFO] scope.pipeline: Disk cache hit for cat_fountain/product [SIMULATE] in 0.010s (1.32 MB compressed)
2026-11-12 15:47:18 [INFO] scope: Background pre-warming completed for cat_fountain/product in 0.02s
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: Loading geometry for cat_fountain/product [SIMULATE] (subassembly: None, step: None)...
2026-11-12 15:47:19 [INFO] scope: Delivered cached geometry for cat_fountain/product [SIMULATE] in 0.000s (1.32 MB compressed)
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /api/scope/load?project=cat_fountain&target=product&subassembly=&mode=SIMULATE HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 15:47:19 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 15:47:19] "GET /api/scope/simulation_telemetry?project=cat_fountain&target=product HTTP/1.1" 200 -
2026-11-12 15:47:38 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 15:54:24 [INFO] scope: Starting Scope workstation in foreground (PID 70008)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 70008).
2026-11-12 15:54:24 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 15:54:24 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.118s (2.86 MB compressed)
2026-11-12 15:54:24 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.12s
2026-11-12 16:00:20 [INFO] scope: Starting Scope workstation in foreground (PID 72019)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 72019).
2026-11-12 16:00:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:20] "GET / HTTP/1.1" 200 -
2026-11-12 16:00:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:20] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 16:00:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:20] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 16:00:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:20] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 16:00:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:20] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 16:00:20 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:20] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:00:22 [INFO] scope: Loading geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-12 16:00:22 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/battery_cover [CAD] (subassembly: None, step: None)...
2026-11-12 16:00:27 [INFO] scope.pipeline: Geometry carrier_board/battery_cover [CAD] tessellated in 4.16s (1 parts, 1 instances, bounds: {'xmin': -31.899999618530273, 'xmax': 10.399999618530273, 'ymin': -30.399999618530273, 'ymax': 23.899999618530273, 'zmin': 0.0, 'zmax': 7.0})
2026-11-12 16:00:27 [INFO] scope.pipeline: Persisted disk cache for carrier_board/battery_cover [CAD] in 4.17s (0.01 MB compressed)
2026-11-12 16:00:27 [INFO] scope: Successfully loaded geometry for carrier_board/battery_cover [CAD] in 4.17s
2026-11-12 16:00:27 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:27] "GET /api/scope/load?project=carrier_board&target=battery_cover&subassembly=&mode=CAD HTTP/1.1" 200 -
2026-11-12 16:00:34 [INFO] scope: Loading geometry for carrier_board/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 16:00:34 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/product [DIAGRAM] (subassembly: None, step: None)...
2026-11-12 16:00:42 [INFO] scope.pipeline: Geometry carrier_board/product [DIAGRAM] tessellated in 7.69s (6 parts, 6 instances, bounds: {'xmin': -33.5, 'xmax': 36.0, 'ymin': -48.5, 'ymax': 87.75, 'zmin': -8.300000190734863, 'zmax': 17.8})
2026-11-12 16:00:42 [INFO] scope.pipeline: Persisted disk cache for carrier_board/product [DIAGRAM] in 7.74s (0.56 MB compressed)
2026-11-12 16:00:42 [INFO] scope: Successfully loaded geometry for carrier_board/product [DIAGRAM] in 7.74s
2026-11-12 16:00:42 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:00:42] "GET /api/scope/load?project=carrier_board&target=product&subassembly=&mode=DIAGRAM HTTP/1.1" 200 -
2026-11-12 16:01:03 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 16:06:01 [INFO] scope: Starting Scope workstation in foreground (PID 77018)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 77018).
2026-11-12 16:06:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:02] "GET / HTTP/1.1" 200 -
2026-11-12 16:06:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:02] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 16:06:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:02] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 16:06:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:02] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 16:06:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:02] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 16:06:02 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:02] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:06:16 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:06:16 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:06:26 [INFO] scope: Starting Scope workstation in foreground (PID 77760)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 77760).
2026-11-12 16:06:26 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 16:06:26 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:06:29 [INFO] scope: Loading geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-12 16:06:29 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [CAD] (subassembly: None, step: None)...
2026-11-12 16:06:52 [INFO] scope: Starting Scope workstation in foreground (PID 77998)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 77998).
2026-11-12 16:06:53 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:53] "GET / HTTP/1.1" 200 -
2026-11-12 16:06:53 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:53] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 16:06:53 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:53] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 16:06:53 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:53] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 16:06:53 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:53] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 16:06:53 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:06:53] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:06:58 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:06:58 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:08:22 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 84.08s (7 parts, 5795 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -0.8400000000000001, 'zmax': 0.8400000000000002})
2026-11-12 16:08:22 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [PCB] in 84.63s (2.86 MB compressed)
2026-11-12 16:08:22 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 84.63s
2026-11-12 16:08:23 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:08:23] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 16:11:25 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:11:25] "POST /api/scope/target_bug HTTP/1.1" 200 -
2026-11-12 16:12:07 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 16:17:46 [INFO] scope: Starting Scope workstation in foreground (PID 85813)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 85813).
2026-11-12 16:17:46 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 16:17:46 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.111s (2.86 MB compressed)
2026-11-12 16:17:46 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.11s
2026-11-12 16:31:18 [INFO] scope: Starting Scope workstation in foreground (PID 94356)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 94356).
2026-11-12 16:31:18 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 16:31:18 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.202s (2.86 MB compressed)
2026-11-12 16:31:18 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.21s
2026-11-12 16:40:40 [INFO] scope: Starting Scope workstation in foreground (PID 97762)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 97762).
2026-11-12 16:40:41 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:41] "GET / HTTP/1.1" 200 -
2026-11-12 16:40:41 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:41] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 16:40:41 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:41] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 16:40:41 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:41] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 16:40:41 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:41] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 16:40:41 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:41] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:40:49 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:40:49 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.006s (2.86 MB compressed)
2026-11-12 16:40:49 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:40:49] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 16:41:16 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 16:44:03 [INFO] scope: Starting Scope workstation in foreground (PID 99593)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 99593).
2026-11-12 16:44:03 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 16:44:03 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.126s (2.86 MB compressed)
2026-11-12 16:44:03 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.14s
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 16:44:04 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:44:04 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.000s (2.86 MB compressed)
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 16:44:04 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:44:04] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:44:26 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 16:45:00 [INFO] scope: Starting Scope workstation in foreground (PID 430)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 430).
2026-11-12 16:45:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:00] "GET / HTTP/1.1" 200 -
2026-11-12 16:45:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:00] "GET /static/common.css HTTP/1.1" 200 -
2026-11-12 16:45:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:00] "GET /static/three-cad-viewer.css HTTP/1.1" 200 -
2026-11-12 16:45:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:00] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-12 16:45:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:00] "GET /static/three-cad-viewer.esm.js HTTP/1.1" 200 -
2026-11-12 16:45:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:00] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:45:07 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:45:07 [INFO] scope: Delivered cached geometry for carrier_board/carrier_board [PCB] in 0.008s (2.86 MB compressed)
2026-11-12 16:45:07 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:07] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 16:45:26 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:26] "GET /api/scope/sync HTTP/1.1" 200 -
2026-11-12 16:45:26 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:45:26] "GET /api/scope/projects HTTP/1.1" 200 -
2026-11-12 16:45:26 [INFO] scope: Loading geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:45:26 [INFO] scope.pipeline: Resolving and compiling geometry for carrier_board/carrier_board [PCB] (subassembly: None, step: None)...
2026-11-12 16:46:00 [INFO] scope.pipeline: Geometry carrier_board/carrier_board [PCB] tessellated in 33.38s (7 parts, 5795 instances, bounds: {'xmin': -30.0, 'xmax': 30.0, 'ymin': -45.0, 'ymax': 45.0, 'zmin': -0.8400000000000001, 'zmax': 0.8400000000000002})
2026-11-12 16:46:00 [INFO] scope.pipeline: Persisted disk cache for carrier_board/carrier_board [PCB] in 33.72s (2.86 MB compressed)
2026-11-12 16:46:00 [INFO] scope: Successfully loaded geometry for carrier_board/carrier_board [PCB] in 33.72s
2026-11-12 16:46:00 [INFO] scope: 127.0.0.1 - - [12/Nov/2026 16:46:00] "GET /api/scope/load?project=carrier_board&target=carrier_board&subassembly=&mode=PCB HTTP/1.1" 200 -
2026-11-12 16:46:32 [INFO] scope: Desktop window closed; shutting down scope server...
2026-11-12 20:29:41 [INFO] scope: Starting Scope workstation in foreground (PID 49786)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 49786).
2026-11-12 20:29:41 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 20:29:41 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.03 MB compressed)
2026-11-12 20:29:41 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.00s
2026-11-12 22:08:49 [INFO] scope: Starting Scope workstation in foreground (PID 82506)...
➜ Scope workstation running at http://127.0.0.1:8000/?project=carrier_board&target=carrier_board&subassembly=&mode=PCB (PID 82506).
2026-11-12 22:08:49 [INFO] scope: Background pre-warming geometry for carrier_board/carrier_board [PCB]...
2026-11-12 22:08:49 [INFO] scope.pipeline: Disk cache hit for carrier_board/carrier_board [PCB] in 0.002s (0.03 MB compressed)
2026-11-12 22:08:49 [INFO] scope: Background pre-warming completed for carrier_board/carrier_board in 0.00s
2026-11-14 13:16:25 [INFO] scope: Starting Scope workstation in foreground (PID 35228)...
➜ Scope workstation running at http://127.0.0.1:8000/ (PID 35228).
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET / HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /static/common.css HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/main.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /static/scope-icon.svg HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/resizer.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/toast.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/camera_controller.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/ui_scale.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/cad_scene.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/core/runtime_context.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/decoder.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/markup_tool.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/inspector.js HTTP/1.1" 200 -
2026-11-14 13:16:26 [INFO] scope: 127.0.0.1 - - [14/Nov/2026 13:16:26] "GET /js/scope/sim_renderer.js HTTP/1.1" 200 -
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
```

#### Attached Commits

- `abef5295`

#### Review Tasks & Functional Checklist

- [ ] <!-- task:2d32dd79 --> Inspect carrier_board in 3D CAD view (both Top and Bottom sides) and verify all silkscreen board labels (OVERRIDES, STATUS, RESET) and reference designators (U1, R1, C1) read left-to-right without horizontal mirroring | `python tools/scope.py carrier_board/carrier_board`

#### Resolution Notes

Removed the legacy 180-deg X reflection from F.SilkS text & reference designator extrusions and rotated B.SilkS extrusions by 180 deg around Y in PCB3DAssembler.build_silkscreen so both top and bottom silkscreens read unmirrored left-to-right in Scope right-handed 3D CAD coordinates.
