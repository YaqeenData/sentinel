"""







Sentinel visual identity: palette, page CSS and the Plotly chart layout.







"""















from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path















import streamlit as st























# Logo path used by both the browser tab favicon and the top navigation.
# Sentinel logo asset.
LOGO_RELATIVE_PATH = Path("assets") / "sentinel-logo.svg"


def logo_path() -> Path | None:
    """Return the Sentinel logo path from the working directory or repo root."""
    for root in (Path.cwd(), Path(__file__).resolve().parents[3]):
        candidate = root / LOGO_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    return None
  
def logo_path_png() -> Path | None:
    """Return the Sentinel logo path from the working directory or repo root."""
    for root in (Path.cwd(), Path(__file__).resolve().parents[3]):
        candidate = root / LOGO_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def logo_data_uri() -> str | None:
    """Return the SVG logo as a data URI for inline navbar use."""
    path = logo_path()
    if path is None:
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


DARK_COLORS = {







    "background": "#07111F",







    "card": "#101D2E",







    "secondary": "#17283D",







    "cyan": "#22D3EE",







    "teal": "#0097A7",







    "blue": "#3B82F6",







    "green": "#22C55E",







    "amber": "#F59E0B",







    "rose": "#F43F5E",







    "text": "#F1F5F9",







    "muted": "#94A3B8",







}















LIGHT_COLORS = {







    "background": "#F4F7FA",







    "card": "#FFFFFF",







    "secondary": "#DCE4EC",







    "cyan": "#0891B2",







    "teal": "#0E7490",







    "blue": "#2563EB",







    "green": "#16A34A",







    "amber": "#D97706",







    "rose": "#E11D48",







    "text": "#0F172A",







    "muted": "#64748B",







}















# Keep this dictionary object alive because other modules import COLORS.







# We mutate it in-place when switching theme.







COLORS = DARK_COLORS.copy()















TONES = (







    "cyan",







    "teal",







    "blue",







    "green",







    "amber",







    "rose",







    "muted",







)















FONT_SANS = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"







FONT_MONO = "'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace"























def set_theme(mode: str) -> None:







    """Switch Sentinel's active palette in place."""















    palette = LIGHT_COLORS if mode.lower() == "light" else DARK_COLORS







    COLORS.clear()







    COLORS.update(palette)























def tone_color(tone: str) -> str:







    return COLORS.get(tone, COLORS["muted"])























def rgba(hex_color: str, alpha: float) -> str:







    value = hex_color.lstrip("#")







    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))







    return f"rgba({red},{green},{blue},{alpha})"























def _tone_classes() -> str:







    rules: list[str] = []















    for tone in TONES:







        color = tone_color(tone)







        rules.append(







            f".sn-chip.sn-{tone}{{color:{color};background:{rgba(color, 0.12)};"







            f"border-color:{rgba(color, 0.35)};}}"







            f".sn-text-{tone}{{color:{color};}}"







            f".sn-dot-{tone}{{background:{color};}}"







            f".sn-ring-{tone}{{border-color:{color};"







            f"box-shadow:0 0 0 7px {rgba(color, 0.08)};}}"







            f".sn-accent-{tone}{{border-left-color:{color};}}"







        )















    return "".join(rules)























