from __future__ import annotations

import warnings

from gronestats.processing.legacy import st_parquets_dashboard as _legacy

warnings.warn(
    "gronestats.processing.st_parquets_dashboard is deprecated. Use published bundles from the pipeline "
    "or gronestats.processing.legacy.st_parquets_dashboard explicitly.",
    DeprecationWarning,
    stacklevel=2,
)

globals().update({name: value for name, value in vars(_legacy).items() if not name.startswith("__")})

if __name__ == "__main__":
    main = getattr(_legacy, "main", None)
    if callable(main):
        main()

