#!/usr/bin/env python3
"""META Q3 2026 evidence/template regression checks.

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
BASE = '481c4ce08feef7b9ac53f156e0270412ada4e23b'
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



for file in FILES:
 source=(ROOT/file).read_text(); prior=oldfile(file);template=(ROOT/file.replace('meta','mu')).read_text()
 doc,old,mu=map(html.fromstring,[source,prior,template])
 check(file+':six_tabs_three_charts',doc.xpath('//section/@id')==TABS and doc.xpath('//canvas/@id')==CANVASES)
 check(file+':unique_ids',len(doc.xpath('//@id'))==len(set(doc.xpath('//@id'))))
 check(file+':language_links',doc.xpath('//select/option/@value')==FILES and doc.xpath('//select/option[@selected]/@value')==[file])
 check(file+':styles_fonts_dependencies_match_mu',doc.xpath('//style/text()')==mu.xpath('//style/text()') and doc.xpath('//head/link/@href')==mu.xpath('//head/link/@href') and doc.xpath('//script/@src')==mu.xpath('//script/@src'))
 for id in ['pi-modal','disclaimer']:check(file+':protected_'+id,protected_dom(doc,id)==protected_dom(old,id))
 # Financial note is an explicitly added company-basis explanation; rating color and negative-number text colors may differ.
 def layout_sig(d):
  d=copy.deepcopy(d)
  for el in d.xpath('//script|//*[@id="pi-modal"]|//*[@id="disclaimer"]|//section[@id="financials"]/div[contains(@class,"mt-6")]/p'):el.getparent().remove(el)
  result=[]
  for el in d.iter():
   if not isinstance(el.tag,str):continue
   a=dict(el.attrib)
   if el.tag=='option':a['value']=a.get('value','').replace('mu','meta')
   if 'class' in a:a['class']=re.sub(r'(?:text-(?:slate|emerald|purple|blue)-(?:500|600|700|800)|bg-(?:slate|emerald|blue)-100)','COLOR',a['class'])
   result.append((el.tag,sorted(a.items()),len([c for c in el if isinstance(c.tag,str)])))
  return result
 check(file+':mu_layout_structure',layout_sig(doc)==layout_sig(mu))
 check(file+':no_stale_micron_or_old_targets',not re.search(r'\bMU\b|Micron|美光|CMBU|CDBU|1,621|417\.17|374\.01|2026/07/23|memory semiconductor',source))
 check(file+':four_views_four_kpis_five_rows',len(doc.xpath('//section[@id="our-comments"]//li'))==4 and len(doc.xpath('//section[@id="financials"]/div[contains(@class,"lg:grid-cols-4")]/div'))==4 and len(doc.xpath('//tbody/tr'))==5)
 table=[[numbers(text(td)) for td in tr.xpath('./td')[1:]] for tr in doc.xpath('//tbody/tr')];TABLES.append(table)
 expected=[[[51242],[64601],[26.1]],[[20535],[12988],[-36.8]],[[2709],[9860],[]],[[1.05],[3.83],[-3.57]],[[29999,19374,10625],[32786,34906,-2120],[80.2]]]
 check(file+':official_table_values',table==expected,table if table!=expected else None)
 check(file+':broker_order_ratings_targets',all(name in text(card) and 'Buy' in text(card) and target in numbers(text(card)) and 'bg-emerald-100 text-emerald-800' in card.xpath('.//span')[0].get('class','') for card,name,target in zip(doc.xpath('//section[@id="street-comments"]//div[contains(@class,"metric-card")]'),['UBS','Citi','Jefferies'],[884,895,875])))
 check(file+':risk_styles',all(x.get('class')=='text-base' for x in doc.xpath('//section[@id="risks"]//strong')))
 try:
  result=run_vm(file,source,doc); prior_vm=run_vm(file,prior,old,True);mu_vm=run_vm('mu',template,mu,True);RUNTIMES[file]=result
  check(file+':JS_mock_execution',True)
  check(file+':chart_keys_tabs_resize',result['keys']==KEYS and all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']]==[1,1,1])
  check(file+':PI_gate_never_accepted',result['storageWrites']==0 and result['piVisible'] and result['bodyLocked'])
  check(file+':disclaimer_loaded_no_live_AI',result['disclaimerLoaded'] and result['fetches']==['disclaimer.html'])
  check(file+':protected_PI_API_functions',all(normalize_function(result['functions'][n])==normalize_function(prior_vm['functions'][n]) for n in ['acceptPI','declinePI','callGeminiAPI']))
  check(file+':protected_disclaimer_loader',normalize_function(result['loader'])==normalize_function(prior_vm['loader']))
  names=['switchTab','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']
  check(file+':MU_frontend_functions',all(normalize_function(result['functions'][n])==normalize_function(mu_vm['functions'][n]) for n in names))
  check(file+':MU_tooltip_listeners',all([normalize_function(v) for v in result['listeners'][n]]==[normalize_function(v) for v in mu_vm['listeners'][n]] for n in ['mouseup','mousedown']))
  charts=[c['config'] for c in result['charts']]
  check(file+':revenue_chart_reconciles',charts[0]['data']['datasets'][0]['data']==[63061,1097,443] and sum(charts[0]['data']['datasets'][0]['data'])==64601)
  check(file+':margin_chart', [d['data'] for d in charts[1]['data']['datasets']]==[[51242,60801,64601],[40,31,20]])
  check(file+':peer_calendar_FY2027_GAAP_values',charts[2]['data']['datasets'][0]['data']==[20.62,21.96,24.30])
  check(file+':AI_facts_and_no_realtime_claim',all(v in result['standardPrompt'] for v in ['2026/10/22','2026/09/30','2026/10/21','No live market','697.52','819.27','20.62']))
 except Exception as e:check(file+':JS_mock_execution',False,str(e))
check('three_language_financial_parity',all(v==TABLES[0] for v in TABLES))
check('fcf_reconciliation',32786-33942-964==-2120 and 29999-18829-545==10625)
check('litigation_operating_income_reconciliation',12988+9890==22878)
check('EEO_FCF_basis_reconciliation',32786-33942==-1156 and -1156-964==-2120)
check('growth_calculations',round((64601/51242-1)*100,1)==26.1 and round((12988/20535-1)*100,1)==-36.8 and round((34906/19374-1)*100,1)==80.2)
a=html.fromstring((ROOT/'index.html').read_text());b=html.fromstring(oldfile('index.html'))
newcards=a.xpath('//div[contains(@class,"card-hover")]');oldcards=b.xpath('//div[contains(@class,"card-hover")]')
check('homepage_META_TSLA_first_preserve_release_date_tie',[x.get('onclick') for x in newcards[:2]]==["window.location.href='meta.html'","window.location.href='tsla.html'"])
check('other_homepage_cards_unchanged',[(x.get('onclick'),html.tostring(x)) for x in newcards if all(t not in x.get('onclick','') for t in ['tsla.html','meta.html'])]==[(x.get('onclick'),html.tostring(x)) for x in oldcards if all(t not in x.get('onclick','') for t in ['tsla.html','meta.html'])])
report={'base_commit':BASE,'status':'local draft only; not committed, pushed or published','checks':CHECKS,'passed':sum(c['status']=='pass' for c in CHECKS),'failed':sum(c['status']=='fail' for c in CHECKS),'limitations':['JavaScript behavior tested in fake DOM without accepting PI or calling live AI.','Real Chromium launch failed before page creation: socket() EPERM in process_singleton_posix. No desktop/mobile visual verification completed.','No official earnings-call transcript used; forward outlook limited to issuer release.']}
(ROOT/'research/meta-2026-q3-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2));raise SystemExit(bool(report['failed']))