def apply_sentinel_theme(mode: str = "dark") -> None:







    """Inject the Sentinel stylesheet for the selected theme."""















    set_theme(mode)







    c = COLORS







    scheme = "light" if mode.lower() == "light" else "dark"


















    css = f"""







@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');















html, body, .stApp, [data-testid="stAppViewContainer"] {{







    background:{c['background']};







    color:{c['text']};







    font-family:{FONT_SANS};







    color-scheme:{scheme};







    --background-color:{c['background']};







    --secondary-background-color:{c['card']};







    --text-color:{c['text']};







    --primary-color:{c['cyan']};







}}















.stApp p,







.stApp li,







.stApp label {{







    font-family:{FONT_SANS};







}}















.block-container {{







    padding-top:1.1rem;







    padding-bottom:2.5rem;







    max-width:1480px;







}}















header[data-testid="stHeader"] {{







    display:none;







}}















#MainMenu,







footer,







[data-testid="stDecoration"],







[data-testid="stStatusWidget"] {{







    display:none;







}}















[data-testid="stSidebar"],







[data-testid="collapsedControl"] {{







    display:none;







}}















h1, h2, h3, h4 {{







    color:{c['text']};







    font-family:{FONT_SANS};







    letter-spacing:-0.01em;







}}















hr {{







    border-color:{c['secondary']};







}}















[data-testid="stCaptionContainer"],







.stCaption {{







    color:{c['muted']};







}}















/* ---------- top bar ---------- */















.sn-brand {{







    display:flex;







    align-items:center;







    gap:12px;







    padding-top:4px;







}}

.sn-logo {{
    width:38px;
    height:38px;
    object-fit:contain;
    display:block;
    flex-shrink:0;
}}















.sn-mark {{







    width:30px;







    height:30px;







    border-radius:8px;







    border:2px solid {c['cyan']};







    display:flex;







    align-items:center;







    justify-content:center;







}}















.sn-mark span {{







    width:10px;







    height:10px;







    border-radius:3px;







    background:{c['cyan']};







}}















.sn-wordmark {{







    font-weight:800;







    letter-spacing:0.24em;







    font-size:1.05rem;







    color:{c['text']};







}}















.sn-brand-sub {{







    font-size:0.68rem;







    letter-spacing:0.14em;







    text-transform:uppercase;







    color:{c['muted']};







}}















.sn-refresh {{







    text-align:right;







    font-size:0.74rem;







    color:{c['muted']};







    line-height:1.45;







    padding-top:2px;







}}















.sn-refresh b {{







    color:{c['text']};







    font-weight:600;







    font-family:{FONT_MONO};







    font-size:0.72rem;







}}















.sn-topbar-rule {{







    height:1px;







    background:{c['secondary']};







    margin:10px 0 18px 0;







}}















/* ---------- top navigation ---------- */















.st-key-page div[data-testid="stButtonGroup"] {{







    gap:4px;







}}















.st-key-page div[data-testid="stButtonGroup"] button {{







    background:transparent !important;







    border:none !important;







    border-bottom:2px solid transparent !important;







    border-radius:0 !important;







    color:{c['muted']} !important;







    padding:6px 14px !important;







    font-weight:500 !important;







    box-shadow:none !important;







}}















.st-key-page div[data-testid="stButtonGroup"] button:hover {{







    color:{c['text']} !important;







}}















.st-key-page div[data-testid="stButtonGroup"] button[kind$="Active"] {{







    background:transparent !important;







    color:{c['cyan']} !important;







    border-bottom-color:{c['cyan']} !important;







    font-weight:600 !important;







}}















/* ---------- typography ---------- */















.sn-hero {{







    margin:4px 0 18px 0;







}}















.sn-hero-q {{







    font-size:1.55rem;







    font-weight:700;







    color:{c['text']};







    letter-spacing:-0.015em;







}}















.sn-hero-q em {{







    font-style:normal;







    color:{c['cyan']};







}}















.sn-hero-sub {{







    color:{c['muted']};







    font-size:0.9rem;







    margin-top:4px;







}}















.sn-page-title {{







    font-size:1.35rem;







    font-weight:700;







    color:{c['text']};







    margin:2px 0 2px 0;







}}















.sn-page-sub {{







    color:{c['muted']};







    font-size:0.86rem;







    margin-bottom:16px;







}}















.sn-eyebrow {{







    font-size:0.68rem;







    font-weight:700;







    letter-spacing:0.14em;







    text-transform:uppercase;







    color:{c['muted']};







}}















.sn-section-title {{







    font-size:0.95rem;







    font-weight:650;







    color:{c['text']};







    margin-bottom:2px;







}}















.sn-section-sub {{







    font-size:0.78rem;







    color:{c['muted']};







    margin-bottom:6px;







}}















.sn-mono {{







    font-family:{FONT_MONO};







}}















.sn-muted {{







    color:{c['muted']};







}}















.sn-tech {{







    font-family:{FONT_MONO};







    font-size:0.7rem;







    color:{c['muted']};







    opacity:0.85;







}}















/* ---------- cards ---------- */















.sn-card {{







    background:{c['card']};







    border:1px solid {c['secondary']};







    border-radius:14px;







    padding:20px 22px;







    height:100%;







}}















.sn-card-tall {{







    min-height:356px;







    display:flex;







    flex-direction:column;







}}















.sn-card-head {{







    display:flex;







    justify-content:space-between;







    align-items:center;







    margin-bottom:16px;







}}















.sn-accent {{







    border-left:3px solid {c['secondary']};







}}















div[class*="st-key-panel"] {{







    background:{c['card']};







    border:1px solid {c['secondary']};







    border-radius:14px;







    padding:18px 20px 12px 20px;







}}















/* chips */















.sn-chip {{







    display:inline-flex;







    align-items:center;







    gap:6px;







    font-size:0.66rem;







    font-weight:700;







    letter-spacing:0.08em;







    text-transform:uppercase;







    padding:3px 9px;







    border-radius:999px;







    border:1px solid {c['secondary']};







    white-space:nowrap;







}}















.sn-dot {{







    width:7px;







    height:7px;







    border-radius:50%;







    display:inline-block;







}}















/* health ring */















.sn-health {{







    display:flex;







    flex-direction:column;







    align-items:center;







    gap:14px;







    margin:6px 0 18px 0;







}}















.sn-ring {{







    width:148px;







    height:148px;







    border-radius:50%;







    border:9px solid {c['secondary']};







    display:flex;







    flex-direction:column;







    align-items:center;







    justify-content:center;







}}















.sn-ring-label {{







    font-size:1.05rem;







    font-weight:800;







    letter-spacing:0.1em;







    text-transform:uppercase;







}}















.sn-ring-sub {{







    font-size:0.62rem;







    letter-spacing:0.14em;







    text-transform:uppercase;







    color:{c['muted']};







    margin-top:2px;







}}















.sn-health-detail {{







    font-size:0.84rem;







    color:{c['muted']};







    text-align:center;







}}















/* stat rows inside cards */















.sn-stats {{







    margin-top:auto;







    border-top:1px solid {c['secondary']};







    padding-top:12px;







}}















.sn-stat {{







    display:flex;







    justify-content:space-between;







    font-size:0.8rem;







    padding:4px 0;







    color:{c['muted']};







}}















.sn-stat b {{







    color:{c['text']};







    font-weight:600;







    font-family:{FONT_MONO};







    font-size:0.78rem;







}}















/* resource rows */















.sn-res {{







    display:flex;







    justify-content:space-between;







    align-items:center;







    padding:13px 14px;







    border:1px solid {c['secondary']};







    border-radius:10px;







    margin-bottom:10px;







    background:{c['background']};







}}















.sn-res-name {{







    font-weight:650;







    color:{c['text']};







    font-size:0.95rem;







}}















.sn-res-sub {{







    font-size:0.74rem;







    color:{c['muted']};







    margin-top:2px;







}}















.sn-res.sn-off {{







    opacity:0.62;







}}















.sn-res.sn-off .sn-res-name {{







    color:{c['muted']};







}}















/* active incident */















.sn-inc-type {{







    font-size:0.72rem;







    font-weight:700;







    letter-spacing:0.14em;







    text-transform:uppercase;







}}















.sn-inc-title {{







    font-size:1.18rem;







    font-weight:700;







    color:{c['text']};







    margin-top:6px;







}}















.sn-inc-sub {{







    font-size:0.78rem;







    color:{c['muted']};







    margin-top:2px;







}}















.sn-compare {{







    display:flex;







    align-items:flex-end;







    gap:16px;







    margin:20px 0 6px 0;







}}















.sn-compare-val {{







    font-family:{FONT_MONO};







    font-size:2rem;







    font-weight:600;







    line-height:1;







}}















.sn-compare-op {{







    font-family:{FONT_MONO};







    font-size:1.3rem;







    color:{c['muted']};







    padding-bottom:3px;







}}















.sn-compare-lab {{







    font-size:0.66rem;







    letter-spacing:0.12em;







    text-transform:uppercase;







    color:{c['muted']};







    margin-top:6px;







}}















.sn-chips {{







    display:flex;







    gap:6px;







    flex-wrap:wrap;







}}















.sn-empty-ok {{







    display:flex;







    flex-direction:column;







    align-items:center;







    justify-content:center;







    flex:1;







    gap:10px;







    text-align:center;







    color:{c['muted']};







    font-size:0.86rem;







}}















.sn-empty-ok .sn-big {{







    font-size:1.05rem;







    font-weight:650;







}}















/* pipeline strip */















.sn-strip {{







    display:flex;







    align-items:stretch;







    gap:0;







    margin-top:18px;







    background:{c['card']};







    border:1px solid {c['secondary']};







    border-radius:14px;







    padding:14px 18px;







}}















.sn-strip-step {{







    flex:1;







    display:flex;







    align-items:center;







    gap:14px;







}}















.sn-strip-icon {{







    width:38px;







    height:38px;







    border-radius:10px;







    border:1.5px solid;







    display:flex;







    align-items:center;







    justify-content:center;







    font-family:{FONT_MONO};







    font-size:0.8rem;







    font-weight:700;







}}















.sn-strip-k {{







    font-size:0.62rem;







    letter-spacing:0.18em;







    font-weight:700;







}}















.sn-strip-n {{







    font-size:0.95rem;







    font-weight:650;







    color:{c['text']};







}}















.sn-strip-d {{







    font-size:0.72rem;







    color:{c['muted']};







}}















.sn-strip-arrow {{







    display:flex;







    align-items:center;







    color:{c['muted']};







    padding:0 18px;







    font-size:1.1rem;







}}















/* kpi tiles */















.sn-kpi {{







    background:{c['card']};







    border:1px solid {c['secondary']};







    border-radius:12px;







    padding:14px 16px;







    height:100%;







}}















.sn-kpi-v {{







    font-family:{FONT_MONO};







    font-size:1.45rem;







    font-weight:600;







    color:{c['text']};







    margin-top:6px;







    line-height:1.15;







}}















.sn-kpi-d {{







    font-size:0.72rem;







    color:{c['muted']};







    margin-top:4px;







}}















/* threshold gauge */















.sn-gauge {{







    margin:8px 0 4px 0;







}}















.sn-gauge-nums {{







    display:flex;







    justify-content:space-between;







    align-items:flex-end;







    margin-bottom:12px;







}}















.sn-gauge-track {{







    position:relative;







    height:12px;







    border-radius:999px;







    background:{c['secondary']};







}}















.sn-gauge-fill {{







    position:absolute;







    left:0;







    top:0;







    bottom:0;







    border-radius:999px;







}}















.sn-gauge-mark {{







    position:absolute;







    top:-7px;







    bottom:-7px;







    width:2px;







    background:{c['amber']};







}}















.sn-gauge-scale {{







    position:relative;







    height:18px;







    font-family:{FONT_MONO};







    font-size:0.66rem;







    color:{c['muted']};







    margin-top:9px;







}}















.sn-gauge-scale span {{







    position:absolute;







    transform:translateX(-50%);







}}















.sn-gauge-note {{







    font-size:0.8rem;







    color:{c['muted']};







    margin-top:10px;







}}















/* key/value grid */















.sn-kv {{







    display:grid;







    grid-template-columns:1fr;







    gap:0;







}}















.sn-kv-row {{







    display:flex;







    justify-content:space-between;







    gap:12px;







    padding:8px 0;







    border-bottom:1px solid {c['secondary']};







    font-size:0.82rem;







}}















.sn-kv-row:last-child {{







    border-bottom:none;







}}















.sn-kv-k {{







    color:{c['muted']};







}}















.sn-kv-v {{







    color:{c['text']};







    text-align:right;







    font-weight:500;







}}















/* distribution table */















.sn-dist {{







    width:100%;







    border-collapse:collapse;







    font-size:0.8rem;







    margin-top:4px;







}}















.sn-dist th {{







    text-align:right;







    color:{c['muted']};







    font-weight:600;







    font-size:0.66rem;







    letter-spacing:0.1em;







    text-transform:uppercase;







    padding:6px 8px;







    border-bottom:1px solid {c['secondary']};







}}















.sn-dist th:first-child,







.sn-dist td:first-child {{







    text-align:left;







}}















.sn-dist td {{







    text-align:right;







    padding:7px 8px;







    border-bottom:1px solid {c['secondary']};







    font-family:{FONT_MONO};







    color:{c['text']};







}}















.sn-dist td:first-child {{







    font-family:{FONT_SANS};







}}















/* themed static incident/schema tables */















.sn-table-wrap {{







    width:100%;







    overflow-x:auto;







    border:1px solid {c['secondary']};







    border-radius:12px;







    background:{c['card']};







    margin-top:12px;







}}















table.sn-table {{







    width:100%;







    border-collapse:separate;







    border-spacing:0;







    font-size:0.82rem;







}}















table.sn-table thead th {{







    background:{c['secondary']};







    color:{c['text']};







    font-size:0.67rem;







    font-weight:700;







    letter-spacing:0.08em;







    text-transform:uppercase;







    text-align:left;







    padding:11px 13px;







    white-space:nowrap;







    border-bottom:1px solid {c['secondary']};







}}















table.sn-table tbody td {{







    background:{c['card']};







    color:{c['text']};







    padding:11px 13px;







    border-bottom:1px solid {c['secondary']};







    vertical-align:middle;







    white-space:nowrap;







}}















table.sn-table tbody tr:last-child td {{







    border-bottom:none;







}}















table.sn-table tbody tr:hover td {{







    background:{rgba(c['cyan'], 0.05)};







}}















table.sn-table td.sn-mono {{







    font-family:{FONT_MONO};







}}















/* detector coverage */















.sn-det {{







    background:{c['card']};







    border:1px solid {c['secondary']};







    border-radius:12px;







    padding:14px 16px;







    height:100%;







}}















.sn-det-name {{







    font-weight:650;







    font-size:0.88rem;







    color:{c['text']};







    margin:10px 0 6px 0;







}}















.sn-det-line {{







    font-size:0.74rem;







    color:{c['muted']};







    line-height:1.5;







}}















.sn-det.sn-off {{







    opacity:0.7;







}}















/* severity bar */















.sn-sevbar {{







    display:flex;







    height:10px;







    border-radius:999px;







    overflow:hidden;







    background:{c['secondary']};







    margin:10px 0 10px 0;







}}















.sn-legend {{







    display:flex;







    gap:14px;







    flex-wrap:wrap;







    font-size:0.74rem;







    color:{c['muted']};







}}















.sn-legend b {{







    color:{c['text']};







    font-family:{FONT_MONO};







    font-weight:600;







    margin-left:4px;







}}















/* empty states and notes */















.sn-empty {{







    border:1px dashed {c['secondary']};







    border-radius:12px;







    padding:22px;







    text-align:center;







    color:{c['muted']};







    font-size:0.86rem;







    background:{rgba(c['card'], 0.6)};







}}















.sn-empty .sn-big {{







    color:{c['text']};







    font-weight:600;







    font-size:0.95rem;







    margin-bottom:4px;







}}















.sn-note {{







    border-left:3px solid {c['secondary']};







    padding:8px 12px;







    font-size:0.78rem;







    color:{c['muted']};







    background:{c['background']};







    border-radius:0 8px 8px 0;







    margin:8px 0;







}}















.sn-footer {{







    margin-top:26px;







    padding-top:12px;







    border-top:1px solid {c['secondary']};







    display:flex;







    justify-content:space-between;







    font-size:0.74rem;







    color:{c['muted']};







}}















/* detail panel */















.sn-detail-grid {{







    display:grid;







    grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));







    gap:14px 20px;







    margin-top:14px;







}}















.sn-detail-k {{







    font-size:0.64rem;







    letter-spacing:0.12em;







    text-transform:uppercase;







    color:{c['muted']};







}}















.sn-detail-v {{







    font-size:0.9rem;







    color:{c['text']};







    margin-top:3px;







}}















.sn-message {{







    margin-top:16px;







    background:{c['background']};







    border:1px solid {c['secondary']};







    border-radius:10px;







    padding:12px 14px;







    font-family:{FONT_MONO};







    font-size:0.76rem;







    color:{c['muted']};







    white-space:pre-wrap;







    word-break:break-word;







}}















/* ---------- native widgets ---------- */















[data-testid="stExpander"] details {{







    background:{c['card']};







    border:1px solid {c['secondary']};







    border-radius:12px;







}}















span[data-baseweb="tag"] {{







    background:{c['secondary']} !important;







    color:{c['cyan']} !important;







}}















.stButton button {{







    background:{c['card']};







    border:1px solid {c['secondary']};







    color:{c['text']};







    border-radius:8px;







    font-size:0.78rem;







    padding:2px 12px;







    min-height:30px;







}}















.stButton button:hover {{







    border-color:{c['cyan']};







    color:{c['cyan']};







}}















[data-testid="stWidgetLabel"] p {{







    font-size:0.72rem;







    letter-spacing:0.06em;







    text-transform:uppercase;







    color:{c['muted']};







}}















/* ---------- selectbox / dropdown ----------

   One authoritative block only. */

/* Closed control */
[data-testid="stSelectbox"] {{
    --primary-color:{c['cyan']} !important;
    --background-color:{c['card']} !important;
    --secondary-background-color:{c['card']} !important;
    --text-color:{c['text']} !important;
    background:transparent !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] {{
    background:{c['card']} !important;
    background-color:{c['card']} !important;
    color:{c['text']} !important;
    border-radius:10px !important;
    box-shadow:none !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSelectbox"] div:has(> [role="combobox"]),
[data-testid="stSelectbox"] [role="combobox"],
[data-testid="stSelectbox"] [data-baseweb="input"],
[data-testid="stSelectbox"] [data-baseweb="base-input"] {{
    background:{c['card']} !important;
    background-color:{c['card']} !important;
    color:{c['text']} !important;
    -webkit-text-fill-color:{c['text']} !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] > div {{
    border:1px solid {c['secondary']} !important;
    border-radius:10px !important;
    box-shadow:none !important;
    outline:none !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] > div > div {{
    background:transparent !important;
    background-color:transparent !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stSelectbox"] [data-baseweb="select"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-value"],
[data-testid="stSelectbox"] [role="combobox"] span,
[data-testid="stSelectbox"] [role="combobox"] div {{
    color:{c['text']} !important;
    -webkit-text-fill-color:{c['text']} !important;
    opacity:1 !important;
}}

/* Real Streamlit/React-Aria dropdown button.
   The SVG uses fill=currentColor, so the button color is the source of truth. */
[data-testid="stSelectbox"] button[aria-label="Open"][aria-haspopup="listbox"],
[data-testid="stSelectbox"] button[aria-haspopup="listbox"] {{
    color:{c['text']} !important;
    -webkit-text-fill-color:{c['text']} !important;
    background:transparent !important;
    border:none !important;
    opacity:1 !important;
}}

[data-testid="stSelectbox"] button[aria-haspopup="listbox"] svg {{
    color:inherit !important;
    fill:currentColor !important;
    opacity:1 !important;
    display:block !important;
    visibility:visible !important;
}}

[data-testid="stSelectbox"] button[aria-haspopup="listbox"] svg path:not([fill="none"]) {{
    fill:currentColor !important;
    stroke:none !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {{
    border-color:{c['cyan']} !important;
}}

[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {{
    background:{c['card']} !important;
    background-color:{c['card']} !important;
    border-color:{c['cyan']} !important;
    box-shadow:0 0 0 1px {rgba(c['cyan'], 0.22)} !important;
}}

[data-testid="stSelectbox"] label,
[data-testid="stSelectbox"] label p {{
    color:{c['muted']} !important;
}}

/* Open BaseWeb menu: mounted in a portal under body. */



body div[data-baseweb="popover"],



body div[data-baseweb="popover"] > div,



body div[data-baseweb="menu"],



body div[data-baseweb="menu"] > div,



body [role="listbox"] {{



    background:{c['card']} !important;



    background-color:{c['card']} !important;



    color:{c['text']} !important;



}}







body [role="listbox"] {{



    border:1px solid {c['secondary']} !important;



    border-radius:8px !important;



}}







body [role="option"],



body [role="option"] > div {{



    background:{c['card']} !important;



    background-color:{c['card']} !important;



    color:{c['text']} !important;



    -webkit-text-fill-color:{c['text']} !important;



}}







body [role="option"] span,



body [role="option"] div {{



    color:{c['text']} !important;



    -webkit-text-fill-color:{c['text']} !important;



}}







body [role="option"]:hover,



body [role="option"]:hover > div {{



    background:{c['secondary']} !important;



    background-color:{c['secondary']} !important;



    color:{c['text']} !important;



}}







body [role="option"][aria-selected="true"],



body [role="option"][aria-selected="true"] > div {{



    background:{rgba(c['cyan'], 0.12)} !important;



    background-color:{rgba(c['cyan'], 0.12)} !important;



    color:{c['cyan']} !important;



}}







body [role="option"][aria-selected="true"] span {{



    color:{c['cyan']} !important;



    -webkit-text-fill-color:{c['cyan']} !important;



}}







/* ---------- Plotly ---------- */















[data-testid="stPlotlyChart"] {{







    background:{c['card']} !important;







    border-radius:12px;







}}















[data-testid="stPlotlyChart"] > div {{







    background:{c['card']} !important;







}}















/* ---------- remaining native dataframe shells ---------- */















[data-testid="stDataFrame"] {{







    background:{c['card']} !important;







    border:1px solid {c['secondary']} !important;







    border-radius:10px;







}}















@media (max-width: 1100px) {{







    .sn-card-tall {{







        min-height:0;







    }}















    .sn-strip {{







        flex-direction:column;







        gap:12px;







    }}















    .sn-strip-arrow {{







        display:none;







    }}







}}















{_tone_classes()}







"""















    # One line, no blank lines: Markdown can never mistake it for text or code.







    compact = " ".join(line.strip() for line in css.splitlines() if line.strip())







    st.markdown(f"<style>{compact}</style>", unsafe_allow_html=True)























