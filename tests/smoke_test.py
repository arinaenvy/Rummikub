"""Browser checks against a running Streamlit app (default port 8501)."""

import os
import re
import shutil
import unittest

from playwright.sync_api import expect, sync_playwright

expect.set_options(timeout=35_000)  # Includes the opponent's thinking and animation.


class BrowserSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        # Use an installed browser if supplied; otherwise use Playwright Chromium.
        executable = os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium")
        cls.browser = cls.playwright.chromium.launch(
            headless=True, executable_path=executable
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        # A repeatable deal with a legal human opening; production randomness is unchanged.
        self.page.add_init_script("""
            let seed = 1;
            Math.random = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
        """)

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [], "Browser JavaScript errors")

    def load(self):
        self.page.goto(os.environ.get("APP_URL", "http://127.0.0.1:8501"))
        self.game = self.page.frame_locator('iframe[title="streamlit_app.rummikub"]')
        expect(self.game.locator("#start")).to_be_visible()

    def exercise_game(self, width, height):
        self.page.set_viewport_size({"width": width, "height": height})
        self.load()
        g = self.game
        g.locator("#timing").select_option("0")
        g.locator("#start").click()
        expect(g.locator("#draw")).to_be_enabled()
        expect(g.locator("#rack .tile")).to_have_count(14)
        expect(g.locator("#clock")).to_have_text("Practice · untimed")

        # Invalid drafts are rejected, and both undo and reset recover the rack.
        for recovery in ("undo", "reset"):
            g.locator("#rack .tile").first.click()
            g.locator("#newSet").click()
            expect(g.locator("#rack .tile")).to_have_count(13)
            g.locator("#end").click()
            expect(g.locator("#message")).to_contain_text("Every set must be a valid")
            g.locator(f"#{recovery}").click()
            expect(g.locator("#rack .tile")).to_have_count(14)

        # A suggested opening commits and the computer completes its reply.
        g.locator("#hint").click()
        expect(g.locator("#message")).to_contain_text("Suggested play staged")
        staged_count = g.locator("#rack .tile").count()
        self.assertLess(staged_count, 14)
        g.locator("#end").click()
        expect(g.locator("#draw")).to_be_enabled()
        expect(g.locator("#opening")).to_contain_text("Opened")
        expect(g.locator("#rack .tile")).to_have_count(staged_count)
        expect(g.locator("#log")).to_contain_text("You played")
        expect(g.locator("#log")).to_contain_text("Computer")

        g.locator("#draw").click()
        expect(g.locator("#draw")).to_be_enabled()
        expect(g.locator("#rack .tile")).to_have_count(staged_count + 1)
        expect(g.locator("#log")).to_contain_text("You drew 1 tile")
        expect(g.locator("#rack .new-draw")).to_have_count(1)
        drawn_id = g.locator("#rack .new-draw").get_attribute("data-tile")
        g.locator("#sortNumber").click()
        expect(g.locator("#rack .new-draw")).to_have_attribute("data-tile", drawn_id)
        expect(g.locator("#rack .new-draw .change-tag")).to_have_text("NEW")

        g.locator("#newGame").click()
        g.locator("#cancelNew").click()
        expect(g.locator("#rack .tile")).to_have_count(staged_count + 1)
        g.locator("#help summary").click()
        expect(g.locator("#help")).to_contain_text("Groups:")

        # The floating timer stays in the actual host viewport after scrolling
        # well below the original clock, on desktop and mobile.
        g.locator("#help .panel").scroll_into_view_if_needed()
        self.assert_dock_visible()
        expect(g.locator("#dockClock")).to_have_text("No timer")

        # The component fits its content without horizontal scrolling, even on mobile.
        frame = self.page.frames[1]
        self.assertTrue(frame.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        ))
        expect(self.page.locator("iframe")).to_have_attribute("height", re.compile(r"[1-9]\d{2,}"))
        self.page.wait_for_function("""() => {
            const f = document.querySelector('iframe');
            return f && f.contentWindow.innerHeight >=
              f.contentDocument.querySelector('main').getBoundingClientRect().height;
        }""")

        # Refresh returns to setup rather than sharing another player's state.
        self.page.reload()
        expect(g.locator("#start")).to_be_visible()
        expect(g.locator("#game")).to_be_hidden()

    def assert_dock_visible(self):
        self.page.wait_for_function("""() => {
            const f = document.querySelector('iframe');
            const dock = f?.contentDocument.querySelector('#turnDock');
            if (!dock || getComputedStyle(dock).visibility !== 'visible') return false;
            const frame = f.getBoundingClientRect(), box = dock.getBoundingClientRect();
            return frame.top + box.top >= 0 &&
                frame.top + box.bottom <= window.innerHeight &&
                frame.left + box.left >= 0 && frame.left + box.right <= window.innerWidth;
        }""")

    def test_desktop_gameplay(self):
        self.exercise_game(1280, 900)

    def test_mobile_gameplay(self):
        self.exercise_game(390, 844)

    def test_classic_timeout(self):
        self.page.clock.install()
        self.load()
        g = self.game
        expect(g.locator("#timing")).to_have_value("60")
        g.locator("#start").click()
        expect(g.locator("#draw")).to_be_enabled()
        self.page.clock.fast_forward(61_000)
        self.page.clock.run_for(1_000)
        expect(g.locator("#log")).to_contain_text("You drew 1 tile — time expired")
        expect(g.locator("#rack .tile")).to_have_count(15)
        expect(g.locator("#rack .new-draw")).to_have_count(1)

    def prepare_computer_play(self, can_play=True, draw=True):
        """Deal a known legal computer opening, using the real solver."""
        self.page.clock.install()
        self.load()
        self.frame = self.page.frames[1]
        self.frame.evaluate("""() => {
            const human = [0,2,4,6,8,10,12,14,16,18,20,22,24,26];
            const bot = [44,70,96,28,32,36,40,48,52,56,60,64,68,13];
            Rummy.shuffle = ids => ids.length === 104
              ? [24,0,...ids.filter(id => id !== 24 && id !== 0)]
              : [...human,...bot,...ids.filter(id => !human.includes(id) && !bot.includes(id))];
        }""")
        if not can_play:
            self.frame.evaluate("""() => {
                const shuffle=Rummy.shuffle;
                const human=[0,2,4,6,8,10,12,14,16,18,20,22,24,26];
                const bot=[28,32,36,40,44,48,52,56,60,64,68,72,76,80];
                Rummy.shuffle=ids=>ids.length===104?shuffle(ids):
                    [...human,...bot,...ids.filter(id=>!human.includes(id)&&!bot.includes(id))];
            }""")
        self.game.locator("#start").click()
        if draw:
            self.game.locator("#draw").click()

    def test_computer_animation_and_fresh_human_clock(self):
        self.prepare_computer_play()
        g = self.game
        expect(g.locator("#dockClock")).to_have_text("Thinking…")
        expect(g.locator("#end")).to_be_disabled()
        self.page.clock.run_for(3_900)
        expect(g.locator("#table .tile")).to_have_count(0)
        self.page.clock.run_for(1_100)  # Seeded delay is 4,945 ms.
        expect(g.locator("#table .opponent-added")).to_have_count(1)
        expect(g.locator("#dockClock")).to_have_text("Playing…")
        expect(g.locator("#turnNotice")).to_contain_text("Opponent played")
        self.page.clock.run_for(850)
        expect(g.locator("#table .opponent-added")).to_have_count(2)
        expect(g.locator("#end")).to_be_disabled()
        # Finish each visible stage and check no tile disappears or duplicates.
        for _ in range(30):
            ids = g.locator("#table .tile").evaluate_all("els => els.map(el => el.dataset.tile)")
            self.assertEqual(len(ids), len(set(ids)))
            if g.locator("#end").is_enabled():
                break
            self.page.clock.run_for(850)
        expect(g.locator("#end")).to_be_enabled()
        self.assertGreaterEqual(int(g.locator("#dockClock").inner_text().removesuffix("s")), 59)
        self.assertGreaterEqual(g.locator("#table .opponent-added").count(), 3)
        expect(g.locator("#rack .new-draw")).to_have_count(1)
        expect(g.locator("#turnNotice")).to_contain_text("Your turn")

    def test_opponent_draw_notification(self):
        self.prepare_computer_play(can_play=False)
        g = self.game
        expect(g.locator("#turnNotice")).to_contain_text("You drew")
        self.page.clock.run_for(5_000)
        expect(g.locator("#turnNotice")).to_have_text("Opponent drew a tile. Your turn.")
        expect(g.locator("#rack .new-draw")).to_have_count(1)
        expect(g.locator("#table .tile")).to_have_count(0)
        expect(g.locator("#opponent")).to_contain_text("15 tiles")

    def test_floating_countdown_and_penalty_draw(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.page.clock.install()
        self.load()
        g = self.game
        g.locator("#start").click()
        expect(g.locator("#draw")).to_be_enabled()
        g.locator("#rack .tile").first.click()
        g.locator("#newSet").click()
        g.locator("#help summary").click()
        g.locator("#help .panel").scroll_into_view_if_needed()
        self.page.clock.run_for(51_000)
        self.assert_dock_visible()
        expect(g.locator("#dockClock")).to_have_text("9s")
        expect(g.locator("#turnDock")).to_have_class("urgent")
        self.page.clock.run_for(9_000)
        expect(g.locator("#rack .new-draw")).to_have_count(3)
        expect(g.locator("#rack .tile")).to_have_count(17)
        expect(g.locator("#table .tile")).to_have_count(0)
        expect(g.locator("#log")).to_contain_text("unfinished arrangement at timeout")

    def test_new_game_cancels_in_progress_computer_animation(self):
        self.prepare_computer_play()
        g = self.game
        self.page.clock.run_for(5_000)
        expect(g.locator("#table .opponent-added")).to_have_count(1)
        g.locator("#newGame").click()
        g.locator("#timing").select_option("0")
        g.locator("#start").click()
        self.page.clock.run_for(30_000)
        expect(g.locator("#table .tile")).to_have_count(0)
        expect(g.locator("#rack .tile")).to_have_count(14)
        expect(g.locator("#rack .new-draw")).to_have_count(0)
        expect(g.locator("#end")).to_be_enabled()

    def test_rearrangement_keeps_old_tiles_and_marks_both_split_sets(self):
        self.prepare_computer_play(draw=False)
        g = self.game
        # Supply two legal solver results to exercise a specific rearrangement.
        # The production audit still checks each plan before animation and commit.
        self.frame.evaluate("""() => {
            Rummy.solve=(rack,table,opened)=>{
                if(!opened) return {
                    table:[...table,{id:'bot-opening',tiles:[44,70,96],choice:null}],
                    rack:rack.filter(id=>![44,70,96].includes(id)), played:3
                };
                return {
                    table:[{id:'split-a',tiles:[13,14,16,18],choice:null},
                           {id:'split-b',tiles:[20,22,24],choice:null},
                           table.find(row=>row.tiles.includes(44))],
                    rack:rack.filter(id=>id!==13), played:1
                };
            };
        }""")
        for tile in [14, 16, 18, 20, 22, 24]:
            g.locator(f'#rack [data-tile="{tile}"]').click()
        g.locator("#newSet").click()
        g.locator("#end").click()
        self.page.clock.run_for(12_000)
        expect(g.locator("#draw")).to_be_enabled()
        before = set(g.locator("#table .tile").evaluate_all("els=>els.map(el=>el.dataset.tile)"))
        g.locator("#draw").click()
        for _ in range(25):
            self.page.clock.run_for(500)
            current = g.locator("#table .tile").evaluate_all("els=>els.map(el=>el.dataset.tile)")
            self.assertTrue(before.issubset(set(current)))
            self.assertEqual(len(current), len(set(current)))
            if g.locator("#draw").is_enabled():
                break
        expect(g.locator("#draw")).to_be_enabled()
        expect(g.locator("#table .opponent-moved")).to_have_count(6)
        expect(g.locator('#table .opponent-added[data-tile="13"]')).to_have_count(1)
        expect(g.locator("#table .tile")).to_have_count(10)

    def prepare_grid_layout(self, human=None):
        self.load()
        self.frame = self.page.frames[1]
        human = human or [66, 40, 14, 68, 42, 94, 26, 28, 30, 70, 44, 104, 92, 2]
        self.frame.evaluate("""human => {
            Rummy.shuffle=ids=>ids.length===104
              ?[24,0,...ids.filter(id=>id!==24&&id!==0)]
              :[...human,...ids.filter(id=>!human.includes(id))];
        }""", human)
        self.game.locator("#timing").select_option("0")
        self.game.locator("#start").click()

    def stage_set(self, ids):
        for tile in ids:
            self.game.locator(f'#rack [data-tile="{tile}"]').click()
        self.game.locator("#newSet").click()

    def assert_tiles_fit(self):
        self.frame.wait_for_function("""() => {
            const areas=['runsGrid','groupsGrid','draftsGrid','rackTiles'];
            return areas.every(id=>{
                const content=document.getElementById(id), parent=content.parentElement;
                if(!parent.getClientRects().length) return true;
                const box=parent.getBoundingClientRect();
                return [...content.querySelectorAll('.tile,.empty-slot,[data-add],select')].every(el=>{
                    const r=el.getBoundingClientRect();
                    return r.width>0 && r.height>0 && r.left>=box.left-1 && r.top>=box.top-1 &&
                        r.right<=box.right+1 && r.bottom<=box.bottom+1;
                });
            });
        }""")

    def test_group_color_slots_and_table_controls(self):
        self.prepare_grid_layout()
        g = self.game
        for ids in [[66, 40, 14], [68, 42, 94], [26, 28, 30], [70, 44, 104]]:
            self.stage_set(ids)
        expect(g.locator("#groupsGrid .meld")).to_have_count(3)
        expect(g.locator("#runsGrid .meld")).to_have_count(1)
        expect(g.locator("#draftsZone")).to_be_hidden()
        for width in [1280, 390]:
            self.page.set_viewport_size({"width": width, "height": 900})
            self.assert_tiles_fit()
            # Every group has four explicit color slots, including jokers and gaps.
            for row in g.locator("#groupsGrid .meld").all():
                self.assertEqual(row.locator("[data-column-color]").evaluate_all(
                    "els=>els.map(el=>el.dataset.columnColor)"), ["2", "1", "3", "0"])
            expect(g.locator('#groupsGrid [data-set-id="set1"] .empty-slot[data-column-color="3"]')).to_have_count(1)
            expect(g.locator('#groupsGrid [data-set-id="set2"] .empty-slot[data-column-color="0"]')).to_have_count(1)
            expect(g.locator('#groupsGrid [data-tile="104"]')).to_have_attribute("data-column-color", "0")
            self.assertTrue(self.frame.evaluate("""() =>
                [...document.querySelectorAll('.group-stack')].every(stack=>{
                    const rows=[...stack.querySelectorAll('.group-row')];
                    return [0,1,2,3].every(color=>{
                        const cells=rows.map(row=>row.querySelector(`[data-column-color="${color}"]`));
                        return cells.every(cell=>Math.abs(cell.getBoundingClientRect().left-
                            cells[0].getBoundingClientRect().left)<1);
                    });
                })"""))
        g.locator('#rack [data-tile="92"]').click()
        g.locator('[data-add="set1"]').click()
        expect(g.locator('#groupsGrid [data-set-id="set1"] .empty-slot')).to_have_count(0)
        expect(g.locator('#groupsGrid [data-tile="92"]')).to_have_attribute("data-column-color", "3")
        g.locator("#undo").click()
        expect(g.locator('#rack [data-tile="92"]')).to_have_count(1)
        expect(g.locator('#groupsGrid [data-set-id="set1"] .empty-slot')).to_have_count(1)

    def test_joker_choice_reclassifies_sets_and_incomplete_drafts_stay_visible(self):
        self.prepare_grid_layout([42, 104, 105, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20])
        g = self.game
        self.stage_set([42, 104, 105])
        expect(g.locator("#runsGrid .meld")).to_have_count(1)
        g.locator('select[data-choice="set1"]').select_option("g9")
        expect(g.locator("#groupsGrid .meld")).to_have_count(1)
        expect(g.locator("#runsGrid .meld")).to_have_count(0)
        expect(g.locator('#groupsGrid .empty-slot[data-column-color="3"]')).to_have_count(1)
        initial_height = g.locator("#table").bounding_box()["height"]
        g.locator('#table [data-tile="42"]').click()
        g.locator("#return").click()
        expect(g.locator("#draftsGrid .tile")).to_have_count(2)
        expect(g.locator("#draftsZone")).to_be_visible()
        self.assertEqual(g.locator("#table").bounding_box()["height"], initial_height)
        self.assert_tiles_fit()
        g.locator("#undo").click()
        expect(g.locator("#groupsGrid .tile")).to_have_count(3)
        expect(g.locator("#draftsZone")).to_be_hidden()

    def test_dense_grids_fit_on_desktop_and_mobile(self):
        self.prepare_grid_layout()
        for ids in [[66, 40, 14], [26, 28, 30]]:
            self.stage_set(ids)
        # Stress the real rendered card/tile geometry with a full-deck-sized view.
        # These DOM-only fixtures do not change game state or bypass turn validation.
        self.frame.evaluate("""() => {
            const groups=document.getElementById('groupsGrid');
            const group=groups.querySelector('.meld');
            for(let i=1;i<34;i++) groups.appendChild(group.cloneNode(true));
            const rack=document.getElementById('rackTiles'), tile=rack.querySelector('.tile');
            while(rack.children.length<106) rack.appendChild(tile.cloneNode(true));
        }""")
        for width in [1280, 390, 768]:
            self.page.set_viewport_size({"width": width, "height": 900})
            self.frame.evaluate("window.dispatchEvent(new Event('resize'))")
            self.assert_tiles_fit()
            expect(self.game.locator("#table .tile")).to_have_count(105)
            expect(self.game.locator("#rack .tile")).to_have_count(106)
            self.assertEqual(self.game.locator("#table").bounding_box()["height"], 440 if width == 390 else 380)
            self.assertTrue(self.frame.evaluate("""() => {
                const scale=id=>new DOMMatrix(getComputedStyle(document.getElementById(id)).transform).a;
                return scale('groupsGrid')<1 && scale('rackTiles')<1 &&
                    document.getElementById('table').scrollTop===0 &&
                    document.documentElement.scrollWidth<=window.innerWidth;
            }"""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
