import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import BytesIO
import ssl
import datetime

# --- НАСТРОЙКИ ---
SHEET_ID = "1GmPi4yQ3bcSAOF_9XAbCdOw-PW3ptPv4Z61hHNrbIvA"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

# --- PAGE CONFIG ---
st.set_page_config(page_title="Аналитика Продаж", layout="wide", page_icon="🏆")

# --- CUSTOM CSS (PREMIUM UI) ---
st.markdown("""
    <style>
    /* Global Background */
    .stApp {
        background-color: #f8f9fc;
    }
    
    /* Metrics Styling */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e4e8;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        transition: all 0.3s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.05);
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        color: #1e293b;
        font-weight: 700;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #ffffff;
        border-radius: 8px;
        color: #64748b;
        font-weight: 600;
        border: 1px solid #e2e8f0;
        padding: 0 20px;
        margin-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        border-color: #3b82f6 !important;
    }

    /* DataFrame */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    </style>
    """, unsafe_allow_html=True)

# --- UTILS ---
@st.cache_resource(ttl=300)
def load_excel_file():
    # Helper to load from bytes
    def read_bytes(b):
        try:
            return pd.ExcelFile(BytesIO(b), engine='openpyxl')
        except:
             return pd.ExcelFile(BytesIO(b))

    # 1. Try Requests
    try:
        try:
            _create_unverified_https_context = ssl._create_unverified_context
            ssl._create_default_https_context = _create_unverified_https_context
        except: pass

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(EXPORT_URL, headers=headers, verify=False, timeout=30)
        if response.status_code == 200:
             return read_bytes(response.content)
        else:
            print(f"Requests failed with status {response.status_code}, trying curl...")
    except Exception as e:
        print(f"Requests error: {e}, trying curl...")

    # 2. Fallback to Curl
    try:
        import subprocess
        # Use a localized temp file to confirm download
        cmd = ["curl", "-L", "-k", "-s", EXPORT_URL]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and len(result.stdout) > 0:
            return read_bytes(result.stdout)
    except Exception as e:
        st.error(f"Curl error: {e}")

    st.error("Не удалось загрузить файл ни одним методом.")
    return None

# --- MAIN ---
xls = load_excel_file()

