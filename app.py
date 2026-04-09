import streamlit as st
import pandas as pd
import sqlite3
import datetime

# 1. 데이터베이스 연결 및 테이블 생성 (카테고리 컬럼 추가)
def init_db():
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            category TEXT,
            amount INTEGER,
            memo TEXT
        )
    ''')
    # 혹시 기존 테이블에 category 컬럼이 없는 경우를 대비해 추가 시도
    try:
        c.execute("ALTER TABLE expenses ADD COLUMN category TEXT DEFAULT '기타'")
    except:
        pass 
    conn.commit()
    conn.close()

# 2. 데이터 저장 함수
def insert_data(date, type_, category, amount, memo):
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    c.execute("INSERT INTO expenses (date, type, category, amount, memo) VALUES (?, ?, ?, ?, ?)",
              (date, type_, category, amount, memo))
    conn.commit()
    conn.close()

# 3. 데이터 업데이트 함수 (수정용)
def update_db(edited_df):
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    for index, row in edited_df.iterrows():
        # 금액에서 콤마 제거
        clean_amount = int(str(row['amount']).replace(',', '').replace('원', '').strip())
        c.execute("""
            UPDATE expenses 
            SET date = ?, type = ?, category = ?, amount = ?, memo = ? 
            WHERE id = ?
        """, (str(row['date']), row['type'], row['category'], clean_amount, row['memo'], row['id']))
    conn.commit()
    conn.close()

# 4. 데이터 불러오기 함수
def load_data():
    conn = sqlite3.connect('money.db')
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()
    return df

init_db()

# --- 세션 상태 초기화 ---
if 'current_date' not in st.session_state:
    st.session_state['current_date'] = datetime.date.today()

# --- 화면 구성 ---
st.title('💰 나의 스마트 가계부')

# 날짜 선택 조작
st.write("날짜 선택")
col_prev, col_date, col_next = st.columns([1, 4, 1])
with col_prev:
    if st.button("◀ 이전", use_container_width=True):
        st.session_state['current_date'] -= datetime.timedelta(days=1)
with col_date:
    selected_date = st.date_input("날짜 입력", value=st.session_state['current_date'], label_visibility="collapsed")
    st.session_state['current_date'] = selected_date
with col_next:
    if st.button("다음 ▶", use_container_width=True):
        st.session_state['current_date'] += datetime.timedelta(days=1)

# 입력 폼
with st.form("입력폼", clear_on_submit=True):
    col_t, col_c = st.columns(2)
    with col_t:
        type_ = st.radio("구분", ["지출", "수입"], index=0, horizontal=True)
    with col_c:
        # 카테고리 목록 정의
        category_list = ["식비", "교통", "쇼핑", "의료", "주거", "교육", "저축", "기타"]
        category = st.selectbox("카테고리", category_list)
        
    amount = st.number_input("금액을 입력하세요 (원)", min_value=0, step=1000)
    memo = st.text_input("상세 내역 (메모)")
    
    submitted = st.form_submit_button("내역 저장하기", use_container_width=True)

if submitted:
    insert_data(str(st.session_state['current_date']), type_, category, amount, memo)
    st.success(f"{category} 항목으로 저장되었습니다!")
    st.rerun()

st.divider()

# --- 통계 및 내역 조회 ---
df = load_data()

if not df.empty:
    df['date'] = pd.to_datetime(df['date']).dt.date
    df['year_month'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m')
    
    month_options = sorted(df['year_month'].unique(), reverse=True)
    selected_month = st.selectbox("조회할 월을 선택하세요", month_options)
    
    filtered_df = df[df['year_month'] == selected_month].copy()
    
    # 상단 요약 지표
    total_income = filtered_df[filtered_df['type'] == '수입']['amount'].sum()
    total_expense = filtered_df[filtered_df['type'] == '지출']['amount'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 수입", f"{total_income:,}원")
    c2.metric("이번 달 지출", f"{total_expense:,}원")
    c3.metric("남은 잔액", f"{total_income - total_expense:,}원")

    # --- 카테고리별 통계 차트 ---
    st.subheader("📊 카테고리별 지출 분석")
    
    # 지출 데이터만 필터링
    expense_df = filtered_df[filtered_df['type'] == '지출']
    
    if not expense_df.empty:
        # 카테고리별로 묶어서 합계 계산
        category_sum = expense_df.groupby('category')['amount'].sum().reset_index()
        
        # 막대 차트 그리기
        st.bar_chart(data=category_sum, x='category', y='amount', color="#FF4B4B")
        
        # 상세 수치 표시
        for i, row in category_sum.iterrows():
            st.write(f"**{row['category']}**: {row['amount']:,}원")
    else:
        st.info("이번 달 지출 내역이 없어 통계를 표시할 수 없습니다.")

    st.divider()
    st.subheader("📋 전체 내역 수정")
    
    # 표 출력을 위해 금액 포맷팅
    display_df = filtered_df.copy()
    display_df['amount'] = display_df['amount'].apply(lambda x: f"{x:,}")
    
    edited_df = st.data_editor(
        display_df,
        column_config={
            "id": None, "year_month": None,
            "type": st.column_config.SelectboxColumn("구분", options=["지출", "수입"]),
            "category": st.column_config.SelectboxColumn("카테고리", options=category_list),
            "amount": st.column_config.TextColumn("금액 (원)"),
            "date": st.column_config.DateColumn("날짜")
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("✅ 수정사항 저장", use_container_width=True):
        update_db(edited_df)
        st.success("데이터가 업데이트되었습니다.")
        st.rerun()
else:
    st.info("저장된 내역이 없습니다.")