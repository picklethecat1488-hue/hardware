# 🟢 `[BUG-SWIFT-MITE-462]` The engineering questions of your 3D print order#C-E72W908185A_bowl.stl

- **UUID**: `a736e893-03c5-43c4-9dce-db6b5b6c5d1d`
- **ID**: `BUG-SWIFT-MITE-462`
- **Status**: `CLOSED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-11-09 18:19:42 UTC`
- **Resolved**: `2026-11-09 23:00:49 UTC`
- **Accepted**: `2026-11-09 23:00:55 UTC`

#### Description

1. See the attached pic, the thickness for red-indicated places is too thin, and they may be broken during printing. There are two suggestions for your reference.
A. Increase the thickness to 1 mm. And then send the new file to us for an update.

#### Attached Commits

- `b8520759`

#### Review Tasks & Functional Checklist

- [x] <!-- task:a23e29b4 --> Build bowl STL and inspect PCB clip detent lip and charger port wall thickness | `python tools/build.py cat_fountain:bowl:stl`

#### Resolution Notes

Increase PCB clip retaining lip thickness to 1.0mm and parameterize charger port cutout depth to 6.0mm ensuring >= 1.0mm wall thickness
