#!/usr/bin/env python3
"""Recheck the NVDA Q2 FY27 update without network calls or PI acceptance.

Run from any directory. Requires Python lxml and Node (or
CODEX_PRIMARY_RUNTIME_NODE). The isolated VM is a mocked functional check,
not a browser/rendering test. It never accepts or hides the PI gate.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from html.parser import HTMLParser
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
LEDGER = json.loads((ROOT / 'research/nvda-fy2027-q2-2026-10-08.json').read_text())
BASE = LEDGER['source_version_base_commit']
PAGES = ['nvda.html', 'nvda-sc.html', 'nvda-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'sandbox', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
CHECKS = []
DETAILS = {}


def check(name, ok, detail=None):
    row = {'check': name, 'status': 'pass' if ok else 'fail'}
    if detail is not None:
        row['detail'] = detail
    CHECKS.append(row)


def original(name):
    return subprocess.check_output(['git', 'show', f'{BASE}:{name}'], cwd=ROOT, text=True)


def text_of(element):
    return ' '.join(element.text_content().split())


def scripts(source):
    return re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>', source)


def normalize_js(source):
    # Only chart label/data literals and the dated company context may change.
    marker = source.find("fetch('disclaimer.html')")
    before, after = (source[:marker], source[marker:]) if marker >= 0 else (source, '')
    before = re.sub(r'\b(labels|data):\s*\[[^\]]*\]', r'\1: [REPLACEABLE]', before)
    before = re.sub(r"\blabel:\s*'[^']*'", "label: 'REPLACEABLE'", before)
    result = before + after
    result = re.sub(r'const (standardPrompt|sysPrompt) = `[\s\S]*?`;', r'const \1 = `REPLACEABLE`;', result)
    # The explain-term first argument is company context; its output-language
    # instruction (second argument) must remain byte-for-byte unchanged.
    result = re.sub(r'(await callGeminiAPI\()`[^`]*\$\{selectedText\}[^`]*`', r'\1`REPLACEABLE`', result)
    return result


class RawTags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        # This is the only authorized attribute-content replacement.
        if dict(attrs).get('id') == 'custom-scenario-input':
            raw = re.sub(r'placeholder="[^"]*"', 'placeholder="REPLACEABLE"', raw)
        if tag == 'span' and 'text-xs font-bold px-2 py-1 rounded' in dict(attrs).get('class', ''):
            raw = re.sub(r'(?:bg-(?:blue|emerald|slate|pink|red)-100|text-(?:blue-800|emerald-800|slate-600|pink-700|red-600))', 'RATING_COLOR', raw)
        self.tags.append(raw)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        self.tags.append(f'</{tag}>')


def tag_signature(source, remove_source_line=False):
    if remove_source_line:
        source = re.sub(r'<p\b[^>]*>[^<]*Bloomberg ANR[^<]*</p>', '', source)
    parser = RawTags()
    parser.feed(source)
    return parser.tags


HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const events = {}, elements = [], ids = {}, charts = [], fetches = [];
let storageWrites = 0;
function element(record) {
  const classes = new Set((record.class || '').split(/\s+/).filter(Boolean));
  const item = {id: record.id || '', tagName:record.tag, style:{}, innerHTML:'',
    classList:{add(...c){c.forEach(x=>classes.add(x))}, remove(...c){c.forEach(x=>classes.delete(x))},
      contains(c){return classes.has(c)}, toggle(c){classes.has(c)?classes.delete(c):classes.add(c)}},
    getContext(type){if(type!=='2d') throw Error('Unknown canvas context'); return {canvasId:this.id}},
    get classes(){return Array.from(classes)},
  };
  elements.push(item); if(item.id) ids[item.id]=item; return item;
}
input.elements.forEach(element);
const body = {style:{}};
const document = {
  body,
  addEventListener(name, fn){(events[name] ||= []).push(fn)},
  getElementById(id){if(!ids[id]) throw Error('Unknown DOM ID '+id); return ids[id]},
  querySelectorAll(selector){
    if(!['.tab-content','.tab-btn'].includes(selector)) throw Error('Unmocked selector '+selector);
    return elements.filter(e=>e.classList.contains(selector.slice(1)));
  }
};
const sandbox = {document, console, sessionStorage:{getItem(){return null},setItem(){storageWrites++;throw Error('PI acceptance forbidden')}},
  window:{}, alert(){throw Error('Unexpected alert')},
  Chart:function(context,config){charts.push({canvasId:context.canvasId,config})},
  fetch:async function(url){fetches.push(url);if(url!=='disclaimer.html')throw Error('Network/API call forbidden');return {ok:true,text:async()=>input.disclaimer}},
};
const context=vm.createContext(sandbox);
(async()=>{
  for(let i=0;i<input.scripts.length;i++)new vm.Script(input.scripts[i],{filename:input.file+':inline-'+i}).runInContext(context);
  for(const fn of events.DOMContentLoaded||[]) fn();
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate not active');
  const tabResults=[]; const buttons=elements.filter(e=>e.classList.contains('tab-btn'));
  for(let i=0;i<input.tabs.length;i++){
    // Exercise pure function only in fake DOM; gate remains active throughout.
    context.switchTab({currentTarget:buttons[i]},input.tabs[i]);
    const active=elements.filter(e=>e.classList.contains('tab-content')&&e.classList.contains('active')).map(e=>e.id);
    const activeButtons=buttons.filter(e=>e.classList.contains('active'));
    tabResults.push({tab:input.tabs[i],ok:active.length===1&&active[0]===input.tabs[i]&&activeButtons.length===1&&activeButtons[0]===buttons[i]});
    if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('Gate changed during unit check');
  }
  const standardPrompt = vm.runInContext('standardPrompt',context);
  process.stdout.write(JSON.stringify({charts,tabResults,fetches,storageWrites,piVisible:ids['pi-modal'].style.display==='flex',
    bodyLocked:body.style.overflow==='hidden',disclaimerLoaded:ids['disclaimer-container'].innerHTML===input.disclaimer,standardPrompt}));
})().catch(e=>{console.error(e.stack);process.exit(1)});
"""


