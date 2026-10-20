"""Real browser tutorial checks against an isolated running lab server.

LAB_TEST_URL=http://127.0.0.1:8766 python tests/test_repair_tour_browser.py
"""
import json
import os
from pathlib import Path

BASE = os.environ.get('LAB_TEST_URL', 'http://127.0.0.1:8766')
ART = Path(os.environ.get('LAB_BROWSER_ARTIFACTS', 'data/browser-artifacts/repair-tour'))


def exercise(browser, width, height):
    context = browser.new_context(viewport={'width': width, 'height': height}, accept_downloads=True)
    page = context.new_page()
    errors, writes = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: writes.append(r.url) if r.method == 'POST' else None)
    page.set_default_timeout(12000)

    def stage(name):
        page.wait_for_function('(s) => document.querySelector(".repair-tour-card")?.dataset.stage === s', arg=name, timeout=90000 if name in ('first', 'compare') else 12000)
        page.wait_for_function('() => { const v=document.querySelector("#workspace-view"); return !v.inert && v.dataset.route === location.hash.slice(1); }')

    def target_click(selector):
        item = page.locator(selector).first
        item.scroll_into_view_if_needed()
        page.wait_for_function('(sel) => {const el=document.querySelector(sel), r=el?.getBoundingClientRect(); return r && document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest(sel);}', arg=selector)
        item.click()

    def screenshot(name):
        page.screenshot(path=str(ART / f'{width}-{name}.png'))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), 'Horizontal overflow'

    try:
        page.goto(BASE + '/demos/01-repair-agent/#overview')
        page.wait_for_load_state('networkidle')
        screenshot('entry')
        page.locator('[data-case-fill]').click()
        stage('create')
        assert page.locator('#task-form [name=repository]').input_value() == 'opensource-mean'
        assert page.locator('#task-form [name=candidate]').input_value() == 'progressive'
        assert page.locator('#task-form [name=max_attempts]').input_value() == '2'
        assert writes == [], 'Prefill must not create a task'
        # The mask and capture guard block both pointer and keyboard activation.
        page.locator('[data-nav=settings]').dispatch_event('click')
        assert page.evaluate('location.hash').startswith('#new?')
        page.locator('#task-form [name=mode]').dispatch_event('focusin')
        assert page.evaluate('document.activeElement.name') != 'mode'
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.closest(".repair-tour-card") !== null')
        screenshot('create')
        # A failed POST must stay on this step, unlock retry, and retain fields.
        page.route('**/api/repair-workspace/tasks', lambda r: r.fulfill(status=503, content_type='application/json', body=json.dumps({'error':'测试中的暂时故障'})), times=1)
        target_click('#task-form button[type=submit]')
        page.locator('.repair-tour-card .tour-problem').wait_for()
        assert page.locator('.repair-tour-card').get_attribute('data-stage') == 'create'
        page.locator('[data-tour=retry]').click()
        stage('create')
        target_click('#task-form button[type=submit]')
        stage('first')
        first = page.evaluate('window.LabRepairTour.state.first')
        data = page.request.get(BASE + '/api/repair-workspace/tasks/' + first).json()
        assert data['status'] == 'succeeded' and len(data['attempts']) == 2
        assert not data['attempts'][0]['passed'] and data['attempts'][1]['passed']
        # Refresh must retain this exact run and restore the next real action.
        count = len(writes)
        page.reload()
        stage('first')
        assert page.evaluate('window.LabRepairTour.state.first') == first and len(writes) == count
        target_click('.attempt-tabs a[href*="attempt=1"]')
        stage('failure')
        target_click('.test-row.fail')
        stage('second')
        assert page.locator('.test-log').is_visible()
        screenshot('failure-log')
        target_click('.attempt-tabs a[href*="attempt=2"]')
        stage('changes')
        target_click('.patch-tabs a[href*="tab=changes"]')
        stage('diff')
        assert page.locator('.test-changes').is_visible()
        screenshot('test-changes')
        target_click('.patch-tabs a[href*="tab=diff"]')
        stage('review')
        assert page.locator('.diff-table').is_visible()
        target_click('#open-review')
        stage('review-form')
        assert page.locator('#review-dialog').is_visible()
        assert page.locator('#review-form [name=actor]').input_value()
        page.locator('.repair-tour-card [data-tour=exit]').click()
        assert not page.locator('#review-dialog').is_visible()
        page.locator('[data-tour=resume]').click()
        stage('review-form')
        assert page.locator('#review-dialog').is_visible()
        page.locator('#review-form [name=actor]').fill('浏览器体验核对人')
        screenshot('review')
        target_click('#review-form button[type=submit]')
        stage('create-second')
        assert page.locator('#task-form [name=candidate]').input_value() == 'correct'
        assert page.locator('#task-form [name=max_attempts]').input_value() == '1'
        target_click('#task-form button[type=submit]')
        stage('compare')
        second = page.evaluate('window.LabRepairTour.state.second')
        ids = page.locator('[name=task_ids]:checked').evaluate_all('(els)=>els.map(e=>e.value)')
        assert set(ids) == {first, second}
        first_data = page.request.get(BASE + '/api/repair-workspace/tasks/' + first).json()
        assert first_data['reviews'][-1]['actor'] == '浏览器体验核对人'
        screenshot('comparison')
        target_click('#comparison-form button[type=submit]')
        stage('export')
        page.route('**/api/repair-workspace/comparisons/*/export?format=markdown', lambda r: r.fulfill(status=503, content_type='application/json', body='{}'), times=1)
        target_click('.page-heading a[href*="format=markdown"]')
        page.locator('.repair-tour-card .tour-problem').wait_for()
        assert page.locator('.repair-tour-card').get_attribute('data-stage') == 'export'
        page.locator('[data-tour=retry]').click()
        stage('export')
        with page.expect_download() as info:
            target_click('.page-heading a[href*="format=markdown"]')
        download = info.value
        download.save_as(str(ART / f'{width}-comparison.md'))
        stage('complete')
        report = page.evaluate('window.LabRepairTour.state.report')
        assert report and '平均值精度修复' in (ART / f'{width}-comparison.md').read_text(encoding='utf-8')
        saved_report = page.request.get(BASE + '/api/repair-workspace/comparisons/' + report).json()
        assert {column['task_id'] for column in saved_report['columns']} == {first, second}
        screenshot('complete')
        page.locator('.repair-tour-card button[data-tour=exit]').last.click()
        assert not page.locator('.repair-tour-shade').is_visible()
        assert not page.locator('body').evaluate('(e)=>e.classList.contains("repair-tour-active")')
        # Escape is an unconditional escape hatch even during form setup.
        page.locator('[data-case-fill]').click()
        stage('create')
        page.keyboard.press('Escape')
        page.locator('[data-nav=settings]').click()
        page.wait_for_function('location.hash === "#settings"')
        assert not errors, errors
        print(f'PASS {width}px: two real tasks, error recovery, reload, focus/mask, review, comparison, actual download and exit')
    except Exception:
        page.screenshot(path=str(ART / f'{width}-failure.png'), full_page=True)
        (ART / f'{width}-failure.html').write_text(page.content(), encoding='utf-8')
        print('Stage:', page.evaluate('window.LabRepairTour?.state'), 'Errors:', errors)
        raise
    finally:
        context.close()


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    ART.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            exercise(browser, 1440, 1000)
            exercise(browser, 390, 844)
        finally:
            browser.close()
