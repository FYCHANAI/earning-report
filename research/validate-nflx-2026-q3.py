#!/usr/bin/env python3
"""NFLX Q3 2026 evidence/template regression checks.

Fake-DOM/Chart VM only: never accepts PI, writes session storage, hides the
PI modal or calls live AI. This does not establish real-browser rendering.
The harness/protected-DOM mechanics are adapted from the existing JNJ audit.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
BASE = '9be61618d46a17ef95c8c4638982aece3c8e9003'
FILES = ['nflx.html', 'nflx-sc.html', 'nflx-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
KEYS = ['nflxSegment', 'nflxProfit', 'nflxValuation']
CHECKS, RUNTIMES, DETAILS, TABLES = [], {}, {}, []


def check(name, ok, detail=None):
    record = {'check': name, 'status': 'pass' if ok else 'fail'}
    if detail is not None:
        record['detail'] = detail
    CHECKS.append(record)

def oldfile(file):
    return subprocess.check_output(['git', 'show', f'{BASE}:{file}'], cwd=ROOT).decode('utf-8').replace('\r\n', '\n')

def text(element):
    return ' '.join(element.text_content().split())

def scripts(source):
    return re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', source)

def numbers(value):
    value = value.replace('−', '-').replace('–', '-')
    value = re.sub(r'-\s*((?:US)?\$)', r'\1-', value)
    return [float(n.replace(',', '')) for n in re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?', value)]

def normalize_function(value):
    return re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', value)).replace('muSegment', 'nflxSegment').replace('muProfit', 'nflxProfit').replace('muValuation', 'nflxValuation')

def signature(doc):
    """MU DOM and classes, excluding separately protected PI/disclaimer.

    Content-linked source anchors and rating colors may differ from MU;
    report card, table, navigation and chart-container structures may not.
    """
    doc = copy.deepcopy(doc)
    for element in doc.xpath('//script | //*[@id="pi-modal"] | //*[@id="disclaimer"]'):
        element.getparent().remove(element)
    for element in doc.xpath('//section[@id="financials" or @id="our-comments"]//a'):
        element.drop_tag()
    records = []
    for element in doc.iter():
        if not isinstance(element.tag, str):
            continue
        attrs = dict(element.attrib)
        if element.tag == 'option':
            attrs['value'] = attrs.get('value', '').replace('mu', 'nflx')
        if element.tag == 'span' and 'text-xs font-bold px-2 py-1 rounded' in attrs.get('class', ''):
            attrs['class'] = re.sub(r'(?:bg-(?:blue|emerald|slate|pink|red)-100|text-(?:blue-800|emerald-800|slate-600|pink-700|red-600))', 'RATING_COLOR', attrs['class'])
        records.append((element.tag, sorted(attrs.items()), len([c for c in element if isinstance(c.tag, str)])))
    return records

HARNESS = r"""
const fs=require('fs'),vm=require('vm');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const events={},elements=[],ids={},charts=[],fetches=[];let storageWrites=0;
for(const record of input.elements){
 const classes=new Set((record.class||'').split(/\s+/).filter(Boolean));
 const item={id:record.id||'',style:{},innerHTML:'',
  classList:{add(...cs){cs.forEach(c=>classes.add(c))},remove(...cs){cs.forEach(c=>classes.delete(c))},contains(c){return classes.has(c)},toggle(c){classes.has(c)?classes.delete(c):classes.add(c)}},
  getContext(type){if(type!=='2d')throw Error('Unknown context');return{canvasId:this.id}}};
 elements.push(item);if(item.id)ids[item.id]=item;
}
const body={style:{}};
const document={body,addEventListener(name,fn){(events[name]||=[]).push(fn)},
 getElementById(id){if(!ids[id])throw Error('Unknown ID: '+id);return ids[id]},
 querySelectorAll(selector){if(!['.tab-content','.tab-btn'].includes(selector))throw Error('Unmocked selector');return elements.filter(e=>e.classList.contains(selector.slice(1)))}
};
const sandbox={document,window:{},console,
 sessionStorage:{getItem(){return null},setItem(){storageWrites++;throw Error('PI acceptance forbidden')}},
 Chart:function(ctx,config){this.canvasId=ctx.canvasId;this.config=config;this.resizeCalls=0;this.resize=()=>this.resizeCalls++;charts.push(this)},
 fetch:async url=>{fetches.push(url);if(url!=='disclaimer.html')throw Error('Network/API request forbidden');return{ok:true,text:async()=>input.disclaimer}}
};
const context=vm.createContext(sandbox);
(async()=>{
 for(let i=0;i<input.scripts.length;i++)new vm.Script(input.scripts[i],{filename:input.file+':inline-'+i}).runInContext(context);
 const listeners={};for(const name of ['mouseup','mousedown'])listeners[name]=(events[name]||[]).map(fn=>fn.toString());
 const functions={};for(const name of ['switchTab','acceptPI','declinePI','callGeminiAPI','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','explainSelectedTerm','closeExplainModal']){
  functions[name]=context[name].toString();
 }
 const domListener=events.DOMContentLoaded[0].toString();
 const loader=domListener.slice(domListener.indexOf("fetch('disclaimer.html')")).replace(/\s*\}\s*$/,'');
 const gate=domListener.slice(domListener.indexOf("if (!sessionStorage.getItem('pi_agreed'))"),domListener.indexOf('window.charts.')).replace(/\/\/[^\n]*/g,'').trim();
 if(input.functionsOnly){process.stdout.write(JSON.stringify({functions,loader,gate,listeners}));return;}
 for(const fn of events.DOMContentLoaded||[])fn();
 await Promise.resolve();await Promise.resolve();await Promise.resolve();await Promise.resolve();
 if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate inactive');
 const buttons=elements.filter(e=>e.classList.contains('tab-btn')),tabs=[];
 for(let i=0;i<input.tabs.length;i++){
  // Pure-function unit check on fake nodes; the PI gate remains active.
  context.switchTab({currentTarget:buttons[i]},input.tabs[i]);
  const active=elements.filter(e=>e.classList.contains('tab-content')&&e.classList.contains('active')).map(e=>e.id);
  tabs.push({id:input.tabs[i],ok:active.length===1&&active[0]===input.tabs[i]&&buttons.filter(e=>e.classList.contains('active')).length===1&&buttons[i].classList.contains('active')});
  if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate altered');
 }
 process.stdout.write(JSON.stringify({charts,keys:Object.keys(sandbox.window.charts),tabs,fetches,storageWrites,
  piVisible:ids['pi-modal'].style.display==='flex',bodyLocked:body.style.overflow==='hidden',
  disclaimerLoaded:ids['disclaimer-container'].innerHTML===input.disclaimer,
  listeners,standardPrompt:vm.runInContext('standardPrompt',context),functions,loader,gate}));
})().catch(e=>{console.error(e.stack);process.exit(1)});
"""

def run_vm(file, source, doc, functions_only=False):
    payload = {'file': file, 'scripts': scripts(source), 'tabs': TABS,
               'disclaimer': (ROOT/'disclaimer.html').read_text(), 'functionsOnly': functions_only,
               'elements': [{'tag': e.tag, **dict(e.attrib)} for e in doc.iter() if isinstance(e.tag, str)]}
    result = subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_NODE', 'node'), '-e', HARNESS],
                            input=json.dumps(payload), capture_output=True, text=True, cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)

def protected_dom(doc, target_id):
    node = copy.deepcopy(doc.get_element_by_id(target_id))
    if target_id == 'disclaimer':
        # Normalize only section numbering; legal wording and all other DOM
        # attributes remain protected.
        heading = node.xpath('.//h2')[0]
        heading.text = re.sub(r'^(?:VII\.|VI\.|7\.|6\.|七、|六、)', 'SECTION_NUMBER', heading.text)
    return [(e.tag, sorted(e.attrib.items()), ' '.join((e.text or '').split()), ' '.join((e.tail or '').split()) if e is not node else '') for e in node.iter() if isinstance(e.tag,str)]



COLORS = {'Overweight': 'bg-blue-100 text-blue-800', 'Buy': 'bg-emerald-100 text-emerald-800',
          'Neutral': 'bg-slate-100 text-slate-600', 'Sell': 'bg-pink-100 text-pink-700',
          'Underweight': 'bg-red-100 text-red-600'}
# Independent references transcribed from the official shareholder letter and
# owner-provided Bloomberg screenshots. The evidence ledger retains provenance.
ANR_PRICE = 68.69
ANR_TARGET = 90.12
BROKERS = [
    {'firm':'Morgan Stanley','rating':'Overweight','target':80.0,'date':'2026/10/08'},
    {'firm':'JP Morgan','rating':'Overweight','target':85.0,'date':'2026/10/07'},
    {'firm':'Citi','rating':'Buy','target':100.0,'date':'2026/10/20'}]
FORBIDDEN = r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|\bSCAs\b|1-gamma|G9 NAND|Kioxia|SK Hynix|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|107\.85|74\.35|2026/07/17'

def public_text(doc):
    doc = copy.deepcopy(doc)
    for e in doc.xpath('//script | //style'):
        e.getparent().remove(e)
    return text(doc)

for file in FILES:
    source = (ROOT/file).read_text()
    template_name = file.replace('nflx', 'mu')
    template, prior = (ROOT/template_name).read_text(), oldfile(file)
    doc, mu, old = map(html.fromstring, [source, template, prior])
    locale = 'sc' if '-sc.' in file else 'en' if '-en.' in file else 'tc'
    sig, musig = signature(doc), signature(mu)
    diffs = [{'index': i, 'nflx': a, 'mu': b} for i, (a, b) in enumerate(zip(sig, musig)) if a != b][:5]
    check(file+':mu_layout_dom_attributes', sig == musig, {'actual_nodes':len(sig),'template_nodes':len(musig),'first_differences':diffs} if sig != musig else None)
    check(file+':mu_styles_fonts_and_dependencies', doc.xpath('//style/text()') == mu.xpath('//style/text()') and doc.xpath('//head/link/@href') == mu.xpath('//head/link/@href') and doc.xpath('//script/@src') == mu.xpath('//script/@src'))
    check(file+':six_tabs_three_charts_unique_ids', doc.xpath('//section/@id') == TABS and doc.xpath('//canvas/@id') == CANVASES and doc.xpath('//nav/button/@onclick') == [f"switchTab(event, '{tab}')" for tab in TABS] and len(doc.xpath('//@id')) == len(set(doc.xpath('//@id'))))
    check(file+':language_links_and_selected_locale', doc.xpath('//select/option/@value') == FILES and doc.xpath('//select/option[@selected]/@value') == [file])
    check(file+':protected_pi_legal_dom_and_disclaimer', protected_dom(doc, 'pi-modal') == protected_dom(old, 'pi-modal') and protected_dom(doc, 'disclaimer') == protected_dom(old, 'disclaimer'))
    check(file+':no_stale_template_facts_or_placeholders', not re.search(FORBIDDEN, source, re.I) and not re.search(r'||\bturn\d+(?:search|view|fetch)\d+|\bTODO\b|\bTBD\b|\{\{', source))
    views = text(doc.get_element_by_id('our-comments'))
    check(file+':dates_voice_and_four_viewpoints', all(v in views for v in ['2026/09/30', '2026/10/20', '2026/10/21']) and len(doc.get_element_by_id('our-comments').xpath('.//li')) == 4 and {'tc': '我們認為', 'sc': '我们认为', 'en': 'We believe'}[locale] in views)
    header = text(doc.xpath('//header')[0])
    check(file+':header_quarter_consensus_rating_and_target', all(v in header for v in ['Q3', '2026', '90.12', '4.40']))
    financials = doc.get_element_by_id('financials')
    table = financials.xpath('.//table')[0]
    rows = table.xpath('.//tbody/tr')
    check(file+':four_kpis_and_five_row_comparison', len(financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div')) == 4 and len(table.xpath('.//thead/tr/th')) == 4 and len(rows) == 5 and all(len(r.xpath('./td')) == 4 for r in rows))
    table_numbers = [[numbers(text(td)) for td in row.xpath('./td')[1:]] for row in rows]
    TABLES.append(table_numbers)
    expected_rows = [
        [[11510.31], [12874.18], [11.8]],
        [[3248.25], [4458.6], [37.3]],
        [[28.2], [34.6], [6.4]],
        [[2546.92], [3663.93], [43.9]],
        [[0.59], [0.87], [49.0]]]
    check(file+':official_gaap_financial_values_and_changes', table_numbers == expected_rows, table_numbers if table_numbers != expected_rows else None)
    check(file+':eps_growth_identified_as_company_reported', bool(re.search(r'公司|company', text(rows[-1]), re.I)))
    kpis = financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div/p[1]')
    check(file+':kpis_reconcile_official_actuals', [numbers(text(k)) for k in kpis] == [[12874.18],[0.87],[34.6],[2883.51]])
    financial_text = text(financials)
    check(file+':fcf_reconciliation_and_non_gaap_label', {3162.279, 278.766, 2883.513} <= set(numbers(financial_text)) and 'Non-GAAP' in financial_text)
    check(file+':q4_company_guidance_distinct_from_market_forecast', {13442, 3500, 26.0, 0.67, 51.1, 31.5, 13513, 0.731} <= set(numbers(financial_text)) and 'Bloomberg EEO' in financial_text and bool(re.search(r'公布前|發布前|发布前|pre.?release|pre.?announcement', financial_text, re.I)))
    check(file+':financial_table_units_and_gaap_basis', bool(re.search(r'GAAP', text(financials))) and bool(re.search(r'美元|USD|US\$|million|Million', text(financials))))
    check(file+':diluted_eps_and_split_basis', bool(re.search(r'diluted|攤薄|摊薄|稀釋|稀释', text(financials), re.I)) and bool(re.search(r'拆|split', text(financials), re.I)))
    valuation = text(doc.get_element_by_id('valuation'))
    check(file+':valuation_period_accounting_and_business_limits', all(v in valuation for v in ['2027', 'GAAP+', 'Adj+']) and bool(re.search(r'業務|业务|business', valuation, re.I)) and bool(re.search(r'財年|财年|fiscal', valuation, re.I)) and bool(re.search(r'日期|時點|时点|date|timestamp', valuation, re.I)))
    street = doc.get_element_by_id('street-comments')
    cards = street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    card_results = []
    for card, broker in zip(cards, BROKERS):
        body, badge = text(card), card.xpath('.//span')[0]
        ret = round((broker['target']/ANR_PRICE-1)*100, 1)
        ok = broker['firm'] in text(card.xpath('.//h3')[0]) and text(badge) == broker['rating'] and COLORS[broker['rating']] in badge.get('class', '')
        ok = ok and broker['target'] in numbers(body) and f'{ret:.1f}%' in body and broker['date'] in body and len(card.xpath('.//li')) == 2
        card_results.append({'firm': broker['firm'], 'ok': ok, 'return_pct': ret})
    check(file+':broker_order_ratings_colors_dates_and_returns', len(cards) == 3 and len(card_results) == 3 and all(c['ok'] for c in card_results), card_results)
    source_lines = [text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
    check(file+':compact_anr_source_no_classification_explanation', len(source_lines) == 1 and all(v in source_lines[0] for v in ['2026/10/21', '10/20', '68.69']) and len(source_lines[0]) < 240 and not re.search(r'統一分類|统一分类|standardized|standardised|site category|display category', text(street), re.I))
    visible = public_text(doc)
    check(file+':no_calculator_attribution', not re.search(r'NTAM\s*(?:計算|计算|calculation|calculated|estimates)', visible, re.I))
    risk = doc.get_element_by_id('risks')
    headings = risk.xpath('.//li/strong')
    check(file+':all_risks_same_dark_heading', len(headings) == 4 and all(h.get('class') == 'text-base' for h in headings) and not re.search(r'text-(?:red|rose)-', html.tostring(risk, encoding='unicode')))
    try:
        result = run_vm(file, source, doc)
        mu_result = run_vm(template_name, template, mu, functions_only=True)
        old_result = run_vm(file, prior, old, functions_only=True)
        RUNTIMES[file] = result
        check(file+':javascript_parse_and_mock_execution', True)
        check(file+':tab_switch_and_resize', result['keys'] == KEYS and all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']] == [1, 1, 1])
        check(file+':pi_active_no_acceptance_no_live_api', result['storageWrites'] == 0 and result['piVisible'] and result['bodyLocked'] and result['fetches'] == ['disclaimer.html'] and result['disclaimerLoaded'])
        check(file+':pi_api_and_disclaimer_functions_preserved', all(normalize_function(result['functions'][n]) == normalize_function(old_result['functions'][n]) for n in ['acceptPI', 'declinePI', 'callGeminiAPI']) and all(normalize_function(result[n]) == normalize_function(old_result[n]) for n in ['loader', 'gate']))
        interaction_names = ['switchTab', 'toggleChat', 'appendMessage', 'showTypingIndicator', 'handleChatSubmit', 'closeExplainModal']
        check(file+':mu_fixed_chat_and_chart_behavior', all(normalize_function(result['functions'][n]) == normalize_function(mu_result['functions'][n]) for n in interaction_names))
        check(file+':mu_tooltip_behavior', all([normalize_function(v) for v in result['listeners'][n]] == [normalize_function(v) for v in mu_result['listeners'][n]] for n in ['mouseup', 'mousedown']))
        prompt = result['standardPrompt']
        prompt_numbers = set(numbers(prompt))
        check(file+':dated_nflx_ai_basis_and_facts', all(v in prompt for v in ['NFLX', '2026/10/21', '2026/09/30', '2026/10/20', 'GAAP']) and {0.87, 68.69, 90.12} <= prompt_numbers and not re.search(FORBIDDEN, prompt, re.I))
        check(file+':ai_language_format_and_snapshot_limits', 'markdown' in prompt.lower() and '<b>' in prompt and {'tc': '繁體中文', 'sc': '简体中文', 'en': 'English'}[locale] in prompt and bool(re.search(r'即時|即时|real.time|live market', prompt, re.I)))
        charts = {c['canvasId']: c['config'] for c in result['charts']}
        regional, profit, peer = [charts[c] for c in CANVASES]
        check(file+':regional_revenue_chart', regional['type'] == 'doughnut' and regional['data']['datasets'][0]['data'] == [5628.215, 4106.572, 1602.603, 1536.786])
        check(file+':profit_chart_dates_and_values', profit['data']['labels'] == ['Q3 2025', 'Q4 2025', 'Q1 2026', 'Q2 2026', 'Q3 2026'] and [d['data'] for d in profit['data']['datasets']] == [[11510, 12051, 12250, 12560, 12874], [28.2, 24.5, 32.3, 33.4, 34.6]])
        check(file+':fy2027_peer_values_order_and_nflx_highlight', peer['data']['datasets'][0]['data'] == [6.36,12.41,14.86,18.14] and all(ticker in label for ticker,label in zip(['CMCSA','SKYD','DIS','NFLX'],peer['data']['labels'])) and peer['data']['datasets'][0]['backgroundColor'] == ['rgba(148, 163, 184, 0.6)', 'rgba(148, 163, 184, 0.6)', 'rgba(148, 163, 184, 0.6)', 'rgba(37, 99, 235, 0.95)'])
        check(file+':profit_chart_separate_axes', profit['type'] == 'bar' and profit['data']['datasets'][1].get('yAxisID') == 'percentageAxis' and profit['options']['scales']['percentageAxis']['position'] == 'right' and profit['options']['scales']['percentageAxis']['max'] == 100)
        check(file+':responsive_chart_configuration', all(c['options'].get('responsive') is True and c['options'].get('maintainAspectRatio') is False for c in charts.values()) and peer['options'].get('indexAxis') == 'y')
        DETAILS[file] = {'sha256': hashlib.sha256((ROOT/file).read_bytes()).hexdigest(), 'mock_charts': result['charts']}
    except Exception as exc:
        check(file+':javascript_parse_and_mock_execution', False, str(exc))

numeric = [[[d['data'] for d in c['config']['data']['datasets']] for c in r['charts']] for r in RUNTIMES.values()]
check('three_languages:financial_table_and_chart_numeric_parity', len(TABLES) == 3 and all(t == TABLES[0] for t in TABLES) and len(numeric) == 3 and all(n == numeric[0] for n in numeric))
check('evidence:target_return', round((ANR_TARGET/ANR_PRICE-1)*100, 1) == 31.2)
check('evidence:quarterly_cashflow_and_regional_revenue_reconcile', round(3162.279 - 278.766,3) == 2883.513 and round(sum([5628.215,4106.572,1602.603,1536.786]),3) == 12874.176)
check('evidence:yoy_growth_precision', [round((new/old-1)*100,1) for new,old in [(12874.176,11510.307),(4458.600,3248.247),(3663.927,2546.916),(2883.513,2660.455)]] == [11.8,37.3,43.9,8.4] and round(((3663.927/4195.127)/(2546.916/4340.392)-1)*100) == 49)

tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
protected = [p for p in tracked if p.startswith('api/') or p in ['CNAME', 'disclaimer.html', 'vercel.json', 'package.json', 'package-lock.json', 'mu.html', 'mu-sc.html', 'mu-en.html']]
check('protected:infrastructure_and_mu_files_unchanged', all((ROOT/p).read_text() == oldfile(p) for p in protected), protected)
changed = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
check('scope:only_nflx_and_homepage_html_modified', all(not p.endswith('.html') or p in FILES+['index.html'] for p in changed), changed)
index_source, old_index_source = (ROOT/'index.html').read_text(), oldfile('index.html')
index, old_index = map(html.fromstring, [index_source, old_index_source])
cards = index.xpath('//div[contains(@onclick,"window.location.href=")]')
old_cards = old_index.xpath('//div[contains(@onclick,"window.location.href=")]')
tickers = [text(c.xpath('.//h3')[0]) for c in cards]
old_tickers = [text(c.xpath('.//h3')[0]) for c in old_cards]
check('homepage:nflx_first_other_order_preserved', len(cards) == len(old_cards) == 25 and tickers[0] == 'NFLX' and [t for t in tickers if t != 'NFLX'] == [t for t in old_tickers if t != 'NFLX'], tickers)
nflx_card = text(next(c for c in cards if text(c.xpath('.//h3')[0]) == 'NFLX'))
check('homepage:nflx_date_quarter_target', all(v in nflx_card for v in ['2026年10月21日更新', '90.12', '31.2%']) and bool(re.search(r'Q3|第三季', nflx_card)))

def raw_homepage_blocks(source):
    pattern = r'<div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm card-hover flex flex-col h-full cursor-pointer group" onclick="window.location.href=\'([^\']+)\'">'
    starts = list(re.finditer(pattern, source))
    end = source.index('</div>\n</main>', starts[-1].start())
    blocks = {m[1]: source[m.start():starts[i+1].start() if i+1 < len(starts) else end] for i, m in enumerate(starts)}
    return source[:starts[0].start()], blocks, source[end:]

prefix, blocks, suffix = raw_homepage_blocks(index_source)
old_prefix, old_blocks, old_suffix = raw_homepage_blocks(old_index_source)
check('homepage:other_24_cards_and_outer_document_unchanged', len(blocks) == 25 and all(block == old_blocks[name] for name, block in blocks.items() if name != 'nflx.html') and prefix == old_prefix and suffix == old_suffix)
def card_dom_signature(card):
    return [(e.tag, sorted(e.attrib.items()), len([c for c in e if isinstance(c.tag, str)])) for e in card.iter() if isinstance(e.tag, str)]
current_nflx = next(c for c in cards if text(c.xpath('.//h3')[0]) == 'NFLX')
prior_nflx = next(c for c in old_cards if text(c.xpath('.//h3')[0]) == 'NFLX')
check('homepage:nflx_card_structure_preserved', card_dom_signature(current_nflx) == card_dom_signature(prior_nflx))
whitespace = subprocess.run(['git', '-c', 'core.whitespace=cr-at-eol', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
check('git_diff_whitespace', whitespace.returncode == 0, whitespace.stdout+whitespace.stderr or None)
failed = [r for r in CHECKS if r['status'] == 'fail']
report = {'report': 'NFLX Q3 2026 official/Bloomberg evidence and MU-template validation',
          'checked_on': '2026-10-21', 'base_commit': BASE, 'status': 'fail' if failed else 'pass',
          'checks': CHECKS, 'page_details': DETAILS,
          'limitations': ['Fake DOM and Chart constructor only; not real-browser rendering or Chart.js rasterization.',
                          'No PI acceptance, storage write, PI modal removal/hiding, access-control bypass or live AI call.',
                          'Financial fact transcription and primary-source provenance are recorded separately in the source ledger.',
                          'EEO snapshot forecast cutoff is unknown; estimates are not verified prerelease consensus.',
                          'ANR 2026/10/21 shows 10/20 quote US$68.69; not an established post-earnings reaction.',
                          'Screen-visible broker coverage is incomplete; selected Morgan Stanley/JP Morgan/Citi cards use readable evidence only.',
                          'Peer P/E fiscal windows and accounting adjustments differ; comparison limits are disclosed.',
                          'Desktop/mobile browser review and production HTTP comparison, if completed, are recorded separately.']}
destination = ROOT/'research/nflx-2026-q3-validation.json'
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': report['status'], 'checks': len(CHECKS), 'failed': failed, 'output': str(destination)}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failed))
