# 🟢 `[BUG-VERMIFORM-CRAWLER-442]` Update issue ID generator with bug and insect themed nouns and adjectives

- **UUID**: `62b936ce-96d2-49bd-ae8c-1160e14ee039`
- **ID**: `BUG-VERMIFORM-CRAWLER-442`
- **Status**: `RESOLVED`
- **Severity**: `LOW`
- **Category**: `INFRASTRUCTURE`
- **Component**: `id_generator`
- **Created**: `2026-10-15 04:09:20 UTC`
- **Resolved**: `2026-10-15 04:15:08 UTC`

#### Description

Issue ID generator currently uses worm and annelid terms ported from WORM-029 (sandworm, oligochaete, tapeworm, etc.). Update dictionaries in id_generator.py and bug_report.html.j2 with true bug, insect, and arthropod themed names (cicada, mantis, dragonfly, beetle, firefly, etc.) while preserving backward compatibility with existing Docker-pattern regex.

#### Resolution Notes

Updated issue ID generator compressed word lists in id_generator.py and frontend bug_report.html.j2 with true bug and insect themed nouns (cicada, mantis, dragonfly, beetle, firefly, etc.) and adjectives (buzzing, winged, chitinous, iridescent, etc.), purged worm/annelid terms, and added regression test test_regression_bug_vermiform_crawler_442_bug_themed_id_generator.
