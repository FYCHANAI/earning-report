#!/usr/bin/env python3
"""KO Q3 2026 evidence/template regression checks.

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
BASE = '572a637ff64bb588b54fc733db2958cc84e878fc'
FILES = ['meta.html', 'meta-sc.html', 'meta-en.html']
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
KEYS = ['metaSegment', 'metaProfit', 'metaValuation']
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
    return re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', value)).replace('muSegment', 'metaSegment').replace('muProfit', 'metaProfit').replace('muValuation', 'metaValuation')

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
            attrs['value'] = attrs.get('value', '').replace('mu', 'meta')
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
               'disclaimer': (ROOT/'disclaimer.html').read_text(encoding='utf8'), 'functionsOnly': functions_only,
               'elements': [{'tag': e.tag, **dict(e.attrib)} for e in doc.iter() if isinstance(e.tag, str)]}
    result = subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_NODE', 'node'), '-e', HARNESS],
                            input=json.dumps(payload), capture_output=True, text=True, encoding="utf8", cwd=ROOT)
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



FILES=['ko.html','ko-sc.html','ko-en.html'];KEYS=['koSegment','koProfit','koValuation'];BASE='572a637ff64bb588b54fc733db2958cc84e878fc'
def normalize_function(value):
 return re.sub(r'\s+','',re.sub(r'//[^\n]*','',value)).replace('muSegment','koSegment').replace('muProfit','koProfit').replace('muValuation','koValuation')
def layout_sig(d):
 d=copy.deepcopy(d)
 for el in d.xpath('//script|//*[@id="pi-modal"]|//*[@id="disclaimer"]|//section[@id="financials"]/div[contains(@class,"mt-6")]/p'):el.getparent().remove(el)
 result=[]
 for el in d.iter():
  if not isinstance(el.tag,str):continue
  a=dict(el.attrib)
  if el.tag=='option':a['value']=a.get('value','').replace('mu','ko')
  if 'class' in a:a['class']=re.sub(r'(?:text-(?:slate|emerald|purple|blue)-(?:500|600|700|800)|bg-(?:slate|emerald|blue)-100)','COLOR',a['class'])
  result.append((el.tag,sorted(a.items()),len([c for c in el if isinstance(c.tag,str)])))
 return result
for file in FILES:
 source=(ROOT/file).read_text(encoding='utf8');prior=oldfile(file);template=(ROOT/file.replace('ko','mu')).read_text(encoding='utf8')
 doc,old,mu=map(html.fromstring,[source,prior,template])
 check(file+':six_tabs_three_charts',doc.xpath('//section/@id')==TABS and doc.xpath('//canvas/@id')==CANVASES)
 check(file+':unique_ids',len(doc.xpath('//@id'))==len(set(doc.xpath('//@id'))))
 check(file+':language_links',doc.xpath('//select/option/@value')==FILES and doc.xpath('//select/option[@selected]/@value')==[file])
 check(file+':styles_fonts_dependencies_match_mu',doc.xpath('//style/text()')==mu.xpath('//style/text()') and doc.xpath('//head/link/@href')==mu.xpath('//head/link/@href') and doc.xpath('//script/@src')==mu.xpath('//script/@src'))
 for id in ['pi-modal','disclaimer']:check(file+':protected_'+id,protected_dom(doc,id)==protected_dom(old,id))
 check(file+':mu_layout_structure',layout_sig(doc)==layout_sig(mu))
 check(file+':no_stale_MU_Q2_data',not re.search(r'\bMU\b|Micron|美光|CMBU|CDBU|1,621|92\.64|88\.27|2026/07/29|FY2026 Est Forward|26\.88|\$0\.97|NTAM 計算|NTAM calculation|本站統一分類',source))
 check(file+':four_views_four_kpis_five_rows',len(doc.xpath('//section[@id="our-comments"]//li'))==4 and len(doc.xpath('//section[@id="financials"]/div[contains(@class,"lg:grid-cols-4")]/div'))==4 and len(doc.xpath('//tbody/tr'))==5)
 table=[[numbers(text(td)) for td in tr.xpath('./td')[1:]] for tr in doc.xpath('//tbody/tr')];TABLES.append(table)
 expected=[[[13380],[13354],[7,8]],[[4465],[4397],[12,11]],[[33.37],[32.93],[106]],[[0.93],[0.91],[8,11]],[[12471,1063],[11408],[13000]]]
 check(file+':official_table_values',table==expected,table if table!=expected else None)
 check(file+':broker_order_ratings_targets',all(name in text(card) and rating in text(card) and target in numbers(text(card)) and color in card.xpath('.//span')[0].get('class','') for card,name,rating,target,color in zip(doc.xpath('//section[@id="street-comments"]//div[contains(@class,"metric-card")]'),['UBS','Morgan Stanley','JP Morgan'],['Buy','Overweight','Overweight'],[106,100,98],['bg-emerald-100 text-emerald-800','bg-blue-100 text-blue-800','bg-blue-100 text-blue-800'])))
 check(file+':risk_styles',all(x.get('class')=='text-base' for x in doc.xpath('//section[@id="risks"]//strong')))
 check(file+':internal_links_exist',all((ROOT/p).exists() for p in doc.xpath('//a/@href|//option/@value') if not p.startswith(('http','#'))))
 try:
  result=run_vm(file,source,doc);prior_vm=run_vm(file,prior,old,True);mu_vm=run_vm('mu',template,mu,True);RUNTIMES[file]=result
  check(file+':JS_mock_execution',True)
  check(file+':chart_keys_tabs_resize',result['keys']==KEYS and all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']]==[1,1,1])
  check(file+':PI_gate_never_accepted',result['storageWrites']==0 and result['piVisible'] and result['bodyLocked'])
  check(file+':disclaimer_loaded_no_live_AI',result['disclaimerLoaded'] and result['fetches']==['disclaimer.html'])
  check(file+':protected_PI_API_functions',all(normalize_function(result['functions'][n])==normalize_function(prior_vm['functions'][n]) for n in ['acceptPI','declinePI','callGeminiAPI']))
  check(file+':protected_disclaimer_loader',normalize_function(result['loader'])==normalize_function(prior_vm['loader']))
  check(file+':MU_frontend_functions',all(normalize_function(result['functions'][n])==normalize_function(mu_vm['functions'][n]) for n in ['switchTab','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']))
  check(file+':MU_tooltip_listeners',all([normalize_function(v) for v in result['listeners'][n]]==[normalize_function(v) for v in mu_vm['listeners'][n]] for n in ['mouseup','mousedown']))
  charts=[c['config'] for c in result['charts']]
  check(file+':regional_growth_chart',[d['data'] for d in charts[0]['data']['datasets']]==[[7,16,3,6,12],[5,6,0,6,8]])
  check(file+':revenue_margin_chart',[d['data'] for d in charts[1]['data']['datasets']]==[[12455,13380],[31.97,33.37],[31.87,32.93]])
  check(file+':FY2027_peer_values',charts[2]['data']['datasets'][0]['data']==[25.87,17.76,15.55,13.61])
  check(file+':AI_facts_no_live_claim',all(v in result['standardPrompt'] for v in ['2026/10/28','2026/10/02','2026/10/27','No live market','91.18','97.80','25.87','11408','not quarterly']))
 except Exception as e:check(file+':JS_mock_execution',False,str(e))
check('three_language_financial_parity',all(v==TABLES[0] for v in TABLES))
check('YTD_FCF_math',12471-1063==11408)
check('margins_rounding',round(4465/13380*100,2)==33.37 and round(4397/13354*100,2)==32.93 and round(3982/12455*100,2)==31.97 and round(3957/12412*100,2)==31.88)
# Issuer margin reconciliation reports prior comparable margin31.87 and current32.93; issuer's 106bp is retained, while rounded dollar inputs yield31.88. This rounding is documented, not overwritten.
check('target_returns',[round((x/91.18-1)*100,1) for x in [97.8,106,100,98]]==[7.3,16.3,9.7,7.5])
a=html.fromstring((ROOT/'index.html').read_text(encoding='utf8'));b=html.fromstring(oldfile('index.html'))
newcards=a.xpath('//div[contains(@class,"card-hover")]');oldcards=b.xpath('//div[contains(@class,"card-hover")]')
check('homepage_KO_first',newcards[0].get('onclick')=="window.location.href='ko.html'")
check('homepage_other24_unchanged',[(x.get('onclick'),html.tostring(x,with_tail=False)) for x in newcards if 'ko.html' not in x.get('onclick','')]==[(x.get('onclick'),html.tostring(x,with_tail=False)) for x in oldcards if 'ko.html' not in x.get('onclick','')])
check('homepage_KO_current',all(s in text(newcards[0]) for s in ['Q3','2026年10月28日','97.80','91.18','7.3%']))
for file in ['mu.html','mu-sc.html','mu-en.html','CNAME','disclaimer.html','api/gemini.js']:
 if (ROOT/file).exists():check('unchanged:'+file,(ROOT/file).read_bytes().replace(b'\r\n',b'\n')==subprocess.check_output(['git','show',f'{BASE}:{file}'],cwd=ROOT).replace(b'\r\n',b'\n'))
report={'base_commit':BASE,'status':'Local draft only; not pushed or published','checks':CHECKS,'passed':sum(c['status']=='pass' for c in CHECKS),'failed':sum(c['status']=='fail' for c in CHECKS),'limitations':['Source PNGs were visually inspected by parent in cloud; local supported materialization failed on Windows os.setxattr. No original screenshot is committed.','Runtime checks use fake DOM and Chart instances. No PI acceptance, storage bypass or live AI call.','Actual browser observations recorded separately.']}
(ROOT/'research/ko-2026-q3-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'passed':report['passed'],'failed':report['failed'],'failures':[c for c in CHECKS if c['status']=='fail']},ensure_ascii=False,indent=2));raise SystemExit(bool(report['failed']))
