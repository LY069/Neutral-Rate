"""The six BOJ-surveyed estimation methods for Japan's natural rate of interest."""
from . import (  # noqa: F401
    delnegro_var,
    dsge,
    goy_iwasaki,
    hlw,
    nakajima_nyc,
    natural_yield_curve,
)

# Display name -> (module, citation) for the orchestrator / reports.
METHOD_REGISTRY = {
    "HLW (2023)": (hlw, "Holston, Laubach & Williams (2017/2023)"),
    "DSGE (Okazaki-Sudo 2018)": (dsge, "Okazaki & Sudo (2018), BOJ WP 18-E-6"),
    "Natural Yield Curve (Imakubo et al. 2015)":
        (natural_yield_curve, "Imakubo, Kojima & Nakajima (2015)"),
    "Natural Yield Curve (Nakajima et al. 2023)":
        (nakajima_nyc, "Nakajima, Sudo, Hogen & Takizuka (2023)"),
    "Macro-finance (Goy-Iwasaki 2024)":
        (goy_iwasaki, "Goy & Iwasaki (2024)"),
    "VAR common trends (Del Negro et al. 2017)":
        (delnegro_var, "Del Negro, Giannone, Giannoni & Tambalotti (2017)"),
}
