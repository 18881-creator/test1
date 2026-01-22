# 🧪 Streamlit 기반 서술형 평가 + GPT 자동 피드백 시스템

이 프로젝트는 **Streamlit**을 활용해
학생의 **서술형 답안을 수집 → GPT로 채점 및 피드백 → Supabase DB에 저장**하는
수업용 웹 애플리케이션 예시입니다.

---

## 📌 전체 흐름 한눈에 보기

```
학생 입력
   ↓
[Step 1] 답안 제출
   ↓
제출 검증 (빈칸, 학번)
   ↓
[Step 2] GPT 채점 버튼 활성화
   ↓
GPT 피드백 생성 (O/X + 설명)
   ↓
Supabase DB 저장
   ↓
화면에 피드백 출력
```

---

## 🧱 구성 단계

### ✅ Step 1 – 서술형 문제 입력 및 제출

* 학번 입력
* 서술형 문제 **3문항**
* `st.form()`을 사용해 **한 번에 제출**
* 모든 답안이 채워졌을 때만 제출 성공

📄 예시 화면

```
[학번 입력]

서술형 문제 1
[답안 입력 칸]

서술형 문제 2
[답안 입력 칸]

서술형 문제 3
[답안 입력 칸]

[ 제출 ]
```

---

### ✅ Step 2 – GPT 기반 자동 채점 & 피드백

* 제출 성공 시에만 **GPT 피드백 버튼 활성화**
* 문항별 채점 기준(`GRADING_GUIDELINES`) 적용
* 출력 형식 강제:

  * `O: ...` 또는 `X: ...`
  * 한 줄
  * 200자 이내
* 학생에게 말하듯 **친절한 피드백**

🧠 GPT 역할

```
너는 친절하지만 정확한 과학 교사다.
```

---

### ✅ Step 3 – Supabase DB 저장

* GPT 피드백 생성 후 자동 저장
* 저장 항목 예시:

  * 학번
  * 문항별 답안
  * 문항별 피드백
  * 채점 기준
  * 사용 모델명
  * 생성 시각

📦 DB 구조 개념도

```
student_submissions
 ├─ student_id
 ├─ answer_1 / answer_2 / answer_3
 ├─ feedback_1 / feedback_2 / feedback_3
 ├─ guideline_1 / guideline_2 / guideline_3
 ├─ model
 └─ created_at
```

---

## 🔐 필수 환경 설정

### 1️⃣ Python 라이브러리 설치

```bash
pip install streamlit openai supabase
```

### 2️⃣ `.streamlit/secrets.toml` 설정

```toml
OPENAI_API_KEY = "sk-..."
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "service-role-key"
```

⚠️ `SERVICE_ROLE_KEY`는 **절대 외부에 노출 금지**

---

## 🧩 핵심 설계 포인트

* ✅ **answers 리스트**로 문항 확장 용이
* ✅ GPT 호출은 **버튼 클릭 시 1회만**
* ✅ 세션 상태(`st.session_state`)로 새로고침에도 결과 유지
* ✅ DB 저장 로직을 함수로 분리 → 유지보수 용이
* ✅ 교사가 채점 기준만 바꾸면 바로 다른 단원 적용 가능

---

## 🚀 확장 아이디어

* 📊 점수화 로직 추가
* 👨‍🏫 교사용 대시보드
* 📈 학생별 성장 추적
* 🧑‍🤝‍🧑 학급 단위 통계 분석
* 🔐 로그인 / 반 선택 기능

---

## ✨ 활용 예시

* 물리·화학·생명과학 서술형 수행평가
* 수행평가 즉시 피드백 제공
* AI 보조 채점 연수용 데모
* 과정 중심 평가 실습

---

## 📎 한 줄 요약

> **“서술형 평가의 채점 부담은 줄이고, 피드백의 질은 높이는 Streamlit + GPT 수업 도구”**

---
