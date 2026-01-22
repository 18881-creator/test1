import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
from datetime import datetime, timedelta

# --------------------------------------------------
# 1. 초기 설정 및 Supabase 연결
# --------------------------------------------------
st.set_page_config(page_title="교사용 대시보드", layout="wide")

@st.cache_resource
def get_supabase_client() -> Client:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_SERVICE_ROLE_KEY"]
        return create_client(url, key)
    except Exception:
        st.error("Secrets 설정이 누락되었습니다. .streamlit/secrets.toml을 확인하세요.")
        st.stop()

supabase = get_supabase_client()

# --------------------------------------------------
# 2. 데이터 로드 및 전처리 함수
# --------------------------------------------------
def load_data():
    """Supabase에서 데이터를 가져와 Pandas DataFrame으로 변환합니다."""
    try:
        # student_submissions 테이블의 모든 데이터 조회
        response = supabase.table("student_submissions").select("*").execute()
        rows = response.data
        
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # 날짜 형식 변환 (UTC -> KST 변환 예시)
        if "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"])
            # 한국 시간(KST)으로 변환 (UTC+9)
            df["created_at"] = df["created_at"] + timedelta(hours=9)
            df["제출시간"] = df["created_at"].dt.strftime("%Y-%m-%d %H:%M:%S")
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

def parse_ox(feedback_text):
    """피드백 텍스트(O: ... / X: ...)에서 정오답 여부를 추출합니다."""
    if not isinstance(feedback_text, str):
        return "판정불가"
    clean_text = feedback_text.strip()
    if clean_text.startswith("O") or clean_text.startswith("O:"):
        return "정답(O)"
    elif clean_text.startswith("X") or clean_text.startswith("X:"):
        return "오답(X)"
    else:
        return "판정불가"

# --------------------------------------------------
# 3. 메인 화면 구성
# --------------------------------------------------
st.title("📊 과학 수업 서술형 평가 - 교사용 대시보드")
st.markdown("학생들이 제출한 답안과 AI의 피드백 결과를 실시간으로 모니터링합니다.")

# 사이드바: 데이터 새로고침
with st.sidebar:
    st.header("설정")
    if st.button("데이터 새로고침 🔄"):
        st.cache_data.clear()
        st.rerun()
    st.info("Supabase DB와 연동되어 있습니다.")

# 데이터 로딩
df = load_data()

if df.empty:
    st.warning("아직 제출된 데이터가 없습니다. 학생 페이지에서 제출을 진행해주세요.")
else:
    # ── 데이터 전처리: 정오답 열 추가 ──
    for i in range(1, 4):
        df[f"Q{i}_판정"] = df[f"feedback_{i}"].apply(parse_ox)

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["📈 종합 통계", "📋 전체 데이터 조회", "🧑‍🎓 학생별 상세 보기"])

    # ==================================================
    # Tab 1: 종합 통계 (시각화)
    # ==================================================
    with tab1:
        # 1. 상단 지표 (Metrics)
        col1, col2, col3 = st.columns(3)
        total_students = df["student_id"].nunique()
        total_submissions = len(df)
        
        # 전체 정답률 계산 (모든 문항 합산)
        total_q_count = len(df) * 3
        correct_count = (
            (df["Q1_판정"] == "정답(O)").sum() + 
            (df["Q2_판정"] == "정답(O)").sum() + 
            (df["Q3_판정"] == "정답(O)").sum()
        )
        avg_score = round((correct_count / total_q_count) * 100, 1) if total_q_count > 0 else 0

        col1.metric("총 참여 학생 수", f"{total_students}명")
        col2.metric("총 제출 건수", f"{total_submissions}건")
        col3.metric("전체 평균 정답률", f"{avg_score}%")
        
        st.divider()

        # 2. 문항별 정답/오답 비율 그래프
        st.subheader("문항별 정오답 현황")
        
        # 시각화를 위한 데이터 재구조화 (Wide -> Long)
        ox_counts = []
        for i in range(1, 4):
            counts = df[f"Q{i}_판정"].value_counts().reset_index()
            counts.columns = ["판정", "학생수"]
            counts["문항"] = f"문항 {i}"
            ox_counts.append(counts)
        
        chart_df = pd.concat(ox_counts)
        
        # Plotly 바 차트
        fig = px.bar(
            chart_df, 
            x="문항", 
            y="학생수", 
            color="판정", 
            title="문항별 성취도 분석",
            text_auto=True,
            color_discrete_map={"정답(O)": "#2ecc71", "오답(X)": "#e74c3c", "판정불가": "#95a5a6"},
            category_orders={"판정": ["정답(O)", "오답(X)", "판정불가"]}
        )
        st.plotly_chart(fig, use_container_width=True)

    # ==================================================
    # Tab 2: 전체 데이터 조회 (Dataframe)
    # ==================================================
    with tab2:
        st.subheader("전체 제출 내역")
        st.caption("컬럼 헤더를 클릭하여 정렬하거나, 오른쪽 상단 돋보기를 눌러 검색할 수 있습니다.")
        
        # 표시할 컬럼 선택 및 이름 정리
        display_cols = ["student_id", "제출시간", 
                        "Q1_판정", "answer_1", "feedback_1",
                        "Q2_판정", "answer_2", "feedback_2",
                        "Q3_판정", "answer_3", "feedback_3"]
        
        # 데이터프레임 표시
        st.dataframe(
            df[display_cols],
            column_config={
                "student_id": "학번",
                "제출시간": "제출 시간",
                "answer_1": st.column_config.TextColumn("문항1 답안", width="medium"),
                "feedback_1": st.column_config.TextColumn("문항1 피드백", width="medium"),
                "answer_2": st.column_config.TextColumn("문항2 답안", width="medium"),
                "feedback_2": st.column_config.TextColumn("문항2 피드백", width="medium"),
                "answer_3": st.column_config.TextColumn("문항3 답안", width="medium"),
                "feedback_3": st.column_config.TextColumn("문항3 피드백", width="medium"),
            },
            hide_index=True,
            use_container_width=True
        )

    # ==================================================
    # Tab 3: 학생별 상세 보기 (Drill-down)
    # ==================================================
    with tab3:
        st.subheader("학생별 상세 피드백 리포트")
        
        # 학번 선택 박스
        student_list = sorted(df["student_id"].unique())
        selected_student = st.selectbox("학번을 선택하세요", student_list)
        
        if selected_student:
            # 해당 학생의 가장 최근 제출 데이터 가져오기
            student_data = df[df["student_id"] == selected_student].sort_values("created_at", ascending=False).iloc[0]
            
            st.markdown(f"### 👤 학번: {selected_student}")
            st.caption(f"제출 시간: {student_data['제출시간']}")
            
            # 카드 형태로 문항별 상세 내용 표시
            for i in range(1, 4):
                with st.container():
                    st.markdown(f"#### 📝 문항 {i}")
                    
                    col_a, col_b = st.columns([1, 1])
                    
                    with col_a:
                        st.markdown("**[학생 답안]**")
                        st.info(student_data[f"answer_{i}"])
                    
                    with col_b:
                        ox = student_data[f"Q{i}_판정"]
                        # 정답/오답에 따른 색상 구분
                        if ox == "정답(O)":
                            st.success(f"**[AI 피드백]** {student_data[f'feedback_{i}']}")
                        else:
                            st.error(f"**[AI 피드백]** {student_data[f'feedback_{i}']}")
                    
                    st.divider()
