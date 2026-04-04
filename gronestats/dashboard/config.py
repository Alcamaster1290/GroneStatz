from __future__ import annotations

from pathlib import Path

APP_TITLE = "GroneStatz"
APP_SUBTITLE = "Dashboard analitico de Liga 1"
LEAGUE_NAME = "Liga 1 Peru"
DEFAULT_SEASON_YEAR = 2025


def build_season_label(season_year: int) -> str:
    return f"Liga 1 {season_year}"

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_ROOT = BASE_DIR / "gronestats" / "data" / LEAGUE_NAME
PLAYER_IMAGES_DIR = BASE_DIR / "gronestats" / "images" / "players"
TEAM_IMAGES_DIR = BASE_DIR / "gronestats" / "images" / "teams"

REGULAR_SEASON_MAX_ROUND = 20
ROUND_RANGE_FALLBACK = (1, REGULAR_SEASON_MAX_ROUND)
TOP_FORM_TEAMS = 5
RECENT_FORM_MATCHES = 5

TOURNAMENT_LABELS = {
    "Liga 1, Apertura": "Apertura",
    "Liga 1, Clausura": "Clausura",
    "Primera Division, Grand Final": "Grand Final",
}

TOURNAMENT_ORDER = {
    "Liga 1, Apertura": 0,
    "Liga 1, Clausura": 1,
    "Primera Division, Grand Final": 2,
}

DEFAULT_DASHBOARD_TOURNAMENTS = (
    "Liga 1, Apertura",
    "Liga 1, Clausura",
)

COLORS = {
    "bg": "#081019",
    "surface": "#0f1824",
    "surface_alt": "#142030",
    "border": "#263447",
    "text": "#edf2f7",
    "muted": "#9aa8ba",
    "accent": "#c6b170",
    "accent_alt": "#7ec4b8",
    "success": "#63d08b",
    "warning": "#d9bf6a",
    "danger": "#db7c7c",
}

PREFERRED_MATCH_STATS = [
    ("Posesion", "ballPossession", True),
    ("Tiros totales", "totalShotsOnGoal", False),
    ("Tiros al arco", "shotsOnGoal", False),
    ("Corners", "cornerKicks", False),
    ("Atajadas", "goalkeeperSaves", False),
    ("Pases", "passes", False),
    ("Pases precisos", "accuratePasses", False),
    ("Faltas", "fouls", False),
    ("Tarjetas amarillas", "yellowCards", False),
]

BASE_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Newsreader:opsz,wght@6..72,500;6..72,700&display=swap');

:root {{
  --gs-bg: {COLORS["bg"]};
  --gs-surface: {COLORS["surface"]};
  --gs-surface-alt: {COLORS["surface_alt"]};
  --gs-border: {COLORS["border"]};
  --gs-text: {COLORS["text"]};
  --gs-muted: {COLORS["muted"]};
  --gs-accent: {COLORS["accent"]};
  --gs-accent-alt: {COLORS["accent_alt"]};
  --gs-success: {COLORS["success"]};
  --gs-warning: {COLORS["warning"]};
  --gs-danger: {COLORS["danger"]};
}}

html, body, [class*="css"] {{
  font-family: "Plus Jakarta Sans", sans-serif;
}}

.stApp {{
  background:
    radial-gradient(circle at top left, rgba(198, 177, 112, 0.18), transparent 28%),
    radial-gradient(circle at top right, rgba(126, 196, 184, 0.12), transparent 24%),
    linear-gradient(180deg, #09111b 0%, #081019 100%);
  color: var(--gs-text);
}}

[data-testid="stSidebar"] {{
  background:
    linear-gradient(180deg, rgba(10, 17, 27, 0.98), rgba(12, 20, 30, 0.98)),
    var(--gs-bg);
  border-right: 1px solid rgba(198, 177, 112, 0.16);
}}

[data-testid="stSidebar"] * {{
  color: var(--gs-text);
}}

[data-testid="stSidebarNav"] {{
  display: none;
}}

.block-container {{
  padding-top: 1.1rem;
  padding-bottom: 2rem;
  max-width: 1480px;
}}

.gs-shell {{
  display: grid;
  gap: 1rem;
}}

.gs-header {{
  display: grid;
  gap: 0.35rem;
  padding: 1rem 1.15rem 0.95rem;
  border: 1px solid rgba(198, 177, 112, 0.18);
  border-radius: 22px;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)),
    rgba(15, 24, 36, 0.92);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
}}

