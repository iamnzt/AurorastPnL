import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import ssl

# Disable SSL verification for macOS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- Page Configuration ---
st.set_page_config(
    page_title="Калькулятор Накрутки",
    page_icon="🌸",
    layout="wide"
)

# --- Constants ---
SHEET_ID = "1NUpmMswEtKyX1AIeM9p1m8VHjWpPnR8VeJfr1m7Qgsg"
GID = "680482883"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx&gid={GID}"

# --- Data Loading ---
import requests
import io

# --- Data Loading ---
@st.cache_data(ttl=600)  # Cache for 10 minutes
def load_data():
    try:
        # Use requests to fetch data, which determines the file type
        response = requests.get(EXPORT_URL, timeout=10)
        response.raise_for_status() # Raise error for 400/500 codes
        
        # Load directly from bytes
        df = pd.read_excel(io.BytesIO(response.content))
        
        # Verify columns exist
        required_columns = ["Название", "Категория", "Себестоимость", "Цена_Базовая"]
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            st.error(f"Missing columns in Google Sheet: {missing}")
            return pd.DataFrame()
            
        # Select and Clean Data
        df = df[required_columns]
        df["Себестоимость"] = pd.to_numeric(df["Себестоимость"], errors='coerce').fillna(0)
        df["Цена_Базовая"] = pd.to_numeric(df["Цена_Базовая"], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

# --- Sidebar: Commissions ---
st.sidebar.header("⚙️ Настройки Комиссий")

# Defaults
default_kaspi = 0.95
default_florist = 2.0
default_manager = 2.0
default_tax = 3.0

pct_kaspi = st.sidebar.number_input("Kaspi Pay (%)", value=default_kaspi, min_value=0.0, step=0.05)
pct_florist = st.sidebar.number_input("Флористу (%)", value=default_florist, min_value=0.0, step=0.5)
pct_manager = st.sidebar.number_input("Менеджеру (%)", value=default_manager, min_value=0.0, step=0.5)
pct_tax = st.sidebar.number_input("Налог (%)", value=default_tax, min_value=0.0, step=0.5)

total_commission_pct = pct_kaspi + pct_florist + pct_manager + pct_tax
st.sidebar.markdown(f"**Всего комиссий: {total_commission_pct:.2f} %**")

# --- Main Logic: Cart ---
st.title("🌸 Калькулятор Цветочного Комбо")

if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- Section A: Add Item ---
st.subheader("1. Сборка Корзины")

col1, col2, col3 = st.columns([2, 3, 1])

with col1:
    categories = df["Категория"].dropna().unique().tolist()
    selected_category = st.selectbox("Категория", options=["Выберите..."] + categories)

with col2:
    if selected_category != "Выберите...":
        filtered_items = df[df["Категория"] == selected_category]
        item_names = filtered_items["Название"].tolist()
        selected_item_name = st.selectbox("Товар", options=item_names)
    else:
        selected_item_name = None
        st.selectbox("Товар", options=["Сначала выберите категорию"], disabled=True)

with col3:
    quantity = st.number_input("Количество", min_value=1, value=1, step=1)

# Show Hint
if selected_item_name:
    item_row = df[df["Название"] == selected_item_name].iloc[0]
    base_price = item_row["Цена_Базовая"]
    st.info(f"Базовая цена: {base_price:,.0f} ₸".replace(",", " "))

    if st.button("Добавить в состав", type="primary"):
        # Add to cart
        cart_item = {
            "Название": selected_item_name,
            "Количество": quantity,
            "Себестоимость_шт": item_row["Себестоимость"],
            "Цена_Базовая_шт": item_row["Цена_Базовая"],
            "Сумма_Себестоимости": item_row["Себестоимость"] * quantity,
            "Сумма_Базовая": item_row["Цена_Базовая"] * quantity
        }
        st.session_state.cart.append(cart_item)
        st.rerun()

# --- Section B: Cart Table ---
st.subheader("2. Состав Комбо")

if st.session_state.cart:
    cart_df = pd.DataFrame(st.session_state.cart)
    
    # Display table with formatting
    display_df = cart_df[["Название", "Количество", "Себестоимость_шт", "Сумма_Себестоимости", "Сумма_Базовая"]].copy()
    
    st.dataframe(
        display_df,
        column_config={
            "Себестоимость_шт": st.column_config.NumberColumn(format="%.0f ₸"),
            "Сумма_Себестоимости": st.column_config.NumberColumn(label="Сумма Себ.", format="%.0f ₸"),
            "Сумма_Базовая": st.column_config.NumberColumn(label="Сумма Баз. Цена", format="%.0f ₸"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("Очистить корзину"):
        st.session_state.cart = []
        st.rerun()

    total_material_cost = cart_df["Сумма_Себестоимости"].sum()
    total_base_price_sum = cart_df["Сумма_Базовая"].sum()
    
    st.markdown(f"#### ИТОГО СЕБЕСТОИМОСТЬ: :red[{total_material_cost:,.0f} ₸]".replace(",", " "))
    
    st.divider()
    
    # --- Section 3: Final Calculation ---
    st.subheader("3. Финальный Расчет и Накрутка")
    
    col_calc1, col_calc2 = st.columns(2)
    
    with col_calc1:
        target_markup = st.slider("Желаемая накрутка (от себестоимости)", min_value=1.5, max_value=4.0, value=2.5, step=0.1)
        suggested_price = total_material_cost * target_markup
        st.caption(f"Рекомендуемая цена (Себ. x {target_markup:.1f}): **{suggested_price:,.0f} ₸**")

    with col_calc2:
        final_price = st.number_input(
            "ИТОГОВАЯ ЦЕНА ПРОДАЖИ (₸)",
            value=float(suggested_price) if 'suggested_price' in locals() else float(total_base_price_sum), 
            step=100.0,
            format="%.0f"
        )
    
    # Calculations
    commission_cost = final_price * (total_commission_pct / 100)
    total_expenses = total_material_cost + commission_cost
    net_profit = final_price - total_expenses
    
    # Markup Metrics
    gross_markup = 0.0
    net_markup = 0.0
    
    if total_material_cost > 0:
        gross_markup = final_price / total_material_cost
        
    if total_expenses > 0:
        net_markup = final_price / total_expenses

    # Metrics Display
    st.markdown("### 📊 Результаты")
    
    # Row 1: Financials
    r1_c1, r1_c2, r1_c3 = st.columns(3)
    r1_c1.metric("💵 Выручка", f"{final_price:,.0f} ₸".replace(",", " "))
    r1_c2.metric("📉 Расходы (Мат.+Ком.)", f"{total_expenses:,.0f} ₸".replace(",", " "), delta_color="inverse")
    profit_color = "normal" if net_profit >= 0 else "inverse"
    r1_c3.metric("💰 Чистая Прибыль", f"{net_profit:,.0f} ₸".replace(",", " "), delta_color=profit_color)
    
    # Row 2: Markups
    r2_c1, r2_c2, r2_c3 = st.columns(3)
    r2_c1.metric("📈 Накрутка (Gross)", f"{gross_markup:.1f}x", help="Цена / Себестоимость материалов")
    r2_c2.metric("📉 Накрутка (Net)", f"{net_markup:.1f}x", help="Цена / (Себестоимость + Комиссии)")
    r2_c3.caption(f"Комиссии: **{commission_cost:,.0f} ₸** ({total_commission_pct}%)")

    if net_profit < 0:
        st.error(f"⚠️ УБЫТОК: {net_profit:,.0f} ₸")
    
    # Chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name='Себестоимость',
        x=['Структура'],
        y=[total_material_cost],
        marker_color='rgb(55, 83, 109)',
        text=[f"{total_material_cost:,.0f}"],
        textposition='auto'
    ))
    
    fig.add_trace(go.Bar(
        name='Комиссии',
        x=['Структура'],
        y=[commission_cost],
        marker_color='rgb(255, 160, 122)',
        text=[f"{commission_cost:,.0f}"],
        textposition='auto'
    ))
    
    if net_profit > 0:
        fig.add_trace(go.Bar(
            name='Прибыль',
            x=['Структура'],
            y=[net_profit],
            marker_color='rgb(60, 179, 113)',
            text=[f"{net_profit:,.0f}"],
            textposition='auto'
        ))
    
    fig.update_layout(
        barmode='stack',
        title="Структура Цены",
        xaxis_title="",
        yaxis_title="Сумма (₸)",
        showlegend=True,
        height=400
    )
    
    st.plotly_chart(fig)

else:
    st.info("Корзина пуста. Добавьте товары, чтобы увидеть расчет.")

