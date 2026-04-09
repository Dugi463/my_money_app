import streamlit as st
import pandas as pd
import sqlite3
import datetime

# 1. 데이터베이스 연결 및 테이블 생성
def init_db():
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            amount INTEGER,
            memo TEXT
        )
    ''')
    conn.commit()
    conn.close()

# 2. 데이터 저장 함수
def insert_data(date, type_, amount, memo):
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    c.execute("INSERT INTO expenses (date, type, amount, memo) VALUES (?, ?, ?, ?)",
              (date, type_, amount, memo))
    conn.commit()
    conn.close()

# 3. 데이터 업데이트 함수 (수정용)
def update_db(edited_df):
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    for index, row in edited_df.iterrows():
        # 금액 열의 값에서 콤마(,)나 '원' 글자가 있으면 제거하고 순수 숫자로 변환합니다.
        clean_amount = int(str(row['amount']).replace(',', '').replace('원', '').strip())
        
        c.execute("""
            UPDATE expenses 
            SET date = ?, type = ?, amount = ?, memo = ? 
            WHERE id = ?
        """, (str(row['date']), row['type'], clean_amount, row['memo'], row['id']))
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
st.title('💰 나의 심플 가계부')

# 날짜 선택 조작
st.write("날짜 선택")
col_prev, col_date, col_next = st.columns([1, 4, 1])
with col_prev:
    # 버튼이 왼쪽 끝에 꽉 차도록 옵션 추가
    if st.button("◀ 이전", use_container_width=True):
        st.session_state['current_date'] -= datetime.timedelta(days=1)
with col_date:
    selected_date = st.date_input("날짜 입력", value=st.session_state['current_date'], label_visibility="collapsed")
    st.session_state['current_date'] = selected_date
with col_next:
    # 버튼이 오른쪽 끝에 꽉 차도록 옵션 추가
    if st.button("다음 ▶", use_container_width=True):
        st.session_state['current_date'] += datetime.timedelta(days=1)

# 입력 폼
with st.form("입력폼", clear_on_submit=True):
    type_ = st.radio("구분", ["지출", "수입"], index=0, horizontal=True)
    amount = st.number_input("금액을 입력하세요 (원)", min_value=0, step=1000)
    memo = st.text_input("어디에 쓰셨나요? (메모)")
    
    submitted = st.form_submit_button("내역 저장하기")

if submitted:
    insert_data(str(st.session_state['current_date']), type_, amount, memo)
    st.success("저장되었습니다!")
    st.rerun()

st.divider()

# --- 월별 내역 및 수정 ---
st.subheader("📋 내역 조회 및 수정")
df = load_data()

if not df.empty:
    df['date'] = pd.to_datetime(df['date']).dt.date
    df['year_month'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m')
    
    month_options = sorted(df['year_month'].unique(), reverse=True)
    selected_month = st.selectbox("조회할 월을 선택하세요", month_options)
    
    filtered_df = df[df['year_month'] == selected_month].copy()
    
    # 1. 요약 지표 계산 (데이터가 순수 숫자일 때 미리 합계를 구합니다)
    total_income = filtered_df[filtered_df['type'] == '수입']['amount'].sum()
    total_expense = filtered_df[filtered_df['type'] == '지출']['amount'].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("총 수입", f"{total_income:,}원")
    col2.metric("총 지출", f"{total_expense:,}원")
    col3.metric("잔액", f"{total_income - total_expense:,}원")
    
    st.info("💡 표의 칸을 더블 클릭해서 수정 후 아래 '수정사항 저장' 버튼을 누르세요. (금액은 콤마 없이 숫자만 입력해도 됩니다)")
    
    # 2. 표 출력을 위해 금액 데이터를 천 단위 콤마가 있는 '문자열'로 변환합니다.
    filtered_df['amount'] = filtered_df['amount'].apply(lambda x: f"{x:,}")
    
    # 데이터 에디터 (수정 가능하게 만들기)
    edited_df = st.data_editor(
        filtered_df,
        column_config={
            "id": None, 
            "year_month": None, 
            "type": st.column_config.SelectboxColumn("구분", options=["지출", "수입"]),
            # 금액 열을 TextColumn으로 변경하여 콤마가 포함된 문자열을 표시합니다.
            "amount": st.column_config.TextColumn("금액 (원)"),
            "date": st.column_config.DateColumn("날짜")
        },
        hide_index=True,
        use_container_width=True
    )

    # 수정된 내용이 있을 경우 DB에 반영
    if st.button("✅ 수정사항 저장"):
        update_db(edited_df)
        st.success("데이터베이스에 반영되었습니다!")
        st.rerun()
    
else:
    st.info("아직 저장된 내역이 없습니다.")