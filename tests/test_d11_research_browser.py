"""Read-only native browser checks; run against LAB_BASE_URL."""
import json
import os
from pathlib import Path

BASE = os.environ.get('LAB_BASE_URL', 'http://127.0.0.1:8766')
ART = Path('data/browser-artifacts/d11-research')


def exercise(browser, width):
    context = browser.new_context(viewport={'width': width, 'height': 900}, accept_downloads=True)
    page = context.new_page()
    errors, writes = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('request', lambda r: writes.append(r.url) if r.method == 'POST' else None)
    try:
        page.goto(BASE + '/demos/01-repair-agent/#research')
        page.wait_for_load_state('networkidle')
        expect(page.get_by_role('heading', name='真实仓库实验', exact=True)).to_be_visible()
        expect(page.get_by_role('status').filter(has_text='显示 30 / 30')).to_be_visible()
        page.get_by_label('实验结果', exact=True).select_option('not_reproduced')
        page.get_by_role('button', name='筛选', exact=True).click()
        expect(page.get_by_role('status').filter(has_text='显示 1 / 30')).to_be_visible()
        page.get_by_role('link', name='tornado-3', exact=True).click()
        expect(page.get_by_text('为什么未复现？', exact=True)).to_be_visible()
        expect(page.get_by_role('heading', name='3 · 模型诊断')).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role('link', name='下载本例证据').click()
        saved = ART / f'{width}-evidence.json'
        download.value.save_as(saved)
        assert json.loads(saved.read_text(encoding='utf8'))['case']['id'] == 'tornado-3'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(ART / f'{width}-detail.png'), full_page=True)
        page.get_by_role('link', name='返回实验列表').click()
        expect(page.get_by_label('实验结果', exact=True)).to_have_value('not_reproduced')
        page.get_by_role('link', name='清除筛选').click()
        expect(page.get_by_role('status').filter(has_text='显示 30 / 30')).to_be_visible()
        for status, count in [('input_out_of_scope', 11), ('model_error', 17), ('budget_exhausted', 1)]:
            page.get_by_label('实验结果', exact=True).select_option(status)
            page.get_by_role('button', name='筛选', exact=True).click()
            expect(page.get_by_role('status').filter(has_text=f'显示 {count} / 30')).to_be_visible()
        page.get_by_label('仓库', exact=True).select_option('httpie')
        page.get_by_role('button', name='筛选', exact=True).click()
        expect(page.get_by_text('没有符合条件的记录，请更换筛选条件。')).to_be_visible()
        page.get_by_role('link', name='清除筛选').click()
        expect(page.get_by_role('status').filter(has_text='显示 30 / 30')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(ART / f'{width}-list.png'), full_page=True)
        page.reload()
        expect(page.get_by_role('heading', name='真实仓库实验', exact=True)).to_be_visible()
        page.goto(BASE + '/demos/01-repair-agent/#research/not-a-case')
        expect(page.get_by_role('heading', name='未找到此实验')).to_be_visible()
        assert not errors, errors
        assert not writes, writes
    finally:
        context.close()


def retry(browser):
    page = browser.new_page()
    pattern = '**/research-data/index.json'
    page.route(pattern, lambda route: route.fulfill(status=503, body='unavailable'))
    page.goto(BASE + '/demos/01-repair-agent/#research')
    expect(page.locator('#workspace-error')).to_be_visible()
    page.unroute(pattern)
    page.get_by_role('button', name='重新读取', exact=True).click()
    expect(page.get_by_role('heading', name='真实仓库实验', exact=True)).to_be_visible()
    page.close()


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright, expect
    ART.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for width in (1440, 390):
                exercise(browser, width)
            retry(browser)
        finally:
            browser.close()
    print('D11 research: desktop/mobile, filters, evidence download, reload, errors and read-only checks passed.')
