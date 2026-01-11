import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import io
import ssl

# Bypass SSL verification for legacy environments
ssl._create_default_https_context = ssl._create_unverified_context

# --- Configuration ---
st.set_page_config(page_title="P&L Отчет", layout="wide")

# Updated Data Source
DATA_URL = "https://docs.google.com/spreadsheets/d/1NUpmMswEtKyX1AIeM9p1m8VHjWpPnR8VeJfr1m7Qgsg/export?format=xlsx"

# --- Helper Functions ---

def clean_amount(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.replace(' ', '').replace('\xa0', '')
        val = val.replace(',', '.')
        try:
            return float(val)
        except ValueError:
            return 0.0
    return 0.0

def get_russian_month_name(date_obj):
    if pd.isnull(date_obj):
        return None
    months = {
        1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
        5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
        9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
    }
    return months.get(date_obj.month)

def format_currency(value):
    """
    Format number: 1234567.89 -> "1 234 567" or "1 234 567.89"
    Removes decimals if .00
    Uses space as thousand separator.
    """
    if value == 0:
        return "0"
    
    # Check if integer (no decimals)
    if value % 1 == 0:
        return f"{int(value):,}".replace(",", " ")
    else:
         # Standard format with space, then replace dot if needed (user asked for dot OR space as separator, let's use space for thousands, dot for decimal)
         s = f"{value:,.2f}".replace(",", " ")
         return s

# --- Data Loading ---
@st.cache_data(ttl=300)
def load_data(url):
    try:
        response = requests.get(url, verify=False)
        response.raise_for_status()
        xls = pd.ExcelFile(io.BytesIO(response.content))
        df_expenses = pd.read_excel(xls, 'Лист1')
        df_target = pd.read_excel(xls, 'Таргет')
        df_sales = pd.read_excel(xls, 'Продажи по месяцам')
        return df_expenses, df_target, df_sales
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def preprocess_data(df_expenses, df_target, df_sales):
    # Expenses (List1)
    if not df_expenses.empty:
        if 'Сумма' in df_expenses.columns:
            df_expenses['Сумма'] = df_expenses['Сумма'].apply(clean_amount)
        if 'Дата' in df_expenses.columns:
            df_expenses['Дата'] = pd.to_datetime(df_expenses['Дата'], dayfirst=True, errors='coerce')
            df_expenses['Месяц'] = df_expenses['Дата'].apply(get_russian_month_name)
    
    # Target (Target Ads) - Renaming columns to match centralized schema (Date, Amount, Category)
    if not df_target.empty:
        if 'Сумма в тенге' in df_target.columns:
            df_target['Сумма'] = df_target['Сумма в тенге'].apply(clean_amount) # Create 'Amount'
        if 'Дата' in df_target.columns:
            df_target['Дата'] = pd.to_datetime(df_target['Дата'], dayfirst=True, errors='coerce')
            df_target['Месяц'] = df_target['Дата'].apply(get_russian_month_name)
        
        # Add explicit Category for Target rows
        df_target['Категория'] = 'Таргет'

    # Sales
    if not df_sales.empty and 'Месяц' in df_sales.columns:
        df_sales['Месяц'] = df_sales['Месяц'].astype(str).str.strip()
        if 'Сумма продаж' in df_sales.columns:
            df_sales['Сумма продаж'] = df_sales['Сумма продаж'].apply(clean_amount)
            
    return df_expenses, df_target, df_sales

# --- Main App ---
def main():
    st.title("Aurora Astana P&L Отчет")
    
    # Sidebar
    if st.sidebar.button("Обновить данные"):
        st.cache_data.clear()
        st.rerun()

    raw_expenses, raw_target, raw_sales = load_data(DATA_URL)
    
    if raw_sales.empty:
        st.warning("Не удалось загрузить данные (нет листа Продажи).")
        return

    df_expenses, df_target, df_sales = preprocess_data(raw_expenses.copy(), raw_target.copy(), raw_sales.copy())

    # Sidebar: Month Selection
    available_months = df_sales['Месяц'].unique().tolist() if 'Месяц' in df_sales.columns else []
    available_months = [m for m in available_months if m and str(m).lower() != 'nan']
    
    if not available_months:
        st.error("Не найдены месяцы в листе 'Продажи по месяцам'.")
        return

    selected_month = st.sidebar.selectbox("Выберите месяц", available_months)

    # --- Filtering & Logic ---
    
    # 1. Filter DataFrames
    expenses_curr = df_expenses[df_expenses['Месяц'] == selected_month].copy()
    target_curr = df_target[df_target['Месяц'] == selected_month].copy()
    sales_curr = df_sales[df_sales['Месяц'] == selected_month].copy()

    # 2. Combine Expenses (Regular + Target) for analysis
    # Need consistent columns: Дата, Категория, Сумма
    cols = ['Дата', 'Категория', 'Сумма']
    
    # Fix missing columns if empty
    if 'Категория' not in expenses_curr.columns: expenses_curr['Категория'] = 'Uncategorized'
    if 'Сумма' not in expenses_curr.columns: expenses_curr['Сумма'] = 0.0
    
    # Combine
    combined_expenses = pd.concat([
        expenses_curr[cols],
        target_curr[cols]
    ], ignore_index=True)

    # 3. Calculate KPI Values
    val_revenue = sales_curr['Сумма продаж'].sum() if not sales_curr.empty else 0.0
    val_expenses = combined_expenses['Сумма'].sum() if not combined_expenses.empty else 0.0
    val_net_profit = val_revenue - val_expenses

    # --- BLOCK 1: MAIN KPIs ---
    st.header("Ключевые показатели")
    kpi1, kpi2, kpi3 = st.columns(3)
    
    kpi1.metric("💰 ВЫРУЧКА", format_currency(val_revenue))
    kpi2.metric("📉 РАСХОДЫ", format_currency(val_expenses))
    kpi3.metric("💵 ЧИСТАЯ ПРИБЫЛЬ", format_currency(val_net_profit), 
                delta_color="normal" if val_net_profit >= 0 else "inverse")

    st.divider()

    # --- BLOCK 2: CHARTS ---
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Структура расходов (Топ)")
        if not combined_expenses.empty:
            # Group by Category
            cat_group = combined_expenses.groupby('Категория')['Сумма'].sum().reset_index()
            # Sort descending for horizontal bar (visual top-down)
            cat_group = cat_group.sort_values(by='Сумма', ascending=True) 
            
            fig_bar = px.bar(cat_group, x='Сумма', y='Категория', orientation='h', text_auto='.2s')
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}) 
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Нет данных")

    with c2:
        st.subheader("Доля расходов в %")
        if not combined_expenses.empty:
            # Group by Category for Pie Chart (All categories)
            pie_data = combined_expenses.groupby('Категория')['Сумма'].sum().reset_index()
            # Remove 0s
            pie_data = pie_data[pie_data['Сумма'] > 0]
            
            fig_donut = px.pie(pie_data, values='Сумма', names='Категория', hole=0.5)
            # Show percent
            fig_donut.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Нет данных")

    st.divider()

    # --- BLOCK 3: TABLES ---
    t1, t2 = st.columns(2)
    
    with t1:
        st.subheader("Детализация Расходов (Лист1)")
        if not expenses_curr.empty:
            # Sort by Date
            exp_display = expenses_curr.sort_values(by='Дата', ascending=False).copy()
            exp_display['Дата'] = exp_display['Дата'].dt.strftime('%d.%m.%Y')
            exp_display['Сумма'] = exp_display['Сумма'].apply(format_currency)
            st.dataframe(exp_display[['Дата', 'Категория', 'Сумма']], use_container_width=True, height=500)
        else:
            st.write("Нет расходов.")

    with t2:
        st.subheader("Детализация Таргета")
        if not target_curr.empty:
            # Sort by Date
            tgt_display = target_curr.sort_values(by='Дата', ascending=False).copy()
            tgt_display['Дата'] = tgt_display['Дата'].dt.strftime('%d.%m.%Y')
            tgt_display['Сумма'] = tgt_display['Сумма'].apply(format_currency)
            # Target usually doesn't have varied categories, but we added 'Таргет' column. 
            # We can show it or just Date/Amount. Let's show Category too for consistency or just Amount.
            st.dataframe(tgt_display[['Дата', 'Сумма']], use_container_width=True, height=500)
        else:
            st.write("Нет трат на таргет.")

if __name__ == "__main__":
    main()
