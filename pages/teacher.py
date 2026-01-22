# teacher.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from supabase import create_client, Client

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="교사용 대시보드",
    page_icon="📊",
    layout="wide",
)

KST = ZoneInfo("Asia/Seoul")
UTC = timezone.utc

TABLE_NAME = "student_submissions"

# -----------------------------
# Supabase client
# -----------------------------
@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]  # 서버 전용 (절대 노출 금지)
    return create_client(url, key)

# -----------------------------
# (선택) 간단 교사용 비밀번호 보호
# - secrets.toml에 TEACHER_PASSWORD를 넣으면 작동
# - 없으면 보호 없이 열림
# -----------------------------
def teacher_gate():
    pw = st.secrets.get("TEACHER_PASSWORD", None)
    if not pw:
        return True  # 비번 설정 안 하면 그냥 통과

    if "teacher_authed" not in st.session_state:
        st.session_state.teacher_authed = False

    if st.session_state.teacher_authed:
        return True

    st.sidebar.subheader("🔐 교사용 로그인")
    input_pw = st.sidebar.text_input("비밀번호", type="password")
    if st.sidebar.button("로그인"):
        if input_pw == pw:
            st.session_state.teacher_authed = True
            st.sidebar.success("로그인 완료")
            st.rerun()
        else:
            st.sidebar.error("비밀번호가 틀렸습니다.")
    st.stop()

teacher_gate()

# -----------------------------
# 데이터 불러오기
# -----------------------------
@st.cache_data(ttl=30)
def fetch_rows(limit: int = 2000):
    """최근 limit개를 가져옵니다. (필요 시 페이지네이션 확장 가능)"""
    supabase = get_supabase_client()
    # created_at 내림차순
    res = (
        supabase.table(TABLE_NAME)
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    data = res.data or []
    return data

def to_df(rows: list) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # created_at 파싱
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)

        # KST 표시용 컬럼
        df["created_at_kst"] = df["created_at"].dt.tz_convert(KST)

    # 학생 id 문자열로 통일 (검색 편의)
    if "student_id" in df.columns:
        df["student_id"] = df["student_id"].astype(str)

    return df

# -----------------------------
# 피드백 O/X 판정 파싱
# -----------------------------
def ox_from_feedback(feedback: str):
    if not isinstance(feedback, str) or not feedback:
        return None
    f = feedback.strip()
    if f.startswith("O:"):
        return "O"
    if f.startswith("X:"):
        return "X"
    return None

def build_analytics(df: pd.DataFrame):
    """문항별 O/X 비율 및 결측 현황"""
    if df.empty:
        return None

    stats = []
    for i in [1, 2, 3]:
        col = f"feedback_{i}"
        if col not in df.columns:
            continue

        ox = df[col].apply(ox_from_feedback)
        o_cnt = int((ox == "O").sum())
        x_cnt = int((ox == "X").sum())
        n = int(ox.notna().sum())
        missing = int(ox.isna().sum())

        o_rate = (o_cnt / n * 100) if n else 0.0
        x_rate = (x_cnt / n * 100) if n else 0.0

        stats.append(
            {
                "문항": f"Q{i}",
                "O 개수": o_cnt,
                "X 개수": x_cnt,
                "O 비율(%)": round(o_rate, 1),
                "X 비율(%)": round(x_rate, 1),
                "판정 불가/결측": missing,
            }
        )

    return pd.DataFrame(stats)

# -----------------------------
# UI 헤더
# -----------------------------
st.title("📊 서술형 평가 교사용 대시보드")
st.caption("학생 제출 내용, GPT 피드백(O/X), 문항별 통계, 검색/필터, CSV 내보내기를 제공합니다.")

