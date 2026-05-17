from __future__ import annotations

import warnings

from gronestats.processing.legacy import st_parquets_updater as _legacy

warnings.warn(
    "gronestats.processing.st_parquets_updater is deprecated. Use the pipeline and fantasy export modules "
    "or gronestats.processing.legacy.st_parquets_updater explicitly.",
    DeprecationWarning,
    stacklevel=2,
)

globals().update({name: value for name, value in vars(_legacy).items() if not name.startswith("__")})

if __name__ == "__main__":
    main = getattr(_legacy, "main", None)
    if callable(main):
        main()
