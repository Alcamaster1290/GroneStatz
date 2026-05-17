from __future__ import annotations

import warnings

from gronestats.processing.legacy import normalize_parquets as _legacy

warnings.warn(
    "gronestats.processing.normalize_parquets is deprecated. Use gronestats.processing.pipeline "
    "or gronestats.processing.legacy.normalize_parquets explicitly.",
    DeprecationWarning,
    stacklevel=2,
)

globals().update({name: value for name, value in vars(_legacy).items() if not name.startswith("__")})

if __name__ == "__main__":
    main = getattr(_legacy, "main", None)
    if callable(main):
        main()