def runtime(file, doc, source):
    payload = {'file': file, 'scripts': scripts(source), 'tabs': TABS,
               'elements': [{'tag': e.tag, **dict(e.attrib)} for e in doc.iter() if isinstance(e.tag, str)],
               'disclaimer': (ROOT / 'disclaimer.html').read_text()}
    result = subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_NODE', 'node'), '-e', HARNESS], input=json.dumps(payload),
                            capture_output=True, text=True, cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


docs, runtimes = {}, {}
for file in PAGES:
    source, old = (ROOT / file).read_text(), original(file)
    doc, olddoc = html.fromstring(source), html.fromstring(old)
    docs[file] = doc
    check(file + ':raw_tags_attributes_preserved', tag_signature(source, True) == tag_signature(old),
          'Only rating color tokens, scenario placeholder, and one compact ANR source paragraph are allowed.')
    check(file + ':styles_exact', doc.xpath('//style/text()') == olddoc.xpath('//style/text()'))
    check(file + ':legal_gate_exact', source[source.index('    <div id="pi-modal"'):source.index('    <header')] ==
          old[old.index('    <div id="pi-modal"'):old.index('    <header')])
    check(file + ':fixed_js_exact', [normalize_js(s) for s in scripts(source)] == [normalize_js(s) for s in scripts(old)])
    old_standard = re.search(r'const standardPrompt = `([\s\S]*?)`;', old).group(1)
    new_standard = re.search(r'const standardPrompt = `([\s\S]*?)`;', source).group(1)
    old_sandbox = re.search(r'const sysPrompt = `([\s\S]*?)`;', old).group(1)
    new_sandbox = re.search(r'const sysPrompt = `([\s\S]*?)`;', source).group(1)
    format_start = {'nvda.html':'請用客觀','nvda-sc.html':'请用客观','nvda-en.html':'Please answer objectively'}[file]
    check(file + ':ai_output_language_and_format_preserved',
          new_standard.endswith(old_standard[old_standard.index(format_start):]) and
          new_sandbox.endswith(old_sandbox[old_sandbox.index('\n'):]))
    check(file + ':seven_tabs_order', doc.xpath('//section/@id') == TABS and
          doc.xpath('//nav/button/@onclick') == [f"switchTab(event, '{tab}')" for tab in TABS])
    check(file + ':canvases_exact', doc.xpath('//canvas/@id') == CANVASES)
    check(file + ':language_links', set(doc.xpath('//select/option/@value')) == set(PAGES))
    ids = doc.xpath('//@id')
    check(file + ':unique_ids', len(ids) == len(set(ids)))
    check(file + ':target_consensus', f"{LEDGER['bloomberg_anr']['consensus_target']:.2f}" in text_of(doc.xpath('//header')[0]))
    street = doc.get_element_by_id('street-comments')
    cards = street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    brokers = LEDGER['bloomberg_anr']['brokers']
    check(file + ':three_broker_cards', len(cards) == 3)
    broker_details = []
    for card, broker in zip(cards, brokers):
        rating = card.xpath('.//span')[0]
        color = 'bg-blue-100 text-blue-800' if broker['display_rating'] == 'Overweight' else 'bg-emerald-100 text-emerald-800'
        body = text_of(card)
        implied = (broker['target_usd'] / LEDGER['bloomberg_anr']['reference_price'] - 1) * 100
        ok = (text_of(card.xpath('.//h3')[0]) == broker['firm'] and text_of(rating) == broker['display_rating'] and
              color in rating.get('class') and broker['analyst'] in body and str(broker['target_usd']) in body and
              f'{implied:.1f}%' in body and broker['rating_date'].replace('-', '/') in body)
        broker_details.append({'firm':broker['firm'],'ok':ok,'price_return_percent':round(implied,1)})
    check(file + ':broker_facts_colors_returns', all(r['ok'] for r in broker_details), broker_details)
    source_lines = [text_of(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text_of(p)]
    check(file + ':one_compact_anr_source', len(source_lines) == 1 and all(v in source_lines[0] for v in ['2026/10/08','10/07','237.47']), source_lines)
    try:
        result = runtime(file, doc, source)
        runtimes[file] = result
        check(file + ':inline_js_syntax_and_mock_execution', True)
        check(file + ':mock_tabs', all(row['ok'] for row in result['tabResults']))
        check(file + ':mock_disclaimer', result['fetches'] == ['disclaimer.html'] and result['disclaimerLoaded'])
        check(file + ':pi_never_accepted_or_hidden', result['storageWrites'] == 0 and result['piVisible'] and result['bodyLocked'])
        check(file + ':dated_ai_context', '2026/10/08' in result['standardPrompt'] or '2026-10-08' in result['standardPrompt'])
        DETAILS[file] = {'sha256':hashlib.sha256(source.encode()).hexdigest(), 'mock_runtime':result}
    except Exception as exc:
        check(file + ':inline_js_syntax_and_mock_execution', False, str(exc))

official = LEDGER['official_company_evidence']
fin = official['financials_comparable']
platforms = fin['market_platforms']
check('ledger:revenue_platform_reconciliation', all(platforms['data_center'][i]+platforms['edge_computing'][i] == fin['revenue'][i] and
      platforms['hyperscale'][i]+platforms['ai_clouds_industrial_enterprise'][i] == platforms['data_center'][i] for i in range(3)))
check('ledger:company_fcf_reconciliation', all(fin['operating_cash_flow'][i]-fin['capex_equipment_intangibles'][i]-
      fin['principal_payments_equipment_intangibles'][i] == fin['free_cash_flow'][i] for i in range(3)))
peer_order = ['INTC','AMD','AVGO','NVDA']
expected = {
    'segmentRevenueChart':[platforms['data_center'][0]/1000,platforms['edge_computing'][0]/1000],
    'profitabilityChart':[round(fin['revenue'][0]/1000,2),round(fin['gaap_operating_income'][0]/1000,2),round(fin['non_gaap_net_income'][0]/1000,2)],
    'valuationChart':[LEDGER['bloomberg_eeo']['peers'][ticker]['forward_pe_adj'] for ticker in peer_order],
}
for file,result in runtimes.items():
    actual = {c['canvasId']: c['config']['data']['datasets'][0]['data'] for c in result['charts']}
    exact_profit = [fin['revenue'][0]/1000,fin['gaap_operating_income'][0]/1000,fin['non_gaap_net_income'][0]/1000]
    matches = (actual.get('segmentRevenueChart') == expected['segmentRevenueChart'] and
               actual.get('valuationChart') == expected['valuationChart'] and
               actual.get('profitabilityChart') in [expected['profitabilityChart'], exact_profit])
    check(file + ':chart_data_matches_evidence', matches, {'actual':actual,'expected':expected,'exact_profit_alternative':exact_profit})
check('three_languages:chart_numeric_parity', len(runtimes)==3 and len({json.dumps([c['config']['data']['datasets'][0]['data'] for c in v['charts']]) for v in runtimes.values()})==1)
table_numbers=[]
for file,doc in docs.items():
    table=doc.get_element_by_id('financials').xpath('.//table')[0]
    numbers=re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?%?',text_of(table))
    table_numbers.append(numbers)
    expected_rows = [platforms['data_center'],platforms['hyperscale'],platforms['ai_clouds_industrial_enterprise'],platforms['edge_computing'],fin['revenue']]
    row_checks=[]
    for row,amounts in zip(table.xpath('.//tbody/tr'),expected_rows):
        cells=row.xpath('./td')
        amount=float(re.sub(r'[^0-9.]','',text_of(cells[1])))
        growth=float(re.sub(r'[^0-9.+-]','',text_of(cells[2])))
        exact=(amounts[0]/amounts[2]-1)*100
        row_checks.append(amount==amounts[0] and growth in [round(exact),round(exact,1)])
    check(file + ':platform_table_matches_company', len(row_checks)==5 and all(row_checks))
check('three_languages:financial_table_numeric_parity', all(n == table_numbers[0] for n in table_numbers))

order = json.loads((ROOT / 'research/homepage-earnings-order-2026-10-08.json').read_text())['records']
homepage = html.fromstring((ROOT/'index.html').read_text())
oldhome = html.fromstring(original('index.html'))
known = {r['file'] for r in order}
def card_file(element):
    match = re.fullmatch(r"window.location.href='([^']+)'", element.get('onclick', ''))
    return match.group(1) if match else None
cards = [a for a in homepage.xpath('//div[@onclick]') if card_file(a) in known]
oldcards = {card_file(a):a for a in oldhome.xpath('//div[@onclick]') if card_file(a) in known}
check('homepage:all_25_cards_once', len(cards)==25 and len({card_file(a) for a in cards})==25)
check('homepage:descending_earnings_date', [card_file(a) for a in cards]==[r['file'] for r in order] and
      order==sorted(order,key=lambda r:(-int(r['earnings_publication_date'].replace('-','')),r['prior_position'])))
check('homepage:other_24_cards_exact', all(html.tostring(a)==html.tostring(oldcards[card_file(a)]) for a in cards if card_file(a)!='nvda.html'))
nvda_card = next(a for a in cards if card_file(a)=='nvda.html')
check('homepage:nvda_quarter_and_edit_date', 'Q2' in text_of(nvda_card) and '2026年10月8日更新' in text_of(nvda_card))
protected = ['CNAME','disclaimer.html','api/gemini.js','vercel.json','package.json']
present = [p for p in protected if (ROOT/p).exists()]
check('protected_files_unchanged', all((ROOT/p).read_text()==original(p) for p in present), present)
changed = subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
check('no_other_company_pages_changed', not any(p.endswith('.html') and p not in PAGES+['index.html'] for p in changed), changed)

report = {
    'report':'NVIDIA FY2027 Q2 update', 'checked_on':'2026-10-08', 'base_commit':BASE,
    'status':'pass' if all(c['status']=='pass' for c in CHECKS) else 'fail',
    'method':'Static raw-template comparison, source-ledger arithmetic, and isolated Node VM with fake DOM/Chart/fetch. No network requests.',
    'checks':CHECKS, 'page_details':DETAILS,
    'limitations':[
        'This is not a real-browser rendering verification; desktop/mobile layout has not been claimed as visually checked.',
        'No live AI request, PI acceptance, PI storage mutation, gate hiding, or access-control bypass was performed.',
        'Source authenticity and visual screenshot transcription rely on the separately documented primary-source and Bloomberg evidence review.',
        'The pre-existing switchTab function has no explicit chart resize calls or stored chart instances; preserved unchanged. Charts use responsive:true.',
        'The existing AI response formatter and API behavior remain unchanged; runtime tests intentionally do not call the API.'
    ]
}
destination = ROOT/'research/nvda-fy2027-q2-validation.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
failed = [c for c in CHECKS if c['status']=='fail']
print(json.dumps({'status':report['status'],'checks':len(CHECKS),'failed':failed,'output':str(destination)},ensure_ascii=False,indent=2))
raise SystemExit(bool(failed))
