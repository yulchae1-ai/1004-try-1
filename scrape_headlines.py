#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, re, time, datetime as dt, hashlib
from pathlib import Path
import requests
from bs4 import BeautifulSoup

SECTIONS = {'politics':100,'economy':101,'society':102,'culture':103,'world':104,'it_science':105}
HEADERS={'User-Agent':'Mozilla/5.0'}
OUT=Path('outputs'); OUT.mkdir(exist_ok=True)

def soup(url):
    r=requests.get(url,headers=HEADERS,timeout=15); r.raise_for_status(); return BeautifulSoup(r.text,'lxml')

def clean(txt):
    if not txt: return ''
    txt=re.sub(r'[\w\.-]+@[\w\.-]+',' ',txt)
    txt=re.sub(r'무단.*?재배포.*?금지',' ',txt,flags=re.I)
    txt=re.sub(r'\s+',' ',txt).strip()
    return txt

def extract(url):
    try:s=soup(url)
    except Exception:return{'title':'','content':''}
    title='';body=''
    for sel in['h2#title_area','.media_end_head_headline','h1#title_area','title']:
        el=s.select_one(sel)
        if el:title=el.get_text(' ',strip=True);break
    for sel in['div#dic_area','article#newsct_article','div#articleBodyContents']:
        el=s.select_one(sel)
        if el:body=el.get_text(' ',strip=True);break
    return{'title':title,'content':clean(body)}

def summarize(t,maxlen=350):
    sents=re.split(r'(?:다\.|요\.|[.!?])\s+',t)
    sents=[x.strip() for x in sents if x.strip()]
    summ=' '.join(sents[:3])
    return (summ[:maxlen]+'…') if len(summ)>maxlen else summ

def dedup(lst):
    seen=set();out=[]
    for x in lst:
        k=hashlib.md5((x['title']+x['content'][:150]).encode()).hexdigest()
        if k not in seen:seen.add(k);out.append(x)
    return out

def scrape(name,sid,top,delay):
    s=soup(f'https://news.naver.com/section/{sid}')
    links=[]
    for a in s.select('a[href]'):
        h=a['href']
        if '/read.naver' in h or '/mnews/article/' in h:
            if not h.startswith('http'):h='https://news.naver.com'+h
            if h not in links:links.append(h)
        if len(links)>=top*4:break
    out=[];today=dt.datetime.now().strftime('%Y%m%d')
    for h in links:
        time.sleep(delay)
        art=extract(h)
        if art['title'] and art['content']:
            out.append({'date':today,'section':name,'url':h,'title':art['title'],'content':art['content'],'summary':summarize(art['content'])})
        if len(out)>=top:break
    return dedup(out)[:top]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--top-k',type=int,default=3)
    ap.add_argument('--delay',type=float,default=0.8)
    a=ap.parse_args()
    all=[]
    for n,s in SECTIONS.items():
        print('[INFO]',n)
        try:items=scrape(n,s,a.top_k,a.delay)
        except Exception as e:print('fail',e);items=[]
        (OUT/f'{n}.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
        all+=items
    (OUT/'all_sections.json').write_text(json.dumps(all,ensure_ascii=False,indent=2),encoding='utf-8')
    print('[DONE] saved')
if __name__=='__main__':main()
