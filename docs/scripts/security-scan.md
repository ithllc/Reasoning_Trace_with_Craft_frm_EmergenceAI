# `scripts/security_scan.py`

Purpose: detect common credential shapes, known event identifiers, and private event endpoints without printing secret values. The default scans the working tree excluding ignored private planning and run files. `--history` scans all Git revisions and reports only commit fingerprints. A history finding requires revocation first, then a coordinated `git filter-repo` rewrite and fresh-clone verification.
