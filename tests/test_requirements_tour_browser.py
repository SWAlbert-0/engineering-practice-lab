"""D09 complete guided walkthrough, using an isolated running lab server."""
import json
import os
from pathlib import Path

BASE=os.environ.get('LAB_TEST_URL','http://127.0.0.1:8766')
ART=Path(os.environ.get('LAB_BROWSER_ARTIFACTS','data/browser-artifacts/requirements-tour'))


def exercise(browser,width,height):
    context=browser.new_context(viewport={'width':width,'height':height},accept_downloads=True)
    page=context.new_page()
    page.set_default_timeout(15000)
    errors=[]
    posts=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)

    def stage(name):
        page.wait_for_function('(s)=>document.querySelector(".requirements-tour-card")?.dataset.stage===s',arg=name)
        page.wait_for_function('()=>{const v=document.querySelector("#workspace-view");return !v.inert&&v.dataset.route===location.hash.slice(1);} ')

    def click(selector):
        el=page.locator(selector).first
        el.scroll_into_view_if_needed()
        page.wait_for_function('(s)=>{const e=document.querySelector(s),r=e?.getBoundingClientRect();return r&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest(s);}',arg=selector)
        el.click()

    def screenshot(name):
        page.screenshot(path=str(ART/f'{width}-{name}.png'))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Horizontal overflow'

    def suite():
        sid=page.evaluate('window.LabRequirementsTour.state.suite')
        response=page.request.get(BASE+'/api/requirements-workspace/sets/'+sid)
        assert response.ok
        return response.json()

    try:
        page.goto(BASE+'/demos/05-requirements/#overview')
        page.wait_for_load_state('networkidle')
        screenshot('entry')
        page.locator('[data-case-fill]').click()
        stage('import')
        assert posts==[], 'Entry must not automatically create business records'
        assert '200' in page.locator('#import-form [name=text]').input_value()
        page.locator('[data-nav=settings]').dispatch_event('click')
        assert page.evaluate('location.hash')=='#import'
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.closest(".requirements-tour-card")!==null')
        screenshot('import')
        page.route('**/api/requirements-workspace/documents',lambda r:r.fulfill(status=503,content_type='application/json',body=json.dumps({'error':'教学测试中的暂时故障'})),times=1)
        click('#import-form [type=submit]')
        page.locator('.tour-problem').wait_for()
        assert page.evaluate('window.LabRequirementsTour.state.stage')=='import'
        page.locator('[data-tour=retry]').click()
        stage('import')
        click('#import-form [type=submit]')
        stage('analyze')
        assert page.locator('#analyze-form [name=mode]').input_value()=='offline'
        click('#analyze-form [type=submit]')
        stage('edit-success')
        page.wait_for_function('()=>{const r=document.querySelector("#commit-cases").getBoundingClientRect();return r.top>=0&&r.bottom<innerHeight;}')
        sid=page.evaluate('window.LabRequirementsTour.state.suite')
        assert len(suite()['cases'])==3
        assert page.locator('#case-form [name=title]').input_value()=='正确凭据登录返回 200'
        page.locator('#case-form [name=title]').fill('我已核对的成功登录用例')
        page.wait_for_function('document.querySelector("#save-state").textContent.includes("草稿已保存")')
        count=len(posts)
        page.reload()
        stage('edit-success')
        assert page.evaluate('window.LabRequirementsTour.state.suite')==sid
        assert page.locator('#case-form [name=title]').input_value()=='我已核对的成功登录用例'
        assert len(posts)==count,'Restoring a saved draft must not create more writes'
        # A conflict must release the tour lock so recovery controls stay usable.
        page.route('**/api/requirements-workspace/sets/*/draft',lambda r:r.fulfill(status=409,content_type='application/json',body=json.dumps({'error':'保存冲突：服务端已有较新的内容。'})),times=1)
        page.locator('#case-form [name=title]').fill('模拟另一页面发生冲突的修改')
        page.locator('#conflict-dialog').wait_for()
        page.wait_for_function('window.LabRequirementsTour.state.active===false')
        page.locator('#conflict-latest').click()
        page.locator('#conflict-dialog').wait_for(state='hidden')
        page.locator('[data-tour=resume]').click()
        stage('edit-success')
        assert page.locator('#case-form [name=title]').input_value()=='我已核对的成功登录用例'
        page.locator('#delete-case').dispatch_event('click')
        assert len(suite()['draft']['cases'])==3,'Other editor actions must stay locked'
        screenshot('edit-success')
        click('#commit-cases')
        stage('edit-auth')
        assert page.locator('#case-form [name=title]').input_value()=='错误密码登录返回 401'
        click('#commit-cases')
        stage('edit-fields')
        assert page.locator('#case-form [name=kind]').input_value()=='异常'
        assert '422' in page.locator('#case-form [name=title]').input_value()
        screenshot('edit-fields')
        click('#commit-cases')
        stage('trace')
        d=suite()
        assert d['version']==4 and not d['draft']
        assert not any(c['questions'] for c in d['cases'])
        assert all(c['origin']=='rule+human' for c in d['cases'])
        assert d['cases'][0]['title']=='我已核对的成功登录用例'
        click('.work-modes a[href*="mode=trace"]')
        stage('trace-source')
        screenshot('trace')
        click('[data-source-route]')
        stage('quality')
        assert page.locator('#source-P001').evaluate('(e)=>e.classList.contains("selected")')
        click('.work-modes a[href*="mode=quality"]')
        stage('review-back')
        screenshot('quality')
        click('.work-modes a[href*="mode=edit"]')
        stage('review-open')
        assert page.locator('[name=review-case]:checked').count()==3
        click('#open-review')
        stage('review-form')
        page.locator('.requirements-tour-card [data-tour=exit]').click()
        assert not page.locator('#review-dialog').is_visible()
        page.locator('[data-tour=resume]').click()
        stage('review-form')
        page.reload()
        stage('review-open')
        click('#open-review')
        stage('review-form')
        page.locator('#review-form [name=actor]').fill('体验核对人')
        screenshot('review')
        click('#review-form [type=submit]')
        stage('publish-open')
        assert len(suite()['reviews'])==3
        click('#open-publish')
        stage('publish-form')
        page.locator('#publish-form [name=actor]').fill('体验发布人')
        screenshot('publish')
        click('#publish-form [type=submit]')
        stage('export')
        release=page.evaluate('window.LabRequirementsTour.state.release')
        assert release
        selector=f'a[href="/api/requirements-workspace/releases/{release}/export?format=json"]'
        page.route('**/releases/*/export?format=json',lambda r:r.fulfill(status=503,body='{}'),times=1)
        click(selector)
        page.locator('.tour-problem').wait_for()
        assert page.evaluate('window.LabRequirementsTour.state.stage')=='export'
        page.locator('[data-tour=retry]').click()
        stage('export')
        with page.expect_download() as info:
            click(selector)
        info.value.save_as(str(ART/f'{width}-release.json'))
        stage('complete')
        bundle=json.loads((ART/f'{width}-release.json').read_text(encoding='utf-8'))
        assert bundle['status']=='released' and bundle['set_id']==sid and bundle['set_version']==4
        assert bundle['published_by']=='体验发布人'
        assert len(bundle['reviews'])==3 and all(r['actor']=='体验核对人' for r in bundle['reviews'])
        screenshot('complete')
        page.locator('.requirements-tour-card [data-tour=exit]').last.click()
        assert not page.locator('.requirements-tour-shade').is_visible()
        page.locator('[data-case-fill]').click()
        stage('import')
        page.keyboard.press('Escape')
        page.locator('[data-nav=settings]').click()
        page.wait_for_function('location.hash==="#settings"')
        assert not errors,errors
        print(f'PASS {width}px: import, actual offline job, 3 case commits, draft restore, trace, review, publish, download, failure recovery and mask/exit')
    except Exception:
        page.screenshot(path=str(ART/f'{width}-failure.png'),full_page=True)
        (ART/f'{width}-failure.html').write_text(page.content(),encoding='utf-8')
        print('Stage:',page.evaluate('window.LabRequirementsTour?.state'),'Errors:',errors)
        raise
    finally:
        context.close()


if __name__=='__main__':
    from playwright.sync_api import sync_playwright
    ART.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            exercise(browser,1440,1000)
            exercise(browser,390,844)
        finally:
            browser.close()
