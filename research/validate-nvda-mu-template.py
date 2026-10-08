#!/usr/bin/env python3
"""Validate the explicitly authorized MU-template migration of NVDA.

This supersedes the seven-tab preservation check for this layout migration.
Checks use the committed evidence ledger and corresponding MU language files.
Node VM checks are mocked, not real-browser rendering or live-AI verification.
The PI gate is never accepted, hidden, removed or bypassed.
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
BASE = '2eba1f5cf35cb2da6031d7c82061f1e19c6a31e5'
LEDGER = json.loads((ROOT/'research/nvda-fy2027-q2-2026-10-08.json').read_text())
F = LEDGER['official_company_evidence']['financials_comparable']
P = F['market_platforms']
FILES = ['nvda.html','nvda-sc.html','nvda-en.html']
TABS = ['our-comments','financials','valuation','street-comments','risks','disclaimer']
CANVASES = ['segmentRevenueChart','profitabilityChart','valuationChart']
KEYS = ['nvdaSegment','nvdaProfit','nvdaValuation']
CHECKS, DETAILS, RUNTIMES = [], {}, {}


def check(name, ok, detail=None):
    result = {'check':name,'status':'pass' if ok else 'fail'}
    if detail is not None:
        result['detail'] = detail
    CHECKS.append(result)


def oldfile(file):
    return subprocess.check_output(['git','show',f'{BASE}:{file}'],cwd=ROOT,text=True)


def text(element):
    return ' '.join(element.text_content().split())


def scripts(source):
    return re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',source)


def numbers(value):
    return [float(n.replace(',','')) for n in re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?',value)]


def signature(doc):
    """Ignore company prose; compare exact layout attributes and nesting."""
    doc = copy.deepcopy(doc)
    for e in doc.xpath('//script | //*[@id="pi-modal"]'):
        e.getparent().remove(e)
    records=[]
    for e in doc.iter():
        if not isinstance(e.tag,str):
            continue
        attrs=dict(e.attrib)
        if e.tag=='option':
            attrs['value']=attrs.get('value','').replace('mu','nvda')
        if e.tag=='span' and 'text-xs font-bold px-2 py-1 rounded' in attrs.get('class',''):
            attrs['class']=re.sub(r'(?:bg-(?:blue|emerald|slate|pink|red)-100|text-(?:blue-800|emerald-800|slate-600|pink-700|red-600))','RATING_COLOR',attrs['class'])
        records.append((e.tag,sorted(attrs.items()),len([c for c in e if isinstance(c.tag,str)])))
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
 for(const fn of events.DOMContentLoaded||[])fn();
 await Promise.resolve();await Promise.resolve();await Promise.resolve();await Promise.resolve();
 if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate inactive');
 const buttons=elements.filter(e=>e.classList.contains('tab-btn')),tabs=[];
 for(let i=0;i<input.tabs.length;i++){
  // This is a pure-function unit check on fake nodes; the PI gate stays active.
  context.switchTab({currentTarget:buttons[i]},input.tabs[i]);
  const active=elements.filter(e=>e.classList.contains('tab-content')&&e.classList.contains('active')).map(e=>e.id);
  tabs.push({id:input.tabs[i],ok:active.length===1&&active[0]===input.tabs[i]&&buttons.filter(e=>e.classList.contains('active')).length===1&&buttons[i].classList.contains('active')});
  if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate altered');
 }
 const functions={};for(const name of ['switchTab','acceptPI','declinePI','callGeminiAPI','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']){
  functions[name]=context[name].toString();
 }
 process.stdout.write(JSON.stringify({charts,keys:Object.keys(sandbox.window.charts),tabs,fetches,storageWrites,
  piVisible:ids['pi-modal'].style.display==='flex',bodyLocked:body.style.overflow==='hidden',
  disclaimerLoaded:ids['disclaimer-container'].innerHTML===input.disclaimer,
  standardPrompt:vm.runInContext('standardPrompt',context),functions}));
})().catch(e=>{console.error(e.stack);process.exit(1)});
"""


