#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, re, time, datetime as dt, hashlib, sys
from pathlib import Path
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

SECTIONS = {
    "politics": 100,
    "economy": 101,
    "society": 102,
    "culture": 103,
    "world": 104,
    "it_science": 105,
}

OUT = Path("outputs"); OUT.mkdir(exist_ok=True)

# ✅ 차단 회피용 강한 헤더
BASE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/123.0.0.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,image/apng,*/*;q=0.8"),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://news.naver.com/",
}

def get_soup(url: str, mobile: bool = False) -> BeautifulSoup:
    headers = dict(BASE_HEADERS)
    if mobile:
        headers["User-Agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        headers["Referer"] = "https://n.news.naver.com/"
    r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def find_links_from_section(soup: BeautifulSoup, limit: int) -> List[str]:
    """
    데스크톱/모바일 공통으로 기사 링크 패턴만 추출.
    - /read.naver?oid=... or /mnews/article/... or n.news.naver.com/mnews/article/...
    - 순서 유지 + 중복 제거
    """
    links, seen = [], set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if not href:
            continue
        pattern = ("/read.naver" in href) or ("/mnews/article/" in href)
        if not pattern:
            continue
        if not href.startswith("http"):
            href = "https://news.naver.com" + href
        if href not in seen:
            seen.add(href)
            links.append(href)
        if len(links) >= limit * 6:  # 여유
            break
    return links

def clean_text(t: str) -> str:
    if not t: return ""
    t = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", " ", t)
    t = re.sub(r"\d{2,3}-\d{3,4}-\d{4}", " ", t)
    t = re.sub(r"무단\s*전재\s*및\s*재배포\s*금지", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def extract_article(url: str) -> Dict[str, str]:
    # 본문/제목 선택자 후보(데스크톱+모바일)
    title_selectors = [
        "h2#title_area", ".media_end_head_headline", "h1#title_area",
        "h1.end_tit", "title",
    ]
    body_selectors = [
        "div#dic_area", "article#newsct_article", "div#articleBodyContents", "div#articeBody",
    ]
    # 먼저 데스크톱, 실패 시 모바일 HTML로 재시도
    for mobile_flag in (False, True):
        try:
            s = get_soup(url, mobile=mobile_flag)
        except Exception:
            continue
        title = ""
        for sel in title_selectors:
            el = s.select_one(sel)
            if el and el.get_text(strip=True):
                title = el.get_text(" ", strip=True)
                break
        if not title:
            title = s.title.get_text(strip=True) if s.title else ""
        body = ""
        for sel in body_selectors:
            el = s.select_one(sel)
            if el and el.get_text(strip=True):
                body = el.get_text(" ", strip=True)
                break
        body = clean_text(body)
        if title and body:
            return {"title": title, "content": body}
    return {"title": "", "content": ""}

def summarize(text: str, max_len: int = 420) -> str:
    if not text: return ""
    parts = re.split(r"(?:다\.|요\.|[.!?])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]
    s = " ".join(parts[:3])
    return (s[:max_len] + "…") if len(s) > max_len else s

def dedup(rows):
    seen, out = set(), []
    for r in rows:
        k = hashlib.md5((r["title"] + r["content"][:160]).encode("utf-8")).hexdigest()
        if k not in seen:
            seen.add(k); out.append(r)
    return out

def scrape_one(section_name: str, sid: int, top_k: int, delay: float):
    # 1) 데스크톱 섹션 페이지 → 2) 모바일 섹션 페이지 순서로 링크 수집
    urls_to_try = [
        f"https://news.naver.com/section/{sid}",
        f"https://n.news.naver.com/section/{sid}",
    ]
    all_links: List[str] = []
    for i, u in enumerate(urls_to_try):
        try:
            s = get_soup(u, mobile=(i == 1))
            links = find_links_from_section(s, top_k)
            all_links.extend(links)
        except Exception as e:
            print(f"[WARN] section {sid} fetch failed: {e}", file=sys.stderr)

    # 중복 제거 & 상위 링크부터 기사 수집
    seen = []; [seen.append(x) for x in all_links if x not in seen]
    rows, today = [], dt.datetime.now().strftime("%Y%m%d")
    print(f"[INFO] {section_name}: found {len(seen)} candidate links")

    for h in seen:
        time.sleep(delay)
        art = extract_article(h)
        if art["title"] and art["content"]:
            rows.append({
                "date": today, "section": section_name, "url": h,
                "title": art["title"], "content": art["content"],
                "summary": summarize(art["content"]),
            })
        if len(rows) >= top_k:
            break
    print(f"[INFO] {section_name}: saved {len(rows)} items")
    return dedup(rows)[:top_k]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--delay", type=float, default=1.2)  # Actions 환경은 넉넉히
    a = ap.parse_args()

    all_rows = []
    for name, sid in SECTIONS.items():
        items = scrape_one(name, sid, a.top_k, a.delay)
        (OUT / f"{name}.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        all_rows.extend(items)

    (OUT / "all_sections.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[DONE] outputs/*.json written")

if __name__ == "__main__":
    main()
