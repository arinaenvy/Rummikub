"""Streamlit entry point for the self-contained Rummikub browser game."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Rummikub", page_icon="🃏", layout="wide")

# Give the game the viewport instead of Streamlit's document-style page margins.
st.html("""
<style>
[data-testid="stHeader"] { display: none; }
[data-testid="stMainBlockContainer"] {
    padding: 0 !important;
    max-width: none !important;
}
[data-testid="stVerticalBlock"] { gap: 0; }
iframe[title="streamlit_app.rummikub"] { display: block; }
</style>
""")

# Resolve assets relative to this file, so deployment does not depend on cwd.
game = components.declare_component(
    "rummikub", path=str(Path(__file__).resolve().parent / "game")
)
game(key="rummikub_game")
