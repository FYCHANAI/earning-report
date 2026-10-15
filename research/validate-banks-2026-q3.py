#!/usr/bin/env python3
"""Independent 15-page bank/MU structural and mock-runtime QA.

The VM never accepts/removes the PI gate, writes PI storage, or calls a live API.
A separate browser check can prove the initial gate but cannot prove access after it.
Run only after the report build; facts come from the independently reviewed ledger.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_BASE = '7c8ee4159563770cfcb953eb50a5a1dfac27347c'
BASE = os.environ.get('BANKS_BASE', UPSTREAM_BASE)
TICKERS = ['jpm', 'c', 'gs', 'bac', 'ms']
SUFFIXES = ['', '-sc', '-en']
FILES = [t+s+'.html' for t in TICKERS for s in SUFFIXES]
TABS = ['our-comments', 'financials', 'valuation', 'street-comments', 'risks', 'disclaimer']
CANVASES = ['segmentRevenueChart', 'profitabilityChart', 'valuationChart']
COLORS = {'Overweight':'bg-blue-100 text-blue-800','Buy':'bg-emerald-100 text-emerald-800','Neutral':'bg-slate-100 text-slate-600','Sell':'bg-pink-100 text-pink-700','Underweight':'bg-red-100 text-red-600'}
PEERS = {'C':9.46,'BAC':9.89,'GS':11.98,'JPM':13.20,'MS':13.30}
PRIORITY = ['UBS','Morgan Stanley','JP Morgan','Citi','HSBC']
SAME_DAY_EXCEPTION = {
    'banks':['jpm','c','gs','bac','ms'],
    'authority':'Owner requested announcement-day rows for all five banks on 2026-10-15.',
    'scope':'Allow release-day ANR rows for all five banks; do not claim verified after-results timing.'
}
FORBIDDEN = r'\bMU\b|Micron|美光|CMBU|CDBU|MCBU|AEBU|\bSCAs\b|1-gamma|G9 NAND|Kioxia|SK Hynix|Samsung|1,621\.44|1621\.44|1,088\.00|1088\.00|54,229|54229|331\.91'
CHECKS, DETAILS, RUNTIMES = [], {}, {}


def check(name, ok, detail=None):
    row = {'check': name, 'status': 'pass' if bool(ok) else 'fail'}
    if detail is not None:
        row['detail'] = detail
    CHECKS.append(row)


def oldfile(file):
    return subprocess.check_output(['git','show',f'{BASE}:{file}'],cwd=ROOT,text=True).replace('\r\n','\n')


def text(element):
    return ' '.join(' '.join(element.itertext()).split())


def scripts(source):
    return re.findall(r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',source)


def numbers(value):
    value=value.replace('−','-').replace('–','-')
    value=re.sub(r'-\s*((?:US)?\$)',r'\1-',value)
    return [float(n.replace(',','')) for n in re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?',value)]


def has_date(value, date):
    year, month, day=date.split('-')
    months=['January','February','March','April','May','June','July','August','September','October','November','December']
    name=months[int(month)-1]
    return any(v.lower() in value.lower() for v in [date,date.replace('-','/'),f'{int(day)} {name} {year}',f'{name} {int(day)}, {year}',f'{year}年{int(month)}月{int(day)}日'])


def direction_numbers(value):
    value=re.sub(r'(?:季減|季减|下降|下跌|減少|减少|下滑|Down)\s*([0-9]+(?:\.[0-9]+)?)',r'-\1',value,flags=re.I)
    return numbers(value)


def norm(value):
    value = re.sub(r'\b(?:mu|jpm|c|gs|bac|ms)(Segment|Profit|Valuation)\b',r'BANK\1',value)
    return re.sub(r'\s+','',value)


def protected_dom(doc,target_id):
    node=copy.deepcopy(doc.get_element_by_id(target_id))
    if target_id=='disclaimer':
        heading=node.xpath('.//h2')[0]
        heading.text=re.sub(r'^(?:VII\.|VI\.|7\.|6\.|七、|六、)','SECTION_NUMBER',heading.text)
    return [(e.tag,sorted(e.attrib.items()),' '.join((e.text or '').split()),' '.join((e.tail or '').split()) if e is not node else '') for e in node.iter() if isinstance(e.tag,str)]


def layout_signature(doc):
    """Allow factual hyperlinks, company filenames, rating colors and directional data colors.

    All other element nesting and layout attributes match the corresponding MU master.
    Protected target legal components are separately compared to baseline.
    """
    doc=copy.deepcopy(doc)
    for element in doc.xpath('//script | //*[@id="pi-modal"] | //*[@id="disclaimer"]'):
        element.getparent().remove(element)
    for element in doc.xpath('//section//a'):
        element.drop_tag()
    # Bank-specific evidence note and a different number of financial rows are
    # explicitly permitted; table layout/data is checked independently below.
    for element in doc.xpath('//section[@id="financials"]/div[contains(@class,"mt-6")]/p'):
        element.getparent().remove(element)
    for element in doc.xpath('//section[@id="financials"]//tbody'):
        for child in list(element): element.remove(child)
    # Broker availability changes the content/grid count, not the shell. The
    # source heading is retained here, and actual cards are audited separately.
    street=doc.get_element_by_id('street-comments')
    for child in list(street)[1:]: street.remove(child)
    result=[]
    for element in doc.iter():
        if not isinstance(element.tag,str):continue
        attrs=dict(element.attrib)
        if element.tag=='option':attrs['value']=re.sub(r'^(?:mu|jpm|c|gs|bac|ms)', 'BANK',attrs.get('value',''))
        classes=attrs.get('class','')
        if element.tag=='span' and 'text-xs font-bold px-2 py-1 rounded' in classes:
            classes=re.sub(r'\b(?:bg-(?:blue|emerald|slate|pink|red)-100|text-(?:blue-800|emerald-800|slate-600|pink-700|red-600))\b','RATING_COLOR',classes)
        # Direction colors may differ only in KPI supplementary values/table data.
        if element.tag in ['td','th','p'] and element.xpath('ancestor::section[@id="financials"]'):
            classes=re.sub(r'\btext-(?:emerald|red|slate|blue|purple|amber)-(?:400|500|600)\b','DATA_COLOR',classes)
        if 'class' in attrs:attrs['class']=classes
        result.append((element.tag,sorted(attrs.items()),len([c for c in element if isinstance(c.tag,str)])))
    return result


HARNESS=r"""
const fs=require('fs'),vm=require('vm'),input=JSON.parse(fs.readFileSync(0,'utf8'));
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
 querySelectorAll(selector){if(!['.tab-content','.tab-btn'].includes(selector))throw Error('Unmocked selector');return elements.filter(e=>e.classList.contains(selector.slice(1)))}};
