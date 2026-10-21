"""Native browser acceptance for D01, D02 and D13 against an isolated server."""
import json
import os
import time
from pathlib import Path

BASE=os.environ.get('LAB_TEST_URL','http://127.0.0.1:8766')
ART=Path(os.environ.get('LAB_BROWSER_ARTIFACTS','data/browser-artifacts/guided-tours'))


def exercise(browser,folder,project,width,height):
    context=browser.new_context(viewport={'width':width,'height':height},accept_downloads=True)
    page=context.new_page()
    page.set_default_timeout(20000)
    errors,posts,downloads=[],[],[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
    page.on('download',lambda d:downloads.append(d))
    previous=context.request.get(BASE+'/api/mlops-workspace/service').json() if project=='D02' else None
    try:
        page.goto(BASE+'/demos/'+folder+'/#overview')
        page.locator('[data-case-fill]').wait_for()
        page.screenshot(path=str(ART/f'{project}-{width}-entry.png'))
        page.locator('[data-case-fill]').click()
        page.locator('.guided-tour-card').wait_for()
        page.locator('[data-guided-target]').wait_for()
        assert not posts,'A case prefill must not submit a business request'
        # Verify that both the pointer overlay and captured keyboard actions lock navigation.
        old=page.evaluate('location.hash')
        page.locator('[data-nav]').first.dispatch_event('click')
        assert page.evaluate('location.hash')==old
        page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.closest(".guided-tour-card")!==null')
        seen=set()
        for _ in range(130):
            run=page.evaluate('window.LabGuidedTour.context.run')
            stage=run['stage']
            if stage=='complete':break
            if stage.startswith('wait-'):
                page.wait_for_function('(s)=>window.LabGuidedTour.context.run.stage!==s||document.querySelector(".tour-problem")',arg=stage,timeout=90000)
                continue
            action=page.locator(f'[data-guided-target="{stage}"]')
            action.wait_for()
            page.locator('.guided-tour-card .tour-problem').wait_for(state='hidden')
            if project=='D13' and stage=='project':page.locator('[name=outline_confirmed]').check()
            if project=='D02' and (stage.startswith('deploy-form') or stage=='rollback'):page.locator('#deploy-form [name=confirmed]').check()
            if stage not in seen and ('form' in stage or stage in ('edit','review','audit-result','window','claims')):
                page.screenshot(path=str(ART/f'{project}-{width}-{stage}.png'))
            seen.add(stage)
            # Refresh at a read-only step and continue the exact run, without extra writes.
            if stage=='export' and 'reload-checked' not in seen:
                count=len(posts)
                page.reload()
                page.locator(f'[data-guided-target="{stage}"]').wait_for()
                assert len(posts)==count
                seen.add('reload-checked')
            if stage.startswith('export'):
                with page.expect_download():action.click()
            else:action.click()
            # Prefill may update metadata (e.g. the training cycle); only a
            # completed action may advance the stage and unlock the next click.
            page.wait_for_function('(stage)=>window.LabGuidedTour.context.run.stage!==stage||document.querySelector(".tour-problem")',arg=stage,timeout=90000)
            assert not page.locator('.tour-problem').count(),page.locator('.tour-problem').all_text_contents()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'Horizontal overflow'
        run=page.evaluate('window.LabGuidedTour.context.run')
        assert run['stage']=='complete'
        assert len(downloads)==(3 if project=='D13' else 1)
        for i,download in enumerate(downloads):download.save_as(str(ART/f'{project}-{width}-{i}-{download.suggested_filename}'))
        bundle=json.loads(downloads[-1].path().read_text(encoding='utf-8'))
        if project=='D01':
            assert bundle['version']==2
            assert any(s['document_id']==run['document'] for s in bundle['data']['sources'])
        elif project=='D02':
            assert run['model1']!=run['model2'] and run['prediction']['model_id']==run['model1']
            assert bundle['id']==run['model1'] and bundle['artifact']['schema']=='lab-linear-v1'
        else:
            assert bundle['schema']=='d13-release-v1' and bundle['version']==2
            assert len(run['evidence'])==6
        page.screenshot(path=str(ART/f'{project}-{width}-complete.png'))
        page.locator('.guided-tour-card [data-guided=exit]').last.click()
        page.locator('.guided-tour-shade').wait_for(state='hidden')
        page.locator('[data-case-fill]').click()
        page.locator('[data-guided-target]').wait_for()
        page.keyboard.press('Escape')
        page.locator('.guided-tour-shade').wait_for(state='hidden')
        assert not errors,errors
        print(f'PASS {project} {width}px: real jobs, gates, native download, refresh/exit and layout')
    except Exception:
        page.screenshot(path=str(ART/f'{project}-{width}-failure.png'),full_page=True)
        (ART/f'{project}-{width}-failure.html').write_text(page.content(),encoding='utf-8')
        raise
    finally:
        # CI also verifies earlier workflows after restart. Return the active
        # service to the model that was loaded before this isolated walkthrough.
        if previous and previous.get('ready') and previous.get('model'):
            current=context.request.get(BASE+'/api/mlops-workspace/service').json()
            if current.get('model')!=previous['model']:
                result=context.request.post(BASE+'/api/mlops-workspace/deployments',data={'model':previous['model'],'revision':current['revision'],'rollback':True,'actor':'浏览器回归恢复','comment':'恢复本次体验测试之前的已加载模型。'})
                assert result.ok,result.text()
                job=result.json()['job_id']
                until=time.monotonic()+90
                while time.monotonic()<until:
                    state=context.request.get(BASE+'/api/mlops-workspace/jobs/'+job).json()
                    if state['status']=='succeeded':break
                    assert state['status'] not in ('failed','cancelled','interrupted'),state
                    time.sleep(.2)
                assert state['status']=='succeeded'
        context.close()


if __name__=='__main__':
    from playwright.sync_api import sync_playwright
    ART.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            for folder,project in [('06-literature','D13'),('02-process-rag','D01'),('03-mlops','D02')]:
                for width,height in [(1440,1000),(390,844)]:exercise(browser,folder,project,width,height)
        finally:
            browser.close()