def run_vm(file,source,doc):
    payload={'file':file,'scripts':scripts(source),'tabs':TABS,'disclaimer':(ROOT/'disclaimer.html').read_text(),
             'elements':[{'tag':e.tag,**dict(e.attrib)} for e in doc.iter() if isinstance(e.tag,str)]}
    result=subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_NODE','node'),'-e',HARNESS],input=json.dumps(payload),capture_output=True,text=True,cwd=ROOT)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def normalized_function(value):
    return re.sub(r'\s+','',value).replace('muSegment','nvdaSegment').replace('muProfit','nvdaProfit').replace('muValuation','nvdaValuation')


for file in FILES:
    source=(ROOT/file).read_text()
    template_name=file.replace('nvda','mu')
    template=(ROOT/template_name).read_text()
    prior=oldfile(file)
    doc,mu,old=map(html.fromstring,[source,template,prior])
    check(file+':mu_structure_and_layout_attributes',signature(doc)==signature(mu))
    check(file+':mu_styles_fonts_and_script_versions',doc.xpath('//style/text()')==mu.xpath('//style/text()') and
          doc.xpath('//head/link/@href')==mu.xpath('//head/link/@href') and doc.xpath('//script/@src')==mu.xpath('//script/@src'))
    check(file+':six_tabs',doc.xpath('//section/@id')==TABS and doc.xpath('//nav/button/@onclick')==[f"switchTab(event, '{tab}')" for tab in TABS])
    check(file+':no_dead_sandbox',not re.search(r'sandbox|generateCustomScenario|custom-scenario|scenario-loading|scenario-result',source,re.I))
    check(file+':three_chart_containers',doc.xpath('//canvas/@id')==CANVASES and len(doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," chart-container ")]'))==3)
    ids=doc.xpath('//@id')
    check(file+':unique_ids',len(ids)==len(set(ids)))
    check(file+':language_links',set(doc.xpath('//select/option/@value'))==set(FILES))
    pi_new,pi_old=doc.get_element_by_id('pi-modal'),old.get_element_by_id('pi-modal')
    check(file+':nvda_pi_legal_dom_exact',html.tostring(pi_new,with_tail=False)==html.tostring(pi_old,with_tail=False))
    rating_word={'nvda.html':'買入','nvda-sc.html':'买入','nvda-en.html':'Buy'}[file]
    check(file+':header_consensus_preserved','323.89' in text(doc.xpath('//header')[0]) and rating_word in text(doc.xpath('//header')[0]))
    forbidden=r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|SCAs|1-gamma|G9 NAND|Kioxia|SK Hynix|Samsung|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|33\.42'
    remnants=re.findall(forbidden,source,re.I)
    check(file+':no_micron_entities_or_distinctive_values',not remnants,remnants)
    views=text(doc.get_element_by_id('our-comments'))
    check(file+':research_dates_preserved',all(v in views for v in ['2026/07/26','2026/08/26','2026/10/08']))
    table=doc.get_element_by_id('financials').xpath('.//table')[0]
    rows=table.xpath('.//tbody/tr')
    check(file+':four_column_five_row_table',len(table.xpath('.//thead/tr/th'))==4 and len(rows)==5 and all(len(r.xpath('./td'))==4 for r in rows))
    expected_rows=[([F['revenue'][0]],[F['revenue'][0]],[(F['revenue'][0]/F['revenue'][1]-1)*100]),
                   ([F['gaap_gross_profit'][0],F['gaap_gross_margin_percent'][0]],[F['non_gaap_gross_profit'][0],F['non_gaap_gross_margin_percent'][0]],[F['non_gaap_gross_margin_percent'][0]-F['non_gaap_gross_margin_percent'][1]]),
                   ([F['gaap_operating_income'][0]],[F['non_gaap_operating_income'][0]],[(F['non_gaap_operating_income'][0]/F['non_gaap_operating_income'][1]-1)*100,(F['non_gaap_operating_income'][0]/F['non_gaap_operating_income'][2]-1)*100]),
                   ([F['gaap_net_income'][0]],[F['non_gaap_net_income'][0]],[(F['non_gaap_net_income'][0]/F['non_gaap_net_income'][1]-1)*100]),
                   ([F['gaap_diluted_eps'][0]],[F['non_gaap_diluted_eps'][0]],[F['operating_cash_flow'][0]])]
    table_evidence=[]
    for row,expected in zip(rows,expected_rows):
        observed=[numbers(text(td)) for td in row.xpath('./td')[1:]]
        expected=[expected[0],expected[1],[round(v,1) for v in expected[2]]]
        table_evidence.append({'observed':observed,'expected':expected,'ok':observed==expected})
    check(file+':gaap_nongaap_table_and_qoq_math',len(table_evidence)==5 and all(v['ok'] for v in table_evidence),table_evidence)
    street=doc.get_element_by_id('street-comments')
    cards=street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
    broker_checks=[]
    for card,b in zip(cards,LEDGER['bloomberg_anr']['brokers']):
        rating=card.xpath('.//span')[0]
        color='bg-blue-100 text-blue-800' if b['display_rating']=='Overweight' else 'bg-emerald-100 text-emerald-800'
        body=text(card)
        ret=(b['target_usd']/LEDGER['bloomberg_anr']['reference_price']-1)*100
        broker_checks.append(b['firm'] in text(card.xpath('.//h3')[0]) and text(rating)==b['display_rating'] and
                             color in rating.get('class') and b['analyst'] in body and f"{b['target_usd']:.2f}" in body and
                             b['rating_date'].replace('-','/') in body and f'{ret:.1f}%' in body)
    check(file+':brokers_facts_priority_returns_colors',len(cards)==3 and len(broker_checks)==3 and all(broker_checks))
    sourcelines=[text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
    check(file+':compact_anr_source',len(sourcelines)==1 and all(v in sourcelines[0] for v in ['2026/10/08','10/07','237.47']),sourcelines)
    try:
        result=run_vm(file,source,doc)
        mu_result=run_vm(template_name,template,mu)
        RUNTIMES[file]=result
        check(file+':inline_js_syntax_and_mock_execution',True)
        check(file+':chart_cache_keys',result['keys']==KEYS,result['keys'])
        check(file+':tab_and_chart_resize_behavior',all(t['ok'] for t in result['tabs']) and
              [c['resizeCalls'] for c in result['charts']]==[1,1,1])
        check(file+':pi_never_accepted_hidden_or_storage_written',result['storageWrites']==0 and result['piVisible'] and result['bodyLocked'])
        prior_pi_functions={name:re.search(r'function '+name+r'\([^)]*\)\s*\{[^}]*\}',prior).group(0) for name in ['acceptPI','declinePI']}
        check(file+':original_nvda_pi_functions_preserved',all(normalized_function(result['functions'][name])==normalized_function(value) for name,value in prior_pi_functions.items()))
        check(file+':disclaimer_loaded_no_api_or_live_network',result['fetches']==['disclaimer.html'] and result['disclaimerLoaded'])
        fixed=['switchTab','callGeminiAPI','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']
        check(file+':mu_fixed_interaction_and_api_functions',all(normalized_function(result['functions'][k])==normalized_function(mu_result['functions'][k]) for k in fixed))
        check(file+':dated_company_ai_context','2026/10/08' in result['standardPrompt'] and 'NVDA' in result['standardPrompt'] and not re.search(forbidden,result['standardPrompt'],re.I))
        configs={c['canvasId']:c['config'] for c in result['charts']}
        segment=configs['segmentRevenueChart']
        profit=configs['profitabilityChart']
        valuation=configs['valuationChart']
        check(file+':market_platform_revenue_chart',segment['data']['datasets'][0]['data']==[P['data_center'][0],P['edge_computing'][0]] and segment['type']=='doughnut')
        check(file+':breakdown_chart_no_invented_margin',profit['type']=='bar' and len(profit['data']['datasets'])==1 and
              profit['data']['datasets'][0]['data']==[P['hyperscale'][0],P['ai_clouds_industrial_enterprise'][0],P['edge_computing'][0]] and
              'percentageAxis' not in json.dumps(profit))
        labels=valuation['data']['labels'];values=valuation['data']['datasets'][0]['data']
        mapped={next((ticker for ticker in ['INTC','AMD','AVGO','NVDA'] if ticker in label),'UNKNOWN'):value for label,value in zip(labels,values)}
        check(file+':peer_valuation_matches_eeo',mapped=={ticker:row['forward_pe_adj'] for ticker,row in LEDGER['bloomberg_eeo']['peers'].items()})
        DETAILS[file]={'sha256':hashlib.sha256(source.encode()).hexdigest(),'mock_runtime':result}
    except Exception as exc:
        check(file+':inline_js_syntax_and_mock_execution',False,str(exc))

styles=[[[{k:v for k,v in d.items() if k!='label'} for d in c['config']['data']['datasets']] for c in r['charts']] for r in RUNTIMES.values()]
check('three_languages:chart_dataset_styles_and_values',len(styles)==3 and all(v==styles[0] for v in styles))
numeric=[[[d['data'] for d in c['config']['data']['datasets']] for c in r['charts']] for r in RUNTIMES.values()]
check('three_languages:chart_numeric_arrays',len(numeric)==3 and all(v==numeric[0] for v in numeric))
protected=['index.html','mu.html','mu-sc.html','mu-en.html','CNAME','disclaimer.html','api/gemini.js','vercel.json','package.json','research/nvda-fy2027-q2-2026-10-08.json']
existing=[f for f in protected if (ROOT/f).exists()]
check('protected_files_exactly_unchanged',all((ROOT/f).read_text()==oldfile(f) for f in existing),existing)
migration=json.loads((ROOT/'research/nvda-mu-template-migration-2026-10-08.json').read_text())
check('migration_ledger:protected_hashes',all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==digest for f,digest in migration['protected_files'].items()))
check('migration_ledger:template_hashes',all(hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256'] for row in migration['canonical_templates']))
display=migration['new_financial_display']
column_map={'revenue':('revenue','revenue'),'gross_profit':('gaap_gross_profit','non_gaap_gross_profit'),
            'gross_margin_percent':('gaap_gross_margin_percent','non_gaap_gross_margin_percent'),
            'operating_income':('gaap_operating_income','non_gaap_operating_income'),
            'net_income':('gaap_net_income','non_gaap_net_income'),'diluted_eps':('gaap_diluted_eps','non_gaap_diluted_eps')}
check('migration_ledger:financial_columns_match_evidence',all(display['gaap_and_non_gaap_columns'][k]==[F[fields[0]][0],F[fields[1]][0]] for k,fields in column_map.items()) and
      display['operating_cash_flow']==F['operating_cash_flow'][0] and display['free_cash_flow']==F['free_cash_flow'][0])
qoq={'revenue':round((F['revenue'][0]/F['revenue'][1]-1)*100,1),
     'gross_margin_percentage_points':round(F['non_gaap_gross_margin_percent'][0]-F['non_gaap_gross_margin_percent'][1],1),
     'operating_income':round((F['non_gaap_operating_income'][0]/F['non_gaap_operating_income'][1]-1)*100,1),
     'net_income':round((F['non_gaap_net_income'][0]/F['non_gaap_net_income'][1]-1)*100,1)}
check('migration_ledger:qoq_math',display['non_gaap_qoq_percent']==qoq)
changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
check('html_scope_nvda_only',all(not f.endswith('.html') or f in FILES for f in changed),changed)
whitespace=subprocess.run(['git','diff','--check'],cwd=ROOT,capture_output=True,text=True)
check('git_diff_whitespace',whitespace.returncode==0,whitespace.stdout+whitespace.stderr)
report={'report':'NVDA migration to corresponding MU three-language template','checked_on':'2026-10-08','base_commit':BASE,
        'authorization':'Explicit owner instruction to use the latest MU layout for NVDA and future reports; supersedes seven-tab preservation.',
        'status':'pass' if all(c['status']=='pass' for c in CHECKS) else 'fail','checks':CHECKS,'page_details':DETAILS,
        'limitations':['Node checks use a fake DOM, fake Chart constructor and local disclaimer response; they are not real-browser visual verification.',
                       'No live AI/network call, PI acceptance, PI storage write, modal hiding/removal or access-control bypass was performed.',
                       'Desktop/mobile content rendering and actual Chart.js rasterization remain unverified behind the PI gate. Visible-gate browser screenshots do not validate hidden report content.',
                       'Primary-source and Bloomberg authenticity review is recorded in the existing research ledger; this check independently reconciles implementation to that evidence.']}
destination=ROOT/'research/nvda-mu-template-validation-2026-10-08.json'
destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
failed=[c for c in CHECKS if c['status']=='fail']
print(json.dumps({'status':report['status'],'checks':len(CHECKS),'failed':failed,'output':str(destination)},ensure_ascii=False,indent=2))
raise SystemExit(bool(failed))