.gs-header__eyebrow {{
  color: var(--gs-accent);
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}}

.gs-header__title {{
  margin: 0;
  color: var(--gs-text);
  font-family: "Newsreader", serif;
  font-size: clamp(2rem, 3vw, 3.4rem);
  line-height: 0.92;
  letter-spacing: -0.04em;
}}

.gs-header__subtitle {{
  margin: 0;
  max-width: 68ch;
  color: var(--gs-muted);
  font-size: 0.95rem;
  line-height: 1.55;
}}

.gs-chip-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 0.2rem;
}}

.gs-chip {{
  border: 1px solid rgba(198, 177, 112, 0.18);
  border-radius: 999px;
  padding: 0.34rem 0.64rem;
  color: var(--gs-text);
  background: rgba(255, 255, 255, 0.03);
  font-size: 0.76rem;
}}

.gs-section-title {{
  margin: 0.15rem 0 0.4rem;
  color: var(--gs-text);
  font-size: 1.03rem;
  font-weight: 700;
}}

.gs-kpi-card {{
  display: grid;
  gap: 0.2rem;
  min-height: 106px;
  padding: 0.8rem 0.82rem;
  border-radius: 16px;
  border: 1px solid rgba(198, 177, 112, 0.12);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.02)),
    rgba(15, 24, 36, 0.88);
}}

.gs-kpi-card__label {{
  color: var(--gs-muted);
  font-size: 0.74rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}

.gs-kpi-card__value {{
  color: var(--gs-text);
  font-family: "Newsreader", serif;
  font-size: clamp(1.45rem, 2vw, 2.3rem);
  line-height: 0.95;
}}

.gs-kpi-card__help {{
  color: var(--gs-muted);
  font-size: 0.76rem;
  line-height: 1.32;
}}

.gs-panel {{
  padding: 0.8rem 0.9rem 0.9rem;
  border-radius: 20px;
  border: 1px solid rgba(198, 177, 112, 0.12);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.015)),
    rgba(15, 24, 36, 0.88);
}}

.gs-mini-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.7rem;
  margin: 0.35rem 0 0;
}}

.gs-mini-meta span {{
  color: var(--gs-muted);
  font-size: 0.82rem;
}}

.gs-form-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.38rem;
  margin-top: 0.38rem;
}}

.gs-form-chip {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2rem;
  padding: 0.28rem 0.52rem;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
}}

.gs-form-chip--W {{
  background: rgba(99, 208, 139, 0.18);
  color: var(--gs-success);
}}

.gs-form-chip--D {{
  background: rgba(217, 191, 106, 0.18);
  color: var(--gs-warning);
}}

.gs-form-chip--L {{
  background: rgba(219, 124, 124, 0.18);
  color: var(--gs-danger);
}}

.gs-form-chip--NA {{
  background: rgba(255, 255, 255, 0.06);
  color: var(--gs-muted);
}}

.gs-note {{
  color: var(--gs-muted);
  font-size: 0.8rem;
  line-height: 1.45;
}}

.gs-empty {{
  border: 1px dashed rgba(154, 168, 186, 0.34);
  border-radius: 16px;
  padding: 0.85rem 0.9rem;
  color: var(--gs-muted);
  background: rgba(255, 255, 255, 0.02);
  font-size: 0.86rem;
}}

.stButton > button,
.stDownloadButton > button {{
  min-height: 2.68rem;
  border-radius: 14px;
  border: 1px solid rgba(198, 177, 112, 0.14);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.018)),
    rgba(15, 24, 36, 0.88);
  color: var(--gs-text);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}}

.stButton > button:hover,
.stDownloadButton > button:hover {{
  border-color: rgba(198, 177, 112, 0.34);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.022)),
    rgba(18, 29, 43, 0.96);
  transform: translateY(-1px);
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.24);
}}

.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible {{
  outline: 3px solid rgba(126, 196, 184, 0.48);
  outline-offset: 2px;
  border-color: rgba(126, 196, 184, 0.52);
}}

.stButton > button:active,
.stDownloadButton > button:active {{
  transform: translateY(0);
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.2);
}}

.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {{
  border-color: rgba(198, 177, 112, 0.3);
  background:
    linear-gradient(180deg, rgba(198,177,112,0.22), rgba(198,177,112,0.12)),
    rgba(15, 24, 36, 0.96);
}}

