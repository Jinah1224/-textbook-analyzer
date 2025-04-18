import streamlit as st
import pandas as pd
import re
from datetime import datetime
import chardet
from io import BytesIO
import feedparser

# -------------------------------
# Streamlit 기본 설정
# -------------------------------
st.set_page_config(page_title="📚 교과서 분석기", layout="wide")
st.title("📚 카카오톡 분석 + Google 뉴스 RSS 수집 통합 앱")

# -------------------------------
# 기준 데이터
# -------------------------------
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
publishers = ["미래엔", "비상", "동아", "아이스크림", "천재", "지학사", "좋은책", "대교", "이룸", "명진", "천재교육"]
subjects = ["국어", "수학", "사회", "과학", "영어", "도덕", "음악", "미술", "체육"]
complaint_keywords = [
    "안 왔어요", "아직", "늦게", "없어요", "오류", "문제", "왜", "헷갈려", "불편",
    "안옴", "지연", "안보여요", "못 받았", "힘들어요", "짜증", "스트레스"
]

news_keywords = ["천재교육", "천재교과서", "지학사", "벽호", "프린피아", "미래엔", "교과서", "동아출판"]
category_keywords = {
    "후원": ["후원", "기탁"], "기부": ["기부"], "협약/MOU": ["협약", "mou"],
    "에듀테크/디지털교육": ["에듀테크", "디지털교육", "ai교육", "스마트교육"],
    "정책": ["정책"], "출판": ["출판"], "인사/채용": ["채용", "교사"],
    "프린트 및 인쇄": ["인쇄", "프린트"], "공급": ["공급"], "교육": ["교육"], "이벤트": ["이벤트", "사은품"]
}

# -------------------------------
# 뉴스 RSS 크롤링
# -------------------------------
def crawl_google_news_rss(keyword):
    feed_url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(feed_url)
    results = []
    for entry in feed.entries:
        title = entry.title
        link = entry.link
        try:
            published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d")
        except:
            published = ""
        full_text = title.lower()
        results.append({
            "출판사명": check_publisher(full_text),
            "카테고리": categorize_news(full_text),
            "날짜": published,
            "제목": title,
            "URL": link,
            "본문내_교과서_또는_발행사_언급": "O" if "교과서" in full_text or "발행사" in full_text else "X"
        })
    return pd.DataFrame(results)

def categorize_news(text):
    for cat, kws in category_keywords.items():
        if any(k in text for k in kws):
            return cat
    return "기타"

def check_publisher(text):
    for pub in news_keywords:
        if pub.replace(" ", "") in text.replace(" ", ""):
            return pub
    return "기타"

# -------------------------------
# 카카오톡 파싱
# -------------------------------
def parse_kakao_text(text):
    parsed = []
    pattern1 = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일 (오전|오후) (\d{1,2}):(\d{2}), (.+?) : (.+)")
    pattern2 = re.compile(r"\[(.+?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] (.+)")
    date_header = re.compile(r"-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일")
    current_date = None
    for line in text.splitlines():
        if m1 := pattern1.match(line):
            y, m, d, ampm, h, mi, sender, msg = m1.groups()
            if sender.strip() == "오픈채팅봇":
                continue
            h, mi = int(h), int(mi)
            if ampm == "오후" and h != 12: h += 12
            elif ampm == "오전" and h == 12: h = 0
            dt = datetime(int(y), int(m), int(d), h, mi)
            parsed.append({"날짜": dt.date(), "시간": dt.time(), "보낸 사람": sender.strip(), "메시지": msg.strip()})
        elif m2 := pattern2.match(line):
            sender, ampm, h, mi, msg = m2.groups()
            if sender.strip() == "오픈채팅봇":
                continue
            h, mi = int(h), int(mi)
            if ampm == "오후" and h != 12: h += 12
            elif ampm == "오전" and h == 12: h = 0
            if current_date:
                parsed.append({"날짜": current_date, "시간": datetime.strptime(f"{h}:{mi}", "%H:%M").time(), "보낸 사람": sender.strip(), "메시지": msg.strip()})
        elif dh := date_header.match(line):
            y, m, d = map(int, dh.groups())
            current_date = datetime(y, m, d).date()
    return pd.DataFrame(parsed)

def classify_category(text):
    for cat, kws in kakao_categories.items():
        if any(w in text for w in kws):
            return cat
    return "기타"

def extract_kakao_publisher(text):
    for pub in publishers:
        if pub in text:
            return pub
    return None

def extract_subject(text):
    for sub in subjects:
        if sub in text:
            return sub
    return None

def detect_complaint(text):
    return "O" if any(w in text for w in complaint_keywords) else "X"

# -------------------------------
# Streamlit UI 구성
# -------------------------------
tab1, tab2 = st.tabs(["💬 카카오톡 분석", "📰 뉴스 수집"])

with tab1:
    st.subheader("카카오톡 .txt 업로드")
    uploaded = st.file_uploader("카카오톡 대화 텍스트 파일 업로드", type="txt")
    if uploaded:
        raw = uploaded.read()
        encoding = chardet.detect(raw)["encoding"]
        text = raw.decode(encoding or "utf-8")
        df_kakao = parse_kakao_text(text)
        if not df_kakao.empty:
            df_kakao["카테고리"] = df_kakao["메시지"].apply(classify_category)
            df_kakao["출판사"] = df_kakao["메시지"].apply(extract_kakao_publisher)
            df_kakao["과목"] = df_kakao["메시지"].apply(extract_subject)
            df_kakao["불만 여부"] = df_kakao["메시지"].apply(detect_complaint)
            st.success(f"✅ {len(df_kakao)}개 메시지 분석 완료!")
            st.dataframe(df_kakao)
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df_kakao.to_excel(writer, index=False, sheet_name="카카오톡분석")
            st.download_button("📥 엑셀 다운로드", buffer.getvalue(), "kakao_result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("❗ 유효한 메시지를 추출할 수 없습니다.")

with tab2:
    st.subheader("Google 뉴스 RSS 기반 수집")
    selected = st.multiselect("🔎 수집 키워드 선택", news_keywords, default=news_keywords)
    if selected and st.button("뉴스 수집 시작"):
        progress = st.progress(0)
        all_data = []
        for i, kw in enumerate(selected):
            df = crawl_google_news_rss(kw)
            all_data.append(df)
            progress.progress((i + 1) / len(selected))
        df_news = pd.concat(all_data, ignore_index=True)
        st.success("✅ 뉴스 수집 완료!")
        st.dataframe(df_news)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df_news.to_excel(writer, index=False, sheet_name="뉴스결과")
        st.download_button("📥 엑셀 다운로드", buffer.getvalue(), "news_result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
