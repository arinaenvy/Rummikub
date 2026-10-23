"""Browser checks against a running Streamlit app (default port 8501)."""

import os
import re
import shutil
import unittest

from playwright.sync_api import expect, sync_playwright


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

        g.locator("#newGame").click()
        g.locator("#cancelNew").click()
        expect(g.locator("#rack .tile")).to_have_count(staged_count + 1)
        g.locator("#help summary").click()
        expect(g.locator("#help")).to_contain_text("Groups:")

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
