import streamlit as st
import pandas as pd

st.set_page_config(page_title="Meesho Ultimate 3-Month Balanced P&L", layout="wide")

st.title("📊 Meesho 3-Month Smart Balanced P&L Dashboard")
st.write("Aapke Orders aur Payments ka perfect cross-referenced analysis.")

st.markdown("---")

# --- STEP 1: MULTI-MONTH FILE UPLOADS ---
st.header("1. Upload 3 Months Reports (Separate Slots)")

col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    st.subheader("📅 Month 1 Files")
    orders_f1 = st.file_uploader("Orders Report (CSV) - M1", type=["csv"], key="ord1")
    pay_f1 = st.file_uploader("Payment Report (Excel) - M1", type=["xlsx"], key="pay1")

with col_m2:
    st.subheader("📅 Month 2 Files")
    orders_f2 = st.file_uploader("Orders Report (CSV) - M2", type=["csv"], key="ord2")
    pay_f2 = st.file_uploader("Payment Report (Excel) - M2", type=["xlsx"], key="pay2")

with col_m3:
    st.subheader("📅 Month 3 Files")
    orders_f3 = st.file_uploader("Orders Report (CSV) - M3", type=["csv"], key="ord3")
    pay_f3 = st.file_uploader("Payment Report (Excel) - M3", type=["xlsx"], key="pay3")

st.markdown("---")

if 'sku_cost_mapping' not in st.session_state:
    st.session_state.sku_cost_mapping = {}

# --- SMART PATTERN MATCHING ENGINE ---
def load_and_smart_sync():
    all_orders = []
    all_payments = []
    all_ads = []

    def process_month(ord_file, p_file):
        if ord_file and p_file:
            df_o = pd.read_csv(ord_file)
            df_o.columns = df_o.columns.str.strip()
            
            df_p = pd.read_excel(p_file, sheet_name="Order Payments", header=1)
            df_p.columns = df_p.columns.str.strip()
            
            df_a = pd.read_excel(p_file, sheet_name="Ads Cost", header=1)
            df_a.columns = df_a.columns.str.strip()
            
            return df_o, df_p, df_a
        return None, None, None

    o1, p1, a1 = process_month(orders_f1, pay_f1)
    o2, p2, a2 = process_month(orders_f2, pay_f2)
    o3, p3, a3 = process_month(orders_f3, pay_f3)

    for o in [o1, o2, o3]:
        if o is not None: all_orders.append(o)
    for p in [p1, p2, p3]:
        if p is not None: all_payments.append(p)
    for a in [a1, a2, a3]:
        if a is not None: all_ads.append(a)

    if not all_orders or not all_payments:
        return None, None, 0.0

    df_orders_raw = pd.concat(all_orders, ignore_index=True)
    df_payments_raw = pd.concat(all_payments, ignore_index=True)

    order_id_col = [c for c in df_orders_raw.columns if 'order id' in c.lower() or 'sub order' in c.lower()][0]
    pay_order_id_col = 'Sub Order No' if 'Sub Order No' in df_payments_raw.columns else [c for c in df_payments_raw.columns if 'order id' in c.lower() or 'sub order' in c.lower()][0]

    # CLEANING FIX: Strip out suffixes like '_1', '_2' to extract the true base numerical ID
    df_orders_raw['clean_id'] = df_orders_raw[order_id_col].astype(str).str.split('_').str[0].str.strip()
    df_payments_raw['clean_id'] = df_payments_raw[pay_order_id_col].astype(str).str.split('_').str[0].str.strip()

    df_orders_clean = df_orders_raw.drop_duplicates(subset=['clean_id'], keep='first').copy()
    
    # Keep historical logs safe but mark cross-overs
    valid_ids = set(df_orders_clean['clean_id'].dropna().unique())
    df_payments_raw['Is_Current_Period'] = df_payments_raw['clean_id'].apply(lambda x: 1 if x in valid_ids else 0)

    total_ads_spend = 0.0
    if all_ads:
        combined_ads = pd.concat(all_ads, ignore_index=True)
        ads_cost_col = 'Total Ads Cost' if 'Total Ads Cost' in combined_ads.columns else [c for c in combined_ads.columns if 'ads' in c.lower() or 'ad cost' in c.lower()][0]
        combined_ads[ads_cost_col] = pd.to_numeric(combined_ads[ads_cost_col], errors='coerce').fillna(0)
        total_ads_spend = abs(combined_ads[ads_cost_col].sum())

    return df_orders_clean, df_payments_raw, total_ads_spend


