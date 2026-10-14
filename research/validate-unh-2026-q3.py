#!/usr/bin/env python3
"""Reconcile the UNH Q3 2026 update to its evidence and MU template.

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
BASE = '6fb25cf6d9228a2f1dcc8139f4984346b5c04228'
LEDGER = json.loads((ROOT/'research/unh-2026-q3-2026-10-14.json').read_text())
OFFICIAL = LEDGER['official_company_evidence']
F = OFFICIAL['consolidated']['q3_2026']
BLOOMBERG = LEDGER['bloomberg_evidence']
ANR = BLOOMBERG['UNH_ANR']
FILES = ['unh.html', 'unh-sc.html', 'unh-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
KEYS = ['unhSegment', 'unhProfit', 'unhValuation']
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
    return re.sub(r'\s+', '', value).replace('muSegment', 'unhSegment').replace('muProfit', 'unhProfit').replace('muValuation', 'unhValuation')


def signature(doc):
    """Compare MU layout; permit source links and four neutral growth labels.

    Table metric names and text do not enter this signature. All five rows,
    columns, element nesting and layout classes still have to match MU.
    Original UNH PI/disclaimer DOM is checked separately against the base.
    """
    doc = copy.deepcopy(doc)
    for element in doc.xpath('//script | //*[@id="pi-modal"] | //*[@id="disclaimer"]'):
        element.getparent().remove(element)
    for element in doc.xpath('//section[@id="financials" or @id="our-comments"]//a'):
        element.drop_tag()
    # Only four approved sign/mixed-direction fields may use neutral slate;
    # no global normalization of text colors is allowed.
    financials = doc.get_element_by_id('financials')
    neutral_nodes = financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div[position()=1 or position()=3]/p[2] | .//table/tbody/tr[position()=1 or position()=2]/td[4]')
    records = []
    for element in doc.iter():
        if not isinstance(element.tag, str):
            continue
        attrs = dict(element.attrib)
        if element.tag == 'option':
            attrs['value'] = attrs.get('value', '').replace('mu', 'unh')
        if element in neutral_nodes and 'class' in attrs:
            attrs['class'] = re.sub(r'text-(?:emerald-[56]00|slate-600)', 'text-MIXED-GROWTH', attrs['class'])
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
 const domListener=events.DOMContentLoaded[0].toString();
 const loader=domListener.slice(domListener.indexOf("fetch('disclaimer.html')")).replace(/\s*\}\s*$/,'');
 const gate=domListener.slice(domListener.indexOf("if (!sessionStorage.getItem('pi_agreed'))"),domListener.indexOf('window.charts.')).replace(/\/\/[^\n]*/g,'').trim();
 if(input.functionsOnly){process.stdout.write(JSON.stringify({functions,loader,gate}));return;}
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
  standardPrompt:vm.runInContext('standardPrompt',context),functions,loader,gate}));
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



BROKERS = ANR['selected_banks']
PRICE, TARGET = ANR['last_price'], ANR['consensus_target_12m']
PEER_VALUES = {'CNC':12.88, 'ELV':14.38, 'UNH':16.62, 'HUM':24.8}
TABLES, RISK_SIGNATURES = [], []
COLORS = {'Overweight':'bg-blue-100 text-blue-800','Buy':'bg-emerald-100 text-emerald-800','Neutral':'bg-slate-100 text-slate-600','Sell':'bg-pink-100 text-pink-700','Underweight':'bg-red-100 text-red-600'}
FORBIDDEN = r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|\bSCAs\b|1-gamma|G9 NAND|Kioxia|SK Hynix|Samsung|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|331\.91|McDonald|麥當勞|麦当劳|Oracle|甲骨文|423\.38|455\.08|2026/07/17|2026/07/16'

for file in FILES:
    source = (ROOT/file).read_text()
    template_name = file.replace('unh', 'mu')
    template, prior = (ROOT/template_name).read_text(), oldfile(file)
    doc, mu, old = map(html.fromstring, [source, template, prior])
    locale = 'sc' if '-sc.' in file else 'en' if '-en.' in file else 'tc'
    observed_signature, template_signature = signature(doc), signature(mu)
    differences = [{'index':i,'unh':a,'mu':b} for i,(a,b) in enumerate(zip(observed_signature,template_signature)) if a!=b][:5]
    check(file+':mu_structure_and_layout_attributes', observed_signature==template_signature, differences or None)
    check(file+':mu_styles_fonts_script_versions', doc.xpath('//style/text()')==mu.xpath('//style/text()') and doc.xpath('//head/link/@href')==mu.xpath('//head/link/@href') and doc.xpath('//script/@src')==mu.xpath('//script/@src'))
    check(file+':six_tabs', doc.xpath('//section/@id')==TABS and doc.xpath('//nav/button/@onclick')==[f"switchTab(event, '{tab}')" for tab in TABS])
    check(file+':three_chart_containers', doc.xpath('//canvas/@id')==CANVASES and len(doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," chart-container ")]'))==3)
    ids=doc.xpath('//@id')
    check(file+':unique_ids',len(ids)==len(set(ids)))
    check(file+':language_links',set(doc.xpath('//select/option/@value'))==set(FILES) and doc.xpath('//select/option[@selected]/@value')==[file])
    for protected_id in ['pi-modal','disclaimer']:
        check(file+':original_'+protected_id+'_legal_dom',protected_dom(doc,protected_id)==protected_dom(old,protected_id))
    check(file+':company_heading_title',all('UNH' in text(node) for node in [doc.xpath('//h1')[0],doc.xpath('//title')[0]]))
    header=text(doc.xpath('//header')[0])
    check(file+':header_consensus_and_date',all(v in header for v in [f'{TARGET:.2f}','4.67/5','UNH','2026/10/14']))
    remnants=re.findall(FORBIDDEN,source,re.I)
    check(file+':no_stale_or_unrelated_template_facts',not remnants,remnants or None)
    check(file+':no_citation_placeholders',not re.search(r'||\bturn\d+(?:search|view|fetch)\d+|\bTODO\b|\bTBD\b|\{\{',source))
    views=text(doc.get_element_by_id('our-comments'))
    check(file+':report_period_release_and_update',all(v in views for v in ['2026/09/30','2026/10/13','2026/10/14']))
    check(file+':views_four_items_and_voice',len(doc.get_element_by_id('our-comments').xpath('.//li'))==4 and {'en':'We believe','sc':'我们认为','tc':'我們認為'}[locale] in views and not re.search(r'NTAM\s*(?:認為|认为|believes)',views,re.I))
    public_doc=copy.deepcopy(doc)
    for element in public_doc.xpath('//script | //style'):
        element.getparent().remove(element)
    public_text=text(public_doc)
    check(file+':no_unverified_close_price_claim',not re.search(r'(?:收盤|收盘|closing|close).{0,20}377\.76|377\.76.{0,20}(?:收盤|收盘|closing|close)',public_text,re.I))
    check(file+':no_unverified_prerelease_consensus_label',not re.search(r'業績前共識|业绩前共识|pre[- ](?:release|earnings) consensus',public_text,re.I) or bool(re.search(r'未能|未經|未经|並非|并非|不可|not|cannot|unverified',public_text,re.I)))
    financials=doc.get_element_by_id('financials')
    kpis=financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div')
    check(file+':four_kpis',len(kpis)==4)
    table=financials.xpath('.//table')[0]
    rows=table.xpath('.//tbody/tr')
    check(file+':four_column_five_row_table',len(table.xpath('.//thead/tr/th'))==4 and len(rows)==5 and all(len(r.xpath('./td'))==4 for r in rows))
    observed_rows=[[numbers(text(td)) for td in row.xpath('./td')[1:]] for row in rows]
    TABLES.append(observed_rows)
    expected_primary=[[[112694],[112715]],[[6563],[6265]],[[4110],[4228]],[[4.56],[4.69]],[[],[4264]]]
    check(file+':table_gaap_adjusted_common_income_eps_analytical_fcf',[row[:2] for row in observed_rows]==expected_primary,{'observed':observed_rows,'expected':expected_primary})
    expected_supplement=[[-0.4],[-21.5],[59.5],[60.6],[5123,859,-15.6]]
    check(file+':table_growth_and_cashflow_supplements',[r[2] for r in observed_rows]==expected_supplement,{'observed':[r[2] for r in observed_rows],'expected':expected_supplement})
    check(file+':table_common_shareholder_income_label',bool(re.search(r'common|普通股',text(rows[2]),re.I)))
    check(file+':table_diluted_eps_label',bool(re.search(r'diluted|稀釋|稀释|攤薄|摊薄',text(rows[3]),re.I)))
    check(file+':fcf_analytical_measure_disclosed','OCF' in text(rows[4]) and bool(re.search(r'資本支出|资本支出|capex',text(rows[4]),re.I)) and observed_rows[4][0]==[])
    check(file+':four_segment_revenues_pre_elimination_disclosed',all(v in text(financials) for v in ['154,641','1,428','40,519','112,694']) and bool(re.search(r'抵銷|抵销|elimination',text(financials),re.I)))
    check(file+':adjusted_income_removes_gains_not_amortization',bool(re.search(r'調整後|调整后|adjusted',text(financials),re.I)) and bool(re.search(r'出售|處置|处置|divestiture|gains',text(financials),re.I)))
    valuation_text=text(doc.get_element_by_id('valuation'))
    check(file+':peer_common_fy2027_adj_basis',all(v in valuation_text for v in ['2027','Adj+','12/31']) and bool(re.search(r'未來四季|未来四季|next-four-quarter',valuation_text,re.I)))
    check(file+':peer_dates_and_adjustment_limitations',bool(re.search(r'日期|date',valuation_text,re.I)) and bool(re.search(r'調整|调整|adjustment',valuation_text,re.I)))
    street=doc.get_element_by_id('street-comments')
    cards=street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    broker_checks=[]
    for card,broker in zip(cards,BROKERS):
        badge=card.xpath('.//span')[0]
        body=text(card)
        ret=(broker['target']/PRICE-1)*100
        ok=broker['firm'] in text(card.xpath('.//h3')[0]) and text(badge)==broker['rating_standardized'] and COLORS[broker['rating_standardized']] in badge.get('class')
        ok=ok and all(v in body for v in [broker['analyst'],f"{broker['target']:.2f}",broker['date'].replace('-','/'),f'{ret:.1f}%'])
        broker_checks.append({'firm':broker['firm'],'ok':ok,'return_percent':round(ret,1)})
    check(file+':brokers_priority_targets_dates_returns_colors',len(cards)==3 and len(broker_checks)==3 and all(b['ok'] for b in broker_checks),broker_checks)
    check(file+':broker_cards_only_two_verified_factual_items',all(len(card.xpath('.//li'))==2 for card in cards))
    check(file+':no_public_classification_note',not re.search(r'統一分類|统一分类|standardized|standardised|site category|display category',text(street),re.I))
    sourcelines=[text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
    check(file+':compact_anr_price_source',len(sourcelines)==1 and all(v in sourcelines[0] for v in ['2026/10/14','10/13','377.76']) and len(sourcelines[0])<240,sourcelines)
    check(file+':no_calculator_attribution',not re.search(r'NTAM\s*(?:計算|计算|calculation|calculated)',public_text,re.I))
    risk=doc.get_element_by_id('risks')
    headings=risk.xpath('.//li/strong')
    check(file+':four_risks_same_dark_style',len(headings)==4 and all(h.get('class')=='text-base' for h in headings) and not re.search(r'text-(?:red|rose)-',html.tostring(risk,encoding='unicode')))
    RISK_SIGNATURES.append([(e.tag,sorted(e.attrib.items())) for e in risk.iter() if isinstance(e.tag,str)])
    try:
        result=run_vm(file,source,doc)
        mu_result=run_vm(template_name,template,mu,functions_only=True)
        old_result=run_vm(file,prior,old,functions_only=True)
        RUNTIMES[file]=result
        check(file+':inline_js_syntax_mock_execution',True)
        check(file+':chart_cache_keys',result['keys']==KEYS,result['keys'])
        check(file+':tab_switches_chart_resize',all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']]==[1,1,1])
        check(file+':pi_gate_active_no_acceptance_storage_write',result['storageWrites']==0 and result['piVisible'] and result['bodyLocked'])
        check(file+':original_pi_api_functions',all(normalize_function(result['functions'][name])==normalize_function(old_result['functions'][name]) for name in ['acceptPI','declinePI','callGeminiAPI']))
        check(file+':original_pi_gate_condition_and_lock',normalize_function(result['gate'])==normalize_function(old_result['gate']))
        check(file+':original_disclaimer_loader_error_handling',normalize_function(result['loader'])==normalize_function(old_result['loader']))
        check(file+':disclaimer_local_mock_no_live_api',result['fetches']==['disclaimer.html'] and result['disclaimerLoaded'])
        interactions=['switchTab','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']
        check(file+':mu_fixed_interactions',all(normalize_function(result['functions'][name])==normalize_function(mu_result['functions'][name]) for name in interactions))
        def explain_skeleton(value):
            return normalize_function(re.sub(r'await callGeminiAPI\([\s\S]*?\);','await COMPANY_EXPLANATION;',value))
        check(file+':mu_explain_interaction',explain_skeleton(result['functions']['explainSelectedTerm'])==explain_skeleton(mu_result['functions']['explainSelectedTerm']))
        prompt=result['standardPrompt']
        check(file+':dated_unh_ai_evidence',all(v in prompt for v in ['UNH','2026/10/14','2026/09/30','2026/10/13','112694','112715','6563','6265','4110','4228','4.56','4.69','5123','859','4264','88.4','610','377.76','476.93','16.62']) and not re.search(FORBIDDEN,prompt,re.I))
        check(file+':ai_keeps_language_and_format',('markdown' in prompt.lower()) and '<b>' in prompt and {'tc':'繁體中文','sc':'简体中文','en':'English'}[locale] in prompt)
        configs={c['canvasId']:c['config'] for c in result['charts']}
        segment,profit,valuation=[configs[canvas] for canvas in CANVASES]
        check(file+':segment_chart_reported_pre_elimination',segment['type']=='doughnut' and segment['data']['datasets'][0]['data']==[86330,22910,5474,39927])
        check(file+':profit_chart_common_income_gaap_adjusted',profit['type']=='bar' and [d['data'] for d in profit['data']['datasets']]==[[6563,4110],[6265,4228]] and 'percentageAxis' not in json.dumps(profit))
        labels,values=valuation['data']['labels'],valuation['data']['datasets'][0]['data']
        tickers=[next((ticker for ticker in PEER_VALUES if ticker in label),'UNKNOWN') for label in labels]
        check(file+':peer_fy2027_values_and_order',tickers==list(PEER_VALUES) and dict(zip(tickers,values))==PEER_VALUES)
        check(file+':chart_responsive',all(c['options'].get('responsive') is True and c['options'].get('maintainAspectRatio') is False for c in configs.values()) and valuation['options'].get('indexAxis')=='y')
        check(file+':unh_valuation_bar_only_blue',valuation['data']['datasets'][0]['backgroundColor']==['rgba(148, 163, 184, 0.6)','rgba(148, 163, 184, 0.6)','rgba(37, 99, 235, 0.95)','rgba(148, 163, 184, 0.6)'])
        DETAILS[file]={'sha256':hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),'mock_runtime':result}
    except Exception as exc:
        check(file+':inline_js_syntax_mock_execution',False,str(exc))

numeric=[[[d['data'] for d in c['config']['data']['datasets']] for c in result['charts']] for result in RUNTIMES.values()]
check('three_languages:chart_numeric_parity',len(numeric)==3 and all(value==numeric[0] for value in numeric))
styles=[[[{k:v for k,v in d.items() if k!='label'} for d in c['config']['data']['datasets']] for c in result['charts']] for result in RUNTIMES.values()]
check('three_languages:chart_dataset_style_parity',len(styles)==3 and all(value==styles[0] for value in styles))
check('three_languages:financial_table_numeric_parity',len(TABLES)==3 and all(value==TABLES[0] for value in TABLES))
check('three_languages:risk_format_parity',len(RISK_SIGNATURES)==3 and all(value==RISK_SIGNATURES[0] for value in RISK_SIGNATURES))
segments=OFFICIAL['segments']['q3_2026']
check('evidence:segment_revenue_reconciliation',sum(segments[k]['revenue_gaap'] for k in ['UnitedHealthcare','Optum_Health','Optum_Insight','Optum_Rx'])-segments['optum_revenue_eliminations']-segments['corporate_revenue_eliminations']==F['revenue_gaap'])
check('evidence:gaap_revenue_components',sum(F[k] for k in ['premium_revenue','product_revenue','service_revenue','investment_and_other_income'])==F['revenue_gaap'])
check('evidence:gaap_operating_income_components',F['revenue_gaap']-sum(F[k] for k in ['medical_costs','operating_costs','cost_of_products_sold','depreciation_and_amortization'])==F['operating_income_gaap'])
check('evidence:adjusted_income_reconciliation',4110+373-148-74-33==F['net_earnings_to_common_adjusted'] and 6563-224-74==F['operating_income_adjusted'] and 112694+21==F['revenue_adjusted'])
cash=OFFICIAL['derived_calculations']['quarterly_cash_flows']['q3_2026']
check('evidence:quarterly_cashflow_from_ytd',cash['cfo']==OFFICIAL['consolidated']['nine_months_2026']['cfo']-OFFICIAL['consolidated']['six_months_2026']['cfo'] and cash['capex']==OFFICIAL['consolidated']['nine_months_2026']['capex_property_equipment_capitalized_software']-OFFICIAL['consolidated']['six_months_2026']['capex_property_equipment_capitalized_software'] and cash['fcf']==cash['cfo']-cash['capex'])
check('evidence:consensus_target_return',round((TARGET/PRICE-1)*100,1)==ANR['return_potential_displayed_pct'])
check('evidence:broker_order_and_rating_basis',[b['firm'] for b in BROKERS]==['UBS','Morgan Stanley','Goldman Sachs'] and BROKERS[1]['rating_raw']=='Overwt/In-Line' and BROKERS[1]['rating_standardized']=='Overweight')
check('evidence:peer_common_fy2027_multiples',all(BLOOMBERG['EEO'][ticker]['multiples']['pe_adj_plus'][3]==v for ticker,v in PEER_VALUES.items()))
for file in ['mu.html','mu-sc.html','mu-en.html']:
    check('canonical_template:'+file,(ROOT/file).read_text()==oldfile(file))
tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
infrastructure=[file for file in tracked if file.startswith('api/') or file in ['CNAME','disclaimer.html','vercel.json','package.json','package-lock.json']]
check('protected_files:infrastructure_exact',all((ROOT/file).read_text()==oldfile(file) for file in infrastructure),infrastructure)
index_source,old_index_source=(ROOT/'index.html').read_text(),oldfile('index.html')
index,old_index=map(html.fromstring,[index_source,old_index_source])
def homepage_cards(doc):
    return doc.xpath('//div[contains(@onclick,"window.location.href=")]')
def card_ticker(card):
    return text(card.xpath('.//h3')[0])
cards,old_cards=homepage_cards(index),homepage_cards(old_index)
order,old_order=list(map(card_ticker,cards)),list(map(card_ticker,old_cards))
check('homepage:unh_first_25_cards_other_order_preserved',len(cards)==25 and order[0]=='UNH' and [t for t in order if t!='UNH']==[t for t in old_order if t!='UNH'],order)
def raw_homepage_blocks(source):
    pattern=r'<div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm card-hover flex flex-col h-full cursor-pointer group" onclick="window.location.href=\'([^\']+)\'">'
    starts=list(re.finditer(pattern,source))
    end=source.index('</div>\n</main>',starts[-1].start())
    blocks={m[1]:source[m.start():starts[i+1].start() if i+1<len(starts) else end] for i,m in enumerate(starts)}
    return source[:starts[0].start()],blocks,source[end:]
prefix,raw_cards,suffix=raw_homepage_blocks(index_source)
old_prefix,old_raw_cards,old_suffix=raw_homepage_blocks(old_index_source)
check('homepage:other_24_card_blocks_byte_exact',len(raw_cards)==25 and all(block==old_raw_cards[file] for file,block in raw_cards.items() if file!='unh.html'))
check('homepage:outside_card_region_byte_exact',prefix==old_prefix and suffix==old_suffix)
unh_card=text(next(card for card in cards if card_ticker(card)=='UNH'))
check('homepage:updated_date_target_return',all(value in unh_card for value in ['2026年10月14日更新','476.93','26.3%']))
ordering=json.loads((ROOT/'research/homepage-earnings-order-2026-10-08.json').read_text())
ordered_records=sorted(ordering['records'],key=lambda row:row['position'])
dates=[row['earnings_publication_date'] for row in ordered_records]
check('homepage:earnings_date_ledger',[row['ticker'] for row in ordered_records]==order and dates==sorted(dates,reverse=True) and ordered_records[0]['earnings_publication_date']=='2026-10-13')
changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
check('scope:only_unh_and_homepage_html',all(not file.endswith('.html') or file in FILES+['index.html'] for file in changed),changed)
check('scope:no_source_screenshots',not any(re.search(r'(?:UNH|ELV|HUM|CNC).*(?:EEO|ANR).*\.(?:png|jpe?g)$',file,re.I) for file in tracked+changed))
whitespace=subprocess.run(['git','-c','core.whitespace=cr-at-eol','diff','--check'],cwd=ROOT,capture_output=True,text=True)
check('git_diff_whitespace',whitespace.returncode==0,whitespace.stdout+whitespace.stderr or None)
report={'report':'UNH Q3 2026 evidence and MU-template validation','checked_on':'2026-10-14','base_commit':BASE,
        'status':'pass' if all(row['status']=='pass' for row in CHECKS) else 'fail','checks':CHECKS,'page_details':DETAILS,
        'limitations':['Mock VM checks are not real-browser rendering or live Chart.js rasterization.',
                      'No live AI call, PI acceptance, PI storage write, modal removal/hiding or access-control bypass was performed.',
                      'PI legal DOM, acceptance/API functions, initial gate and disclaimer loader/error handling are compared with the base UNH files; whitespace is normalized.',
                      'Authoritative-source and screenshot review is recorded in the source ledger; this script reconciles implementation to that evidence.',
                      'Bloomberg ANR is dated 2026/10/14; On13-Oct reference price is not independently established as official close. EEO is post-release, not archived prerelease consensus.',
                      'FY2027 Adj+ P/E shares a calendar year, but company adjustments and business mixes differ.',
                      'Real-browser and deployed HTTP content checks, if performed, are separately documented in the release workflow.']}
destination=ROOT/'research/unh-2026-q3-validation.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
failed=[row for row in CHECKS if row['status']=='fail']
print(json.dumps({'status':report['status'],'checks':len(CHECKS),'failed':failed,'output':str(destination)},ensure_ascii=False,indent=2))
raise SystemExit(bool(failed))
