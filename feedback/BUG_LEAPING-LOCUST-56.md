# 🟢 `[BUG-LEAPING-LOCUST-56]` Pump cover annular ring-insufficient clearance

- **UUID**: `2c95825d-9a2a-4977-a1ed-8d6df2694fb3`
- **ID**: `BUG-LEAPING-LOCUST-56`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-07 00:27:53 UTC`
- **Resolved**: `2026-11-07 00:39:02 UTC`

#### Description

The inner annular ring for the pump cover may have insufficient clearance to fit inside the bowl’s pump cover mount when epoxy is applied. Can we move the annular ring and mount lower (-Z)?

#### Attached Commits

- `c5e17c62ec7760b87ec631fa762a939765866323`

#### Resolution Notes

Moved pump cover mount recess depth to 2.5mm and annular snap ridge/groove Z offset to 1.5mm lower (-Z) to provide generous epoxy clearance
