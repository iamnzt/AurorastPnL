import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ssl
import requests
from io import BytesIO

# --- 🛠 ЛЕЧЕНИЕ SSL И ЗАВИСАНИЙ ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- Конфигурация ---
st.set_page_config(page_title="Финансовый Симулятор", layout="wide")

# --- 🎨 PRO STYLES (CSS) ---
st.markdown("""
    <style>
    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #e0e0e0;
    }
    /* Revenue Metric specific highlight */
    div[data-testid="stMetric"]:nth-child(1) [data-testid="stMetricValue"] {
        color: #2e7d32; /* Green shade */
        font-weight: bold;
        font-size: 2rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Ссылка на таблицу ---
SHEET_ID = "1NUpmMswEtKyX1AIeM9p1m8VHjWpPnR8VeJfr1m7Qgsg"
GID = "1677404640" 
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

@st.cache_data(ttl=600) # Кэшируем на 10 минут, чтобы не грузить постоянно
def load_fixed_costs():
    try:
        # 1. Явное скачивание файла (это надежнее, чем pd.read_excel(url))
        headers = {'User-Agent': 'Mozilla/5.0'} # Притворяемся браузером
        response = requests.get(EXPORT_URL, headers=headers, verify=False, timeout=10)
        response.raise_for_status() # Если ошибка 404/500 - скажет сразу
        
        # 2. Превращаем скачанное в файл для Pandas
        file_content = BytesIO(response.content)
        df = pd.read_excel(file_content)
        
        # 3. Логика фильтрации (берем суммы > 100)
        clean_data = []
        total_sum = 0
        
        # Проверяем, есть ли нужные колонки по индексам (0 и 4)
        if df.shape[1] < 5:
            st.error("В таблице мало колонок! Проверьте формат.")
            return 0, pd.DataFrame()

        for index, row in df.iterrows():
            try:
                # Берем данные по индексам колонок (0 - Название, 4 - Сумма E)
                name = str(row.iloc[0]) 
                value = row.iloc[4]     
                
                # Превращаем в число
                numeric_value = float(value)
                
                # Фильтр: только суммы > 100 (исключаем пустые и проценты)
                if numeric_value > 100:
                    clean_data.append({"Расход": name, "Сумма": numeric_value})
                    total_sum += numeric_value
            except:
                continue # Если строка пустая или ошибка - пропускаем
                
        return total_sum, pd.DataFrame(clean_data)
        
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return 0, pd.DataFrame()

# Загрузка
with st.spinner('Скачиваем данные из таблицы...'):
    base_fixed_costs, details_df = load_fixed_costs()

# --- Интерфейс ---

with st.sidebar:
    st.header("🎛 Панель Управления")
    
    st.divider()
    
    st.subheader("1. 💸 Переменные Расходы")
    target_daily = st.number_input("📢 Таргет в день (₸)", value=5000, step=1000)
    st.caption(f"В месяц: {target_daily * 30:,.0f} ₸")
    
    simulation_add = st.number_input("➕ Добавить к расходам (Симуляция)", value=0, step=50000)
    var_cost_per_order = st.number_input("📦 Расход на 1 заказ (упаковка)", value=1000, step=100)

    st.divider()
    st.subheader("2. 💐 Экономика Заказа")
    avg_check = st.slider("💰 Средний чек", 5000, 50000, 15000, step=500)
    markup = st.slider("📈 Накрутка (Markup)", 1.5, 3.5, 2.2, step=0.1)
    
    st.divider()
    st.subheader("3. 🏦 Комиссии (%)")
    pct_kaspi = st.number_input("Kaspi Pay", value=0.95, step=0.05)
    pct_tax = st.number_input("Налог", value=3.0, step=0.5)
    pct_florist = st.number_input("Флорист", value=2.0, step=0.5)
    pct_manager = st.number_input("Менеджер", value=2.0, step=0.5)

# --- Расчеты ---
total_fixed_costs = base_fixed_costs + (target_daily * 30) + simulation_add
cogs = avg_check / markup
total_commission_pct = pct_kaspi + pct_tax + pct_florist + pct_manager
commission_money = avg_check * (total_commission_pct / 100)
margin_per_order = avg_check - cogs - var_cost_per_order - commission_money

if margin_per_order > 0:
    break_even_qty = total_fixed_costs / margin_per_order
    break_even_revenue = break_even_qty * avg_check
else:
    break_even_qty = 999999
    break_even_revenue = 0

# --- Визуализация ---
st.title("🛡 Финансовый Симулятор: Точка Безубыточности")
st.markdown("### 📊 Ключевые показатели месяца")

with st.container(border=True):
    col1, col2, col3 = st.columns(3)

    # 1. Revenue
    col1.metric(
        "🎯 ТОЧКА БЕЗУБЫТОЧНОСТИ", 
        f"{break_even_revenue:,.0f} ₸".replace(",", " "), 
        f"В день: {(break_even_revenue/30):,.0f} ₸"
    )

    # 2. Fixed Costs
    col2.metric(
        "📉 Постоянные Расходы", 
        f"{total_fixed_costs:,.0f} ₸".replace(",", " "), 
        "Нужно покрыть"
    )

    # 3. Quantity
    daily_qty = break_even_qty / 30 if break_even_qty != 999999 else 0
    col3.metric(
        "📦 В букетах", 
        f"{break_even_qty:,.0f} шт".replace(",", " "), 
        f"~ {daily_qty:.1f} заказов/день"
    )

with st.expander("🔍 Детализация постоянных расходов (из Таблицы)"):
    st.dataframe(details_df, use_container_width=True)
    st.write(f"**+ 📢 Таргет (мес):** {target_daily*30:,.0f}")
    st.write(f"**+ 🎰 Симуляция:** {simulation_add:,.0f}")
    st.info(f"💰 **ИТОГО FIX: {total_fixed_costs:,.0f} ₸**")

# График
if margin_per_order > 0:
    st.divider()
    st.subheader("📈 График Безубыточности")
    
    x_max = int(break_even_qty * 1.5)
    if x_max < 50: x_max = 50
    x_values = [0, x_max]
    
    var_total_per_unit = cogs + var_cost_per_order + commission_money
    y_costs = [total_fixed_costs, total_fixed_costs + (var_total_per_unit * x_max)]
    y_revenue = [0, avg_check * x_max]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_values, y=y_costs, mode='lines', name='Расходы', line=dict(color='#d32f2f', width=3)))
    fig.add_trace(go.Scatter(x=x_values, y=y_revenue, mode='lines', name='Выручка', line=dict(color='#2e7d32', width=3)))
    fig.add_trace(go.Scatter(x=[break_even_qty], y=[break_even_revenue], mode='markers', marker=dict(size=14, color='black', symbol='x'), name='Точка Б/У'))
    
    fig.update_layout(
        title="Динамика Выручки и Расходов", 
        height=500, 
        xaxis_title="Количество заказов", 
        yaxis_title="Сумма (₸)",
        hovermode="x unified",
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Калькулятор: Сколько я заработаю? ---
    st.divider()
    
    # Оформляем блок в контейнер с рамкой для выделения
    with st.container(border=True):
        st.subheader("🔮 Калькулятор Прибыли")
        st.markdown("*Введите желаемую выручку, чтобы узнать ваш реальный доход.*")
        
        # А. Ввод данных
        planned_revenue = st.number_input(
            "Введите планируемую выручку (₸)", 
            value=2500000, 
            step=100000,
            help="Какую сумму вы хотите увидеть в кассе?"
        )
        
        # Б. Логика расчета
        calc_bouquets_count = planned_revenue / avg_check
        total_variable_calc = calc_bouquets_count * var_total_per_unit
        calc_net_profit = planned_revenue - total_fixed_costs - total_variable_calc
        
        if planned_revenue > 0:
            calc_rentability = (calc_net_profit / planned_revenue) * 100
        else:
            calc_rentability = 0
            
        # В. Визуализация ответа
        st.divider()
        c1, c2, c3 = st.columns(3)
        
        # Индикация цветом
        if calc_net_profit >= 0:
            result_color = "normal"
            profit_label = "✅ ЧИСТАЯ ПРИБЫЛЬ"
        else:
            result_color = "inverse"
            profit_label = "🔻 УБЫТОК"

        c1.metric(
            profit_label,
            f"{calc_net_profit:,.0f} ₸".replace(",", " "), 
            f"{calc_rentability:.1f}% Рентабельность",
            delta_color=result_color
        )
        
        c2.metric(
            "📅 Выручка в день",
            f"{(planned_revenue/30):,.0f} ₸".replace(",", " "),
            "Чтобы достичь цели"
        )

        c3.metric(
            "📦 Объем продаж",
            f"{calc_bouquets_count:.0f} шт",
            "Потребуется букетов"
        )
        
        if calc_net_profit >= 0:
            st.success(f"🎉 **Отличная работа!** При выручке **{planned_revenue:,.0f}** вы кладете в карман **{calc_net_profit:,.0f} ₸**.")
        else:
            st.error(f"⚠️ **Внимание!** При такой выручке вы уходите в минус на **{abs(calc_net_profit):,.0f} ₸**.")

else:
    st.error("⛔️ **Критическая ошибка модели:** Вы теряете деньги с каждого заказа! (Отрицательная маржа).")
