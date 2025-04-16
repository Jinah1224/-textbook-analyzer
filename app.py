import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from io import StringIO
import re
import time
import openpyxl

# -------------------------------
# 뉴스 키워드 및 카테고리 기준 정의
# -------------------------------
keywords = ["천재교육", "천재교과서", "지학사", "벽호", "프린피아", "미래엔", "교과서", "동아출판"]
category_keywords = {
    "후원": ["후원", "기탁"],
    "기부": ["기부"],
    "협약/MOU": ["협약", "mou"],
    "에듀테크/디지털교육": ["에듀테크", "디지털교육", "디지털 교육", "ai교육", "ai 교육", "스마트교육", "스마트 교육"],
    "정책": ["정책"],
    "출판": ["출판"],
    "인사/채용": ["채용", "교사"],
    "프린트 및 인쇄": ["인쇄", "프린트"],
    "공급": ["공급"],
    "교육": ["교육"],
    "이벤트": ["이벤트", "사은품"]
}

# -------------------------------
# 뉴스 크롤링 관련 함수
# -------------------------------
@st.cache_data(ttl=3600)
def crawl_news_bs(keyword, pages=10):
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []
    seen_links = set()
    seen_summaries = set()

    for page in range(1, pages + 1):
        start = (page - 1) * 10 + 1
        search_url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1&nso=so%3Add%2Cp%3A2w&start={start}"
        res = requests.get(search_url, headers=headers)
        if res.status_code != 200:
            continue
        soup = BeautifulSoup(res.text, "lxml")
        articles = soup.select(".news_area")

        for a in articles:
            try:
                title_elem = a.select_one(".news_tit")
                title = title_elem.get("title")
                link = title_elem.get("href")
                summary_elem = a.select_one(".dsc_txt_wrap")
                summary = summary_elem.get_text(strip=True) if summary_elem else ""
                press = a.select_one(".info_group a").get_text(strip=True)

                if link in seen_links or summary in seen_summaries:
                    continue
                seen_links.add(link)
                seen_summaries.add(summary)

                body = get_news_body(link)
                full_text = (summary + " " + body).lower()

                results.append({
                    "출판사명": check_publisher(full_text),
                    "카테고리": categorize_news(full_text),
                    "날짜": get_news_date(link),
                    "제목": title,
                    "URL": link,
                    "요약": summary,
                    "언론사": press,
                    "내용점검": match_keyword_flag(full_text),
                    "본문내_교과서_또는_발행사_언급": contains_textbook(body)
                })
            except:
                continue
        time.sleep(0.2)

    return pd.DataFrame(results)
