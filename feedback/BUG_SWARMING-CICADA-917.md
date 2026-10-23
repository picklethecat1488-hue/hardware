# 🟢 `[BUG-SWARMING-CICADA-917]` Replace motor room mount halls with clip mounts

- **UUID**: `098d867c-1283-4051-83af-26809d6149bc`
- **ID**: `BUG-SWARMING-CICADA-917`
- **Status**: `RESOLVED`
- **Severity**: `MEDIUM`
- **Category**: `CAD`
- **Component**: `cat_fountain`
- **Created**: `2026-10-23 23:07:38 UTC`
- **Resolved**: `2026-10-23 23:42:55 UTC`

#### Description

Can we please replace the mount holes with clip in mounts for every component but the charger? The mounting style for these revised mounts should be similar to what we did for the carrier_board enclosure where the board mounting holes can be press fit onto bossed posts which are slightly wide at the top. Additionally, the following mounts only need bosses with no posts for 2 mount points:

- Hall sensor
- Fuel gauge

Additionally, the hall sensor board requires only 2 mount points with posts.

#### Resolution Notes

Replaced motor room standoff mount holes with press-fit clip-in mounting posts (bossed posts with flared retaining heads) for Pico W, Current monitor, Fuel gauge, and Hall sensor. Retained blind screw holes for charger. Fuel gauge and Hall sensor mounts feature 2 bossed posts and 2 resting boss pads with no posts. Added dedicated regression unit test test_regression_bug_swarming_cicada_917_clip_in_mounts.
