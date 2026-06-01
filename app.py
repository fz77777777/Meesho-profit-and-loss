import streamlit as st
import pandas as pd

st.set_page_config(page_title="Meesho Perfect P&L Analytics", layout="wide")

st.title("📊 Meesho Ultimate Profit & Loss Dashboard (Amount-Verified)")
st.write("Aapke Orders CSV aur Payment Excel ke accurate data par adharit.")

st.markdown("---")

# --- STEP 1: FILE UPLOADS ---
st.header("1. Upload Month-wise Reports")
col1, col2 = st.columns(2)

with col1:
    orders_file = st.file_uploader("Upload Orders Report (CSV)", type=["csv"])
with col2:
    payments_file = st.file_uploader("Upload Payment Report (Excel - .xlsx)", type=["xlsx"])

st.markdown("---")

if 'sku_cost_mapping' not in st.session_state:
    st.session_state.sku_cost_mapping = {}

# --- STEP 2: COSTING CONFIGURATION ---
if orders_file and payments_file:
    try:
        # Load Files
        df_orders = pd.read_csv(orders_file)
        df_orders.columns = df_orders.columns.str.strip()
        
        df_pay = pd.read_excel(payments_file, sheet_name="Order Payments", header=1)
        df_pay.columns = df_pay.columns.str.strip()
        
        df_ads = pd.read_excel(payments_file, sheet_name="Ads Cost", header=1)
        df_ads.columns = df_ads.columns.str.strip()
        
        # Detect SKU column and Clean it completely (Uppercase + Strip spaces)
        sku_col = [c for c in df_orders.columns if 'sku' in c.lower() or 'product' in c.lower()][0]
        df_orders[sku_col] = df_orders[sku_col].astype(str).str.strip().str.upper()
        unique_skus = sorted(df_orders[sku_col].dropna().unique().tolist())
        
        st.header("2. SKU Costing Configuration")
        st.info(f"💡 Aapki report ke mutabik kul **{len(unique_skus)} active SKUs** mile hain.")
        
        selected_sku = st.selectbox("🎯 Apna SKU select karein aur cost enter karein:", unique_skus)
        current_cost = st.session_state.sku_cost_mapping.get(selected_sku, 0.0)
        
        col_input1, col_input2 = st.columns([1, 2])
        with col_input1:
            new_cost = st.number_input(f"Cost Price for {selected_sku} (₹):", min_value=0.0, value=float(current_cost), step=1.0)
        
        if st.button(f"💾 Save Cost Price"):
            st.session_state.sku_cost_mapping[selected_sku] = new_cost
            st.toast(f"✅ Cost Saved!", icon="🚀")

        st.markdown("---")

        # --- STEP 3: ANALYTICS CORE ENGINE ---
        order_id_col = [c for c in df_orders.columns if 'order id' in c.lower() or 'sub order' in c.lower()][0]
        sku_summary = df_orders.groupby(sku_col).agg(Total_Orders=(order_id_col, 'count')).reset_index()
        sku_summary.rename(columns={sku_col: 'SKU'}, inplace=True)

        # Process Payments Sheet columns
        pay_sku_col = 'Supplier SKU' if 'Supplier SKU' in df_pay.columns else [c for c in df_pay.columns if 'sku' in c.lower()][0]
        payout_col = 'Final Settlement Amount' if 'Final Settlement Amount' in df_pay.columns else [c for c in df_pay.columns if 'settlement' in c.lower() or 'payout' in c.lower()][0]
        return_charge_col = 'Return Shipping Charge (Incl. GST)' if 'Return Shipping Charge (Incl. GST)' in df_pay.columns else [c for c in df_pay.columns if 'return shipping' in c.lower() or 'penalty' in c.lower()][0]
        order_status_col = 'Live Order Status' if 'Live Order Status' in df_pay.columns else [c for c in df_pay.columns if 'status' in c.lower()][0]

        # Convert to numeric safely
        df_pay[payout_col] = pd.to_numeric(df_pay[payout_col], errors='coerce').fillna(0)
        df_pay[return_charge_col] = pd.to_numeric(df_pay[return_charge_col], errors='coerce').fillna(0)
        df_pay[order_status_col] = df_pay[order_status_col].astype(str).str.strip().str.upper()
        df_pay[pay_sku_col] = df_pay[pay_sku_col].astype(str).str.strip().str.upper()

        # ADVANCED COUNTER LOGIC: Direct based on 150-170 Rs. Charge logic
        # Customer Return = Any row where absolute return charge is between 150 and 175
        df_pay['Is_Customer_Return'] = df_pay[return_charge_col].apply(lambda x: 1 if 145 <= abs(x) <= 175 else 0)
        # RTO = Status has RTO, and no customer return charge
        df_pay['Is_RTO'] = df_pay.apply(lambda r: 1 if ('RTO' in r[order_status_col] and r['Is_Customer_Return'] == 0) else 0, axis=1)
        # Delivered = Status has Delivered/Shipped and not a return
        df_pay['Is_Delivered'] = df_pay.apply(lambda r: 1 if (('DELIVERED' in r[order_status_col] or 'SHIPPED' in r[order_status_col]) and r['Is_Customer_Return'] == 0 and r['Is_RTO'] == 0) else 0, axis=1)

        # Grouping dynamically
        pay_summary = df_pay.groupby(pay_sku_col).agg(
            Net_Payout=(payout_col, 'sum'),
            Return_Charges=(return_charge_col, lambda x: abs(sum(x))),
            Delivered_Orders=('Is_Delivered', 'sum'),
            Customer_Returns=('Is_Customer_Return', 'sum'),
            RTO_Orders=('Is_RTO', 'sum')
        ).reset_index()
        pay_summary.rename(columns={pay_sku_col: 'SKU'}, inplace=True)

        # Process Ads Sheet
        ads_cost_col = 'Total Ads Cost' if 'Total Ads Cost' in df_ads.columns else [c for c in df_ads.columns if 'ads' in c.lower() or 'ad cost' in c.lower()][0]
        df_ads[ads_cost_col] = pd.to_numeric(df_ads[ads_cost_col], errors='coerce').fillna(0)
        total_ads = abs(df_ads[ads_cost_col].sum())

        # Final outer join merge to ensure no data loss
        final_report = pd.merge(sku_summary, pay_summary, on='SKU', how='outer').fillna(0)
        
        # Patching order counts safely
        for idx, row in final_report.iterrows():
            if row['Total_Orders'] == 0:
                final_report.at[idx, 'Total_Orders'] = row['Delivered_Orders'] + row['Customer_Returns'] + row['RTO_Orders']

        # Financial Calculations
        final_report['Unit_Cost'] = final_report['SKU'].map(st.session_state.sku_cost_mapping).fillna(0)
        final_report['Total_Product_Cost'] = final_report['Total_Orders'] * final_report['Unit_Cost']
        final_report['Net_Profit_Loss'] = final_report['Net_Payout'] - final_report['Total_Product_Cost']
        final_report['Total_Return_Qty'] = final_report['Customer_Returns'] + final_report['RTO_Orders']
        
        final_report['Return_Percentage'] = 0.0
        mask = final_report['Total_Orders'] > 0
        final_report.loc[mask, 'Return_Percentage'] = (final_report.loc[mask, 'Total_Return_Qty'] / final_report.loc[mask, 'Total_Orders'] * 100).round(2)

        # Remove extra rows if any empty nan sku leaks
        final_report = final_report[final_report['SKU'] != 'NAN']

        # --- SUMMARY DISPLAY ---
        st.header("🏁 Monthly Performance Summary")
        
        t_orders = int(final_report['Total_Orders'].sum())
        t_delivered = int(final_report['Delivered_Orders'].sum())
        t_cust_returns = int(final_report['Customer_Returns'].sum())
        t_rto = int(final_report['RTO_Orders'].sum())
        
        total_payout = final_report['Net_Payout'].sum()
        total_cost = final_report['Total_Product_Cost'].sum()
        total_return_fees = final_report['Return_Charges'].sum()
        total_pl = total_payout - total_cost - total_ads
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Orders", t_orders)
        c2.metric("Delivered Orders", t_delivered)
        c3.metric("Customer Returns (150-170 Cut)", f"{t_cust_returns} Orders")
        c4.metric("RTO Orders", f"{t_rto} Orders")
        
        st.markdown("### Financial Overview")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Net Payout From Meesho", f"₹{total_payout:,.2f}")
        f2.metric("Sourcing Product Cost", f"₹{total_cost:,.2f}")
        f3.metric("Return Penalties Paid", f"₹{total_return_fees:,.2f}")
        f4.metric("Total Ads Spend", f"₹{total_ads:,.2f}")
        
        st.write("---")
        if total_pl >= 0:
            st.success(f"💰 **Final Net Profit (After Ads & Costs): ₹{total_pl:,.2f}**")
        else:
            st.error(f"📉 **Final Net Loss (After Ads & Costs): ₹{total_pl:,.2f}**")

        # --- DATAFRAME ---
        st.subheader("📋 SKU-Wise Deep Parameters Breakdown")
        display_df = final_report.copy()
        display_df['Return_Percentage'] = display_df['Return_Percentage'].astype(str) + '%'
        
        st.dataframe(
            display_df[[
                'SKU', 'Total_Orders', 'Delivered_Orders', 'Customer_Returns', 'RTO_Orders', 
                'Return_Percentage', 'Unit_Cost', 'Total_Product_Cost', 'Net_Payout', 'Return_Charges', 'Net_Profit_Loss'
            ]],
            hide_index=True
        )

    except Exception as e:
        st.error(f"Error running data analytics: {e}")