if xls:
    # --- SIDEBAR: Sheet Selection ---
    with st.sidebar:
        st.title("⚙️ Настройки")
        all_sheets = [s for s in xls.sheet_names if "оффлайн" not in s.lower()]
        default_index = len(all_sheets) - 1 if len(all_sheets) > 0 else 0
        selected_sheet = st.selectbox("Период (Месяц):", all_sheets, index=default_index)
        st.info("Выберите месяц для загрузки данных и переключайтесь между вкладками справа.")

    # --- DATA LOADING & PROC ---
    try:
        df = pd.read_excel(xls, sheet_name=selected_sheet)
        
        # Column Map
        column_map = {}
        for col in df.columns:
            col_str = str(col).lower()
            if "имя менеджера" in col_str: column_map[col] = "Manager"
            elif "лидов" in col_str: column_map[col] = "Leads"
            elif "оформлены" in col_str: column_map[col] = "Orders"
            elif "итого" in col_str: column_map[col] = "Revenue"
            elif "дата" in col_str: column_map[col] = "Date"

        df = df.rename(columns=column_map)
        
        # Validation
        val_req = ['Manager', 'Leads', 'Orders', 'Revenue', 'Date']
        if not all(col in df.columns for col in val_req):
            st.warning(f"⚠️ Не найдены обязательные колонки на листе '{selected_sheet}'. Проверьте структуру.")
            st.stop()

        # Clean Data
        df = df.dropna(subset=['Manager', 'Date'])
        # Convert Date
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date']) # drop invalid dates
        # Numeric Clean
        for col in ['Leads', 'Orders', 'Revenue']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Global Calculation
        df['Conversion'] = (df['Orders'] / df['Leads'] * 100).fillna(0)

        # Totals
        total_leads = df['Leads'].sum()
        total_orders = df['Orders'].sum()
        total_revenue = df['Revenue'].sum()
        avg_conv = (total_orders / total_leads * 100) if total_leads > 0 else 0
        avg_check = (total_revenue / total_orders) if total_orders > 0 else 0

        # Title
        st.title(f"🏆 Рентген Отдела: {selected_sheet}")
        st.markdown(f"**Данные актуальны на:** {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}")
        st.divider()

        # --- TABS ---
        tab1, tab2, tab3 = st.tabs(["📊 Главная Сводка", "📅 Ежедневная Динамика", "👤 Менеджеры"])

        # TAB 1: OVERVIEW
        with tab1:
            st.markdown("### 🚀 Ключевые показатели месяца")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💰 Выручка", f"{total_revenue:,.0f} ₸".replace(",", " "), delta="Итого")
            c2.metric("🎯 Конверсия", f"{avg_conv:.1f}%", help="Отношение Оформленных к Лидам")
            c3.metric("🧾 Ср. чек", f"{avg_check:,.0f} ₸".replace(",", " "))
            
            # Обновленная метрика: Лиды / Заказы
            c4.metric("📨 Лидов (Вход / Закрыто)", f"{total_leads:,.0f} / {total_orders:,.0f}".replace(",", " "))
            
            st.markdown("---")
            
            # Leaderboard Chart
            st.subheader("🏆 Эффективность Менеджеров")
            st.caption("График: Сравнение по средним продажам за смену и конверсии")
            
            # Aggregate per Manager
            mgr_stats = df.groupby('Manager').agg({
                'Revenue':'sum', 
                'Orders':'sum', 
                'Leads':'sum',
                'Date': 'nunique' # Shifts count
            }).reset_index()
            
            mgr_stats['Conversion'] = (mgr_stats['Orders'] / mgr_stats['Leads'] * 100).fillna(0)
            mgr_stats['AvgShiftSales'] = (mgr_stats['Revenue'] / mgr_stats['Date']).fillna(0)
            
            mgr_stats = mgr_stats.sort_values('AvgShiftSales', ascending=False)
            
            # Combined Chart
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=mgr_stats['Manager'], 
                y=mgr_stats['AvgShiftSales'], 
                name='Продажи за смену', 
                marker_color='#8b5cf6',
                opacity=0.8,
                yaxis='y1'
            ))
            fig.add_trace(go.Scatter(
                x=mgr_stats['Manager'], 
                y=mgr_stats['Conversion'], 
                name='Конверсия %', 
                mode='lines+markers+text', 
                text=[f"{x:.1f}%" for x in mgr_stats['Conversion']],
                textposition="top center",
                line=dict(color='#ef4444', width=3), 
                yaxis='y2'
            ))
            fig.update_layout(
                title="Ср. продажи за смену vs Конверсия",
                yaxis=dict(title="Ср. продажи за смену (₸)", side="left", showgrid=False),
                yaxis2=dict(title="Конверсия", side="right", overlaying="y", showgrid=False),
                legend=dict(orientation="h", y=1.1, x=0.3),
                margin=dict(l=20, r=20, t=50, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)

            # --- НОВАЯ ТАБЛИЦА ПОД ГРАФИКОМ ---
            st.markdown("### 📋 Детальная статистика")
            
            # Готовим красивую таблицу
            table_df = mgr_stats.copy()
            table_df = table_df.rename(columns={
                'Manager': 'Имя менеджера',
                'Date': 'Смен',
                'AvgShiftSales': 'Среднее закрытие (₸)',
                'Leads': 'Поступило лидов',
                'Orders': 'Закрыто лидов',
                'Conversion': 'Конверсия (%)'
            })
            
            # Порядок колонок
            table_df = table_df[['Имя менеджера', 'Смен', 'Среднее закрытие (₸)', 'Поступило лидов', 'Закрыто лидов', 'Конверсия (%)']]
            
            # Вывод стилизованной таблицы
            st.dataframe(
                table_df.style.format({
                    'Среднее закрытие (₸)': '{:,.0f}',
                    'Поступило лидов': '{:.0f}',
                    'Закрыто лидов': '{:.0f}',
                    'Конверсия (%)': '{:.1f}%'
                }),
                use_container_width=True
            )

        # TAB 2: DAILY DYNAMICS
        with tab2:
            st.markdown("### 📅 Анализ по дням")
            
            # Daily Aggregation
            daily_stats = df.groupby('Date').agg({'Revenue':'sum', 'Orders':'sum', 'Leads':'sum'}).reset_index()
            daily_stats = daily_stats.sort_values('Date')
            
            # 1. Bar Chart: Total Revenue Trend WITH TEXT AUTO
            fig_trend = px.bar(daily_stats, x='Date', y='Revenue', 
                                title="Динамика Общей Выручки (По дням)", 
                                text_auto='.2s',
                                color_discrete_sequence=['#3b82f6'])
            fig_trend.update_xaxes(dtick="D1", tickformat="%d.%m")
            fig_trend.update_yaxes(showgrid=True, gridcolor='rgba(0,0,0,0.05)')
            fig_trend.update_traces(textposition='outside')
            fig_trend.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=50, b=50))
            st.plotly_chart(fig_trend, use_container_width=True)

            st.markdown("---")
            
            # 2. Multi-Line Chart: Individual Manager Dynamics
            st.subheader("📈 Динамика менеджеров (Вклад каждого)")
            
            daily_mgr = df.groupby(['Date', 'Manager'])['Revenue'].sum().reset_index()
            
            fig_multi = px.line(daily_mgr, x='Date', y='Revenue', color='Manager',
                                title="Кто и сколько продал в конкретный день",
                                markers=True)
            fig_multi.update_xaxes(dtick="D1", tickformat="%d.%m")
            fig_multi.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                    legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_multi, use_container_width=True)

            st.markdown("---")
            
            # 3. Matrix Table (Styled DataFrame) Instead of Heatmap
            st.subheader("🗓 Матрица Продаж")
            st.caption("Подробная таблица выручки: Менеджеры vs Дни")
            
            try:
                # Add Short Day Column
                df['Day'] = df['Date'].dt.strftime('%d.%m')
                # Pivot: Manager x Day -> Revenue
                pivot_rev_table = df.pivot_table(index='Manager', columns='Day', values='Revenue', aggfunc='sum', fill_value=0)
                
                # Highlight logic
                st.dataframe(pivot_rev_table.style.format("{:,.0f}").background_gradient(cmap="Blues", axis=None), use_container_width=True)
                
            except Exception as ex:
                st.warning("Недостаточно данных для матрицы.")

        # TAB 3: MANAGERS
        with tab3:
            st.markdown("### 👤 Персональная статистика")
            
            managers = sorted(df['Manager'].unique())
            c_sel, _ = st.columns([1, 2])
            with c_sel:
                sel_mgr = st.selectbox("Выберите менеджера:", managers)
            
            # Filter Data
            mgr_df = df[df['Manager'] == sel_mgr]
            
            # Aggregates for Manager
            m_rev = mgr_df['Revenue'].sum()
            m_ord = mgr_df['Orders'].sum()
            m_leads = mgr_df['Leads'].sum()
            m_shifts = mgr_df['Date'].nunique()
            
            m_conv = (m_ord / m_leads * 100) if m_leads > 0 else 0
            m_avg_shift = (m_rev / m_shifts) if m_shifts > 0 else 0
            
            # Metrics Row
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("🗓 Продажи за смену", f"{m_avg_shift:,.0f} ₸".replace(",", " "))
            mc2.metric("🎯 Личная Конверсия", f"{m_conv:.1f}%")
            mc3.metric("💰 Общая Выручка", f"{m_rev:,.0f} ₸".replace(",", " "))
            mc4.metric("📨 Лидов / Смен", f"{m_leads:.0f} / {m_shifts}")
            
            st.divider()
            
            # Manager Trend
            c_chart1, c_chart2 = st.columns([2, 1])
            
            with c_chart1:
                st.subheader(f"📊 Ежедневные продажи: {sel_mgr}")
                m_daily = mgr_df.groupby('Date')['Revenue'].sum().reset_index()
                
                fig_m = px.bar(m_daily, x='Date', y='Revenue', 
                               text_auto='.2s',
                               color_discrete_sequence=['#8b5cf6'])
                fig_m.update_xaxes(dtick="D1", tickformat="%d.%m")
                fig_m.update_traces(textposition='outside')
                fig_m.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_m, use_container_width=True)
            
            # Compare to Avg
            with c_chart2:
                st.subheader("⚖️ Эффективность")
                # Avg stats for all managers
                avg_conv_all = avg_conv
                # Avg per shift for team
                total_shifts_all = df.groupby(['Manager', 'Date']).size().shape[0] # Count of unique manager-days
                avg_shift_all = (total_revenue / total_shifts_all) if total_shifts_all > 0 else 0
                
                comp_df = pd.DataFrame({
                    'Metric': ['Конверсия (%)', 'Продажи/Смена (₸)'],
                    'Вы': [m_conv, m_avg_shift],
                    'Среднее': [avg_conv_all, avg_shift_all]
                })
                
                st.dataframe(comp_df.style.format({
                    'Вы': '{:,.1f}', 
                    'Среднее': '{:,.1f}'
                }), use_container_width=True)
                
                # Visualization of Shift Efficiency
                fig_comp = px.bar(
                    x=['Вы', 'Среднее'], 
                    y=[m_avg_shift, avg_shift_all], 
                    title="Выручка за смену",
                    color=['Вы', 'Среднее'],
                    color_discrete_map={'Вы': '#8b5cf6', 'Среднее': '#cbd5e1'},
                    text_auto='.2s'
                )
                fig_comp.update_layout(showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_comp, use_container_width=True)

    except Exception as e:
        st.error(f"Ошибка обработки данных: {e}")
else:
    st.info("Загружаю данные...")
