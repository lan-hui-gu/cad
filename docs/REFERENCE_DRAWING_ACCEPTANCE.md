# Reference drawing acceptance criteria

This document records the geometry visible in the user's 2026-11-05 reference sketch. Coordinates are approximate image pixels for regression tests, not survey measurements.

The simplified drawing must retain:
1. An upper narrow rectangular frame with two diagonal braces crossing as an X.
2. Two long parallel vertical lines from the upper frame to the middle enclosure.
3. A wide middle rectangle with one internal vertical divider.
4. A narrower lower rectangle centred beneath the middle enclosure.
5. Left-side vertical dimension/extension lines and the horizontal dimension line above the middle enclosure.
6. D1, Y1 and Y2 triangular markers, plus the 4 m elevation annotation.
7. OCR candidates for approximately 4.1 m, 9.4 m, 5.3 m, 4.6 m and 3.2 m, each requiring human confirmation.

Topology-preserving simplification must not merge nearby parallel paths just because they are close. It may merge only collinear fragments with a small endpoint gap, and it must split at real intersections so the X braces and T-junctions remain connected. Never infer real dimensions from pixels; the operator must provide or confirm the scale.

All CAD entities are created and saved by OpenCADStudio v2026.44 through its native local HTTP automation API. No secondary CAD writer is used.
