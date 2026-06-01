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

# Session state to store SKU costs persistently
if 'sku_cost_mapping' not in st.session_state:
    st.session_state.sku_cost_mapping = {}

# --- STEP 2: DYNAMIC SKU DROPDOWN & COSTING ---
if orders_file and payments_file:
    try:
        # Load Orders CSV
        df_orders = pd.read_csv(orders_file)
        df_orders.columns = df_orders.columns.str.strip()
        
        # Load Payments Excel sheets
        excel_file = pd.ExcelFile(payments_file)
        sheet_names = excel_file.sheet_names
        
        # Automatically detect SKU column from Orders CSV
        sku_col = [c for c in df_orders.columns if 'sku' in c.lower() or 'product' in c.lower()][0]
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
        status_col = [c for c in df_orders.columns if 'status' in c.lower() or 'state' in c.lower()][0]
        order_id_col = [c for c in df_orders.columns if 'order id' in c.lower() or 'sub order' in c.lower()][0]
        
        # SKU-wise Order Summary from CSV
        sku_summary = df_orders.groupby(sku_col).agg(
            Total_Orders=(order_id_col, 'count'),
            Delivered_Orders=(status_col, lambda x: sum(x.astype(str).str.contains('Delivered|Completed|Shipped', case=False))),
            Customer_Returns=(status_col, lambda x: sum(x.astype(str).str.contains('Customer Return|Return', case=False))),
            RTO_Orders=(status_col, lambda x: sum(x.astype(str).str.contains('RTO', case=False)))
        ).reset_index()
        sku_summary.rename(columns={sku_col: 'SKU'}, inplace=True)

        # Initialize Payment Variables
        total_net_payout = 0.0
        total_ads_spend = 0.0
        total_return_charges = 0.0
        
        pay_summary_list = []

        # Process each sheet dynamically inside the Meesho Excel File
        for sheet in sheet_names:
            df_sheet = pd.read_excel(payments_file, sheet_name=sheet)
            df_sheet.columns = df_sheet.columns.str.strip()
            
            # Find SKU and Payout/Deduction Columns if present
            sheet_sku_cols = [c for c in df_sheet.columns if 'sku' in c.lower() or 'product' in c.lower()]
            
            if sheet_sku_cols:
                s_sku = sheet_sku_cols[0]
                
                # Look for Payout Amount
                payout_cols = [c for c in df_sheet.columns if 'net payout' in c.lower() or 'payout amount' in c.lower() or 'final payout' in c.lower() or 'amount' in c.lower()]
                # Look for Return Penalty/Shipping
                ret_cols = [c for c in df_sheet.columns if 'return shipping' in c.lower() or 'penalty' in c.lower() or 'deductions' in c.lower()]
                # Look for Ads cost
                ad_cols = [c for c in df_sheet.columns if 'ads' in c.lower() or 'ad cost' in c.lower() or 'advertisement' in c.lower()]
                
                p_col = payout_cols[0] if payout_cols else None
                r_col = ret_cols[0] if ret_cols else None
                a_col = ad_cols[0] if ad_cols else None
                
                # Group by SKU for this sheet
                for name, group in df_sheet.groupby(s_sku):
                    p_amt = group[p_col].sum() if p_col else 0.0
                    r_amt = group[r_col].sum() if r_col else 0.0
                    a_amt = group[a_col].sum() if a_col else 0.0
                    
                    pay_summary_list.append({
                        'SKU': name,
                        'Net_Payout': p_amt,
                        'Return_Charges': r_amt,
                        'Ads_Spend': a_amt
                    })
        
        # Combine all sheet data
        if pay_summary_list:
            df_pay_combined = pd.DataFrame(pay_summary_list)
            pay_summary = df_pay_combined.groupby('SKU').sum().reset_index()
        else:
            pay_summary = pd.DataFrame(columns=['SKU', 'Net_Payout', 'Return_Charges', 'Ads_Spend'])

        # Merge Orders CSV Data with Excel Payments Data
        final_report = pd.merge(sku_summary, pay_summary, on='SKU', how='left').fillna(0)
        
        # Sourcing Cost Mapping
        final_report['Unit_Cost'] = final_report['SKU'].map(st.session_state.sku_cost_mapping).fillna(0)
        final_report['Total_Product_Cost'] = final_report['Total_Orders'] * final_report['Unit_Cost']
        
        # Advanced P&L Math
        final_report['Net_Profit_Loss'] = final_report['Net_Payout'] - final_report['Total_Product_Cost'] - final_report['Ads_Spend']
        final_report['Total_Return_Qty'] = final_report['Customer_Returns'] + final_report['RTO_Orders']
        final_report['Return_Percentage'] = (final_report['Total_Return_Qty'] / final_report['Total_Orders'] * 100).round(2).fillna(0)

        # --- DASHBOARD METRICS ---
        st.header("🏁 Monthly Performance Summary")
        
        t_orders = int(final_report['Total_Orders'].sum())
        t_delivered = int(final_report['Delivered_Orders'].sum())
        t_returns = int(final_report['Total_Return_Qty'].sum())
        total_payout = final_report['Net_Payout'].sum()
        total_cost = final_report['Total_Product_Cost'].sum()
        total_ads = final_report['Ads_Spend'].sum()
        total_return_fees = final_report['Return_Charges'].sum()
        total_pl = final_report['Net_Profit_Loss'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders Processed", t_orders)
        m2.metric("Delivered Orders", t_delivered)
        m3.metric("Total Returns (Customer + RTO)", f"{t_returns} ({ (t_returns/t_orders*100) if t_orders>0 else 0:.1f}%)")
        m4.metric("Total Ads Spend", f"₹{total_ads:,.2f}")
        
        st.markdown("### Financial Overview")
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Total Net Payout", f"₹{total_payout:,.2f}")
        f2.metric("Product Cost (Sourcing)", f"₹{total_cost:,.2f}")
        f3.metric("Return Penalties/Charges", f"₹{total_return_fees:,.2f}")
        
        if total_pl >= 0:
            f4.metric("Net Profit", f"₹{total_pl:,.2f}", delta=f"₹{total_pl:,.2f} Profit", delta_color="normal")
        else:
            f4.metric("Net Loss", f"₹{total_pl:,.2f}", delta=f"₹{total_pl:,.2f} Loss", delta_color="inverse")

        # --- DETAILED SKU WISE TABLE ---
        st.subheader("📋 SKU-Wise Deep Parameters Breakdown")
        
        display_df = final_report.copy()
        display_df['Return_Percentage'] = display_df['Return_Percentage'].astype(str) + '%'
        
        st.dataframe(
            display_df[[
                'SKU', 'Total_Orders', 'Delivered_Orders', 'Customer_Returns', 'RTO_Orders', 
                'Return_Percentage', 'Unit_Cost', 'Total_Product_Cost', 'Net_Payout', 'Return_Charges', 'Ads_Spend', 'Net_Profit_Loss'
            ]].style.background_gradient(subset=['Net_Profit_Loss'], cmap='RdYlGn'),
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
    st.info("💡 Dropdown me SKUs dekhne ke liye pehle upar dono files (CSV aur Excel) upload karein.")
