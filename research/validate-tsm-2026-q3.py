#!/usr/bin/env python3
"""TSM Q3 2026 evidence/template regression checks.

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
BASE = 'ddcc20d27f842113fe41165c3e844ac5ec2ae4b4'
LEDGER = json.loads((ROOT/'research/tsm-2026-q3-2026-10-16.json').read_text())
OFFICIAL, BLOOMBERG = LEDGER['official'], LEDGER['bloomberg']
F, ANR = OFFICIAL['quarterly'], BLOOMBERG['anr']
FILES = ['tsm.html', 'tsm-sc.html', 'tsm-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
KEYS = ['tsmSegment', 'tsmProfit', 'tsmValuation']
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
    return re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', value)).replace('muSegment', 'tsmSegment').replace('muProfit', 'tsmProfit').replace('muValuation', 'tsmValuation')

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
    # Only the operating-margin KPI combines positive YoY with negative QoQ.
    # Neutral gray is allowed for this one mixed-direction supplement.
    mixed = doc.get_element_by_id('financials').xpath('./div[contains(@class,"lg:grid-cols-4")]/div[3]/p[2]')
    records = []
    for element in doc.iter():
        if not isinstance(element.tag, str):
            continue
        attrs = dict(element.attrib)
        if element.tag == 'option':
            attrs['value'] = attrs.get('value', '').replace('mu', 'tsm')
        if element in mixed:
            attrs['class'] = re.sub(r'text-(?:emerald-600|slate-600)', 'text-MIXED-DIRECTION', attrs.get('class', ''))
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
PEERS = ['SAMSUNG', 'TSM', 'SMIC', 'INTC']
PE = [BLOOMBERG['eeo'][ticker]['multiples']['Price_EPS_Adj+'][3] for ticker in PEERS]
FORBIDDEN = r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|\bSCAs\b|1-gamma|G9 NAND|Kioxia|SK Hynix|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|331\.91|UnitedHealthcare|Optum|\bUNH\b|Johnson.{0,4}Johnson|\bJNJ\b|Firefly|Sail Biosciences'


for file in FILES:
    source = (ROOT/file).read_text()
    template_name = file.replace('tsm', 'mu')
    template, prior = (ROOT/template_name).read_text(), oldfile(file)
    doc, mu, old = map(html.fromstring, [source, template, prior])
    locale = 'sc' if '-sc.' in file else 'en' if '-en.' in file else 'tc'
    sig, musig = signature(doc), signature(mu)
    diffs = [{'index': i, 'tsm': a, 'mu': b} for i, (a, b) in enumerate(zip(sig, musig)) if a != b][:5]
    check(file+':mu_layout_dom_attributes', sig == musig, diffs or None)
    check(file+':mu_styles_fonts_and_pinned_chart_library', doc.xpath('//style/text()') == mu.xpath('//style/text()') and doc.xpath('//head/link/@href') == mu.xpath('//head/link/@href') and doc.xpath('//script/@src') == ['https://cdn.tailwindcss.com', 'https://cdn.jsdelivr.net/npm/chart.js@4.5.1'])
    check(file+':six_tabs_three_charts_unique_ids', doc.xpath('//section/@id') == TABS and doc.xpath('//canvas/@id') == CANVASES and doc.xpath('//nav/button/@onclick') == [f"switchTab(event, '{tab}')" for tab in TABS] and len(doc.xpath('//@id')) == len(set(doc.xpath('//@id'))))
    check(file+':language_links', doc.xpath('//select/option/@value') == FILES)
    check(file+':protected_pi_legal_dom_and_disclaimer', protected_dom(doc, 'pi-modal') == protected_dom(old, 'pi-modal') and protected_dom(doc, 'disclaimer') == protected_dom(old, 'disclaimer'))
    check(file+':no_stale_template_facts_or_placeholders', not re.search(FORBIDDEN, source, re.I) and not re.search(r'||\bturn\d+(?:search|view|fetch)\d+|\bTODO\b|\bTBD\b|\{\{', source))
    views = text(doc.get_element_by_id('our-comments'))
    check(file+':dates_voice_and_four_viewpoints', all(v in views for v in ['2026/09/30', '2026/10/15', '2026/10/16']) and len(doc.get_element_by_id('our-comments').xpath('.//li')) == 4 and {'tc': '我們認為', 'sc': '我们认为', 'en': 'We believe'}[locale] in views)
    financials = doc.get_element_by_id('financials')
    table = financials.xpath('.//table')[0]
    rows = table.xpath('.//tbody/tr')
    check(file+':four_kpis_and_five_row_comparison', len(financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div')) == 4 and len(table.xpath('.//thead/tr/th')) == 4 and len(rows) == 5 and all(len(r.xpath('./td')) == 4 for r in rows))
    table_numbers = [[numbers(text(td)) for td in row.xpath('./td')[1:]] for row in rows]
    TABLES.append(table_numbers)
    # The source is NT$ million. Accept consistently stated million or billion
    # presentation, but never accept an unexplained scale mismatch.
    table_title = text(table.getparent().getparent().xpath('./h3')[0])
    divisor = 1 if re.search(r'百萬|百万|million', table_title, re.I) else 1000
    fields = ['net_revenue', 'gross_profit', 'operating_income', 'net_income_attributable_to_parent', 'eps_diluted_ntd']
    expected = []
    for i, field in enumerate(fields):
        factor = 1 if i == 4 else divisor
        values = [[round(F[field][2]/factor, 2)], [round(F[field][0]/factor, 2)]]
        if i == 1:
            values[0].append(F['gross_margin_pct'][2]); values[1].append(F['gross_margin_pct'][0])
        expected.append(values)
    check(file+':financial_comparison_reconciles_official_values', [r[:2] for r in table_numbers] == expected, {'observed': table_numbers, 'expected_first_two_columns': expected})
    check(file+':financial_yoy_growth_and_margin_changes', len(table_numbers) == 5 and table_numbers[0][2] == [50.9] and set(table_numbers[1][2]) <= {68.6, 6.9} and bool(table_numbers[1][2]) and table_numbers[2][2] == [75.0] and table_numbers[3][2] == [68.7] and table_numbers[4][2] == [68.7])
    check(file+':ordinary_diluted_eps_and_parent_income_labels', bool(re.search(r'diluted|攤薄|摊薄|稀釋|稀释', text(rows[4]), re.I)) and bool(re.search(r'歸母|归母|母公司|attributable|parent', text(rows[3]), re.I)) and bool(re.search(r'TIFRS', text(financials))))
    valuation = text(doc.get_element_by_id('valuation'))
    check(file+':valuation_common_fy2027_and_comparability_limits', all(v in valuation for v in ['2027', 'Adj+', 'Q3', 'Q2']) and bool(re.search(r'四季|four.quarter', valuation, re.I)) and bool(re.search(r'業務|业务|business', valuation, re.I)) and bool(re.search(r'日期|時點|时点|date|timestamp', valuation, re.I)))
    street = doc.get_element_by_id('street-comments')
    cards = street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    card_results = []
    for card, broker in zip(cards, ANR['analysts']):
        body, badge = text(card), card.xpath('.//span')[0]
        ret = round((broker['target_price']/ANR['last_price']-1)*100, 1)
        ok = broker['firm'] in text(card.xpath('.//h3')[0]) and text(badge) == broker['rating_standard'] and COLORS[broker['rating_standard']] in badge.get('class', '')
        ok = ok and broker['target_price'] in numbers(body) and f'{ret:.1f}%' in body and broker['date'].replace('-', '/') in body and broker['analyst'] in body and len(card.xpath('.//li')) == 2
        card_results.append({'firm': broker['firm'], 'ok': ok, 'return_pct': ret})
    check(file+':broker_order_ratings_colors_dates_and_returns', len(cards) == 3 and len(card_results) == 3 and all(c['ok'] for c in card_results), card_results)
    source_lines = [text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
    check(file+':compact_anr_source_no_classification_explanation', len(source_lines) == 1 and all(v in source_lines[0] for v in ['2026/10/16', '10/15', '422.25']) and len(source_lines[0]) < 240 and not re.search(r'統一分類|统一分类|standardized|standardised|site category|display category', text(street), re.I))
    public_doc = copy.deepcopy(doc)
    for e in public_doc.xpath('//script | //style'):
        e.getparent().remove(e)
    public_text = text(public_doc)
    check(file+':no_calculator_attribution_or_unsupported_close_claim', not re.search(r'NTAM\s*(?:計算|计算|calculation|calculated)', public_text, re.I) and not re.search(r'(?:收盤|收盘|closing|close).{0,18}422\.25|422\.25.{0,18}(?:收盤|收盘|closing price)', public_text, re.I))
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
        interaction_reference = mu_result if locale == 'tc' else old_result
        interaction_names = ['switchTab', 'toggleChat', 'appendMessage', 'showTypingIndicator', 'handleChatSubmit', 'closeExplainModal']
        check(file+':retain_fixed_chat_and_chart_behavior', all(normalize_function(result['functions'][n]) == normalize_function(interaction_reference['functions'][n]) for n in interaction_names))
        check(file+':retain_tooltip_viewport_behavior', all([normalize_function(v) for v in result['listeners'][n]] == [normalize_function(v) for v in interaction_reference['listeners'][n]] for n in ['mouseup', 'mousedown']))
        prompt = result['standardPrompt']
        prompt_numbers = set(numbers(prompt))
        check(file+':dated_tsm_ai_currency_basis_and_facts', all(v in prompt for v in ['TSM', '2026/10/16', '2026/09/30', '2026/10/15', 'TIFRS', 'ADR']) and {29.43, 4.6, 422.25, 573.07, 18.74} <= prompt_numbers and bool(re.search(r'ordinary|普通', prompt, re.I)) and not re.search(FORBIDDEN, prompt, re.I))
        check(file+':ai_language_format_and_snapshot_limits', 'markdown' in prompt.lower() and '<b>' in prompt and {'tc': '繁體中文', 'sc': '简体中文', 'en': 'English'}[locale] in prompt and bool(re.search(r'即時|即时|real.time|live market', prompt, re.I)))
        charts = {c['canvasId']: c['config'] for c in result['charts']}
        platform, profit, peer = [charts[c] for c in CANVASES]
        check(file+':platform_mix_chart', platform['type'] == 'doughnut' and platform['data']['datasets'][0]['data'] == [68, 21, 4, 4, 1, 2])
        check(file+':profit_chart_dates_values_and_separate_axes', profit['type'] == 'bar' and profit['data']['labels'] == ['Q3 2025', 'Q2 2026', 'Q3 2026'] and [d['data'] for d in profit['data']['datasets']] == [[F['net_revenue'][i]/1000 for i in [2, 1, 0]], [F['operating_margin_pct'][i] for i in [2, 1, 0]]] and profit['data']['datasets'][1].get('yAxisID') == 'percentageAxis' and profit['options']['scales']['percentageAxis']['position'] == 'right' and profit['options']['scales']['percentageAxis']['max'] == 100, profit['data']['labels'])
        labels = peer['data']['labels']
        check(file+':peer_fy2027_values_order_and_tsm_highlight', peer['type'] == 'bar' and peer['data']['datasets'][0]['data'] == PE and all(re.search(p, labels[i], re.I) for i, p in enumerate(['Samsung|三星', 'TSM', 'SMIC|中芯', 'INTC|Intel|英特爾|英特尔'])) and peer['data']['datasets'][0]['backgroundColor'] == ['rgba(148, 163, 184, 0.6)', 'rgba(37, 99, 235, 0.95)', 'rgba(148, 163, 184, 0.6)', 'rgba(148, 163, 184, 0.6)'])
        check(file+':responsive_chart_configuration', all(c['options'].get('responsive') is True and c['options'].get('maintainAspectRatio') is False for c in charts.values()) and peer['options'].get('indexAxis') == 'y')
        DETAILS[file] = {'sha256': hashlib.sha256((ROOT/file).read_bytes()).hexdigest(), 'mock_charts': result['charts']}
    except Exception as exc:
        check(file+':javascript_parse_and_mock_execution', False, str(exc))

numeric = [[[d['data'] for d in c['config']['data']['datasets']] for c in r['charts']] for r in RUNTIMES.values()]
check('three_languages:financial_table_and_chart_numeric_parity', len(TABLES) == 3 and all(t == TABLES[0] for t in TABLES) and len(numeric) == 3 and all(n == numeric[0] for n in numeric))
check('evidence:quarter_release_dates_and_adr_basis', OFFICIAL['quarter_end'] == '2026-09-30' and OFFICIAL['release_date'] == '2026-10-15' and '1 ADR = 5' in OFFICIAL['calculation_rules']['adr'])
check('evidence:profit_statement_reconciles', all(F['net_revenue'][i]-F['cost_of_revenue'][i] == F['gross_profit'][i] and F['gross_profit'][i]-F['operating_expenses'][i]+F['other_operating_income_expenses'][i] == F['operating_income'][i] for i in range(3)))
check('evidence:cashflow_arithmetic_and_presentation_difference_recorded', all(F['cash_from_operations'][i]-F['capex_cash_acquisition_ppe'][i] == F['fcf_exact_calculated'][i] for i in range(3)) and F['fcf_company_presented_ntd_bn'][0] == 476.56 and F['fcf_exact_calculated'][0] == 476570 and bool(OFFICIAL['caution_discrepancies']))
check('evidence:mix_totals', all(sum(values[i] for values in OFFICIAL['revenue_mix'][key].values()) == 100 for key in ['wafer_revenue_technology_pct', 'net_revenue_platform_pct', 'net_revenue_geography_pct'] for i in range(3)))
check('evidence:target_return_and_broker_selection', round((ANR['target_price_12m']/ANR['last_price']-1)*100, 1) == 35.7 and [b['firm'] for b in ANR['analysts']] == ['HSBC', 'BNP Paribas', 'Barclays'] and ANR['priority_banks_visible'] == ['HSBC'])
tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
protected = [p for p in tracked if p.startswith('api/') or p in ['CNAME', 'disclaimer.html', 'vercel.json', 'package.json', 'package-lock.json', 'mu.html', 'mu-sc.html', 'mu-en.html']]
check('protected:infrastructure_and_mu_files_unchanged', all((ROOT/p).read_text() == oldfile(p) for p in protected), protected)
changed = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
check('scope:only_tsm_and_homepage_html_modified', all(not p.endswith('.html') or p in FILES+['index.html'] for p in changed), changed)
index_source, old_index_source = (ROOT/'index.html').read_text(), oldfile('index.html')
index, old_index = map(html.fromstring, [index_source, old_index_source])
cards = index.xpath('//div[contains(@onclick,"window.location.href=")]')
old_cards = old_index.xpath('//div[contains(@onclick,"window.location.href=")]')
tickers = [text(c.xpath('.//h3')[0]) for c in cards]
old_tickers = [text(c.xpath('.//h3')[0]) for c in old_cards]
check('homepage:tsm_first_other_order_preserved', len(cards) == len(old_cards) == 25 and tickers[0] == 'TSM' and [t for t in tickers if t != 'TSM'] == [t for t in old_tickers if t != 'TSM'], tickers)
tsm_card = text(next(c for c in cards if text(c.xpath('.//h3')[0]) == 'TSM'))
check('homepage:tsm_date_quarter_target', all(v in tsm_card for v in ['2026年10月16日更新', '573.07', '35.7%']) and bool(re.search(r'Q3|第三季', tsm_card)))


def raw_homepage_blocks(source):
    pattern = r'<div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm card-hover flex flex-col h-full cursor-pointer group" onclick="window.location.href=\'([^\']+)\'">'
    starts = list(re.finditer(pattern, source))
    end = source.index('</div>\n</main>', starts[-1].start())
    blocks = {m[1]: source[m.start():starts[i+1].start() if i+1 < len(starts) else end] for i, m in enumerate(starts)}
    return source[:starts[0].start()], blocks, source[end:]


prefix, blocks, suffix = raw_homepage_blocks(index_source)
old_prefix, old_blocks, old_suffix = raw_homepage_blocks(old_index_source)
check('homepage:other_24_cards_and_outer_document_unchanged', len(blocks) == 25 and all(block == old_blocks[name] for name, block in blocks.items() if name != 'tsm.html') and prefix == old_prefix and suffix == old_suffix)
def card_dom_signature(card):
    return [(e.tag, sorted(e.attrib.items()), len([c for c in e if isinstance(c.tag, str)])) for e in card.iter() if isinstance(e.tag, str)]
current_tsm = next(c for c in cards if text(c.xpath('.//h3')[0]) == 'TSM')
prior_tsm = next(c for c in old_cards if text(c.xpath('.//h3')[0]) == 'TSM')
check('homepage:tsm_card_structure_preserved', card_dom_signature(current_tsm) == card_dom_signature(prior_tsm))
whitespace = subprocess.run(['git', '-c', 'core.whitespace=cr-at-eol', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
check('git_diff_whitespace', whitespace.returncode == 0, whitespace.stdout+whitespace.stderr or None)
failed = [r for r in CHECKS if r['status'] == 'fail']
report = {'report': 'TSM Q3 2026 official/Bloomberg evidence and MU-template validation',
          'checked_on': '2026-10-16', 'base_commit': BASE, 'status': 'fail' if failed else 'pass',
          'checks': CHECKS, 'page_details': DETAILS,
          'limitations': ['Fake DOM and Chart constructor only; not real-browser rendering or Chart.js rasterization.',
                          'No PI acceptance, storage write, PI modal removal/hiding, access-control bypass or live AI call.',
                          'Financial fact transcription and primary-source provenance are recorded separately in the source ledger.',
                          'EEO snapshot forecast cutoff is unknown; estimates are not verified prerelease consensus.',
                          'ANR 2026/10/16 shows 10/15 quote US$422.25; not independently established here as an official closing price.',
                          'Screen-visible broker coverage is incomplete; HSBC/BNP/Barclays use readable evidence only.',
                          'Quarterly exact financial-statement FCF differs from company summary presentation by NT$0.010bn.',
                          'Desktop/mobile browser review and production HTTP comparison, if completed, are recorded separately.']}
destination = ROOT/'research/tsm-2026-q3-validation.json'
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'status': report['status'], 'checks': len(CHECKS), 'failed': failed, 'output': str(destination)}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failed))

