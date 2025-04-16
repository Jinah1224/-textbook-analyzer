import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from io import StringIO
import re
import time
import openpyxl

# -------------------------------
# 키워드 및 카테고리 기준 정의
# -------------------------------
keywords = ["천재교육", "천재교과서", "지학사", "벽호", "프린피아", "미래엔", "교과서", "동아출판"]
category_keywords = {
    "후원": ["후원", "기탁"],
    "기부": ["기부"],
    "협약/MOU": ["협약", "mou"],
    "에듀테크/디지털교육": ["에듀테크", "디지털교육", "ai교육", "스마트교육"],
    "정책": ["정책"],
    "출판": ["출판"],
    "인사/채용": ["채용", "교사"],
    "프린트 및 인쇄": ["인쇄", "프린트"],
    "공급": ["공급"],
    "교육": ["교육"],
    "이벤트": ["이벤트", "사은품"]
}

# 카카오톡 기준
kakao_categories = {
    "채택: 선정 기준/평가": ["평가표", "기준", "추천의견서", "선정기준"],
    "채택: 위원회 운영": ["위원회", "협의회", "대표교사", "위원"],
    "채택: 회의/심의 진행": ["회의", "회의록", "심의", "심사", "운영"],
    "배송": ["배송"],
    "배송: 지도서/전시본 도착": ["도착", "왔어요", "전시본", "지도서", "박스"],
    "배송: 라벨/정리 업무": ["라벨", "분류", "정리", "전시 준비"],
    "주문: 시스템 사용": ["나이스", "에듀파인", "등록", "입력"],
    "주문: 공문/정산": ["공문", "정산", "마감일", "요청"],
    "출판사: 자료 수령/이벤트": ["보조자료", "자료", "기프티콘", "이벤트"],
    "출판사: 자료 회수/요청": ["회수", "요청", "교사용"]
}
publishers = ["미래엔", "비상", "동아", "아이스크림", "천재", "좋은책", "지학사", "대교", "이룸", "명진", "천재교육"]
subjects = ["국어", "수학", "사회", "과학", "영어", "도덕", "음악", "미술", "체육"]
complaint_keywords = ["안 왔어요", "아직", "늦게", "없어요", "오류", "문제", "왜", "헷갈려", "불편", "안옴", "지연", "안보여요", "못 받았", "힘들어요"]

# -------------------------------
# 뉴스 크롤링 함수
# -------------------------------
def crawl_news_bs(keyword, pages=5):
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []
    seen = set()
    today = datetime.today().date()
    two_weeks_ago = today - timedelta(days=14)

    for page in range(1, pages + 1):
        start = (page - 1) * 10 + 1
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1&nso=so%3Add%2Cp%3A2w&start={start}"
        try:
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, "lxml")
            articles = soup.select(".news_area")
            for a in articles:
                try:
                    title_elem = a.select_one(".news_tit")
                    title = title_elem.get("title")
                    link = title_elem.get("href")
                    summary = a.select_one(".dsc_txt_wrap").get_text(strip=True)
                    press = a.select_one(".info_group a").get_text(strip=True)
                    if link in seen or summary in seen:
                        continue
                    seen.add(link)
                    seen.add(summary)

                    body = get_news_body(link)
                    full_text = (summary + " " + body).lower()

                    date_str = get_news_date(link)
                    try:
                        article_date = datetime.strptime(date_str, "%Y.%m.%d").date()
                        if article_date < two_weeks_ago:
                            continue
                    except:
                        continue

                    results.append({
                        "출판사명": check_publisher(full_text),
                        "카테고리": categorize_news(full_text),
                        "날짜": date_str,
                        "제목": title,
                        "URL": link,
                        "요약": summary,
                        "언론사": press,
                        "내용점검": match_keyword_flag(full_text),
                        "본문내_교과서_또는_발행사_언급": contains_textbook(body)
                    })
                except:
                    continue
            time.sleep(0.3)
        except:
            continue
    return pd.DataFrame(results)

def get_news_body(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, 'lxml')
        for cls in ["article", "article-body", "newsEndContents", "content", "viewContent"]:
            tag = soup.find(class_=cls)
            if tag:
                return tag.get_text(" ", strip=True)
        return soup.get_text(" ", strip=True)
    except:
        return ""

def get_news_date(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, 'lxml')
        meta = soup.find("meta", {"property": "article:published_time"})
        if meta and meta.get("content"):
            return meta["content"][:10].replace("-", ".")
        return "날짜 없음"
    except:
        return "날짜 오류"

def categorize_news(text):
    text = text.lower()
    for category, words in category_keywords.items():
        if any(w in text for w in words):
            return category
    return "기타"

