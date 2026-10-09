#!/usr/bin/env python3
"""Reconcile the NIO Q2 2026 update to its evidence and MU template.

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
BASE = '75bd3a4b5d38688e71fef0a08d899357eed4d126'
LEDGER = json.loads((ROOT/'research/nio-2026-q2-2026-10-09.json').read_text())
OFFICIAL = LEDGER['official_company_evidence']
F = OFFICIAL['quarterly']['Q2 2026']
BLOOMBERG = LEDGER['bloomberg_nio']
ANR = BLOOMBERG['anr']
FILES = ['nio.html', 'nio-sc.html', 'nio-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
KEYS = ['nioSegment', 'nioProfit', 'nioValuation']
CHECKS, DETAILS, RUNTIMES = [], {}, {}


def check(name, ok, detail=None):
    row = {'check': name, 'status': 'pass' if ok else 'fail'}
    if detail is not None:
        row['detail'] = detail
    CHECKS.append(row)


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
    return re.sub(r'\s+', '', value).replace('muSegment', 'nioSegment').replace('muProfit', 'nioProfit').replace('muValuation', 'nioValuation')


def signature(doc):
    """Compare MU layout; permit documented source anchors and loss colors.

    Table metric names and text do not enter this signature. All five rows,
    columns, element nesting and layout classes still have to match MU.
    Original NIO PI/disclaimer DOM is checked separately against the base.
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
            attrs['value'] = attrs.get('value', '').replace('mu', 'nio')
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
    return re.search(r"fetch\('disclaimer.html'\)[\s\S]*?\.catch\(error => console\.error\('[^']*', error\)\);", source).group(0)


def protected_dom(doc, target_id):
    node = copy.deepcopy(doc.get_element_by_id(target_id))
    if target_id == 'disclaimer':
        # Layout migration renumbers the old seventh section to the sixth;
        # every other attribute, node and legal/loading text must match.
        heading = node.xpath('.//h2')[0]
        heading.text = re.sub(r'^(?:VII\.|VI\.|7\.|6\.|七、|六、)', 'SECTION_NUMBER', heading.text)
    return html.tostring(node, with_tail=False)


SOURCE_URLS = {row['id']: row['url'] for row in OFFICIAL['sources']}
PEERS = LEDGER['bloomberg_peers']['peers']
NAMES = {'tc': '蔚來', 'sc': '蔚来', 'en': 'NIO'}
TABLES = []
RISK_SIGNATURES = []
BROKERS = [row for row in ANR['brokers_priority'] if row.get('selected')]
PRICE = ANR['reference_price']['value']
TARGET = ANR['target_12m']['value']
PEER_VALUES = {'9863': 8.23, '1211': 11.69, 'NIO': 33.05, 'LI': 37.92}
PEER_NAMES = {
    '9863': next(row['names'] for row in PEERS if row['security'].startswith('9863')),
    '1211': next(row['names'] for row in PEERS if row['security'].startswith('1211')),
    'LI': next(row['names'] for row in PEERS if row['security'].startswith('LI')),
    'NIO': NAMES,
}

