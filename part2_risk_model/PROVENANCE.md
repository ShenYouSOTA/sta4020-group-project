# Provenance

This directory is a vendored copy of the Part 2 package, not a submodule.

- Upstream: https://github.com/JYWang05/barra-style-risk-model
- Commit: 87773b2 ("Expose risk options and separate dynamic integration methods")
- Vendored: 2026-11-21
- Licence: MIT (see LICENSE in this directory)

Why vendored rather than a submodule: the graded deliverable is a zip of the
repository, and a submodule would ship an empty directory.  A nested repository
would also be silently skipped by the outer repository, so the code would look
present locally and be missing everywhere else.

Rules:

1. Do not edit the vendored sources in place.  The Part 2 owner's adapter,
   panel construction and calibration live outside this directory, in
   src/sta4020_project/part2/ (to be created) or in scripts/.
2. If upstream is updated, replace this directory wholesale and update the
   commit hash above, so a reported number can still be traced to its code.
3. Keep the upstream README and LICENSE untouched.
