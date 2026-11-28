"""Play, pause, skip and replay both K2 storyboards from the story menu."""
from playwright.sync_api import sync_playwright

from _browser import http_base, launch, timeout, ws_base
from _menu import wait_ready
from browser_cold_open_smoke import FAKE_PAD, PADS

SNAPSHOT = """async () => {
  const {getFidelity} = await import('/fidelity.js');
  const {cinematicLookActive} = await import('/story/cutscene_look.js');
  return [getFidelity().snapshot(), localStorage.getItem('rov.fidelity.v1'), cinematicLookActive()];
}"""


def main():
    with sync_playwright() as runner:
        browser = launch(runner)
        page = browser.new_page(viewport={'width': 1600, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script(FAKE_PAD % PADS['playstation'])
        page.goto(f'{http_base()}/?ws={ws_base()}&menu=training&tab=story&quality=performance&fidelity=real')
        wait_ready(page)
        original = page.evaluate(SNAPSHOT)
        assert not original[-1]
        for film in ('harbor', 'strait'):
            card = page.locator(f'[data-chapter="film-{film}"]')
            dialog = page.locator('#cinematicPlayer')
            for skip in (True, False):
                card.click(timeout=timeout(60000))
                dialog.wait_for()
                page.wait_for_function("""() => {
                  const c = document.querySelector('#cinematicPlayer canvas');
                  return c?.getContext('2d').getImageData(600, 300, 1, 1).data[0] > 5;
                }""", timeout=timeout(30000))
                assert page.evaluate(SNAPSHOT) == [*original[:-1], True]
                if skip:
                    page.keyboard.press('Space')
                    pixels = dialog.locator('canvas').evaluate('c => c.toDataURL()')
                    page.wait_for_timeout(400)
                    assert pixels == dialog.locator('canvas').evaluate('c => c.toDataURL()')
                    page.keyboard.press('Space')
                    page.wait_for_function("old => document.querySelector('#cinematicPlayer canvas').toDataURL() !== old",
                                           arg=pixels, timeout=timeout(10000))
                    if film == 'harbor':
                        page.keyboard.press('Escape')
                    else:
                        page.evaluate('window.__pad.buttons[1] = 1')
                        dialog.wait_for(state='detached', timeout=timeout(10000))
                        page.evaluate('window.__pad.buttons[1] = 0')
                else:
                    page.locator('#cinematicPlayer[data-shot="1"]').wait_for(timeout=timeout(60000))
                dialog.wait_for(state='detached', timeout=timeout(60000))
                assert page.evaluate(SNAPSHOT) == original
        assert not errors, errors
        browser.close()
        print('Both films paused, skipped, replayed to completion and restored fidelity.')


if __name__ == '__main__':
    main()