def plotly_layout(**overrides) -> dict:







    """Base Plotly layout in Sentinel colors."""















    c = COLORS















    axis = dict(







        gridcolor=c["secondary"],







        zerolinecolor=c["secondary"],







        linecolor=c["secondary"],







        tickfont=dict(







            color=c["muted"],







            size=11,







        ),







        title=dict(







            font=dict(







                color=c["muted"],







                size=11,







            )







        ),







    )















    layout = dict(







        template="none",







        paper_bgcolor=c["card"],







        plot_bgcolor=c["card"],







        font=dict(







            family=FONT_SANS,







            color=c["text"],







            size=12,







        ),







        margin=dict(







            l=8,







            r=12,







            t=10,







            b=8,







        ),







        xaxis=dict(axis),







        yaxis=dict(axis),







        showlegend=False,







        hoverlabel=dict(







            bgcolor=c["background"],







            bordercolor=c["secondary"],







            font=dict(







                family=FONT_SANS,







                color=c["text"],







                size=12,







            ),







        ),







        legend=dict(







            orientation="h",







            yanchor="bottom",







            y=1.02,







            xanchor="right",







            x=1,







            font=dict(







                color=c["muted"],







                size=11,







            ),







            bgcolor="rgba(0,0,0,0)",







        ),







    )















    layout.update(overrides)







    return layout























PLOTLY_CONFIG = {







    "displayModeBar": False,







    "responsive": True,







}