for file in FILES:
    source = (ROOT/file).read_text()
    template_name = file.replace('nio', 'mu')
    template = (ROOT/template_name).read_text()
    prior = oldfile(file)
    doc, mu, old = map(html.fromstring, [source, template, prior])
    locale = 'sc' if '-sc.' in file else 'en' if '-en.' in file else 'tc'
    layout_matches = signature(doc) == signature(mu)
    differences = []
    if not layout_matches:
        for i, (a, b) in enumerate(zip(signature(doc), signature(mu))):
            if a != b:
                differences.append({'index': i, 'nio': a, 'mu': b})
                if len(differences) == 5:
                    break
    check(file+':mu_structure_and_layout_attributes', layout_matches, differences or None)
    check(file+':mu_styles_fonts_and_script_versions', doc.xpath('//style/text()') == mu.xpath('//style/text()') and
          doc.xpath('//head/link/@href') == mu.xpath('//head/link/@href') and doc.xpath('//script/@src') == mu.xpath('//script/@src'))
    check(file+':six_tabs', doc.xpath('//section/@id') == TABS and doc.xpath('//nav/button/@onclick') == [f"switchTab(event, '{tab}')" for tab in TABS])
    check(file+':no_obsolete_sandbox', not re.search(r'sandbox|generateCustomScenario|custom-scenario|scenario-loading|scenario-result', source, re.I))
    check(file+':three_chart_containers', doc.xpath('//canvas/@id') == CANVASES and len(doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," chart-container ")]')) == 3)
    ids = doc.xpath('//@id')
    check(file+':unique_ids', len(ids) == len(set(ids)))
    check(file+':language_links', set(doc.xpath('//select/option/@value')) == set(FILES) and doc.xpath('//select/option[@selected]/@value') == [file])
    for protected_id in ['pi-modal', 'disclaimer']:
        check(file+':original_'+protected_id+'_dom_except_section_number', protected_dom(doc, protected_id) == protected_dom(old, protected_id))
    check(file+':original_disclaimer_loader_exact', disclaimer_loader(source) == disclaimer_loader(prior))
    check(file+':company_heading_and_title', all(NAMES[locale] in text(node) and 'NIO' in text(node) for node in [doc.xpath('//h1')[0], doc.xpath('//title')[0]]))
    header = text(doc.xpath('//header')[0])
    check(file+':header_consensus', all(v in header for v in [f'{TARGET:.2f}', '4.37/5', 'NIO', '2026/10/09']))
    forbidden = r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|\bSCAs\b|1-gamma|G9 NAND|Kioxia|SK Hynix|Samsung|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|331\.91|McDonald|麥當勞|麦当劳|Oracle|甲骨文'
    remnants = re.findall(forbidden, source, re.I)
    check(file+':no_unrelated_company_template_remnants', not remnants, remnants or None)
    check(file+':no_citation_placeholders', not re.search(r'||\bturn\d+(?:search|view|fetch)\d+|\bTODO\b|\bTBD\b|\{\{', source))
    views = text(doc.get_element_by_id('our-comments'))
    check(file+':period_publication_and_update_dates', all(v in views for v in ['2026/06/30', '2026/09/01', '2026/10/09']))
    check(file+':our_views_four_items_and_voice', len(doc.get_element_by_id('our-comments').xpath('.//li')) == 4 and {'en':'We believe','sc':'我们认为','tc':'我們認為'}[locale] in views and not re.search(r'NTAM\s*(?:認為|认为|believes)', views, re.I))
    public_doc = copy.deepcopy(doc)
    for element in public_doc.xpath('//script | //style'):
        element.getparent().remove(element)
    public_text = text(public_doc)
    check(file+':no_unverified_price_close_claim', not re.search(r'(?:10/0[89]|08-Oct).{0,20}(?:收盤|收盘|closing)|(?:closing price|收盤價|收盘价).{0,15}3\.41', public_text, re.I))
    financials = doc.get_element_by_id('financials')
    kpis = financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div')
    check(file+':four_kpis', len(kpis) == 4)
    check(file+':liquidity_kpi_is_cash_pool_not_fcf', len(kpis) == 4 and 56.7 in numbers(text(kpis[3])) and not re.search(r'free.cash.flow|自由現金流|自由现金流|FCF|net.cash|淨現金|净现金', text(kpis[3]), re.I))
    table = financials.xpath('.//table')[0]
    rows = table.xpath('.//tbody/tr')
    check(file+':four_column_five_row_table', len(table.xpath('.//thead/tr/th')) == 4 and len(rows) == 5 and all(len(row.xpath('./td')) == 4 for row in rows))
    observed_rows = [[numbers(text(td)) for td in row.xpath('./td')[1:]] for row in rows]
    TABLES.append(observed_rows)
    expected_primary = [
        [[round(F['revenue_k']/1000,1)], [round(F['revenue_k']/1000,1)]],
        [[round(F['gross_profit_k']/1000,1),F['gross_margin_pct']], [F['vehicle_margin_pct']]],
        [[round(F['operating_income_k']/1000,1)], [round(F['adjusted_operating_income_k']/1000,1)]],
        [[round(F['net_income_k']/1000,1)], [round(F['adjusted_net_income_k']/1000,1)]],
        [[F['gaap_eps_basic_diluted_rmb']], [F['adjusted_eps_basic_diluted_rmb']]],
    ]
    check(file+':table_matches_gaap_adjusted_and_vehicle_bases', [row[:2] for row in observed_rows] == expected_primary, {'observed':observed_rows,'expected_primary':expected_primary})
    check(file+':table_eps_per_ads_label', bool(re.search(r'diluted|稀釋|稀释|攤薄|摊薄', text(rows[4]), re.I)) and 'ADS' in text(rows[4]))
    check(file+':table_supplement_column_not_non_gaap_vehicle_margin', bool(re.search(r'supplement|補充|补充', text(table.xpath('.//thead/tr/th')[2]), re.I)) and bool(re.search(r'vehicle|汽車|汽车|整車|整车', text(rows[1].xpath('./td')[2]), re.I)))
    check(file+':quarterly_financial_table_rmb_not_usd', bool(re.search(r'RMB|人民幣|人民币', text(table.getparent().getparent().xpath('./h3')[0]),re.I)) and not re.search(r'US\$|USD', text(table)))
    source_links = financials.xpath('.//a/@href')
    check(file+':financial_primary_source_link', SOURCE_URLS['q2_release'] in source_links and all(link in SOURCE_URLS.values() for link in source_links), source_links)
    valuation_text = text(doc.get_element_by_id('valuation'))
    check(file+':peer_fy2027_adj_plus_basis', all(v in valuation_text for v in ['2027','Adj+','12/31','9863','1211','NIO','LI']) and bool(re.search(r'FY|財年|财年', valuation_text)))
    check(file+':peer_eeo_date_limit', bool(re.search(r'(?:未|無|无|not|no).{0,45}(?:日期|date)|(?:日期|date).{0,45}(?:未|無|无|not|no)', valuation_text,re.I)))
    check(file+':peer_valuation_security_and_accounting_limits', 'ADS' in valuation_text and 'CNY' in valuation_text and bool(re.search(r'USD|美元',valuation_text)) and bool(re.search(r'HKD|港元',valuation_text)) and bool(re.search(r'Accounting frameworks and adjustments differ|會計準則及調整項目不同|会计准则及调整项目不同',valuation_text,re.I)))
    street = doc.get_element_by_id('street-comments')
    cards = street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    broker_checks = []
    colors = {'Overweight':'bg-blue-100 text-blue-800','Buy':'bg-emerald-100 text-emerald-800','Neutral':'bg-slate-100 text-slate-600'}
    for card, broker in zip(cards, BROKERS):
        badge = card.xpath('.//span')[0]
        body = text(card)
        ret = (broker['target']/PRICE-1)*100
        ok = broker['firm'] in text(card.xpath('.//h3')[0]) and text(badge) == broker['display_rating'] and colors[broker['display_rating']] in badge.get('class')
        ok = ok and all(v in body for v in [broker['analyst'],f"{broker['target']:.2f}",broker['date'].replace('-','/'),f'{ret:.1f}%'])
        broker_checks.append({'firm':broker['firm'],'ok':ok,'return_percent':round(ret,1)})
    check(file+':brokers_priority_targets_dates_returns_colors',len(cards)==3 and len(broker_checks)==3 and all(b['ok'] for b in broker_checks),broker_checks)
    check(file+':no_public_rating_normalization_note',not re.search(r'統一分類|统一分类|standardized|standardised|site category|display category',text(street),re.I))
    sourcelines = [text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
    check(file+':compact_anr_reference_source',len(sourcelines)==1 and all(v in sourcelines[0] for v in ['2026/10/09','10/08','3.41']) and len(sourcelines[0])<240,sourcelines)
    check(file+':no_public_calculator_attribution',not re.search(r'NTAM\s*(?:計算|计算|calculation|calculated)',public_text,re.I))
    risk = doc.get_element_by_id('risks')
    headings = risk.xpath('.//li/strong')
    check(file+':four_risk_headings_all_same_dark_style',len(headings)==4 and all(h.get('class')=='text-base' for h in headings) and not re.search(r'text-(?:red|rose)-',html.tostring(risk,encoding='unicode')))
    RISK_SIGNATURES.append([(e.tag,sorted(e.attrib.items())) for e in risk.iter() if isinstance(e.tag,str)])
    try:
        result = run_vm(file,source,doc)
        mu_result = run_vm(template_name,template,mu)
        RUNTIMES[file] = result
        check(file+':inline_js_syntax_and_mock_execution',True)
        check(file+':chart_cache_keys',result['keys']==KEYS,result['keys'])
        check(file+':tabs_and_chart_resize',all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']]==[1,1,1])
        check(file+':pi_active_no_acceptance_or_storage_write',result['storageWrites']==0 and result['piVisible'] and result['bodyLocked'])
        restored=['acceptPI','declinePI','callGeminiAPI']
        check(file+':restore_missing_pi_api_functions_from_mu',all(normalize_function(result['functions'][name])==normalize_function(mu_result['functions'][name]) and not re.search(r'function\s+'+name+r'\s*\(',prior) for name in restored))
        check(file+':disclaimer_local_mock_no_api_network',result['fetches']==['disclaimer.html'] and result['disclaimerLoaded'])
        interactions=['switchTab','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']
        check(file+':mu_fixed_interaction_functions',all(normalize_function(result['functions'][name])==normalize_function(mu_result['functions'][name]) for name in interactions))
        def explain_skeleton(value):
            return normalize_function(re.sub(r'await callGeminiAPI\([\s\S]*?\);','await COMPANY_EXPLANATION;',value))
        check(file+':mu_explain_interaction',explain_skeleton(result['functions']['explainSelectedTerm'])==explain_skeleton(mu_result['functions']['explainSelectedTerm']))
        prompt = result['standardPrompt']
        check(file+':dated_nio_ai_evidence_context',all(v in prompt for v in ['NIO','2026/10/09','2026/06/30','2026/09/01','32136.9','347.2','206.9','528','26.1','0.29','0.01','3.41','6.23','33.05']) and not re.search(forbidden,prompt,re.I))
        check(file+':localized_ai_company_context',NAMES[locale] in prompt)
        configs={c['canvasId']:c['config'] for c in result['charts']}
        deliveries,profit,valuation=[configs[canvas] for canvas in CANVASES]
        check(file+':deliveries_chart_brand_counts_reconcile',deliveries['type']=='doughnut' and deliveries['data']['datasets'][0]['data']==[F['brands'][brand] for brand in ['NIO','ONVO','FIREFLY']] and sum(deliveries['data']['datasets'][0]['data'])==F['deliveries'])
        profit_data=[dataset['data'] for dataset in profit['data']['datasets']]
        expected_profit=[[round(F['operating_income_k']/1000,1),round(F['net_income_k']/1000,1)],[round(F['adjusted_operating_income_k']/1000,1),round(F['adjusted_net_income_k']/1000,1)]]
        check(file+':profit_chart_company_total_gaap_adjusted_bases',profit['type']=='bar' and profit_data==expected_profit and 'percentageAxis' not in json.dumps(profit))
        labels,values=valuation['data']['labels'],valuation['data']['datasets'][0]['data']
        tickers=[next((ticker for ticker in PEER_VALUES if ticker in label),'UNKNOWN') for label in labels]
        check(file+':peer_fy2027_pe_values_and_order',tickers==list(PEER_VALUES) and dict(zip(tickers,values))==PEER_VALUES)
        check(file+':localized_verified_peer_names',all(PEER_NAMES[ticker][locale] in label for ticker,label in zip(tickers,labels)))
        check(file+':chart_responsive',all(c['options'].get('responsive') is True and c['options'].get('maintainAspectRatio') is False for c in configs.values()) and valuation['options'].get('indexAxis')=='y')
        DETAILS[file]={'sha256':hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),'mock_runtime':result}
    except Exception as exc:
        check(file+':inline_js_syntax_and_mock_execution',False,str(exc))

numeric=[[[d['data'] for d in c['config']['data']['datasets']] for c in result['charts']] for result in RUNTIMES.values()]
check('three_languages:chart_numeric_parity',len(numeric)==3 and all(value==numeric[0] for value in numeric))
styles=[[[{k:v for k,v in d.items() if k!='label'} for d in c['config']['data']['datasets']] for c in result['charts']] for result in RUNTIMES.values()]
check('three_languages:chart_dataset_style_parity',len(styles)==3 and all(value==styles[0] for value in styles))
check('three_languages:financial_table_numeric_parity',len(TABLES)==3 and all(value==TABLES[0] for value in TABLES))
check('three_languages:risk_format_parity',len(RISK_SIGNATURES)==3 and all(value==RISK_SIGNATURES[0] for value in RISK_SIGNATURES))
check('evidence:brand_delivery_reconciliation',sum(F['brands'].values())==F['deliveries'])
check('evidence:revenue_and_gross_profit_reconciliation',F['vehicle_sales_k']+F['other_sales_k']==F['revenue_k'] and F['revenue_k']-F['cost_sales_k']==F['gross_profit_k'])
check('evidence:adjusted_operating_and_total_net_reconciliation',F['operating_income_k']+F['sbc_k']==F['adjusted_operating_income_k'] and F['net_income_k']+F['sbc_k']==F['adjusted_net_income_k'])
check('evidence:ordinary_shareholder_reconciliation',F['net_income_ordinary_shareholders_k']+F['sbc_k']+F['redemption_accretion_k']==F['adjusted_net_income_ordinary_shareholders_k'])
check('evidence:no_unavailable_quarterly_cashflow_amount_invented',all(OFFICIAL['cash_flow'][key] is None for key in ['q2_2026_operating_cash_flow_amount','q2_2026_capex','q2_2026_free_cash_flow']))
check('evidence:consensus_and_broker_return_formulas',round((TARGET/PRICE-1)*100,1)==ANR['return_potential_percent_displayed'] and all(round((row['target']/PRICE-1)*100,1)==row['return_percent_display'] for row in BROKERS))
check('evidence:anr_priority_and_industry_separation',[row['firm'] for row in BROKERS]==['UBS','Morgan Stanley','JP Morgan'] and BROKERS[1]['raw_rating']=='Overwt/In-Line' and BROKERS[1]['display_rating']=='Overweight')
check('evidence:peer_common_fy2027_multiple_period',all(row['multiples_x']['price_eps_adj_plus'][3]==PEER_VALUES[row['security'].split()[0]] for row in PEERS) and next(row for row in BLOOMBERG['eeo']['current_multiples']['rows'] if row['label']=='Price/EPS, Adj+')['values'][3]==PEER_VALUES['NIO'])
check('evidence:q3_deliveries_guidance_met_not_financial_actuals',OFFICIAL['q3_2026_guidance_at_q2_release']['delivery_units_low']<=OFFICIAL['q3_2026_delivery_actual']['quarter_deliveries']<=OFFICIAL['q3_2026_guidance_at_q2_release']['delivery_units_high'] and OFFICIAL['reporting_period']['latest_financial_quarter_verified']=='Q2 2026')
for row in LEDGER['canonical_templates']:
    check('canonical_template:'+row['path'],hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256'] and (ROOT/row['path']).read_text()==oldfile(row['path']))
check('protected_files:ledger_hashes_and_base',all(hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest and (ROOT/file).read_text()==oldfile(file) for file,digest in LEDGER['protected_files'].items()))
tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
infrastructure=[file for file in tracked if file.startswith('api/') or file in ['CNAME','disclaimer.html','vercel.json','package.json','package-lock.json']]
check('protected_files:infrastructure_exact',all((ROOT/file).read_text()==oldfile(file) for file in infrastructure),infrastructure)
index_source,old_index_source=(ROOT/'index.html').read_text(),oldfile('index.html')
index,old_index=map(html.fromstring,[index_source,old_index_source])
def homepage_cards(doc):
    return doc.xpath('//div[contains(@onclick,"window.location.href=")]')
cards,old_cards=homepage_cards(index),homepage_cards(old_index)
def card_ticker(card):
    return text(card.xpath('.//h3')[0])
order,old_order=list(map(card_ticker,cards)),list(map(card_ticker,old_cards))
check('homepage:nio_fourth_25_cards_other_order_preserved',len(cards)==25 and order[3]=='NIO' and [t for t in order if t!='NIO']==[t for t in old_order if t!='NIO'],order)
old_by_ticker={card_ticker(card):html.tostring(card,with_tail=False) for card in old_cards}
check('homepage:other_24_card_contents_exact',all(html.tostring(card,with_tail=False)==old_by_ticker[card_ticker(card)] for card in cards if card_ticker(card)!='NIO'))
def raw_homepage_blocks(source):
    pattern=r'<div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm card-hover flex flex-col h-full cursor-pointer group" onclick="window.location.href=\'([^\']+)\'">'
    starts=list(re.finditer(pattern,source))
    end=source.index('</div>\n</main>',starts[-1].start())
    blocks={m[1]:source[m.start():starts[i+1].start() if i+1<len(starts) else end] for i,m in enumerate(starts)}
    return source[:starts[0].start()],blocks,source[end:]
prefix,raw_cards,suffix=raw_homepage_blocks(index_source)
old_prefix,old_raw_cards,old_suffix=raw_homepage_blocks(old_index_source)
check('homepage:other_24_blocks_byte_exact',len(raw_cards)==25 and all(block==old_raw_cards[file] for file,block in raw_cards.items() if file!='nio.html'))
check('homepage:outside_card_region_byte_exact',prefix==old_prefix and suffix==old_suffix)
nio_card=text(next(card for card in cards if card_ticker(card)=='NIO'))
check('homepage:nio_updated_period_target_and_return',all(value in nio_card for value in ['2026年10月9日更新','6.23','82.7%']))
ordering=json.loads((ROOT/'research/homepage-earnings-order-2026-10-08.json').read_text())
ordered_records=sorted(ordering['records'],key=lambda row:row['position'])
dates=[row['earnings_publication_date'] for row in ordered_records]
check('homepage:ledger_actual_earnings_order',[row['ticker'] for row in ordered_records]==order and dates==sorted(dates,reverse=True) and ordered_records[3]['earnings_publication_date']=='2026-09-01')
changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
check('scope:only_nio_and_homepage_html',all(not file.endswith('.html') or file in FILES+['index.html'] for file in changed),changed)
check('scope:no_source_screenshots_tracked',not any(re.search(r'(?:NIO|LI|BYD|9863).*(?:EEO|ANR).*\.(?:png|jpe?g)$',file,re.I) for file in tracked+changed))
whitespace=subprocess.run(['git','-c','core.whitespace=cr-at-eol','diff','--check'],cwd=ROOT,capture_output=True,text=True)
check('git_diff_whitespace',whitespace.returncode==0,whitespace.stdout+whitespace.stderr or None)
report={'report':'NIO Q2 2026 evidence and MU-template validation','checked_on':'2026-10-09','base_commit':BASE,
        'status':'pass' if all(row['status']=='pass' for row in CHECKS) else 'fail','checks':CHECKS,'page_details':DETAILS,
        'limitations':['Mock VM checks are not real-browser rendering or live Chart.js rasterization.',
                      'No live AI call, PI acceptance, PI storage write, modal removal/hiding or access-control bypass was performed.',
                      'Original NIO PI modal and disclaimer legal/loading content are preserved. Missing PI/API/chat functions are restored from corresponding MU masters; these are not claimed to be unchanged from broken old NIO implementations.',
                      'Authoritative-source and screenshot review is recorded in the evidence ledger; this script reconciles the implementation to that evidence.',
                      'ANR is dated2026/10/09; reference quote says On08-Oct without a year or verified close. EEO independent dates are absent.',
                      'FY2027 Adj+ P/E is a common displayed period, not a common accounting framework or the Next4 quarter window.',
                      'Real browser and deployed HTTP content checks, if performed, are separately documented in the release workflow.']}
destination=ROOT/'research/nio-2026-q2-validation.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
failed=[row for row in CHECKS if row['status']=='fail']
print(json.dumps({'status':report['status'],'checks':len(CHECKS),'failed':failed,'output':str(destination)},ensure_ascii=False,indent=2))
raise SystemExit(bool(failed))
