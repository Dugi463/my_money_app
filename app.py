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

# 4. 데이터 불러오기 함수 (문자를 숫자로 강제 변환)
def load_data():
    conn = sqlite3.connect('money.db')
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()
    if not df.empty:
        df['amount'] = df['amount'].astype(str).str.replace(',', '').str.replace('원', '').astype(int)
    return df

# 5. 데이터 삭제 함수
def delete_data(ids):
    if not ids:
        return
    conn = sqlite3.connect('money.db')
    c = conn.cursor()
    query = f"DELETE FROM expenses WHERE id IN ({','.join(map(str, ids))})"
    c.execute(query)
    conn.commit()
    conn.close()
    
# 6. CSV 내보내기용 변환 함수
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# 7. CSV 데이터를 DB에 업로드하는 함수
def import_csv_to_db(uploaded_file):
    try:
        import_df = pd.read_csv(uploaded_file)
        required_columns = ['date', 'type', 'category', 'amount', 'memo']
        
        if not all(col in import_df.columns for col in required_columns):
            st.error("CSV 파일 형식이 잘못되었습니다.")
            return
        
        import_df['date'] = pd.to_datetime(import_df['date'], format='mixed').dt.strftime('%Y-%m-%d')
        import_df['amount'] = import_df['amount'].astype(str).str.replace(',', '').str.replace('원', '').astype(int)

        conn = sqlite3.connect('money.db')
        import_df[required_columns].to_sql('expenses', conn, if_exists='append', index=False)
        conn.close()
        st.success(f"{len(import_df)}개의 내역을 가져왔습니다!")
        st.rerun()
    except Exception as e:
        st.error(f"오류 발생: {e}")

init_db()

# --- 세션 상태 초기화 ---
if 'current_date' not in st.session_state:
    st.session_state['current_date'] = datetime.date.today()

# 카테고리 (교육->여가, 의료->고정 반영)
category_list = ["식비", "교통", "쇼핑", "고정", "주거", "여가", "저축", "기타"]

# --- 화면 구성 ---
st.title('💰 나의 스마트 가계부')

st.write("날짜 선택")
col_prev, col_date, col_next = st.columns([1, 4, 1])

with col_prev:
    if st.button("◀ 이전", use_container_width=True):
        st.session_state['current_date'] -= datetime.timedelta(days=1)
        st.rerun() 

with col_date:
    selected_date = st.date_input("날짜 입력", value=st.session_state['current_date'], label_visibility="collapsed")
    st.session_state['current_date'] = selected_date

with col_next:
    if st.button("다음 ▶", use_container_width=True):
        st.session_state['current_date'] += datetime.timedelta(days=1)
        st.rerun() 

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
    df['date'] = pd.to_datetime(df['date'], format='mixed').dt.date
    df['year_month'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m')
    
    month_options = sorted(df['year_month'].unique(), reverse=True)
    selected_month = st.selectbox("조회할 월을 선택하세요", month_options)
    
    # 선택된 달의 데이터만 남깁니다.
    filtered_df = df[df['year_month'] == selected_month].copy()
    
    # 🌟 사이드바: 위치를 이곳으로 이동하여 '선택된 달'의 데이터만 백업되도록 합니다.
    with st.sidebar:
        st.header("📂 데이터 관리")
        
        st.subheader(f"데이터 백업 ({selected_month})")
        # 전체 데이터(all_data)가 아닌 선택된 달의 데이터(filtered_df)를 CSV로 변환
        csv_data = convert_df_to_csv(filtered_df)
        st.download_button(
            label=f"📥 {selected_month} 내역 CSV로 저장",
            data=csv_data,
            file_name=f"my_money_history_{selected_month}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.divider()
        
        st.subheader("데이터 복구/추가")
        uploaded_file = st.file_uploader("CSV 파일을 선택하세요", type=["csv"])
        if uploaded_file is not None:
            if st.button("🚀 DB에 데이터 추가하기", use_container_width=True):
                import_csv_to_db(uploaded_file)
    
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
    
    # 🌟 차트 데이터에서 '저축' 제외
    merged_df = merged_df[merged_df['category'] != '저축']
    chart_categories = [c for c in category_list if c != '저축']
    
    color_scale = alt.Scale(scheme='set2')

    base_chart = alt.Chart(merged_df).encode(
        x=alt.X('category:N', sort=chart_categories, axis=alt.Axis(labelAngle=0, title='카테고리'))
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

    #### 파이 차트 ####
    st.subheader("🍕 지출 비중")
    pie_chart = alt.Chart(merged_df).mark_arc(innerRadius=50).encode(
        theta=alt.Theta(field="amount", type="quantitative"),
        color=alt.Color(field="category", type="nominal", scale=color_scale),
        tooltip=['category', 'amount']
    ).properties(height=300)

    st.altair_chart(pie_chart, use_container_width=True)

    st.write("**상세 지출 내역**")
    cols = st.columns(4)
    for i, row in merged_df.iterrows():
        cols[i % 4].write(f"{row['category']}: {int(row['amount']):,}원")

    st.divider()
    st.subheader("📋 전체 내역 수정")
    st.info("💡 표의 칸을 더블 클릭해서 내용을 수정한 후, 아래 [✅ 변경사항 저장] 버튼을 눌러야 반영됩니다.")
    
    display_df = filtered_df.copy()
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
        num_rows="dynamic",  
        key="expense_editor" 
    )

    if st.button("✅ 변경사항(수정/삭제) 저장", use_container_width=True):
        deleted_indices = st.session_state["expense_editor"].get("deleted_rows", [])
        if deleted_indices:
            ids_to_delete = display_df.iloc[deleted_indices]['id'].tolist()
            delete_data(ids_to_delete)

        update_db(edited_df)
        st.success("성공적으로 반영되었습니다!")
        st.rerun()

else:
    # 데이터가 없을 때의 사이드바 (백업 없이 추가 기능만 제공)
    with st.sidebar:
        st.header("📂 데이터 관리")
        st.subheader("데이터 복구/추가")
        uploaded_file = st.file_uploader("CSV 파일을 선택하세요", type=["csv"])
        if uploaded_file is not None:
            if st.button("🚀 DB에 데이터 추가하기", use_container_width=True):
                import_csv_to_db(uploaded_file)
                
    st.info("저장된 내역이 없습니다.")