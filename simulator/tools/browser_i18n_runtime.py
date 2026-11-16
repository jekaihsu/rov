"""Browser language precedence, in-place changes, blocked storage and missing dictionary fallback."""
from playwright.sync_api import sync_playwright
from _browser import http_base, launch


def run():
    with sync_playwright() as p:
        browser = launch(p, headless=True)
        page = browser.new_page(locale='en-US')
        def route_test(route):
            route.fulfill(content_type='text/html; charset=utf-8', body='''
          <html><head></head><body><button id="label"></button><script type="module">
          import {localize, getLanguage} from '/i18n/index.js';
          import {installDisplayPrefs} from '/prefs/display.js';
          window.prefs = installDisplayPrefs();
          window.words = localize('menu.screens', {launch: '下水'});
          window.language = getLanguage;
          document.querySelector('#label').textContent = words.launch;
          window.ready = true;
          </script></body></html>''')

        page.route('**/i18n-test*', route_test)
        page.goto(http_base() + '/i18n-test')
        page.wait_for_function('window.ready')
        assert page.evaluate('language()') == 'en'
        assert page.locator('#label').inner_text() == 'Deploy'
        page.evaluate("window.marker = 42; prefs.set('brightness', 1.1)")
        assert page.evaluate('language()') == 'en'
        page.evaluate("prefs.set('language', 'ja')")
        page.wait_for_function("language() === 'ja'")
        assert page.locator('#label').inner_text() == '着水'
        assert page.evaluate('window.marker') == 42
        assert page.locator('#i18nNotice').is_visible()
        page.evaluate("prefs.set('language', 'zh-Hant')")
        page.wait_for_function("language() === 'zh-Hant'")
        assert page.locator('#label').inner_text() == '下水'
        page.goto(http_base() + '/i18n-test?lang=zh-Hans')
        page.wait_for_function('window.ready')
        page.evaluate("prefs.set('language', 'ja')")
        page.wait_for_timeout(300)
        assert page.evaluate('language()') == 'zh-Hans'
        browser.close()
    print('Language source priority and live changes passed')


if __name__ == '__main__':
    run()