def check_publisher(text):
    for pub in keywords:
        if pub.lower() in text:
            return pub
    return "기타"

def match_keyword_flag(text):
    for pub in keywords:
        if pub.lower() in text:
            return "O"
    return "X"

def contains_textbook(text):
    return "O" if "교과서" in text or "발행사" in text else "X"

# -------------------------------
# 카카오톡 분석 함수
# -------------------------------
def analyze_kakao(text):
    pattern = re.compile(r"(?P<datetime>\d{4}년 \d{1,2}월 \d{1,2}일 (오전|오후) \d{1,2}:\d{2}), (?P<sender>[^:]+) : (?P<message>.+)")
    matches = pattern.findall(text)
    rows = []
    for match in matches:
        date_str, ampm, sender, message = match
        if sender.strip() == "오픈채팅봇":
            continue
        try:
            dt = datetime.strptime(date_str.replace("오전", "AM").replace("오후", "PM"), "%Y년 %m월 %d일 %p %I:%M")
            rows.append({
                "날짜": dt.date(),
                "시간": dt.time(),
                "보낸 사람": sender.strip(),
                "메시지": message.strip(),
                "카테고리": classify_category(message),
                "출판사": extract_kakao_publisher(message),
                "과목": extract_subject(message),
                "불만 여부": detect_complaint(message)
            })
        except:
            continue
    return pd.DataFrame(rows)

def classify_category(text):
    if "배송" in text:
        return "배송"
    for category, words in kakao_categories.items():
        if any(w in text for w in words):
            return category
    return "기타"

def extract_kakao_publisher(text):
    for pub in publishers:
        if pub in text:
            return pub
    return None

def extract_subject(text):
    for subject in subjects:
        if subject in text:
            return subject
    return None

def detect_complaint(text):
    return any(w in text for w in complaint_keywords)

# -------------------------------
# Streamlit UI
# -------------------------------
st.set_page_config(page_title="올인원 교과서 분석기", layout="wide")
st.title("📚 교과서 커뮤니티 분석 & 뉴스 수집 올인원 앱")

tab1, tab2 = st.tabs(["💬 카카오톡 분석", "📰 뉴스 크롤링"])

with tab1:
    st.subheader("📂 카카오톡 대화 분석기")
    uploaded_file = st.file_uploader("카카오톡 .txt 파일을 업로드하세요", type="txt")
    if uploaded_file:
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        df_kakao = analyze_kakao(stringio.read())
        st.success("✅ 대화 분석 완료")
        st.dataframe(df_kakao)
        st.download_button("📥 엑셀 다운로드", data=df_kakao.to_csv(index=False).encode("utf-8"), file_name="카카오톡_분석결과.csv", mime="text/csv")

with tab2:
    st.subheader("📰 출판사 관련 뉴스 수집기 (최근 2주)")
    st.markdown("🔍 **검색할 키워드를 선택하세요**")
    selected_keywords = st.multiselect("※ 여러 개 선택 가능", options=keywords, default=keywords)

    if not selected_keywords:
        st.warning("⚠️ 최소 하나 이상의 키워드를 선택해 주세요.")
    elif st.button("크롤링 시작"):
        progress_bar = st.progress(0, text="🔄 뉴스 크롤링 준비 중...")
        status_placeholder = st.empty()

        total_tasks = len(selected_keywords)
        results = []
        start_time = time.time()

        for i, kw in enumerate(selected_keywords):
            kw_start = time.time()
            df = crawl_news_bs(kw, pages=5)
            results.append(df)

            # 시간 계산
            elapsed_time = time.time() - start_time
            avg_time_per_keyword = elapsed_time / (i + 1)
            remaining = int(avg_time_per_keyword * (total_tasks - (i + 1)))

            mins, secs = divmod(remaining, 60)
            eta = f"⏱ 예상 남은 시간: 약 {mins}분 {secs}초"

            progress_pct = int(((i + 1) / total_tasks) * 100)
            progress_bar.progress(progress_pct, text=f"{kw} 완료 ({progress_pct}%)")
            status_placeholder.info(eta)

        df_news = pd.concat(results, ignore_index=True)
        status_placeholder.success("✅ 전체 크롤링 완료!")

        st.success(f"총 {len(df_news)}건의 뉴스 수집 완료 ✅")
        st.dataframe(df_news)
        st.download_button(
            "📥 뉴스 데이터 다운로드",
            data=df_news.to_csv(index=False).encode("utf-8"),
            file_name="출판사_뉴스_크롤링_결과.csv",
            mime="text/csv"
        )
