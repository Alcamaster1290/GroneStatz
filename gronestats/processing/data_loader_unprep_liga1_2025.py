from __future__ import annotations

import warnings

from gronestats.processing.legacy import data_loader_unprep_liga1_2025 as _legacy

warnings.warn(
    "gronestats.processing.data_loader_unprep_liga1_2025 is deprecated. Use gronestats.processing.pipeline "
    "for production runs or gronestats.processing.legacy.data_loader_unprep_liga1_2025 explicitly.",
    DeprecationWarning,
    stacklevel=2,
)

globals().update({name: value for name, value in vars(_legacy).items() if not name.startswith("__")})

if __name__ == "__main__":
    main = getattr(_legacy, "main", None)
    if callable(main):
        main()

