
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import BytesIO
import ssl
import datetime

# --- НАСТРОЙКИ ГОРОДОВ ---
CITIES = {
    "🌸 Алматы": "1GmPi4yQ3bcSAOF_9XAbCdOw-PW3ptPv4Z61hHNrbIvA",
    "🏙 Астана": "1ZpSAtOcA8X1PWfrfbIrvZKwlC2_JyRN5nptzOunOm0A"
}

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Аналитика Продаж", layout="wide", page_icon="🏆")

# --- СТИЛЬ (CSS) ---
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fc; }
    div[data-testid="metric-container"] {
        background-color: #ffffff; border: 1px solid #e0e4e8;
        padding: 15px; border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    h1, h2, h3 { font-family: 'Inter', sans-serif; color: #1e293b; }
    </style>
    """, unsafe_allow_html=True)

# --- ЗАГРУЗЧИК ---
@st.cache_data(ttl=300)
def load_excel_data(sheet_id):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    
    def read_bytes(b):
        try: return pd.ExcelFile(BytesIO(b), engine='openpyxl')
        except: return pd.ExcelFile(BytesIO(b))

    try:
        try:
            _create_unverified_https_context = ssl._create_unverified_context
            ssl._create_default_https_context = _create_unverified_https_context
        except: pass

        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, verify=False, timeout=30)
        if response.status_code == 200:
            return read_bytes(response.content)
    except Exception:
        pass

    try:
        import subprocess
        cmd = ["curl", "-L", "-k", "-s", url]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0 and len(result.stdout) > 0:
            return read_bytes(result.stdout)
    except Exception:
        pass

    st.error("⚠️ Не удалось скачать файл. Попробуйте обновить страницу.")
    return None

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.title("🌍 Филиал")
    selected_city_name = st.selectbox("Выберите город:", list(CITIES.keys()))
    current_id = CITIES[selected_city_name]
    
    st.divider()
    
    xls = load_excel_data(current_id)
    
    if xls:
        # Фильтр: только 2026 и без "оффлайн"
        all_sheets = [s for s in xls.sheet_names if "2026" in s and "оффлайн" not in s.lower()]
        
        if not all_sheets:
            all_sheets = [s for s in xls.sheet_names if "sheet" not in s.lower()]

        st.header("📅 Период")
        default_idx = len(all_sheets) - 1 if all_sheets else 0
        selected_sheet = st.selectbox("Месяц:", all_sheets, index=default_idx)
    else:
        st.stop()

# --- ОСНОВНАЯ ЛОГИКА ---
if selected_sheet:
    try:
        df = pd.read_excel(xls, sheet_name=selected_sheet)
        
        # Поиск колонок
        col_map = {}
        for col in df.columns:
            c = str(col).lower()
            if "имя менеджера" in c: col_map[col] = "Manager"
            elif "лидов" in c: col_map[col] = "Leads"
            elif "оформлены" in c: col_map[col] = "Orders"
            elif "итого" in c: col_map[col] = "Revenue"
            elif "дата" in c: col_map[col] = "Date"
        
        df = df.rename(columns=col_map)
        
        req = ['Manager', 'Leads', 'Orders', 'Revenue', 'Date']
        if not all(k in df.columns for k in req):
            st.error(f"❌ На листе '{selected_sheet}' нет нужных колонок.")
            st.stop()

        df = df.dropna(subset=['Manager', 'Date'])
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        
        for k in ['Leads', 'Orders', 'Revenue']:
            df[k] = pd.to_numeric(df[k], errors='coerce').fillna(0)

        # Метрики
        total_rev = df['Revenue'].sum()
        total_leads = df['Leads'].sum()
        total_orders = df['Orders'].sum()
        avg_conv = (total_orders / total_leads * 100) if total_leads else 0
        avg_check = (total_rev / total_orders) if total_orders else 0

        # --- ЗАГОЛОВОК ---
        st.title(f"📊 Отчет: {selected_city_name} | {selected_sheet}")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Выручка", f"{total_rev:,.0f} ₸".replace(",", " "))
        c2.metric("🎯 Конверсия", f"{avg_conv:.1f}%")
        c3.metric("🧾 Ср. чек", f"{avg_check:,.0f} ₸".replace(",", " "))
        c4.metric("📨 Лидов / Продаж", f"{total_leads:.0f} / {total_orders:.0f}")

        st.divider()

        tab1, tab2, tab3 = st.tabs(["🏆 Рейтинг Команды", "📅 Динамика", "👤 Личная статистика"])

        # 1. РЕЙТИНГ
        with tab1:
            mgr_stats = df.groupby('Manager').agg({
                'Revenue': 'sum', 'Orders': 'sum', 'Leads': 'sum', 'Date': 'nunique'
            }).reset_index()
            
            mgr_stats['Conversion'] = (mgr_stats['Orders'] / mgr_stats['Leads'] * 100).fillna(0)
            mgr_stats['AvgShift'] = (mgr_stats['Revenue'] / mgr_stats['Date']).fillna(0)
            mgr_stats = mgr_stats.sort_values('AvgShift', ascending=False)

            # ГРАФИК (DESKTOP VERSION)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=mgr_stats['Manager'], y=mgr_stats['AvgShift'], 
                name='Выручка за смену', marker_color='#8b5cf6', yaxis='y1'
            ))
            fig.add_trace(go.Scatter(
                x=mgr_stats['Manager'], y=mgr_stats['Conversion'], 
                name='Конверсия %', mode='lines+markers+text', 
                text=[f"{x:.1f}%" for x in mgr_stats['Conversion']],
                textposition="top center",
                line=dict(color='#ef4444', width=3), yaxis='y2'
            ))
            
            fig.update_layout(
                title="Эффективность (Ср. выручка за смену vs Конверсия)",
                yaxis=dict(title="Тенге", side="left", showgrid=True, gridcolor='#f1f5f9'),
                yaxis2=dict(title="%", side="right", overlaying="y", showgrid=False),
                legend=dict(orientation="h", y=1.1, x=0), # Легенда СВЕРХУ
                height=600, # Высокий график
                margin=dict(l=50, r=50, t=80, b=50)
            )
            st.plotly_chart(fig, use_container_width=True)

            # ТАБЛИЦА
            st.markdown("### 📋 Детальная таблица")
            view_df = mgr_stats[['Manager', 'Date', 'AvgShift', 'Leads', 'Orders', 'Conversion']].copy()
            view_df.columns = ['Менеджер', 'Смен', 'Ср.Чек/Смена', 'Лиды', 'Заказы', 'Conv %']
            
            st.dataframe(
                view_df.style.format({
                    'Ср.Чек/Смена': '{:,.0f}', 'Conv %': '{:.1f}%', 'Лиды': '{:.0f}'
                }).background_gradient(subset=['Ср.Чек/Смена'], cmap="Blues"),
                use_container_width=True
            )

        # 2. ДИНАМИКА
        with tab2:
            st.markdown("### 📈 Выручка по дням")
            daily = df.groupby('Date')['Revenue'].sum().reset_index()
            fig_d = px.bar(daily, x='Date', y='Revenue', text_auto='.2s')
            fig_d.update_xaxes(dtick="D1", tickformat="%d.%m") 
            fig_d.update_layout(height=500)
            st.plotly_chart(fig_d, use_container_width=True)

        # 3. ЛИЧНАЯ СТАТИСТИКА
        with tab3:
            st.markdown("### 👤 Выберите менеджера")
            managers = sorted(df['Manager'].unique())
            sel_mgr = st.selectbox("Сотрудник:", managers)
            
            m_df = df[df['Manager'] == sel_mgr]
            
            m_rev = m_df['Revenue'].sum()
            m_leads = m_df['Leads'].sum()
            m_orders = m_df['Orders'].sum()
            m_shifts = m_df['Date'].nunique()
            m_conv = (m_orders / m_leads * 100) if m_leads else 0
            m_avg = (m_rev / m_shifts) if m_shifts else 0
            
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("🗓 В среднем за смену", f"{m_avg:,.0f} ₸".replace(",", " "))
            mc2.metric("🎯 Личная конверсия", f"{m_conv:.1f}%")
            mc3.metric("💰 Всего принес(ла)", f"{m_rev:,.0f} ₸".replace(",", " "))
            mc4.metric("📊 Смен отработано", f"{m_shifts}")
            
            st.divider()
            
            m_daily = m_df.groupby('Date')['Revenue'].sum().reset_index()
            fig_m = px.bar(m_daily, x='Date', y='Revenue', title=f"Продажи по дням: {sel_mgr}")
            fig_m.update_xaxes(dtick="D1", tickformat="%d.%m")
            fig_m.update_layout(height=500)
            st.plotly_chart(fig_m, use_container_width=True)

    except Exception as e:
        st.error(f"Ошибка обработки данных: {e}")
