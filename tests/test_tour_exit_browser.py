"""Cancel pending tour animation frames without submitting business requests."""
import json
import os

BASE = os.environ.get('LAB_TEST_URL', 'http://127.0.0.1:8765')


def exercise(browser, folder, key, state, selector, width):
    context = browser.new_context(viewport={'width': width, 'height': 1000 if width > 760 else 844})
    # A saved first-step state exposes resume without creating a business record.
    # The sentinel ID is never fetched: both routes are creation forms.
    context.add_init_script(f'localStorage.setItem({json.dumps(key)}, {json.dumps(json.dumps(state))})')
    page = context.new_page()
    errors, writes = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda request: writes.append(request.url) if request.method == 'POST' else None)
    try:
        page.goto(BASE + '/demos/' + folder + '/#' + ('import' if folder == '05-requirements' else 'new?repository=opensource-mean'))
        page.locator(selector).wait_for()
        page.locator('[data-tour=exit]').wait_for()
        page.wait_for_function('(s)=>document.activeElement===document.querySelector(s)', arg=selector)
        page.evaluate('''() => {
            document.querySelector('[data-tour=exit]').click();
            document.querySelector('[data-tour=resume]').click();
            document.querySelector('[data-tour=exit]').click();
        }''')
        # Let the frame queued by resume execute after exit has cleared target.
        page.wait_for_timeout(150)
        assert not errors, errors
        assert not writes, writes
        page.locator('[data-tour=resume]').wait_for()
        print(f'PASS {folder} {width}px: same-frame exit/resume/exit, no script errors or writes')
    finally:
        context.close()


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in (1440, 390):
                exercise(browser, '01-repair-agent', 'lab-repair-tour-v2', {'active': True, 'stage': 'create', 'first': 'exit-test'}, '#task-form [type=submit]', width)
                exercise(browser, '05-requirements', 'lab-requirements-tour-v1', {'active': True, 'stage': 'import', 'document': 'exit-test'}, '#import-form [type=submit]', width)
        finally:
            browser.close()
