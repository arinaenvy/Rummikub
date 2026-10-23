"""Streamlit entry point for the self-contained Rummikub browser game."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Rummikub", page_icon="🃏", layout="wide")

# Resolve assets relative to this file, so deployment does not depend on cwd.
game = components.declare_component(
    "rummikub", path=str(Path(__file__).resolve().parent / "game")
)
game(key="rummikub_game")

st.caption(
    "Play against the computer. Your game stays in this browser tab; "
    "refreshing or closing the page resets your game and session scores."
)
