# Rummikub on Streamlit

A browser tile game for one player against the computer, adapted from the supplied
Colab game. Includes classic 60-second turns, untimed practice, jokers, a 30-point
opening, table rearrangement, undo/reset, move suggestions, and session scoring.

A bottom bar keeps the timer and latest action visible throughout play. The
computer thinks for a random 15–35 seconds and normally pauses 2–4 seconds between
its moves before your full 60-second turn begins. Large plays use shorter pauses
to fit within 24 seconds of animation. Your latest drawn tiles carry a **NEW** badge, while
the opponent's additions show **BOT** and rearranged table tiles show **MOVED**.
These highlights remain throughout your next turn, including after sorting.

The opponent uses its normal solver but has a 15% chance to overlook an otherwise
playable move and draw instead. It never intentionally misses twice in a row,
declines an immediate win, or misses a found move when the pool is empty. This
adds occasional mistakes without changing the deal or looking at your rack.
**Suggest move** always uses the full search and is unaffected by this behavior.

The whole game fits the current screen: table, rack, controls, and timer stay
visible together. The layout adjusts when the window resizes or a phone rotates;
short landscape screens put the rack beside the table. Rules, the game log, and
new-game options open in dialogs instead of extending the page.

The table and rack automatically fit all their tiles into the available space.
Runs and groups are separate. Groups keep the color order **Black, Blue, Orange,
Red**, with a blank slot for each missing color and jokers in the column they
represent. Crowded tables add group stacks and shrink the tiles as needed;
each stack repeats the same aligned color columns. Unfinished sets have an
**In progress** area. Use the **+** beside a set to add selected tiles.
The tiles have no set numbers or point headers. Adjacent runs of the same color
join automatically, preserving joker meanings and leaving gaps and duplicate
numbers separate. Opening plays are validated before joining the existing table;
Undo restores the position before an edit and its automatic joins.

## Run locally

Use Python 3.12 (the tested version). From the repository folder:

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Open the address printed by Streamlit. Choose Classic or Practice, then **Start
game**. The game randomly determines the first player. Expand **How to play** for
the complete rules and controls.

## Upload to GitHub

Upload the contents of this project to the root of `arinaenvy/Rummikub`, preserving
the folders. In GitHub, choose **Add file → Upload files**, add the project files,
and commit to `main`. Do not upload the ZIP itself or your local `.venv` folder.

The deployment needs these files:

```text
streamlit_app.py
requirements.txt
game/
  index.html
.streamlit/
  config.toml
```

Include the README, `.gitignore`, development requirements, and tests as well for
a complete source repository. No API keys, database, or secrets are required.

## Deploy on Streamlit Community Cloud

1. Sign in at https://share.streamlit.io/ with your GitHub account.
2. Choose **Create app** and select `arinaenvy/Rummikub`.
3. Select branch **main** and set **Main file path** to `streamlit_app.py`.
4. In advanced settings, choose **Python 3.12**, then deploy.

Streamlit installs `requirements.txt` automatically and serves the game assets.
After deployment, share the app URL supplied by Streamlit. Future commits to the
selected branch update the deployed app.

## How it works

`streamlit_app.py` hosts `game/index.html` as a local Streamlit component. The
HTML file contains the original game's rules, computer search, interface, and
styles. A small component bridge adjusts its height to fit desktop and mobile
screens. No JavaScript build step or external game assets are needed.

Each browser tab has its own game against the computer; this is not online
multiplayer. State and scores live in browser memory and reset on refresh, closing
the tab, or a component reload. The computer uses a bounded search, so suggestions
may overlook legal moves. The game can also be opened directly from
`game/index.html` without Streamlit.

## Development checks

The rules tests use Node.js 18 or newer, with no npm dependencies:

```bash
node --test tests/rules.test.cjs
```

For browser integration checks, install the optional development dependencies and
Chromium, start Streamlit in another terminal, then run the smoke tests:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/smoke_test.py
```

On a minimal Linux machine, Playwright may require its OS libraries:
`python -m playwright install --with-deps chromium`.