.stButton > button:disabled,
.stDownloadButton > button:disabled {{
  opacity: 0.55;
  transform: none;
  box-shadow: none;
}}

.gs-selection-note {{
  margin: -0.1rem 0 0.5rem;
  color: var(--gs-muted);
  font-size: 0.78rem;
  line-height: 1.42;
}}

.gs-link-card {{
  display: grid;
  gap: 0.24rem;
  padding: 0.72rem 0.8rem;
  border-radius: 15px;
  border: 1px solid rgba(198, 177, 112, 0.1);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.018)),
    rgba(15, 24, 36, 0.9);
  transition:
    transform 180ms ease,
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease;
}}

.gs-link-card--active {{
  border-color: rgba(198, 177, 112, 0.34);
  background:
    radial-gradient(circle at top right, rgba(198,177,112,0.12), transparent 34%),
    linear-gradient(180deg, rgba(255,255,255,0.045), rgba(255,255,255,0.024)),
    rgba(17, 28, 40, 0.96);
  box-shadow: 0 18px 34px rgba(0, 0, 0, 0.22);
}}

.gs-link-card__eyebrow {{
  color: var(--gs-accent);
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}}

.gs-link-card__title {{
  color: var(--gs-text);
  font-size: 0.93rem;
  font-weight: 700;
  line-height: 1.22;
}}

.gs-link-card__note {{
  color: var(--gs-muted);
  font-size: 0.78rem;
  line-height: 1.38;
}}

.gs-link-card__meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.32rem 0.38rem;
  margin-top: 0.08rem;
}}

.gs-link-card__meta span {{
  border-radius: 999px;
  padding: 0.22rem 0.48rem;
  border: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.03);
  color: var(--gs-muted);
  font-size: 0.7rem;
}}

.gs-catalog-shell {{
  display: grid;
  gap: 0.55rem;
}}

.gs-catalog-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}}

.gs-catalog-header__count {{
  color: var(--gs-muted);
  font-size: 0.76rem;
}}

.gs-match-switcher {{
  display: grid;
  gap: 0.28rem;
  padding: 0.72rem 0.82rem;
  border-radius: 16px;
  border: 1px solid rgba(198, 177, 112, 0.12);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.028), rgba(255,255,255,0.016)),
    rgba(15, 24, 36, 0.88);
}}

.gs-match-switcher__title {{
  margin: 0;
  color: var(--gs-text);
  font-size: 0.92rem;
  font-weight: 700;
}}

.gs-match-switcher__note {{
  margin: 0;
  color: var(--gs-muted);
  font-size: 0.78rem;
  line-height: 1.36;
}}

.gs-match-switcher__meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.28rem 0.34rem;
}}

.gs-match-switcher__meta span {{
  border-radius: 999px;
  padding: 0.18rem 0.44rem;
  border: 1px solid rgba(255, 255, 255, 0.06);
  background: rgba(255, 255, 255, 0.03);
  color: var(--gs-muted);
  font-size: 0.68rem;
}}

.gs-toolbar {{
  display: grid;
  gap: 0.52rem;
  padding: 0.75rem 0.88rem;
  border-radius: 18px;
  border: 1px solid rgba(198, 177, 112, 0.14);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.012)),
    rgba(15, 24, 36, 0.84);
}}

.gs-toolbar__kicker {{
  color: var(--gs-accent);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}}

.gs-toolbar__title {{
  margin: 0;
  color: var(--gs-text);
  font-size: 0.92rem;
  font-weight: 700;
}}

.gs-toolbar__note {{
  margin: 0;
  color: var(--gs-muted);
  font-size: 0.8rem;
  line-height: 1.42;
}}

.gs-match-hero {{
  display: grid;
  gap: 0.72rem;
  padding: 0.88rem 0.96rem 0.86rem;
  border-radius: 20px;
  border: 1px solid rgba(198, 177, 112, 0.18);
  background:
    radial-gradient(circle at center, rgba(198, 177, 112, 0.06), transparent 36%),
    linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.012)),
    rgba(15, 24, 36, 0.92);
  box-shadow: 0 24px 54px rgba(0, 0, 0, 0.28);
}}

.gs-match-hero__grid {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: end;
  gap: 0.75rem;
}}

.gs-match-hero__team {{
  display: grid;
  gap: 0.1rem;
}}

.gs-match-hero__team--away {{
  text-align: right;
}}