df_orders_all, df_pay_all, total_ads = load_and_smart_sync()

if df_orders_all is not None and df_pay_all is not None:
    try:
        sku_col = [c for c in df_orders_all.columns if 'sku' in c.lower() or 'product' in c.lower()][0]
        df_orders_all[sku_col] = df_orders_all[sku_col].astype(str).str.strip().str.upper()
        unique_skus = sorted(df_orders_all[sku_col].dropna().unique().tolist())
        
        st.header("2. Master SKU Costing Configuration")
        selected_sku = st.selectbox("🎯 SKU Select karein:", unique_skus)
        current_cost = st.session_state.sku_cost_mapping.get(selected_sku, 0.0)
        
        col_input1, col_input2 = st.columns([1, 2])
        with col_input1:
            new_cost = st.number_input(f"Cost Price for {selected_sku} (₹):", min_value=0.0, value=float(current_cost), step=1.0)
        
        if st.button(f"💾 Save Cost Price"):
            st.session_state.sku_cost_mapping[selected_sku] = new_cost
            st.toast(f"✅ Cost Saved!", icon="🚀")

        st.markdown("---")

        # --- STEP 3: ANALYTICS CORE ENGINE ---
        pay_sku_col = 'Supplier SKU' if 'Supplier SKU' in df_pay_all.columns else [c for c in df_pay_all.columns if 'sku' in c.lower()][0]
        payout_col = 'Final Settlement Amount' if 'Final Settlement Amount' in df_pay_all.columns else [c for c in df_pay_all.columns if 'settlement' in c.lower() or 'payout' in c.lower()][0]
        return_charge_col = 'Return Shipping Charge (Incl. GST)' if 'Return Shipping Charge (Incl. GST)' in df_pay_all.columns else [c for c in df_pay_all.columns if 'return shipping' in c.lower() or 'penalty' in c.lower()][0]
        order_status_col = 'Live Order Status' if 'Live Order Status' in df_pay_all.columns else [c for c in df_pay_all.columns if 'status' in c.lower()][0]

        df_pay_all[payout_col] = pd.to_numeric(df_pay_all[payout_col], errors='coerce').fillna(0)
        df_pay_all[return_charge_col] = pd.to_numeric(df_pay_all[return_charge_col], errors='coerce').fillna(0)
        df_pay_all[order_status_col] = df_pay_all[order_status_col].fillna('').astype(str).str.strip().str.upper()
        df_pay_all[pay_sku_col] = df_pay_all[pay_sku_col].fillna('').astype(str).str.strip().str.upper()

        df_pay_all = df_pay_all[(df_pay_all[pay_sku_col] != '') & (df_pay_all[pay_sku_col] != 'NAN')]

        # Core logic setup
        df_pay_all['Is_Customer_Return'] = df_pay_all[return_charge_col].apply(lambda x: 1 if 145 <= abs(x) <= 175 else 0)
        df_pay_all['Is_RTO'] = df_pay_all.apply(lambda r: 1 if ('RTO' in r[order_status_col] and r['Is_Customer_Return'] == 0) else 0, axis=1)
        df_pay_all['Is_Delivered'] = df_pay_all.apply(lambda r: 1 if (('DELIVERED' in r[order_status_col] or 'SHIPPED' in r[order_status_col]) and r['Is_Customer_Return'] == 0 and r['Is_RTO'] == 0) else 0, axis=1)

        # Aggregate payments per SKU
        pay_summary = df_pay_all.groupby(pay_sku_col).agg(
            Net_Payout=(payout_col, 'sum'),
            Return_Charges=(return_charge_col, lambda x: abs(sum(x))),
            Delivered_Orders=('Is_Delivered', 'sum'),
            Customer_Returns=('Is_Customer_Return', 'sum'),
            RTO_Orders=('Is_RTO', 'sum')
        ).reset_index()
        pay_summary.rename(columns={pay_sku_col: 'SKU'}, inplace=True)

        # Base Orders count per SKU
        sku_summary = df_orders_all.groupby(sku_col).agg(Total_Orders=('clean_id', 'nunique')).reset_index()
        sku_summary.rename(columns={sku_col: 'SKU'}, inplace=True)

        # Balanced Outer Join to prevent zero data printout
        final_report = pd.merge(sku_summary, pay_summary, on='SKU', how='outer').fillna(0)

        # Enforce mathematical synchronization
        for idx, row in final_report.iterrows():
            calculated_sum = row['Delivered_Orders'] + row['Customer_Returns'] + row['RTO_Orders']
            if row['Total_Orders'] < calculated_sum or row['Total_Orders'] == 0:
                final_report.at[idx, 'Total_Orders'] = calculated_sum

        # Sourcing Calculations
        final_report['Unit_Cost'] = final_report['SKU'].map(st.session_state.sku_cost_mapping).fillna(0)
        final_report['Total_Product_Cost'] = final_report['Total_Orders'] * final_report['Unit_Cost']
        
        # Symmetrical Profit Loss Formula
        final_report['Net_Profit_Loss'] = final_report['Net_Payout'] - final_report['Total_Product_Cost']
        final_report['Total_Return_Qty'] = final_report['Customer_Returns'] + final_report['RTO_Orders']
        
        final_report['Return_Percentage'] = 0.0
        mask = final_report['Total_Orders'] > 0
        final_report.loc[mask, 'Return_Percentage'] = (final_report.loc[mask, 'Total_Return_Qty'] / final_report.loc[mask, 'Total_Orders'] * 100).round(2)

        final_report = final_report[(final_report['SKU'] != 'NAN') & (final_report['SKU'] != '')]

        # --- SUMMARY CARD DISPLAY ---
        st.header("🏁 3-Month Balanced Performance Summary")
        
        t_orders = int(final_report['Total_Orders'].sum())
        t_delivered = int(final_report['Delivered_Orders'].sum())
        t_cust_returns = int(final_report['Customer_Returns'].sum())
        t_rto = int(final_report['RTO_Orders'].sum())
        
        total_payout = final_report['Net_Payout'].sum()
        total_cost = final_report['Total_Product_Cost'].sum()
        total_return_fees = final_report['Return_Charges'].sum()
        total_pl = total_payout - total_cost - total_ads
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Smart Orders", t_orders)
        c2.metric("Delivered & Settled", t_delivered)
        c3.metric("Customer Returns", f"{t_cust_returns} Orders")
        c4.metric("RTO Orders", f"{t_rto} Orders")
        
        st.markdown("### Combined Financial Overview")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Total Net Payout", f"₹{total_payout:,.2f}")
        f2.metric("Total Sourcing Cost", f"₹{total_cost:,.2f}")
        f3.metric("Total Return Penalty Paid", f"₹{total_return_fees:,.2f}")
        f4.metric("Total Ads Spend", f"₹{total_ads:,.2f}")
        
        st.write("---")
        if total_pl >= 0:
            st.success(f"💰 **Consolidated Net Profit: ₹{total_pl:,.2f}**")
        else:
            st.error(f"📉 **Consolidated Net Loss: ₹{total_pl:,.2f}**")

        st.subheader("📋 SKU Breakdown (Balanced View)")
        st.dataframe(
            final_report[[
                'SKU', 'Total_Orders', 'Delivered_Orders', 'Customer_Returns', 'RTO_Orders', 'Unit_Cost', 'Net_Payout', 'Net_Profit_Loss'
            ]],
            hide_index=True
        )

    except Exception as e:
        st.error(f"Error running multi-month analytics: {e}")
else:
    st.info("💡 Data calculations dekhne ke liye orders aur payments files upload karein.")
