import streamlit as st
import pandas as pd
import sqlite3
import datetime
import altair as alt

# 1. 데이터베이스 연결 및 테이블 생성
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

# 5. 데이터 삭제 함수 (새로 추가)
def delete_data(ids):
    if not ids:
        return
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    # 선택된 ID들을 한꺼번에 삭제합니다.
    query = f"DELETE FROM expenses WHERE id IN ({','.join(map(str, ids))})"
    c.execute(query)
    conn.commit()
    conn.close()
    
init_db()

# --- 세션 상태 초기화 ---
if 'current_date' not in st.session_state:
    st.session_state['current_date'] = datetime.date.today()

category_list = ["식비", "교통", "쇼핑", "의료", "주거", "여가", "저축", "기타"]

### --- 화면 구성 (수정된 부분) ---
st.title('💰 나의 스마트 가계부')

st.write("날짜 선택")
col_prev, col_date, col_next = st.columns([1, 4, 1])

with col_prev:
    if st.button("◀ 이전", use_container_width=True):
        st.session_state['current_date'] -= datetime.timedelta(days=1)
        st.rerun()  # 즉시 화면을 새로고침하여 바뀐 날짜를 반영

with col_date:
    # date_input의 value는 session_state를 바라보게 합니다.
    selected_date = st.date_input("날짜 입력", value=st.session_state['current_date'], label_visibility="collapsed")
    # 사용자가 달력에서 직접 날짜를 선택했을 때를 위해 state를 동기화합니다.
    st.session_state['current_date'] = selected_date

with col_next:
    if st.button("다음 ▶", use_container_width=True):
        st.session_state['current_date'] += datetime.timedelta(days=1)
        st.rerun()  # 즉시 화면을 새로고침하여 바뀐 날짜를 반영
###

with st.form("입력폼", clear_on_submit=True):
    col_t, col_c = st.columns(2)
    with col_t:
        type_ = st.radio("구분", ["지출", "수입"], index=0, horizontal=True)
    with col_c:
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
    
    total_income = filtered_df[filtered_df['type'] == '수입']['amount'].sum()
    total_expense = filtered_df[filtered_df['type'] == '지출']['amount'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("이번 달 수입", f"{total_income:,}원")
    c2.metric("이번 달 지출", f"{total_expense:,}원")
    c3.metric("남은 잔액", f"{total_income - total_expense:,}원")

    # --- 카테고리별 통계 차트 ---
    st.subheader("📊 카테고리별 지출 분석")

    base_categories = pd.DataFrame({'category': category_list})
    expense_df = filtered_df[filtered_df['type'] == '지출']
    
    if not expense_df.empty:
        category_sum = expense_df.groupby('category')['amount'].sum().reset_index()
    else:
        category_sum = pd.DataFrame(columns=['category', 'amount'])
        
    merged_df = pd.merge(base_categories, category_sum, on='category', how='left').fillna(0)
    
    color_scale = alt.Scale(scheme='set2')

    base_chart = alt.Chart(merged_df).encode(
        x=alt.X('category:N', sort=category_list, axis=alt.Axis(labelAngle=0, title='카테고리'))
    )

    bars = base_chart.mark_bar().encode(
        y=alt.Y('amount:Q', axis=alt.Axis(title='금액 (원)')),
        color=alt.Color('category:N', scale=color_scale, legend=None),
        tooltip=[alt.Tooltip('category', title='카테고리'), alt.Tooltip('amount', title='금액', format=',d')]
    )

    text = base_chart.mark_text(
        align='center',
        baseline='bottom',
        dy=-5, 
        fontSize=12, 
    ).encode(
        y=alt.Y('amount:Q'),
        text=alt.Text('amount:Q', format=',.0f')
    )

    chart = alt.layer(bars, text).properties(height=380)

    st.altair_chart(chart, use_container_width=True)

    #### 파이 차트 추가 예시
    st.subheader("🍕 지출 비중")
    pie_chart = alt.Chart(merged_df).mark_arc(innerRadius=50).encode(
        theta=alt.Theta(field="amount", type="quantitative"),
        color=alt.Color(field="category", type="nominal", scale=color_scale),
        tooltip=['category', 'amount']
    ).properties(height=300)

    st.altair_chart(pie_chart, use_container_width=True)
    ####

    st.write("**상세 지출 내역**")
    cols = st.columns(4)
    for i, row in merged_df.iterrows():
        cols[i % 4].write(f"{row['category']}: {int(row['amount']):,}원")

    st.divider()
    st.subheader("📋 전체 내역 수정")
    st.info("💡 표의 칸을 더블 클릭해서 내용을 수정한 후, 아래 [✅ 수정사항 저장] 버튼을 눌러야 반영됩니다.")
    

    display_df = filtered_df.copy()
# 숫자로 변환하여 편집 가능하게 함
display_df['amount'] = pd.to_numeric(display_df['amount'].astype(str).str.replace(',', ''), errors='coerce')

edited_df = st.data_editor(
    display_df,
    column_order=["date", "type", "amount", "category", "memo"],
    column_config={
        "id": None, "year_month": None,
        "type": st.column_config.SelectboxColumn("구분", options=["지출", "수입"]),
        "category": st.column_config.SelectboxColumn("카테고리", options=category_list),
        "amount": st.column_config.NumberColumn("금액 (원)", format="%d"),
        "date": st.column_config.DateColumn("날짜"),
        "memo": st.column_config.TextColumn("메모")
    },
    hide_index=True,
    use_container_width=True,
    num_rows="dynamic",  # 행 삭제/추가 활성화
    key="expense_editor" # 상태 추적용 키
)


if st.button("✅ 변경사항(수정/삭제) 저장", use_container_width=True):
    # 1. 삭제된 행 처리
    deleted_indices = st.session_state["expense_editor"].get("deleted_rows", [])
    if deleted_indices:
        ids_to_delete = display_df.iloc[deleted_indices]['id'].tolist()
        delete_data(ids_to_delete)

    # 2. 수정된 행 처리 (기존 함수 활용)
    update_db(edited_df)

    st.success("성공적으로 반영되었습니다!")
    st.rerun()

    