const sandbox={document,window:{},console,
 sessionStorage:{getItem(){return null},setItem(){storageWrites++;throw Error('PI acceptance forbidden')}},
 Chart:function(ctx,config){this.canvasId=ctx.canvasId;this.config=config;this.resizeCalls=0;this.resize=()=>this.resizeCalls++;charts.push(this)},
 fetch:async url=>{fetches.push(url);if(url!=='disclaimer.html')throw Error('Network/API request forbidden');return{ok:!input.disclaimerFailure,text:async()=>input.disclaimer}}};
const context=vm.createContext(sandbox);
(async()=>{
 for(let i=0;i<input.scripts.length;i++)new vm.Script(input.scripts[i],{filename:input.file+':inline-'+i}).runInContext(context);
 const functions={};for(const name of ['switchTab','acceptPI','declinePI','callGeminiAPI','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','explainSelectedTerm','closeExplainModal']){
  if(typeof context[name]!=='function')throw Error('Missing function '+name);functions[name]=context[name].toString();
 }
 const domListener=events.DOMContentLoaded[0].toString();
 const loader=domListener.slice(domListener.indexOf("fetch('disclaimer.html')")).replace(/\s*\}\s*$/,'');
 const gate=domListener.slice(domListener.indexOf("if (!sessionStorage.getItem('pi_agreed'))"),domListener.indexOf('window.charts.')).replace(/\/\/[^\n]*/g,'').trim();
 if(input.functionsOnly){process.stdout.write(JSON.stringify({functions,loader,gate}));return;}
 for(const fn of events.DOMContentLoaded||[])fn();
 for(let i=0;i<10;i++)await Promise.resolve();
 if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate inactive');
 const buttons=elements.filter(e=>e.classList.contains('tab-btn')),tabs=[];
 for(let i=0;i<input.tabs.length;i++){
  // Isolated unit checks on fake nodes only; PI gate remains active throughout.
  context.switchTab({currentTarget:buttons[i]},input.tabs[i]);
  const active=elements.filter(e=>e.classList.contains('tab-content')&&e.classList.contains('active')).map(e=>e.id);
  tabs.push({id:input.tabs[i],ok:active.length===1&&active[0]===input.tabs[i]&&buttons.filter(e=>e.classList.contains('active')).length===1&&buttons[i].classList.contains('active')});
  if(ids['pi-modal'].style.display!=='flex'||body.style.overflow!=='hidden')throw Error('PI gate altered');
 }
 process.stdout.write(JSON.stringify({charts,keys:Object.keys(sandbox.window.charts),tabs,fetches,storageWrites,
 piVisible:ids['pi-modal'].style.display==='flex',bodyLocked:body.style.overflow==='hidden',
 disclaimerLoaded:ids['disclaimer-container'].innerHTML===input.disclaimer,disclaimerHTML:ids['disclaimer-container'].innerHTML,
 standardPrompt:vm.runInContext('standardPrompt',context),functions,loader,gate}));
})().catch(e=>{console.error(e.stack);process.exit(1)});
"""


def run_vm(file,source,doc,functions_only=False,disclaimer_failure=False):
    payload={'file':file,'scripts':scripts(source),'tabs':TABS,'disclaimer':(ROOT/'disclaimer.html').read_text(),
             'functionsOnly':functions_only,'disclaimerFailure':disclaimer_failure,
             'elements':[{'tag':e.tag,**dict(e.attrib)} for e in doc.iter() if isinstance(e.tag,str)]}
    result=subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_NODE','node'),'-e',HARNESS],input=json.dumps(payload),capture_output=True,text=True,cwd=ROOT)
    if result.returncode:raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def broker_canonical(value):
    value=value.replace('J.P. Morgan','JP Morgan').replace('JPMorgan','JP Morgan')
    return re.sub(r'\.{3}$','',value).strip()


def load_facts(paths):
    result={}
    for path in paths:
        data=json.loads(Path(path).read_text())
        for key,value in data.get('banks',data).items():
            if key.lower() in TICKERS:
                value=copy.deepcopy(value)
                value['release_date']=value.get('release_date',value.get('earnings_date'))
                result[key.lower()]=value
    return result


def card_blocks(source):
    pattern=r'<div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm card-hover[^\n]+onclick="window.location.href=\'([^\']+)\'">'
    starts=list(re.finditer(pattern,source))
    end=source.rindex('\n</div>\n</main>')
    blocks={m[1]:source[m.start():starts[i+1].start() if i+1<len(starts) else end].rstrip() for i,m in enumerate(starts)}
    return source[:starts[0].start()],blocks,source[end:]


def validate(args):
    global BASE
    BASE=args.base
    facts=load_facts(args.facts)
    check('evidence:all_five_bank_ledgers_loaded',set(facts)==set(TICKERS),sorted(facts))
    for ticker in args.only:
        bank=facts.get(ticker,{})
        tables=[];risks=[];street_numbers=[];kpi_numbers=[]
        for suffix in SUFFIXES:
            file=ticker+suffix+'.html';template_name='mu'+suffix+'.html'
            source=(ROOT/file).read_text();template=(ROOT/template_name).read_text();prior=oldfile(file)
            doc,mu,old=map(html.fromstring,[source,template,prior])
            locale='sc' if suffix=='-sc' else 'en' if suffix=='-en' else 'tc'
            signature,expected=layout_signature(doc),layout_signature(mu)
            differences=[{'index':i,'bank':a,'mu':b} for i,(a,b) in enumerate(zip(signature,expected)) if a!=b][:8]
            check(file+':mu_structure_layout',signature==expected,{'bank_nodes':len(signature),'mu_nodes':len(expected),'differences':differences} if signature!=expected else None)
            check(file+':mu_styles_fonts_script_versions',doc.xpath('//style/text()')==mu.xpath('//style/text()') and doc.xpath('//head/link/@href')==mu.xpath('//head/link/@href') and doc.xpath('//script/@src')==mu.xpath('//script/@src'))
            check(file+':six_tabs',doc.xpath('//section/@id')==TABS and doc.xpath('//nav/button/@onclick')==[f"switchTab(event, '{t}')" for t in TABS])
            check(file+':three_chart_containers',doc.xpath('//canvas/@id')==CANVASES and len(doc.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," chart-container ")]'))==3)
            ids=doc.xpath('//@id');check(file+':unique_ids',len(ids)==len(set(ids)))
            check(file+':language_links',set(doc.xpath('//select/option/@value'))==set(ticker+s+'.html' for s in SUFFIXES) and doc.xpath('//select/option[@selected]/@value')==[file])
            for protected in ['pi-modal','disclaimer']:
                check(file+':original_'+protected+'_legal_dom',protected_dom(doc,protected)==protected_dom(old,protected))
            check(file+':company_heading_title',all(re.search(r'\b'+ticker.upper()+r'\b',text(n)) for n in [doc.xpath('//h1')[0],doc.xpath('//title')[0]]))
            public_doc=copy.deepcopy(doc)
            for element in public_doc.xpath('//script | //style'):
                element.getparent().remove(element)
            public_text=text(public_doc)
            # Ignore source-code template-maintenance comments, but inspect public text and AI JS.
            remnants=re.findall(FORBIDDEN,public_text+'\n'+'\n'.join(scripts(source)),re.I)
            check(file+':no_stale_mu_facts',not remnants,remnants or None)
            check(file+':no_citation_placeholders',not re.search(r'||\bturn\d+(?:search|view|fetch)\d+|\bTODO\b|\bTBD\b|\{\{',public_text))
            views=text(doc.get_element_by_id('our-comments'))
            check(file+':views_four_items_and_voice',len(doc.get_element_by_id('our-comments').xpath('.//li'))==4 and {'en':'We believe','sc':'我们认为','tc':'我們認為'}[locale] in views and not re.search(r'NTAM\s*(?:認為|认为|believes)',views,re.I))
            check(file+':report_period_and_update',all(has_date(views,v) for v in ['2026-09-30','2026-10-15']))
            if bank.get('release_date'):
                check(file+':release_date_matches_primary_evidence',has_date(views,bank['release_date']))
            check(file+':no_calculator_or_classification_prose',not re.search(r'NTAM\s*(?:計算|计算|calculation|calculated)|統一分類|统一分类|site[- ]standardized|site[- ]standardised|display category',public_text,re.I))
            financials=doc.get_element_by_id('financials');kpis=financials.xpath('./div[contains(@class,"lg:grid-cols-4")]/div')
            check(file+':four_kpis',len(kpis)==4)
            kpi_numbers.append([[direction_numbers(text(p)) for p in k.xpath('./p')] for k in kpis])
            table=financials.xpath('.//table')[0];rows=table.xpath('.//tbody/tr')
            check(file+':four_column_verified_row_table',len(table.xpath('.//thead/tr/th'))==4 and len(rows)>0 and all(len(r.xpath('./td'))==4 for r in rows))
            tables.append([[numbers(text(td)) for td in r.xpath('./td')[1:]] for r in rows])
            valuation=text(doc.get_element_by_id('valuation'))
            check(file+':valuation_common_fy2027_adj_basis',all(v in valuation for v in ['2027','Adj+']))
            street=doc.get_element_by_id('street-comments')
            cards=street.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," metric-card ")]')
            actual_cards=[card for card in cards if card.xpath('.//h3')]
            all_pending=bool(re.search(r'pending|待核|待確認|待确认|待補|待补|未核|未驗證|未验证|未提供|未能|not verified|unverified',text(street),re.I))
            check(file+':broker_cards_or_explicit_pending',len(actual_cards)==3 or (len(actual_cards)==0 and all_pending))
            cards=actual_cards
            street_numbers.append([numbers(text(c)) for c in cards])
            for i,card in enumerate(cards):
                badges=card.xpath('.//span[contains(@class,"text-xs")]')
                badge=badges[0] if badges else None
                label=text(badge) if badge is not None else ''
                pending=bool(re.search(r'pending|待核|待確認|待确认|待補|待补|未核|未驗證|未验证|未提供|未能|not verified|unverified',text(card),re.I))
                check(file+f':broker_card_{i+1}_approved_rating_or_pending',label in COLORS or pending,{'rating':label,'pending':pending})
                if label in COLORS:
                    check(file+f':broker_card_{i+1}_rating_color',COLORS[label] in badge.get('class',''))
                check(file+f':broker_card_{i+1}_compact_factual_items',1<=len(card.xpath('.//li'))<=3)
                dates=re.findall(r'2026/\d\d/\d\d',text(card))
                if not pending and bank.get('release_date'):
                    eligible_dates=[date.replace('/','-')>=bank['release_date'] if ticker in SAME_DAY_EXCEPTION['banks'] else date.replace('/','-')>bank['release_date'] for date in dates]
                    check(file+f':broker_card_{i+1}_authorized_release_chronology',bool(dates) and all(eligible_dates),dates)
            sourcelines=[text(p) for p in street.xpath('.//p') if 'Bloomberg ANR' in text(p)]
            check(file+':compact_anr_source',len(sourcelines)==1 and len(sourcelines[0])<310,sourcelines)
            if bank:
                anr=bank.get('anr',{})
                price=anr.get('last_price_usd',anr.get('price_USD'))
                target=anr.get('target_price_usd',anr.get('consensus_target_USD'))
                score=anr.get('consensus_score')
                header_values=numbers(text(doc.xpath('//header')[0]))
                check(file+':header_consensus_target_score_match_evidence',target in header_values and score in header_values,{'target':target,'score':score})
                if price:
                    check(file+':anr_reference_price_matches_evidence',price in numbers(text(street)),price)
                source_rows=anr.get('brokers',anr.get('analysts',[]))
                eligible=[r for r in source_rows if r.get('date','')>=bank['release_date'] and (ticker in SAME_DAY_EXCEPTION['banks'] or r.get('date','')>bank['release_date'])]
                selected=[]
                details=[]
                for card in cards:
                    displayed=broker_canonical(text(card.xpath('.//h3')[0]))
                    matching=[r for r in eligible if broker_canonical(r.get('firm',r.get('firm_display',''))).lower()==displayed.lower()]
                    selected.append(displayed)
                    if len(matching)!=1:
                        details.append({'broker':displayed,'match_count':len(matching),'ok':False});continue
                    row=matching[0];tp=row.get('target_usd',row.get('target_USD'))
                    values=numbers(text(card));date=row['date'].replace('-','/')
                    ret=round((tp/price-1)*100,1) if tp is not None and price else None
                    raw=row.get('rating_as_visible',row.get('rating_raw','')).lower()
                    rating_map={'buy':'Buy','neutral':'Neutral','overweight':'Overweight','equalwt/attractive':'Neutral','overwt/attractive':'Overweight'}
                    expected_rating=rating_map.get(raw)
                    badge_text=text(card.xpath('.//span[contains(@class,"text-xs")]')[0])
                    analyst=row.get('analyst_as_visible',row.get('analyst_display','')).split('...')[0].strip()
                    ok=date in text(card) and tp in values and ret in values and badge_text==expected_rating and analyst in text(card)
                    details.append({'broker':displayed,'target':tp,'return_pct':ret,'date':date,'rating_raw':row.get('rating_as_visible',row.get('rating_raw')),'rating_displayed':badge_text,'analyst_visible_prefix':analyst,'ok':ok})
                check(file+':broker_rows_targets_returns_match_eligible_evidence',all(r['ok'] for r in details) and (bool(details) or not eligible),details)
                preferred=[p for p in PRIORITY if any(broker_canonical(r.get('firm',r.get('firm_display','')))==p for r in eligible)]
                check(file+':eligible_preferred_brokers_selected_first',selected[:len(preferred)]==preferred,{'selected':selected,'preferred':preferred})
                if any(r.get('date')==bank['release_date'] for r in source_rows if broker_canonical(r.get('firm',r.get('firm_display',''))) in selected):
                    check(file+':same_day_dates_not_mislabeled_postresults',not re.search(r'confirmed post[- ]results|verified post[- ]earnings|確定.*業績後|确定.*业绩后',text(street),re.I))
                if ticker=='ms':
                    check(file+':ms_undated_price_not_claimed_14oct_close',bool(re.search(r'未顯示|未显示|未標示|未标示|not displayed|not shown|undated|no date', ' '.join(sourcelines),re.I)))
                if ticker in ['jpm','c']:
                    primary=bank['actuals']
                    revenue=primary['reported_revenue_USDmn'][0]
                    earnings=primary['net_income_USDmn'][0]
                    eps=primary['diluted_EPS_USD'][0]
                else:
                    primary=bank['actuals']
                    revenue=round(primary['revenue']*1000,3)
                    earnings=round(primary.get('net_earnings',primary.get('net_income',primary.get('net_income_applicable_to_ms')))*1000,3)
                    eps=primary.get('eps_diluted_usd',primary.get('eps_gaap_usd',primary.get('eps_usd')))
                values=numbers(views+' '+text(financials))
                check(file+':issuer_reported_revenue_income_eps_present',all(v in values or round(v/1000,6) in values for v in [revenue,earnings]) and eps in values,{'revenue_m':revenue,'net_income_m':earnings,'eps':eps})
            risk=doc.get_element_by_id('risks');heads=risk.xpath('.//li/strong')
            check(file+':four_risks_all_dark',len(heads)==4 and all(h.get('class')=='text-base' for h in heads) and not re.search(r'text-(?:red|rose)-',html.tostring(risk,encoding='unicode')))
            risks.append([(e.tag,sorted(e.attrib.items())) for e in risk.iter() if isinstance(e.tag,str)])
            try:
                result=run_vm(file,source,doc);mu_result=run_vm(template_name,template,mu,True);old_result=run_vm(file,prior,old,True)
                RUNTIMES[file]=result
                check(file+':inline_js_syntax_mock_execution',True)
                check(file+':chart_cache_keys',result['keys']==[ticker+'Segment',ticker+'Profit',ticker+'Valuation'],result['keys'])
                check(file+':tabs_switch_and_resize',all(t['ok'] for t in result['tabs']) and [c['resizeCalls'] for c in result['charts']]==[1,1,1])
                check(file+':pi_active_no_acceptance_storage_write',result['storageWrites']==0 and result['piVisible'] and result['bodyLocked'])
                for fn in ['acceptPI','declinePI','callGeminiAPI']:
                    check(file+':original_'+fn,norm(result['functions'][fn])==norm(old_result['functions'][fn]))
                check(file+':original_gate_condition_and_lock',bool(result['gate']) and norm(result['gate'])==norm(old_result['gate']))
                check(file+':original_disclaimer_loader',bool(result['loader']) and norm(result['loader'])==norm(old_result['loader']))
                check(file+':disclaimer_loaded_mock_no_live_api',result['fetches']==['disclaimer.html'] and result['disclaimerLoaded'])
                failed_loader=run_vm(file,source,doc,disclaimer_failure=True)
                check(file+':disclaimer_error_display_gate_preserved',not failed_loader['disclaimerLoaded'] and len(failed_loader['disclaimerHTML'])>0 and failed_loader['piVisible'] and failed_loader['storageWrites']==0)
                for fn in ['switchTab','toggleChat','appendMessage','showTypingIndicator','handleChatSubmit','closeExplainModal']:
                    check(file+':mu_'+fn,norm(result['functions'][fn])==norm(mu_result['functions'][fn]))
                def explain_skeleton(v):return norm(re.sub(r'await callGeminiAPI\([\s\S]*?\);','await COMPANY_EXPLANATION;',v))
                check(file+':mu_explain_interaction',explain_skeleton(result['functions']['explainSelectedTerm'])==explain_skeleton(mu_result['functions']['explainSelectedTerm']))
                prompt=result['standardPrompt']
                check(file+':dated_ticker_ai_context',ticker.upper() in prompt and all(has_date(prompt,v) for v in ['2026-10-15','2026-09-30']) and not re.search(FORBIDDEN,prompt,re.I))
                check(file+':ai_language_and_format','markdown' in prompt.lower() and '<b>' in prompt and {'tc':'繁體中文','sc':'简体中文','en':'English'}[locale] in prompt)
                configs={c['canvasId']:c['config'] for c in result['charts']}
                check(file+':chart_types',configs[CANVASES[0]]['type'] in ['doughnut','bar'] and all(configs[c]['type']=='bar' for c in CANVASES[1:]))
                segment=configs[CANVASES[0]]
                check(file+':doughnut_no_negative_values',segment['type']!='doughnut' or all(v>=0 for d in segment['data']['datasets'] for v in d['data'] if v is not None))
                check(file+':chart_responsive',all(c['options'].get('responsive') is True and c['options'].get('maintainAspectRatio') is False for c in configs.values()) and configs['valuationChart']['options'].get('indexAxis')=='y')
                values=configs['valuationChart']['data']['datasets'][0]['data'];labels=configs['valuationChart']['data']['labels']
                peer_keys=[next((p for p in PEERS if re.search(r'\b'+p+r'\b',label)),'UNKNOWN') for label in labels]
                check(file+':peer_fy2027_values',dict(zip(peer_keys,values))==PEERS,{'tickers':peer_keys,'values':values})
                colors=configs['valuationChart']['data']['datasets'][0].get('backgroundColor',[])
                check(file+':only_target_valuation_bar_blue',len(colors)==len(PEERS) and all(color==('rgba(37, 99, 235, 0.95)' if peer==ticker.upper() else 'rgba(148, 163, 184, 0.6)') for peer,color in zip(peer_keys,colors)))
                if ticker in ['jpm','c'] and bank:
                    seg=bank['segments']
                    check(file+':segment_revenues_match_issuer',configs[CANVASES[0]]['data']['datasets'][0]['data']==(seg['revenue'] if ticker=='jpm' else seg['revenue'][:-1]))
                    profit_values=[d['data'] for d in configs[CANVASES[1]]['data']['datasets']]
                    check(file+':core_segment_profit_and_returns_match_issuer',seg['net_income'][:-1] in profit_values and seg.get('ROE_pct',seg.get('ROTCE_pct'))[:-1] in profit_values)
                    core_note=text(financials.xpath('./div[contains(@class,"lg:grid-cols-2")]/div')[1])
                    check(file+':excluded_corporate_other_disclosed',bool(re.search(r'排除|不包括|剔除|不含|exclude',core_note,re.I)))
                content_path=Path(args.content_dir)/(ticker+'.json')
                if content_path.exists():
                    content=json.loads(content_path.read_text())['languages'][locale]
                    check(file+':financial_table_matches_reviewed_content',[[text(td) for td in row.xpath('./td')] for row in rows]==content['table']['rows'])
                    for chart_id,spec in zip(CANVASES[:2],content['financial_charts']):
                        config=configs[chart_id]
                        check(file+':'+chart_id+'_matches_reviewed_content',config['type']==spec['type'] and config['data']['labels']==spec['labels'] and [d['data'] for d in config['data']['datasets']]==[d['data'] for d in spec['datasets']])
                DETAILS[file]={'sha256':hashlib.sha256((ROOT/file).read_bytes()).hexdigest(),'mock_runtime':result}
            except Exception as exc:
                check(file+':inline_js_syntax_mock_execution',False,str(exc))
        for label,collection in [('financial_table_numeric',tables),('kpi_numeric',kpi_numbers),('broker_numeric',street_numbers),('risk_format',risks)]:
            check(ticker+':three_languages_'+label+'_parity',len(collection)==3 and all(v==collection[0] for v in collection),collection if not all(v==collection[0] for v in collection) else None)
        runs=[RUNTIMES.get(ticker+s+'.html') for s in SUFFIXES]
        if all(runs):
            numeric=[[[d['data'] for d in c['config']['data']['datasets']] for c in r['charts']] for r in runs]
            styles=[[[{k:v for k,v in d.items() if k!='label'} for d in c['config']['data']['datasets']] for c in r['charts']] for r in runs]
            check(ticker+':three_languages_chart_numeric_parity',all(n==numeric[0] for n in numeric))
            check(ticker+':three_languages_chart_dataset_style_parity',all(s==styles[0] for s in styles))
    for file in ['mu.html','mu-sc.html','mu-en.html','disclaimer.html']:
        check('protected_file:'+file,(ROOT/file).read_text()==oldfile(file))
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
    infra=[f for f in tracked if f.startswith('api/') or f in ['CNAME','vercel.json','package.json','package-lock.json']]
    check('protected_infrastructure:byte_exact',all((ROOT/f).read_text()==oldfile(f) for f in infra),infra)
    if not args.skip_homepage:
        source=(ROOT/'index.html').read_text();oldsource=oldfile('index.html')
        prefix,cards,suffix=card_blocks(source);oldprefix,oldcards,oldsuffix=card_blocks(oldsource)
        order=[name[:-5].upper() for name in cards];oldorder=[name[:-5].upper() for name in oldcards]
        check('homepage:25_cards_and_bank_release_order',len(cards)==25 and order[:7]==['MS','BAC','UNH','JNJ','GS','C','JPM'],order)
        check('homepage:other20_card_content_unchanged',all(block==oldcards[file] for file,block in cards.items() if file[:-5] not in TICKERS))
        check('homepage:other20_relative_order_unchanged',[t for t in order if t.lower() not in TICKERS]==[t for t in oldorder if t.lower() not in TICKERS])
        check('homepage:outside_cards_byte_exact',prefix==oldprefix and suffix==oldsuffix)
        ordering=json.loads((ROOT/'research/homepage-earnings-order-2026-10-08.json').read_text());records=sorted(ordering['records'],key=lambda r:r['position']);dates=[r['earnings_publication_date'] for r in records]
        check('homepage:earnings_ledger_matches_sorted_cards',[r['ticker'] for r in records]==order and dates==sorted(dates,reverse=True))
        expected_order=sorted(oldorder,key=lambda t:next(r['earnings_publication_date'] for r in records if r['ticker']==t),reverse=True)
        check('homepage:stable_earnings_date_sort',order==expected_order)
        for ticker in TICKERS:
            check('homepage:'+ticker+'_editorial_update_label','2026年10月15日更新' in cards[ticker+'.html'])
    changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
    check('scope:only_five_banks_and_homepage_html',all(not f.endswith('.html') or f in FILES+['index.html'] for f in changed),changed)
    check('scope:no_source_screenshot_commits',not any(re.search(r'(?:JPM|BAC|MS|GS|C).*(?:ANR|EEO).*\.(?:png|jpe?g)$',f,re.I) for f in tracked+changed))
    whitespace=subprocess.run(['git','-c','core.whitespace=cr-at-eol','diff','--check'],cwd=ROOT,capture_output=True,text=True)
    check('git_diff_whitespace',whitespace.returncode==0,whitespace.stdout+whitespace.stderr or None)
    failed=[r for r in CHECKS if r['status']=='fail']
    report={'report':'Five-bank Q3 2026 MU-template and mock runtime validation','tickers_checked':args.only,'homepage_checked':not args.skip_homepage,'checked_on':'2026-10-15','upstream_base_commit':UPSTREAM_BASE,'comparison_base_commit':BASE,'user_same_day_exception':SAME_DAY_EXCEPTION,'status':'fail' if failed else 'pass','checks':CHECKS,'page_details':DETAILS,
        'limitations':['Static/VM QA is not browser rasterization, production deployment, authenticated access or a live API test.','PI modal acceptance, PI storage writes and PI bypass are forbidden; none are performed.','Mock switchTab unit tests run against fake nodes with the gate active; they are not evidence of real access flow.','Primary-source and screenshot fact review is separately recorded in the evidence ledger; same-day ANR dates need explicit postresults corroboration.','Only the selected repository files were available at this baseline; absent infrastructure cannot be verified by local content comparison.']}
    browser_status_path=ROOT/'research/banks-2026-q3-browser-status.json'
    report['validation_scope']='Static, evidence-reconciliation and mocked-runtime checks only.'
    report['browser_validation']=json.loads(browser_status_path.read_text()) if browser_status_path.exists() else {'status':'not_run','checks_completed':{'real_browser_initial_pi_gate':False,'real_browser_report_body':False}}
    report['stages']={'static_evidence_and_mock_runtime':report['status'],'real_browser':report['browser_validation']['status']}
    (ROOT/args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(CHECKS),'failed':failed,'output':str(ROOT/args.output)},ensure_ascii=False,indent=2))
    return bool(failed)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',default=BASE)
    parser.add_argument('--only',nargs='+',choices=TICKERS,default=TICKERS)
    parser.add_argument('--skip-homepage',action='store_true')
    parser.add_argument('--facts',nargs='*',default=[str(ROOT/'research/jpm-c-2026-q3-2026-10-15.json'),str(ROOT/'research/gs-bac-ms-2026-q3-2026-10-15.json')])
    parser.add_argument('--content-dir',default=str(ROOT/'research/banks-2026-q3-content'))
    parser.add_argument('--output',default='research/banks-2026-q3-validation.json')
    args=parser.parse_args()
    raise SystemExit(validate(args))