with st.sidebar:
    st.header("⚙️ 필터")
    st.button("🔄 새로고침(캐시 초기화)", on_click=lambda: st.cache_data.clear())

    # 기간 필터 (기본: 최근 7일)
    today_kst = datetime.now(KST).date()
    default_start = today_kst - timedelta(days=7)

    date_range = st.date_input(
        "기간 (KST 기준)",
        value=(default_start, today_kst),
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = default_start, today_kst

    student_query = st.text_input("학번 검색(부분 일치)", value="")
    model_filter = st.text_input("모델 필터(부분 일치)", value="")  # 예: gpt-5-mini
    only_with_feedback = st.checkbox("피드백 생성된 제출만 보기", value=False)

    st.divider()
    st.subheader("표시 옵션")
    show_answers = st.checkbox("표에 답안도 함께 표시", value=False)
    show_guidelines = st.checkbox("표에 채점 기준도 함께 표시", value=False)

# -----------------------------
# 데이터 로드 & 필터링
# -----------------------------
rows = fetch_rows(limit=2000)
df = to_df(rows)

if df.empty:
    st.info("아직 저장된 제출 데이터가 없습니다.")
    st.stop()

# 날짜 필터(KST 기준으로 범위 적용)
# created_at_kst가 있는 경우 그걸로 필터
if "created_at_kst" in df.columns:
    start_dt_kst = datetime.combine(start_date, datetime.min.time(), tzinfo=KST)
    end_dt_kst = datetime.combine(end_date, datetime.max.time(), tzinfo=KST)
    mask = (df["created_at_kst"] >= start_dt_kst) & (df["created_at_kst"] <= end_dt_kst)
    df_f = df.loc[mask].copy()
else:
    df_f = df.copy()

# 학번 검색
if student_query.strip():
    q = student_query.strip()
    df_f = df_f[df_f["student_id"].str.contains(q, na=False)]

# 모델 필터
if model_filter.strip() and "model" in df_f.columns:
    mq = model_filter.strip().lower()
    df_f = df_f[df_f["model"].astype(str).str.lower().str.contains(mq, na=False)]

# 피드백 있는 것만
if only_with_feedback:
    fb_cols = [c for c in ["feedback_1", "feedback_2", "feedback_3"] if c in df_f.columns]
    if fb_cols:
        df_f = df_f[df_f[fb_cols].notna().any(axis=1)]

# -----------------------------
# 상단 KPI
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("제출 수", f"{len(df_f):,}")

with col2:
    uniq_students = df_f["student_id"].nunique() if "student_id" in df_f.columns else 0
    st.metric("학생 수(중복 제거)", f"{uniq_students:,}")

with col3:
    # Q1~Q3 중 O 개수 합
    total_o = 0
    for i in [1, 2, 3]:
        c = f"feedback_{i}"
        if c in df_f.columns:
            total_o += int(df_f[c].apply(ox_from_feedback).eq("O").sum())
    st.metric("총 O 판정(합계)", f"{total_o:,}")

with col4:
    # 최근 제출 시각
    if "created_at_kst" in df_f.columns:
        latest = df_f["created_at_kst"].max()
        st.metric("최근 제출(KST)", latest.strftime("%Y-%m-%d %H:%M") if pd.notna(latest) else "-")
    else:
        st.metric("최근 제출", "-")

st.divider()

# -----------------------------
# 문항별 통계
# -----------------------------
st.subheader("📈 문항별 O/X 통계")
ana = build_analytics(df_f)
if ana is None or ana.empty:
    st.info("통계를 만들 수 없습니다(피드백 컬럼/데이터 확인).")
else:
    st.dataframe(ana, use_container_width=True)

st.divider()

# -----------------------------
# 제출 목록 테이블
# -----------------------------
st.subheader("🗂️ 제출 목록")

# 표에 보여줄 컬럼 구성
base_cols = ["created_at_kst", "student_id", "model", "feedback_1", "feedback_2", "feedback_3"]
answer_cols = ["answer_1", "answer_2", "answer_3"]
guide_cols = ["guideline_1", "guideline_2", "guideline_3"]

cols = [c for c in base_cols if c in df_f.columns]
if show_answers:
    cols += [c for c in answer_cols if c in df_f.columns]
if show_guidelines:
    cols += [c for c in guide_cols if c in df_f.columns]

# 정렬(최신순)
if "created_at_kst" in df_f.columns:
    df_table = df_f.sort_values("created_at_kst", ascending=False)[cols].copy()
else:
    df_table = df_f[cols].copy()

# created_at_kst 보기 좋게 문자열로
if "created_at_kst" in df_table.columns:
    df_table["created_at_kst"] = df_table["created_at_kst"].dt.strftime("%Y-%m-%d %H:%M")

st.dataframe(df_table, use_container_width=True, height=420)

# CSV 내보내기
csv = df_table.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇️ 현재 필터 결과 CSV 다운로드",
    data=csv,
    file_name=f"submissions_{start_date}_{end_date}.csv",
    mime="text/csv",
)