.gs-match-hero__eyebrow {{
  color: var(--gs-accent);
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}}

.gs-match-hero__name {{
  margin: 0;
  color: var(--gs-text);
  font-family: "Newsreader", serif;
  font-size: clamp(1.45rem, 2.2vw, 2.4rem);
  line-height: 0.94;
  letter-spacing: -0.04em;
}}

.gs-match-hero__context {{
  color: var(--gs-muted);
  font-size: 0.8rem;
}}

.gs-match-hero__score {{
  display: grid;
  justify-items: center;
  gap: 0.1rem;
}}

.gs-match-hero__scoreline {{
  color: var(--gs-text);
  font-family: "Newsreader", serif;
  font-size: clamp(1.95rem, 3.6vw, 3.4rem);
  line-height: 0.88;
  letter-spacing: -0.08em;
}}

.gs-match-hero__caption {{
  color: var(--gs-muted);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}}

.gs-match-hero__meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}}

.gs-match-hero__meta span {{
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  padding: 0.28rem 0.52rem;
  color: var(--gs-muted);
  background: rgba(255, 255, 255, 0.025);
  font-size: 0.74rem;
}}

.gs-spotlight {{
  display: grid;
  gap: 0.18rem;
  padding: 0.72rem 0.8rem;
  border-radius: 16px;
  border: 1px solid rgba(198, 177, 112, 0.12);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.015)),
    rgba(15, 24, 36, 0.88);
}}

.gs-spotlight__kicker {{
  color: var(--gs-accent);
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}}

.gs-spotlight__title {{
  color: var(--gs-text);
  font-size: 0.96rem;
  font-weight: 700;
  line-height: 1.2;
}}

.gs-spotlight__meta {{
  color: var(--gs-muted);
  font-size: 0.78rem;
  line-height: 1.36;
}}

.gs-spotlight__note {{
  color: var(--gs-muted);
  font-size: 0.72rem;
  line-height: 1.34;
}}

.gs-spotlight--media {{
  min-height: 100%;
}}

.gs-spotlight__image-fallback {{
  display: grid;
  place-items: center;
  min-height: 94px;
  border-radius: 14px;
  border: 1px dashed rgba(154, 168, 186, 0.28);
  background: rgba(255, 255, 255, 0.025);
  color: var(--gs-muted);
  font-size: 0.74rem;
}}

[data-testid="stPopover"] > div > button {{
  min-height: 2.95rem;
  border-radius: 16px;
  border: 1px solid rgba(198, 177, 112, 0.14);
  background:
    linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.018)),
    rgba(15, 24, 36, 0.88);
  color: var(--gs-text);
}}

[data-testid="stPopoverBody"] {{
  border: 1px solid rgba(198, 177, 112, 0.12);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(13, 20, 31, 0.98), rgba(9, 14, 23, 0.98)),
    var(--gs-surface);
}}

.gs-subpanel {{
  padding: 0.7rem 0.8rem;
  border-radius: 14px;
  border: 1px solid rgba(198, 177, 112, 0.1);
  background: rgba(255, 255, 255, 0.02);
}}

[data-baseweb="tab-list"] {{
  gap: 0.35rem;
  margin-bottom: 0.65rem;
}}

[data-baseweb="tab"] {{
  border-radius: 999px !important;
  border: 1px solid rgba(198, 177, 112, 0.12) !important;
  background: rgba(255, 255, 255, 0.03) !important;
  color: var(--gs-muted) !important;
  min-height: 2.25rem !important;
  padding-inline: 0.76rem !important;
  font-size: 0.82rem !important;
  transition: background 180ms ease, border-color 180ms ease, color 180ms ease !important;
}}

[data-baseweb="tab"]:hover {{
  border-color: rgba(198, 177, 112, 0.22) !important;
  color: var(--gs-text) !important;
  background: rgba(255, 255, 255, 0.05) !important;
}}

[data-baseweb="tab"][aria-selected="true"] {{
  border-color: rgba(198, 177, 112, 0.32) !important;
  background: rgba(198, 177, 112, 0.12) !important;
  color: var(--gs-text) !important;
}}

@media (max-width: 980px) {{
  .gs-match-hero__grid {{
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }}

  .gs-match-hero__team--away {{
    text-align: left;
  }}

  .gs-match-hero__score {{
    justify-items: start;
  }}

  .gs-catalog-header {{
    align-items: flex-start;
    flex-direction: column;
  }}
}}
</style>
"""
