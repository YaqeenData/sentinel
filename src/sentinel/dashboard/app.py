"""
Sentinel dashboard entry point.

    streamlit run src/sentinel/dashboard/app.py

Responsibilities: page config, configuration loading, cached data loading,
refresh, navigation and choosing which page to render. Pages live in
views.py, UI pieces in components.py, SQL in queries.py.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from PIL import Image

import base64
import json

def force_browser_metadata(page: str) -> None:
    """
    Safari fallback for the browser title and favicon.
    """

    if not TAB_ICON_PATH.is_file():
        return

    icon_base64 = base64.b64encode(
        TAB_ICON_PATH.read_bytes()
    ).decode("ascii")

    title = json.dumps(f"Sentinel · {page}")

    st.iframe(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    overflow: hidden;
                }}
            </style>
        </head>

        <body>
        <script>
        (() => {{
            const doc = window.parent.document;

            // -----------------------------
            // Browser tab title
            // -----------------------------
            doc.title = {title};

            const favicon =
                "data:image/png;base64,{icon_base64}";

            // -----------------------------
            // Remove existing favicons
            // -----------------------------
            doc.querySelectorAll(
                'link[rel="icon"], ' +
                'link[rel="shortcut icon"], ' +
                'link[rel="apple-touch-icon"]'
            ).forEach(link => link.remove());

            // -----------------------------
            // Standard favicon
            // -----------------------------
            const icon = doc.createElement("link");
            icon.rel = "icon";
            icon.type = "image/png";
            icon.href = favicon;

            doc.head.appendChild(icon);

            // -----------------------------
            // Safari / Apple icon
            // -----------------------------
            const appleIcon = doc.createElement("link");
            appleIcon.rel = "apple-touch-icon";
            appleIcon.href = favicon;

            doc.head.appendChild(appleIcon);

        }})();
        </script>
        </body>
        </html>
        """,
        height=1,
    )


# ---------------------------------------------------------------------------
# Browser tab
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]
TAB_ICON_PATH = ROOT / "assets" / "sentinel-logo.png"


def _load_tab_icon():
    """
    Load the Sentinel PNG favicon.

    A PIL image is more reliable for Streamlit's browser favicon
    than passing the SVG/path string directly.
    """
    if TAB_ICON_PATH.is_file():
        with Image.open(TAB_ICON_PATH) as image:
            return image.copy()

    # Fallback if the PNG is missing.
    return "◆"


TAB_ICON = _load_tab_icon()