st.divider()

# -----------------------------
# 개별 제출 상세 보기
# -----------------------------
st.subheader("🔎 개별 제출 상세")

# 선택 UI (학번 기준 최신 제출부터 보여주기)
# 학번 리스트
student_ids = sorted(df_f["student_id"].dropna().unique().tolist())
sel_student = st.selectbox("학번 선택", options=["(선택)"] + student_ids, index=0)

if sel_student != "(선택)":
    df_s = df_f[df_f["student_id"] == sel_student].copy()

    # 제출 시각 선택(최신 먼저)
    if "created_at_kst" in df_s.columns:
        df_s = df_s.sort_values("created_at_kst", ascending=False)
        options = df_s["created_at_kst"].dt.strftime("%Y-%m-%d %H:%M").fillna("-").tolist()
        idx_map = {options[i]: df_s.iloc[i] for i in range(len(options))}
        sel_time = st.selectbox("제출 시각(KST) 선택", options=options)
        row = idx_map[sel_time]
    else:
        row = df_s.iloc[0]

    # 상세 표시
    left, right = st.columns([1, 1])

    with left:
        st.markdown("### 🧾 답안")
        for i in [1, 2, 3]:
            a = row.get(f"answer_{i}", "")
            st.markdown(f"**문항 {i} 답안**")
            st.write(a if isinstance(a, str) and a.strip() else "—")

    with right:
        st.markdown("### ✅ GPT 피드백 / 기준")
        for i in [1, 2, 3]:
            fb = row.get(f"feedback_{i}", "")
            gd = row.get(f"guideline_{i}", "")
            tag = ox_from_feedback(fb)
            if tag == "O":
                st.success(f"**문항 {i}**  {fb}")
            elif tag == "X":
                st.info(f"**문항 {i}**  {fb}")
            else:
                st.warning(f"**문항 {i}**  (판정 불가) {fb if fb else '—'}")

            if gd and isinstance(gd, str):
                with st.expander(f"문항 {i} 채점 기준 보기"):
                    st.write(gd)

    st.caption(f"모델: {row.get('model','-')}")

st.divider()

# -----------------------------
# (선택) 학생별 요약 통계
# -----------------------------
st.subheader("👥 학생별 요약 (O 개수 기준)")

def count_o_in_row(r):
    cnt = 0
    for i in [1, 2, 3]:
        fb = r.get(f"feedback_{i}", None)
        if ox_from_feedback(fb) == "O":
            cnt += 1
    return cnt

df_sum = df_f.copy()
df_sum["o_count"] = df_sum.apply(count_o_in_row, axis=1)

# 학생별 최신 제출 1개만 집계(원하면 평균/최대 등으로 바꿀 수 있음)
if "created_at_kst" in df_sum.columns:
    df_latest = df_sum.sort_values("created_at_kst", ascending=False).groupby("student_id", as_index=False).first()
else:
    df_latest = df_sum.groupby("student_id", as_index=False).first()

df_latest = df_latest[["student_id", "o_count"]].sort_values("o_count", ascending=False)

st.dataframe(df_latest, use_container_width=True, height=320)
