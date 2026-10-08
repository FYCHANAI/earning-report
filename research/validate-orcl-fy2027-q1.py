#!/usr/bin/env python3
"""Reconcile the ORCL FY2027 Q1 update to its evidence and MU template.

The Node VM uses a fake DOM and Chart constructor. It never accepts/removes
the PI gate, writes PI storage, or calls a live API. Browser review is separate.
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
BASE = '4898eb467ed00c049cde0e25bb11bb7b1a22b575'
LEDGER = json.loads((ROOT/'research/orcl-fy2027-q1-2026-10-08.json').read_text())
OFFICIAL = LEDGER['official_company_evidence']
F = OFFICIAL['q1_comparison']
B = OFFICIAL['business_mix']
C = OFFICIAL['cashflow']
ANR = LEDGER['bloomberg_orcl']['ANR']
PEERS = LEDGER['bloomberg_peers']['companies']
FILES = ['orcl.html', 'orcl-sc.html', 'orcl-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
KEYS = ['orclSegment', 'orclProfit', 'orclValuation']
CHECKS, DETAILS, RUNTIMES = [], {}, {}


def check(name, ok, detail=None):
    row = {'check': name, 'status': 'pass' if ok else 'fail'}
    if detail is not None:
        row['detail'] = detail
    CHECKS.append(row)


def oldfile(file):
    return subprocess.check_output(['git', 'show', f'{BASE}:{file}'], cwd=ROOT, text=True)


def text(element):
    return ' '.join(element.text_content().split())


def scripts(source):
    return re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', source)


def numbers(value):
    value = value.replace('−', '-').replace('–', '-')
    value = re.sub(r'-\s*((?:US)?\$)', r'\1-', value)
    return [float(n.replace(',', '')) for n in re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?', value)]


def normalize_function(value):
    return re.sub(r'\s+', '', value).replace('muSegment', 'orclSegment').replace('muProfit', 'orclProfit').replace('muValuation', 'orclValuation')


def signature(doc):
    """Compare MU layout; permit documented source anchors and loss colors.

    Table metric names and text do not enter this signature. All five rows,
    columns, element nesting and layout classes still have to match MU.
    Original ORCL PI/disclaimer DOM is checked separately against the base.
    """
    doc = copy.deepcopy(doc)
    for element in doc.xpath('//script | //*[@id="pi-modal"] | //*[@id="disclaimer"]'):
        element.getparent().remove(element)
    for element in doc.xpath('//section[@id="financials"]//a'):
        element.drop_tag()
    records = []
    for element in doc.iter():
        if not isinstance(element.tag, str):
            continue
        attrs = dict(element.attrib)
        if element.tag == 'option':
            attrs['value'] = attrs.get('value', '').replace('mu', 'orcl')
        if 'class' in attrs:
            # A negative FCF has the same typography but a loss color.
            attrs['class'] = re.sub(r'text-(?:emerald|rose)-([56]00)', r'text-SIGN-\1', attrs['class'])
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
 const functions={};for(const name of ['switchTab','acceptPI','declinePI','callGeminiAPI','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','explainSelectedTerm','closeExplainModal']){
  functions[name]=context[name].toString();
 }
 if(input.functionsOnly){process.stdout.write(JSON.stringify({functions}));return;}
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
  standardPrompt:vm.runInContext('standardPrompt',context),functions}));
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


def disclaimer_loader(source):
    return re.search(r"fetch\('disclaimer.html'\)[\s\S]*?\n\s*\}\);", source).group(0)


expected_rows = [
    [[F['revenue'][0]], [F['revenue'][0]], [30]],
    [[F['gaap_operating_income'][0], 34.8], [F['non_gaap_operating_income'][0], 42.1], [31, 35]],
    [[F['gaap_net_income_available_to_common'][0]], [F['non_gaap_net_income_available_to_common'][0]], [60, 34]],
    [[F['gaap_diluted_eps'][0]], [F['non_gaap_diluted_eps'][0]], [55, 30]],
    [[C['operating_cashflow'][0]], [C['free_cashflow'][0]], [C['capital_expenditures_cash_outflow'][0]]],
]

for file in FILES:
    source = (ROOT/file).read_text()
    template_name = file.replace('orcl', 'mu')
    template = (ROOT/template_name).read_text()
    prior = oldfile(file)
    doc, mu, old = map(html.fromstring, [source, template, prior])
    check(file+':mu_structure_and_layout_attributes', signature(doc) == signature(mu))
    check(file+':mu_styles_fonts_and_script_versions', doc.xpath('//style/text()') == mu.xpath('//style/text()') and
          doc.xpath('//head/link/@href') == mu.xpath('//head/link/@href') and doc.xpath('//script/@src') == mu.xpath('//script/@src'))
    check(file+':six_tabs', doc.xpath('//section/@id') == TABS and doc.xpath('//nav/button/@onclick') == [f"switchTab(event, '{tab}')" for tab in TABS])
    check(file+':no_obsolete_sandbox', not re.search(r'sandbox|generateCustomScenario|custom-scenario|scenario-loading|scenario-result', source, re.I))
    check(file+':three_chart_containers', doc.xpath('//canvas/@id') == CANVASES and len(doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," chart-container ")]')) == 3)
    ids = doc.xpath('//@id')
    check(file+':unique_ids', len(ids) == len(set(ids)))
    check(file+':language_links', set(doc.xpath('//select/option/@value')) == set(FILES))
    for protected_id in ['pi-modal', 'disclaimer']:
        check(file+':original_'+protected_id+'_dom_exact', html.tostring(doc.get_element_by_id(protected_id), with_tail=False) == html.tostring(old.get_element_by_id(protected_id), with_tail=False))
    check(file+':original_disclaimer_loader_exact', disclaimer_loader(source) == disclaimer_loader(prior))
    check(file+':company_heading', ('Oracle' if file.endswith('-en.html') else '甲骨文') in text(doc.xpath('//h1')[0]) and 'ORCL' in text(doc.xpath('//h1')[0]))
    header = text(doc.xpath('//header')[0])
    consensus_word = 'Buy' if file.endswith('-en.html') else '买入' if file.endswith('-sc.html') else '買入'
    check(file+':header_consensus', all(v in header for v in ['240.01', 'ORCL', consensus_word]))
    forbidden = r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|SCAs|1-gamma|G9 NAND|Kioxia|SK Hynix|Samsung|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|33\.42|201\.58|169\.78'
    remnants = re.findall(forbidden, source, re.I)
    check(file+':no_micron_or_prior_target_remnants', not remnants, remnants)
    check(file+':no_citation_placeholders', not re.search(r'||\bturn\d+(?:search|view|fetch)\d+|\bTODO\b|\bTBD\b|\{\{', source))
    views = text(doc.get_element_by_id('our-comments'))
    check(file+':period_publication_and_update_dates', all(v in views for v in ['2026/08/31', '2026/09/10', '2026/10/08']))
    check(file+':our_views_voice', ('We believe' if file.endswith('-en.html') else '我们认为' if file.endswith('-sc.html') else '我們認為') in views and not re.search(r'NTAM\s*(?:認為|认为|believes)', views, re.I))
    public_doc = copy.deepcopy(doc)
    for element in public_doc.xpath('//script | //style'):
        element.getparent().remove(element)
    check(file+':no_unverified_oct7_price_date_in_public_copy', not re.search(r'10/07|2026-10-07|Oct(?:ober)?\.?\s+7', text(public_doc), re.I))
    table = doc.get_element_by_id('financials').xpath('.//table')[0]
    rows = table.xpath('.//tbody/tr')
    check(file+':four_column_five_row_table', len(table.xpath('.//thead/tr/th')) == 4 and len(rows) == 5 and all(len(row.xpath('./td')) == 4 for row in rows))
    observed_rows = [[numbers(text(td)) for td in row.xpath('./td')[1:]] for row in rows]
    check(file+':financial_table_matches_official_bases', observed_rows == expected_rows, {'observed': observed_rows, 'expected': expected_rows})
    check(file+':net_income_row_is_common_shareholder_basis', len(rows) >= 3 and bool(re.search(r'common|普通股', text(rows[2]), re.I)))
    cashflow_cells = [text(td) for td in rows[4].xpath('./td')] if len(rows) >= 5 else []
    check(file+':cashflow_row_separates_ocf_fcf', len(cashflow_cells) == 4 and
          bool(re.search(r'OCF|Operating cash flow|營運現金流|营运现金流|运营现金流', cashflow_cells[1], re.I)) and
          bool(re.search(r'FCF|Free cash flow|自由現金流|自由现金流', cashflow_cells[2], re.I)))
    source_links = doc.get_element_by_id('financials').xpath('.//a/@href')
    check(file+':financial_primary_source_links', set(source_links) == {OFFICIAL['q1_comparison']['source'], OFFICIAL['business_mix']['source']} and len(source_links) == 2, source_links)
    valuation_text = text(doc.get_element_by_id('valuation'))
    check(file+':peer_basis_limitations', all(v in valuation_text for v in ['Adj+', 'GAAP+', 'AMZN']) and bool(re.search(r'不同|差異|差异|differ|not.*(?:like|compar)', valuation_text, re.I)))
    street = doc.get_element_by_id('street-comments')
    cards = street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    broker_checks = []
    colors = {'Overweight': 'bg-blue-100 text-blue-800', 'Buy': 'bg-emerald-100 text-emerald-800', 'Neutral': 'bg-slate-100 text-slate-600'}
    for card, broker in zip(cards, ANR['selected_brokers_in_user_priority_order']):
        badge = card.xpath('.//span')[0]
        body = text(card)
        ret = (broker['target_usd']/ANR['last_price_usd']-1)*100
        ok = broker['firm'] in text(card.xpath('.//h3')[0]) and text(badge) == broker['display_rating'] and colors[broker['display_rating']] in badge.get('class')
        ok = ok and all(v in body for v in [broker['analyst'], f"{broker['target_usd']:.2f}", broker['rating_date'].replace('-', '/'), f'{ret:.1f}%'])
        broker_checks.append({'firm': broker['firm'], 'ok': ok, 'return_percent': round(ret, 1)})
    check(file+':brokers_priority_targets_dates_returns_colors', len(cards) == 3 and len(broker_checks) == 3 and all(b['ok'] for b in broker_checks), broker_checks)
    sourcelines = [text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
    check(file+':compact_anr_reference_source', len(sourcelines) == 1 and all(v in sourcelines[0] for v in ['2026/10/08', '143.56']) and len(sourcelines[0]) < 220, sourcelines)
    check(file+':no_public_calculator_attribution', not re.search(r'NTAM\s*(?:計算|计算|calculation|calculated)', text(doc), re.I))
    try:
        result = run_vm(file, source, doc)
        mu_result = run_vm(template_name, template, mu)
        prior_result = run_vm(file+':base', prior, old, functions_only=True)
        RUNTIMES[file] = result
        check(file+':inline_js_syntax_and_mock_execution', True)
        check(file+':chart_cache_keys', result['keys'] == KEYS, result['keys'])
        check(file+':tabs_and_chart_resize', all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']] == [1, 1, 1])
        check(file+':pi_active_no_acceptance_or_storage_write', result['storageWrites'] == 0 and result['piVisible'] and result['bodyLocked'])
        check(file+':original_pi_and_api_functions', all(normalize_function(result['functions'][name]) == normalize_function(prior_result['functions'][name]) for name in ['acceptPI', 'declinePI', 'callGeminiAPI']))
        check(file+':disclaimer_local_mock_no_api_network', result['fetches'] == ['disclaimer.html'] and result['disclaimerLoaded'])
        interactions = ['switchTab', 'toggleChat', 'appendMessage', 'showTypingIndicator', 'handleChatSubmit', 'closeExplainModal']
        check(file+':mu_fixed_interaction_functions', all(normalize_function(result['functions'][name]) == normalize_function(mu_result['functions'][name]) for name in interactions))
        def explain_skeleton(value):
            return normalize_function(re.sub(r'await callGeminiAPI\([\s\S]*?\);', 'await COMPANY_EXPLANATION;', value))
        check(file+':mu_explain_interaction', explain_skeleton(result['functions']['explainSelectedTerm']) == explain_skeleton(mu_result['functions']['explainSelectedTerm']))
        prompt = result['standardPrompt']
        check(file+':dated_orcl_ai_evidence_context', all(v in prompt for v in ['ORCL', '2026/10/08', '2026/08/31', '2026/09/10', '4679', '5758', '143.56', '240.01', '16.75']) and not re.search(forbidden, prompt, re.I))
        configs = {c['canvasId']: c['config'] for c in result['charts']}
        segment, profit, valuation = [configs[canvas] for canvas in CANVASES]
        check(file+':revenue_mix_reconciles', segment['type'] == 'doughnut' and segment['data']['datasets'][0]['data'] == [B['total_cloud'][0], B['total_software'][0], B['hardware'][0], B['services'][0]] and sum(segment['data']['datasets'][0]['data']) == F['revenue'][0])
        profit_data = [dataset['data'] for dataset in profit['data']['datasets']]
        check(file+':profit_chart_common_income_and_operating_income', profit['type'] == 'bar' and profit_data == [[F['gaap_operating_income'][0], F['gaap_net_income_available_to_common'][0]], [F['non_gaap_operating_income'][0], F['non_gaap_net_income_available_to_common'][0]]] and 'percentageAxis' not in json.dumps(profit))
        check(file+':profit_chart_common_income_label', bool(re.search(r'common|普通股', ' '.join(profit['data']['labels']), re.I)))
        labels, values = valuation['data']['labels'], valuation['data']['datasets'][0]['data']
        tickers = [next((ticker for ticker in ['CRM', 'MSFT', 'ORCL', 'AMZN'] if ticker in label), 'UNKNOWN') for label in labels]
        check(file+':peer_pe_values_and_order', tickers == ['CRM', 'MSFT', 'ORCL', 'AMZN'] and dict(zip(tickers, values)) == {peer['ticker']: peer['next4_pe'] for peer in PEERS})
        check(file+':chart_responsive_and_no_hidden_unit_conflict', all(c['options'].get('responsive') is True and c['options'].get('maintainAspectRatio') is False for c in configs.values()) and valuation['options'].get('indexAxis') == 'y')
        DETAILS[file] = {'sha256': hashlib.sha256(source.encode()).hexdigest(), 'mock_runtime': result}
    except Exception as exc:
        check(file+':inline_js_syntax_and_mock_execution', False, str(exc))

numeric = [[[d['data'] for d in c['config']['data']['datasets']] for c in result['charts']] for result in RUNTIMES.values()]
check('three_languages:chart_numeric_parity', len(numeric) == 3 and all(value == numeric[0] for value in numeric))
styles = [[[{k: v for k, v in d.items() if k != 'label'} for d in c['config']['data']['datasets']] for c in result['charts']] for result in RUNTIMES.values()]
check('three_languages:chart_dataset_style_parity', len(styles) == 3 and all(value == styles[0] for value in styles))
check('evidence:financial_reconciliation', B['cloud_iaas'][0]+B['cloud_saas'][0] == B['total_cloud'][0] and C['operating_cashflow'][0]-C['capital_expenditures_cash_outflow'][0] == C['free_cashflow'][0] and F['gaap_net_income'][0]-F['preferred_stock_dividends'][0] == F['gaap_net_income_available_to_common'][0] and F['non_gaap_net_income'][0]-F['preferred_stock_dividends'][0] == F['non_gaap_net_income_available_to_common'][0])
check('evidence:consensus_return', round((ANR['12M_target_usd']/ANR['last_price_usd']-1)*100, 1) == LEDGER['calculations']['consensus_price_return_pct'] == 67.2)
for row in LEDGER['canonical_templates']:
    check('canonical_template:'+row['path'], hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest() == row['sha256'] and (ROOT/row['path']).read_text() == oldfile(row['path']))
check('protected_files:ledger_hashes_and_base', all(hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == digest and (ROOT/file).read_text() == oldfile(file) for file, digest in LEDGER['protected_files'].items()))
tracked = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
infrastructure = [file for file in tracked if file.startswith('api/') or file in ['CNAME', 'disclaimer.html', 'vercel.json', 'package.json', 'package-lock.json']]
check('protected_files:infrastructure_exact', all((ROOT/file).read_text() == oldfile(file) for file in infrastructure), infrastructure)
index, old_index = map(html.fromstring, [(ROOT/'index.html').read_text(), oldfile('index.html')])
def homepage_cards(doc):
    return doc.xpath('//div[contains(@onclick,"window.location.href=")]')
cards, old_cards = homepage_cards(index), homepage_cards(old_index)
def card_ticker(card):
    return text(card.xpath('.//h3')[0])
order, old_order = list(map(card_ticker, cards)), list(map(card_ticker, old_cards))
check('homepage:orcl_second_25_cards_others_same_order', len(cards) == 25 and order[1] == 'ORCL' and [ticker for ticker in order if ticker != 'ORCL'] == [ticker for ticker in old_order if ticker != 'ORCL'], order)
old_by_ticker = {card_ticker(card): html.tostring(card, with_tail=False) for card in old_cards}
check('homepage:other_24_card_contents_exact', all(html.tostring(card, with_tail=False) == old_by_ticker[card_ticker(card)] for card in cards if card_ticker(card) != 'ORCL'))
orcl_card = text(next(card for card in cards if card_ticker(card) == 'ORCL'))
check('homepage:orcl_updated_facts', all(value in orcl_card for value in ['2026年10月8日更新', '19.345', '30%', '1.92', '664', '240.01', '143.56', '67.2%']))
ordering = json.loads((ROOT/'research/homepage-earnings-order-2026-10-08.json').read_text())
ordered_records = sorted(ordering['records'], key=lambda row: row['position'])
dates = [row['earnings_publication_date'] for row in ordered_records]
check('homepage:ledger_matches_actual_earnings_order', [row['ticker'] for row in ordered_records] == order and dates == sorted(dates, reverse=True) and ordered_records[1]['earnings_publication_date'] == '2026-09-10')
changed = subprocess.check_output(['git', 'diff', '--name-only', BASE], cwd=ROOT, text=True).splitlines()
check('scope:only_orcl_and_homepage_html', all(not file.endswith('.html') or file in FILES+['index.html'] for file in changed), changed)
whitespace = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
check('git_diff_whitespace', whitespace.returncode == 0, whitespace.stdout+whitespace.stderr)
report = {'report': 'ORCL FY2027 Q1 evidence and MU-template validation', 'checked_on': '2026-10-08', 'base_commit': BASE,
          'status': 'pass' if all(row['status'] == 'pass' for row in CHECKS) else 'fail', 'checks': CHECKS, 'page_details': DETAILS,
          'limitations': ['Mock VM checks are not real-browser rendering or live Chart.js rasterization.',
                         'No live AI call, PI acceptance, PI storage write, modal removal/hiding or access-control bypass was performed.',
                         'Authoritative-source and screenshot review is recorded in the evidence ledger; this script reconciles the implementation to that evidence.',
                         'The ANR screenshot confirms the 2026/10/08 snapshot and US$143.56 reference price, but not a separate 10/07 closing-price date.',
                         'Desktop/mobile visual review and deployed HTTP content verification are separately performed by the release workflow.']}
destination = ROOT/'research/orcl-fy2027-q1-validation.json'
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
failed = [row for row in CHECKS if row['status'] == 'fail']
print(json.dumps({'status': report['status'], 'checks': len(CHECKS), 'failed': failed, 'output': str(destination)}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failed))