# This must happen before the rest of the Streamlit UI is rendered.
# The title is updated again after navigation is known.
st.set_page_config(
    page_title="Sentinel · Overview",
    page_icon=TAB_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Sentinel imports
# ---------------------------------------------------------------------------

from sentinel.dashboard import components as ui  # noqa: E402
from sentinel.dashboard import views  # noqa: E402
from sentinel.dashboard.model import (  # noqa: E402
    categorical_settings,
    load_monitoring_config,
)
from sentinel.dashboard.queries import (  # noqa: E402
    load_dashboard_snapshot,
)
from sentinel.dashboard.theme import (  # noqa: E402
    apply_sentinel_theme,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Dashboard automatically reruns every 10 seconds.
# Keep the DB cache shorter than the rerun interval so
# every automatic refresh can retrieve fresh PostgreSQL data.
CACHE_TTL_SECONDS = 5


PAGES = {
    "Overview": (
        "overview",
        views.render_overview,
    ),
    # Contract checks are part of Data Quality, per FHIR resource.
    "Data Quality": (
        "data-quality",
        views.render_data_quality,
    ),
    "Incidents": (
        "incidents",
        views.render_incidents,
    ),
}


NAV_KEY = "page"
THEME_KEY = "theme_mode"


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_theme() -> None:
    if THEME_KEY not in st.session_state:
        st.session_state[THEME_KEY] = "dark"


def _init_navigation() -> None:
    if NAV_KEY not in st.session_state:

        slug = st.query_params.get(
            NAV_KEY
        )

        by_slug = {
            slug_: name
            for name, (slug_, _) in PAGES.items()
        }

        st.session_state[NAV_KEY] = (
            by_slug.get(
                slug,
                "Overview",
            )
        )

    if st.session_state.get(
        NAV_KEY
    ):
        st.session_state[
            "_last_page"
        ] = st.session_state[
            NAV_KEY
        ]


def _current_page() -> str:
    return (
        st.session_state.get(NAV_KEY)
        or st.session_state.get(
            "_last_page",
            "Overview",
        )
    )


# ---------------------------------------------------------------------------
# Cached loading
# ---------------------------------------------------------------------------

@st.cache_data(
    ttl=60,
    show_spinner=False,
)
def load_config() -> dict:
    return load_monitoring_config()


@st.cache_data(
    ttl=CACHE_TTL_SECONDS,
    show_spinner=False,
)
def load_snapshot(
    incident_type: str | None,
    metric_name: str | None,
    field_name: str | None,
) -> dict:
    return load_dashboard_snapshot(
        incident_type,
        metric_name,
        field_name,
    )


# ---------------------------------------------------------------------------
# Live dashboard
# ---------------------------------------------------------------------------

@st.fragment(
    run_every="10s"
)
def render_live_dashboard(
    config: dict,
    settings: dict | None,
) -> None:
    """
    Render the live Sentinel dashboard.

    This fragment automatically reruns every 10 seconds,
    pulling a fresh PostgreSQL snapshot when the cache
    has expired.
    """

    # Apply the active dark/light Sentinel theme.
    apply_sentinel_theme(
        st.session_state.get(
            THEME_KEY,
            "dark",
        )
    )

    snapshot = None
    db_error = None

    try:
        snapshot = load_snapshot(
            (
                settings["incident_type"]
                if settings
                else None
            ),
            (
                settings["metric_name"]
                if settings
                else None
            ),
            (
                settings["field_name"]
                if settings
                else None
            ),
        )

    except Exception as error:
        # Database connection, authentication,
        # or missing-table errors.
        db_error = error

    # -----------------------------------------------------------------------
    # Top navigation
    # -----------------------------------------------------------------------

    refresh = ui.render_top_bar(
        list(PAGES),
        NAV_KEY,
        THEME_KEY,
        (
            snapshot["fetched_at"]
            if snapshot
            else None
        ),
        (
            snapshot["data_as_of"]
            if snapshot
            else None
        ),
    )

    # Read the page AFTER rendering the navigation so the browser
    # tab immediately reflects the currently selected dashboard.
    current_page = _current_page()
    
    force_browser_metadata(current_page)

    # Browser tab:
    # Sentinel · Overview
    # Sentinel · Data Quality
    # Sentinel · Incidents
    st.set_page_config(
        page_title=f"Sentinel · {current_page}",
        page_icon=TAB_ICON,
    )

    if refresh:
        load_snapshot.clear()
        load_config.clear()
        st.rerun()

    # -----------------------------------------------------------------------
    # Database error
    # -----------------------------------------------------------------------

    if db_error is not None:
        ui.render_db_error(
            db_error
        )
        return

    # -----------------------------------------------------------------------
    # Current page
    # -----------------------------------------------------------------------

    page = current_page
    slug, render = PAGES[page]

    # Keep the selected dashboard in the URL.
    st.query_params[
        NAV_KEY
    ] = slug

    # -----------------------------------------------------------------------
    # Build and render page data
    # -----------------------------------------------------------------------

    view_data = (
        views.build_view_data(
            snapshot,
            config,
            settings,
        )
    )

    render(
        view_data
    )

    ui.render_footer(
        snapshot["data_as_of"]
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _init_theme()

    apply_sentinel_theme(
        st.session_state.get(
            THEME_KEY,
            "dark",
        )
    )

    _init_navigation()

    try:
        config = load_config()

        settings = (
            categorical_settings(
                config
            )
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as error:

        # Keep the same top bar/theme even if monitoring config fails.
        ui.render_top_bar(
            list(PAGES),
            NAV_KEY,
            THEME_KEY,
            None,
            None,
        )

        ui.empty_state(
            "Monitoring configuration "
            "could not be loaded",
            str(error),
        )

        return

    render_live_dashboard(
        config,
        settings,
    )


main()