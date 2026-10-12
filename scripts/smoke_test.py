#!/usr/bin/env python3
"""Test the reader framework against a generated HTML without modifying it."""
import argparse
import math
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--html', type=Path, default=Path(__file__).resolve().parent.parent / 'examples/demo_reader.html')
    ap.add_argument('--browser-executable', type=Path)
    ap.add_argument('--screenshots', type=Path)
    args = ap.parse_args()
    if not args.html.is_file():
        ap.error('HTML not found; build a reader in your task directory and pass --html')
    executable = args.browser_executable
    if executable is None:
        for candidate in ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', shutil.which('google-chrome'), shutil.which('chromium')):
            if candidate and Path(candidate).is_file():
                executable = Path(candidate)
                break
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)
    errors, network = [], []
    with tempfile.TemporaryDirectory(prefix='courseware-smoke-') as temp, sync_playwright() as p:
        # A unique file origin avoids reading or changing an existing student's notes.
        test_html = Path(temp) / 'reader.html'
        shutil.copy2(args.html, test_html)
        launch = {'headless': True}
        if executable:
            launch['executable_path'] = str(executable)
        browser = p.chromium.launch(**launch)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        def block_network(route):
            network.append(route.request.url)
            route.abort()
        context.route('http://**/*', block_network)
        context.route('https://**/*', block_network)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(test_html.as_uri())
        expect(page.locator('#article h1')).to_be_visible()
        course = page.locator('#COURSE_DATA').evaluate('(el) => JSON.parse(el.textContent)')
        slides = page.locator('#SLIDE_DATA').evaluate('(el) => JSON.parse(el.textContent)')
        expect(page.locator('.pdf-sheet')).to_have_count(len(slides))
        # Move PDF independently, then traverse all lessons without changing that position.
        page.locator('#pdf-page').fill(str(len(slides)))
        page.locator('#pdf-page').dispatch_event('change')
        page.wait_for_timeout(1000)
        pdf_pos = page.locator('#pdf-scroll').evaluate('(el) => el.scrollTop')
        for index, lesson in enumerate(course['lessons']):
            expect(page.locator('#article h1')).to_have_text(lesson['title'])
            assert abs(page.locator('#pdf-scroll').evaluate('(el) => el.scrollTop') - pdf_pos) < 10
            math_blocks = [b for b in lesson['blocks'] if b['type'] == 'equation']
            if math_blocks:
                expect(page.locator('#article .equation svg')).to_have_count(len(math_blocks))
            assert page.locator('#article [data-mml-node="merror"]').count() == 0
            for lab_index, block in enumerate(b for b in lesson['blocks'] if b['type'] == 'interactive'):
                lab = page.locator('.action-block').filter(has=page.locator('.lab-result, .lab-matrices')).nth(lab_index)
                if block['kind'] == 'output_shape':
                    sliders = lab.locator('input[type=range]')
                    for k, value in enumerate((7, 3, 1, 2)):
                        sliders.nth(k).fill(str(value))
                    expect(lab.locator('.lab-result')).to_contain_text('= 4，')
                elif block['kind'] == 'convolution':
                    cfg = block['config']
                    x, kernel = cfg['input'], cfg['kernel']
                    expected = cfg.get('bias', 0) + sum(x[i][j] * kernel[i][j] for i in range(len(kernel)) for j in range(len(kernel[0])))
                    def result():
                        return float(lab.locator('.step-sum').inner_text().rsplit('=', 1)[1])
                    assert math.isclose(result(), expected)
                    new_weight = kernel[0][0] + 1
                    lab.locator('.matrix-table input').first.fill(str(new_weight))
                    lab.locator('.matrix-table input').first.dispatch_event('change')
                    assert math.isclose(result(), expected + x[0][0])
            questions = [q for b in lesson['blocks'] if b['type'] == 'quiz' for q in b.get('questions', [])]
            for q_index, q in enumerate(questions):
                box = page.locator('.quiz-item').nth(q_index)
                button = box.get_by_role('button', name='检查答案')
                button.click()
                expect(box.locator('.feedback')).to_have_text('先完成答案，再检查。')
                if q['type'] == 'single_choice':
                    box.locator('input[type=radio]').nth(q['answer']).check()
                else:
                    values = [q['answer']] if q['type'] == 'numeric' else [part['answer'] for part in q['parts']]
                    for k, value in enumerate(values):
                        box.locator('.quiz-input').nth(k).fill(str(value))
                button.click()
                expect(box.locator('.feedback')).to_have_class('feedback good')
                if q['type'] == 'numeric':
                    box.locator('.quiz-input').fill(str(q['answer'] + abs(q.get('tolerance', 0)) + 1))
                    button.click()
                    expect(box.locator('.feedback')).to_contain_text('再想想：')
                    button.click()
                    expect(box.locator('.feedback')).to_contain_text('逐步解析：')
            if index < len(course['lessons']) - 1:
                page.locator('#lesson-next').click()
        page.locator('.note-box').fill('smoke-test note')
        page.reload()
        expect(page.locator('.note-box')).to_have_value('smoke-test note')
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / 'desktop.png'))
        for width in (375, 768):
            mobile = context.new_page()
            mobile.set_viewport_size({'width': width, 'height': 844})
            mobile.on('pageerror', lambda e: errors.append(str(e)))
            mobile.goto(test_html.as_uri())
            expect(mobile.locator('#lesson-pane')).to_be_visible()
            mobile.locator('#lesson-pane').evaluate('(el) => el.scrollTop = 100')
            left_pos = mobile.locator('#lesson-pane').evaluate('(el) => el.scrollTop')
            mobile.locator('[data-target=pdf]').click()
            expect(mobile.locator('#pdf-pane')).to_be_visible()
            mobile.locator('#pdf-scroll').evaluate('(el) => el.scrollTop = 100')
            right_pos = mobile.locator('#pdf-scroll').evaluate('(el) => el.scrollTop')
            mobile.locator('[data-target=lesson]').click()
            assert mobile.locator('#lesson-pane').evaluate('(el) => el.scrollTop') == left_pos
            mobile.locator('[data-target=pdf]').click()
            assert mobile.locator('#pdf-scroll').evaluate('(el) => el.scrollTop') == right_pos
            assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
            if args.screenshots:
                mobile.screenshot(path=str(args.screenshots / f'mobile-{width}.png'))
            mobile.close()
        assert not errors, errors
        assert not network, f'Unexpected network requests: {network}'
        browser.close()
    print('PASS: all lesson titles, complete PDF, independent navigation, SVG formulas, supported Labs/quiz types present, notes, mobile tabs at 375/768px, no network requests or JS errors.')


if __name__ == '__main__':
    main()
