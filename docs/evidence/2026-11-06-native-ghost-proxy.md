# Native ghost proxy geometry — 6 November 2026

Base: `8759a83eaed240ad37579e9d75fc10431964d005`. Initial source
`d47857e35df4fabe18cbea36e97ae32a0835bfac`; correction
`80854b8dd877727a2d7b424455f1141e279b613e`.

This self-authored filled car-shaped mesh is a pure diagnostic input for a
future renderer experiment. It applies a bounded position and a mathematical
unit quaternion, but has no SDK pose conversion, callback registration, actor,
alpha blending, game model, ghost availability or game-state mutation. Its
dimensions and visual appearance are not a finished Rocket League car.

The GPT-6.1 Sol high builder compiled C++17 Release and reported 2/2 CTests.
Independent GPT-6 Astra max found overlapping, inward-facing triangles in the
first concave side caps despite passing topology checks. The builder reproduced
and corrected the defect, added winding, area and overlap tests, and reported
2/2 CTests. Astra reviewed the corrected delta, independently confirmed the
original defect and correction, and reported MSVC Release CTest 1/1 with no
remaining blocker. Reviewer usage/cost metadata was not available.

No native rendering, alpha, callback lifetime, current-game compatibility,
successful flip-reset recording or live non-interference has been established.
