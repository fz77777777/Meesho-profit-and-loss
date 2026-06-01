import streamlit as st
import pandas as pd

st.set_page_config(page_title="Meesho Advance P&L Analytics", layout="wide")

st.title("📊 Meesho Advance Profit & Loss Dashboard")
st.write("Aapke Orders (CSV) aur Official Payment Excel Report ke base par deep SKU-wise analytics.")

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

# --- STEP 2: DYNAMIC SKU DROPDOWN & COSTING ---
if orders_file and payments_file:
    try:
        # Load Orders CSV
        df_orders = pd.read_csv(orders_file)
        df_orders.columns = df_orders.columns.str.strip()
        
        # Load Payments Excel Sheets (Skip row 0 because it's a grouped category header)
        df_pay = pd.read_excel(payments_file, sheet_name="Order Payments", header=1)
        df_pay.columns = df_pay.columns.str.strip()
        
        df_ads = pd.read_excel(payments_file, sheet_name="Ads Cost", header=1)
        df_ads.columns = df_ads.columns.str.strip()
        
        # Automatically detect SKU column from Orders CSV
        sku_col = [c for c in df_orders.columns if 'sku' in c.lower() or 'product' in c.lower()][0]
        
        # Clean and standardise SKUs
        df_orders[sku_col] = df_orders[sku_col].astype(str).str.strip()
        unique_skus = sorted(df_orders[sku_col].dropna().unique().tolist())
        
        st.header("2. SKU Costing Configuration")
        st.info(f"💡 Aapki file me kul **{len(unique_skus)} unique SKUs** mile hain. Dropdown se select karke cost set karein.")
        
        selected_sku = st.selectbox("🎯 Apna SKU select karein jiski cost enter/change karni hai:", unique_skus)
        current_cost = st.session_state.sku_cost_mapping.get(selected_sku, 0.0)
        
        col_input1, col_input2 = st.columns([1, 2])
        with col_input1:
            new_cost = st.number_input(f"Cost Price for {selected_sku} (₹):", min_value=0.0, value=float(current_cost), step=1.0)
        
        if st.button(f"💾 Save Cost for {selected_sku}"):
            st.session_state.sku_cost_mapping[selected_sku] = new_cost
            st.toast(f"✅ {selected_sku} ki cost ₹{new_cost} save ho gayi!", icon="🚀")

        with st.expander("👁️ Saved Costs Table (Review entered prices)"):
            if st.session_state.sku_cost_mapping:
                preview_df = pd.DataFrame(list(st.session_state.sku_cost_mapping.items()), columns=['SKU', 'Cost_Price'])
                st.dataframe(preview_df, hide_index=True)

        st.markdown("---")

        # --- STEP 3: ANALYTICS ENGINE & CALCULATIONS ---
        order_id_col = [c for c in df_orders.columns if 'order id' in c.lower() or 'sub order' in c.lower()][0]
        
        # Total Orders directly from Orders CSV
        sku_summary = df_orders.groupby(sku_col).agg(
            Total_Orders=(order_id_col, 'count')
        ).reset_index()
        sku_summary.rename(columns={sku_col: 'SKU'}, inplace=True)

        # Process Payout & Returns from Excel Sheet 'Order Payments'
        pay_sku_col = 'Supplier SKU' if 'Supplier SKU' in df_pay.columns else [c for c in df_pay.columns if 'sku' in c.lower()][0]
        payout_col = 'Final Settlement Amount' if 'Final Settlement Amount' in df_pay.columns else [c for c in df_pay.columns if 'settlement' in c.lower() or 'payout' in c.lower()][0]
        return_charge_col = 'Return Shipping Charge (Incl. GST)' if 'Return Shipping Charge (Incl. GST)' in df_pay.columns else [c for c in df_pay.columns if 'return shipping' in c.lower() or 'penalty' in c.lower()][0]
        order_status_col = 'Live Order Status' if 'Live Order Status' in df_pay.columns else [c for c in df_pay.columns if 'status' in c.lower()][0]

        # Standardizing Data Types and removing spaces
        df_pay[payout_col] = pd.to_numeric(df_pay[payout_col], errors='coerce').fillna(0)
        df_pay[return_charge_col] = pd.to_numeric(df_pay[return_charge_col], errors='coerce').fillna(0)
        df_pay[order_status_col] = df_pay[order_status_col].astype(str).str.strip()
        df_pay[pay_sku_col] = df_pay[pay_sku_col].astype(str).str.strip()

        # Calculate metrics from Excel dynamically per SKU
        pay_summary = df_pay.groupby(pay_sku_col).agg(
            Net_Payout=(payout_col, 'sum'),
            Return_Charges=(return_charge_col, lambda x: abs(sum(x))),
            Delivered_Orders=(order_status_col, lambda x: sum(x.str.contains('Delivered|Shipped', case=False, na=False))),
            Customer_Returns=(order_status_col, lambda x: sum(x.str.contains('Return', case=False, na=False))),
            RTO_Orders=(order_status_col, lambda x: sum(x.str.contains('RTO', case=False, na=False)))
        ).reset_index()
        pay_summary.rename(columns={pay_sku_col: 'SKU'}, inplace=True)

        # Calculate Total Ads Spend from 'Ads Cost' Sheet
        ads_cost_col = 'Total Ads Cost' if 'Total Ads Cost' in df_ads.columns else [c for c in df_ads.columns if 'ads' in c.lower() or 'ad cost' in c.lower()][0]
        df_ads[ads_cost_col] = pd.to_numeric(df_ads[ads_cost_col], errors='coerce').fillna(0)
        total_ads = abs(df_ads[ads_cost_col].sum()) 

        # Merge Orders CSV Data with Excel Payments Data
        final_report = pd.merge(sku_summary, pay_summary, on='SKU', how='outer').fillna(0)
        
        # Clean up Total_Orders logic where outer join might cause 0s
        for idx, row in final_report.iterrows():
            if row['Total_Orders'] == 0:
                final_report.at[idx, 'Total_Orders'] = row['Delivered_Orders'] + row['Customer_Returns'] + row['RTO_Orders']

        # Sourcing Cost Mapping
        final_report['Unit_Cost'] = final_report['SKU'].map(st.session_state.sku_cost_mapping).fillna(0)
        final_report['Total_Product_Cost'] = final_report['Total_Orders'] * final_report['Unit_Cost']
        
        # Advanced P&L Math SKU wise
        final_report['Net_Profit_Loss'] = final_report['Net_Payout'] - final_report['Total_Product_Cost']
        final_report['Total_Return_Qty'] = final_report['Customer_Returns'] + final_report['RTO_Orders']
        
        # Handle zero division safely
        final_report['Return_Percentage'] = 0.0
        mask = final_report['Total_Orders'] > 0
        final_report.loc[mask, 'Return_Percentage'] = (final_report.loc[mask, 'Total_Return_Qty'] / final_report.loc[mask, 'Total_Orders'] * 100).round(2)

        # --- DASHBOARD METRICS ---
        st.header("🏁 Monthly Performance Summary")
        
        t_orders = int(final_report['Total_Orders'].sum())
        t_delivered = int(final_report['Delivered_Orders'].sum())
        t_cust_returns = int(final_report['Customer_Returns'].sum())
        t_rto = int(final_report['RTO_Orders'].sum())
        t_returns = t_cust_returns + t_rto
        
        total_payout = final_report['Net_Payout'].sum()
        total_cost = final_report['Total_Product_Cost'].sum()
        total_return_fees = final_report['Return_Charges'].sum()
        
        # Adjust overall P&L with Global Ads Cost
        total_pl = total_payout - total_cost - total_ads
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders", t_orders)
        m2.metric("Delivered Orders", t_delivered)
        m3.metric("Customer Returns (150-170 Cut)", f"{t_cust_returns} Orders")
        m4.metric("RTO Orders Detected", f"{t_rto} Orders")
        
        st.markdown("### Financial Overview")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Total Net Payout From Meesho", f"₹{total_payout:,.2f}")
        f2.metric("Product Cost (Sourcing)", f"₹{total_cost:,.2f}")
        f3.metric("Total Return Penalty Paid", f"₹{total_return_fees:,.2f}")
        f4.metric("Total Ads Spend (Month)", f"₹{total_ads:,.2f}")
        
        st.write("---")
        if total_pl >= 0:
            st.success(f"💰 **Final Net Profit (After Ads & Costs): ₹{total_pl:,.2f}**")
        else:
            st.error(f"📉 **Final Net Loss (After Ads & Costs): ₹{total_pl:,.2f}**")

        # --- DETAILED SKU WISE TABLE ---
        st.subheader("📋 SKU-Wise Deep Parameters Breakdown")
        st.caption("Note: Ads cost poore account ka ek sath upar main overview me minus kiya gaya hai.")
        
        display_df = final_report.copy()
        display_df['Return_Percentage'] = display_df['Return_Percentage'].astype(str) + '%'
        
        # Render clean table
        st.dataframe(
            display_df[[
                'SKU', 'Total_Orders', 'Delivered_Orders', 'Customer_Returns', 'RTO_Orders', 
                'Return_Percentage', 'Unit_Cost', 'Total_Product_Cost', 'Net_Payout', 'Return_Charges', 'Net_Profit_Loss'
            ]],
            hide_index=True
        )
        
        # Download Option
        csv_data = final_report.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Detailed P&L Report as CSV",
            data=csv_data,
            file_name='meesho_detailed_pnl_report.csv',
            mime='text/csv'
        )

    except Exception as e:
        st.error(f"Calculation Error: {e}. Kripya check karein ki aapne sahi reports upload ki hain.")
else:
    st.info("💡 Dropdown me SKUs dekhne ke liye pehle upar dono files (Orders CSV aur Payment Excel) upload karein.")
