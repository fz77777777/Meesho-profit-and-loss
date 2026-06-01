import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import io

st.set_page_config(page_title="Meesho Deep P&L Analytics", layout="wide")

st.title("📊 Meesho Advance Profit & Loss Dashboard")
st.write("Aapke Orders (CSV) aur Payments (HTML) data ke base par deep SKU-wise analytics.")

st.markdown("---")

# --- STEP 1: FILE UPLOADS FIRST (To extract SKUs automatically) ---
st.header("1. Upload Month-wise Reports")
col1, col2 = st.columns(2)

with col1:
    orders_file = st.file_uploader("Upload Orders Report (CSV)", type=["csv"])
with col2:
    payments_file = st.file_uploader("Upload Delivery/Payments Report (HTML)", type=["html"])

st.markdown("---")

# Session state to store SKU costs persistently
if 'sku_cost_mapping' not in st.session_state:
    st.session_state.sku_cost_mapping = {}

# --- STEP 2: DYNAMIC SKU DROPDOWN & COSTING ---
if orders_file and payments_file:
    try:
        # 1. Read Orders CSV to get unique SKUs
        df_orders = pd.read_csv(orders_file)
        df_orders.columns = df_orders.columns.str.strip()
        
        # Detect SKU column automatically
        sku_col = [c for c in df_orders.columns if 'sku' in c.lower() or 'product' in c.lower()][0]
        
        # Get list of unique SKUs from file
        unique_skus = sorted(df_orders[sku_col].dropna().unique().tolist())
        
        st.header("2. SKU Costing Configuration")
        st.info(f"💡 Aapki file me kul **{len(unique_skus)} unique SKUs** mile hain. Dropdown se select karke cost set karein.")
        
        # Dropdown to select SKU
        selected_sku = st.selectbox("🎯 Apna SKU select karein jiski cost enter/change karni hai:", unique_skus)
        
        # Get previous cost if already entered, else default to 0.0
        current_cost = st.session_state.sku_cost_mapping.get(selected_sku, 0.0)
        
        # Input fields for the selected SKU
        col_input1, col_input2 = st.columns([1, 2])
        with col_input1:
            new_cost = st.number_input(f"Cost Price for {selected_sku} (₹):", min_value=0.0, value=float(current_cost), step=1.0)
        
        # Save button to lock the cost in session memory
        if st.button(f"💾 Save Cost for {selected_sku}"):
            st.session_state.sku_cost_mapping[selected_sku] = new_cost
            st.toast(f"✅ {selected_sku} ki cost ₹{new_cost} save ho gayi!", icon="🚀")

        # Visual indicator showing how many SKUs have costs assigned
        entered_count = len([k for k, v in st.session_state.sku_cost_mapping.items() if v > 0])
        st.caption(f"📊 Status: {entered_count} out of {len(unique_skus)} SKUs configured.")
        
        with st.expander("👁️ Saved Costs Table (Review entered prices)"):
            if st.session_state.sku_cost_mapping:
                preview_df = pd.DataFrame(list(st.session_state.sku_cost_mapping.items()), columns=['SKU', 'Cost_Price'])
                st.dataframe(preview_df, hide_index=True)
            else:
                st.write("Abhi tak kisi bhi SKU ki cost enter nahi ki gayi hai.")

        st.markdown("---")

        # --- STEP 3: ANALYTICS ENGINE & CALCULATIONS ---
        # Read Payments HTML
        html_content = payments_file.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        tables = soup.find_all('table')
        
        if not tables:
            st.error("HTML file me koi data table nahi mila. Kripya sahi file upload karein.")
            st.stop()
            
        # Extracting dataframe from HTML
        df_pay = pd.read_html(io.StringIO(str(tables[0])))[0]
        df_pay.columns = df_pay.columns.str.strip()

        status_col = [c for c in df_orders.columns if 'status' in c.lower() or 'state' in c.lower()][0]
        order_id_col = [c for c in df_orders.columns if 'order id' in c.lower() or 'sub order' in c.lower()][0]
        
        # SKU-wise Order Summary
        sku_summary = df_orders.groupby(sku_col).agg(
            Total_Orders=(order_id_col, 'count'),
            Delivered_Orders=(status_col, lambda x: sum(x.astype(str).str.contains('Delivered|Completed|Shipped', case=False))),
            Customer_Returns=(status_col, lambda x: sum(x.astype(str).str.contains('Customer Return|Return', case=False))),
            RTO_Orders=(status_col, lambda x: sum(x.astype(str).str.contains('RTO', case=False)))
        ).reset_index()
        sku_summary.rename(columns={sku_col: 'SKU'}, inplace=True)

        # Extract Payments Parameters from HTML
        pay_sku = [c for c in df_pay.columns if 'sku' in c.lower() or 'product' in c.lower()][0]
        payout_col = [c for c in df_pay.columns if 'net payout' in c.lower() or 'final' in c.lower() or 'amount' in c.lower()][0]
        
        ads_col = [c for c in df_pay.columns if 'ads' in c.lower() or 'ad cost' in c.lower()]
        return_fee_col = [c for c in df_pay.columns if 'return shipping' in c.lower() or 'penalty' in c.lower()]
        
        agg_dict = {payout_col: 'sum'}
        if ads_col: agg_dict[ads_col[0]] = 'sum'
        if return_fee_col: agg_dict[return_fee_col[0]] = 'sum'
        
        pay_summary = df_pay.groupby(pay_sku).agg(agg_dict).reset_index()
        pay_summary.rename(columns={pay_sku: 'SKU', payout_col: 'Net_Payout'}, inplace=True)
        
        if ads_col: pay_summary.rename(columns={ads_col[0]: 'Ads_Spend'}, inplace=True)
        else: pay_summary['Ads_Spend'] = 0.0
            
        if return_fee_col: pay_summary.rename(columns={return_fee_col[0]: 'Return_Charges'}, inplace=True)
        else: pay_summary['Return_Charges'] = 0.0

        # Merge Data
        final_report = pd.merge(sku_summary, pay_summary, on='SKU', how='left').fillna(0)
        
        # Apply the dropdown dictionary costs
        final_report['Unit_Cost'] = final_report['SKU'].map(st.session_state.sku_cost_mapping).fillna(0)
        
        # Calculations
        final_report['Total_Product_Cost'] = final_report['Total_Orders'] * final_report['Unit_Cost']
        final_report['Net_Profit_Loss'] = final_report['Net_Payout'] - final_report['Total_Product_Cost']
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
        total_pl = final_report['Net_Profit_Loss'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Orders Processed", t_orders)
        m2.metric("Delivered Orders", t_delivered)
        m3.metric("Total Returns (Customer + RTO)", f"{t_returns} ({ (t_returns/t_orders*100) if t_orders>0 else 0:.1f}%)")
        m4.metric("Total Ads Spend Listed", f"₹{total_ads:,.2f}")
        
        st.markdown("### Financial Overview")
        f1, f2, f3 = st.columns(3)
        f1.metric("Total Net Payout Received", f"₹{total_payout:,.2f}")
        f2.metric("Total Product Cost (Sourcing)", f"₹{total_cost:,.2f}")
        
        if total_pl >= 0:
            f3.metric("Net Profit/Loss", f"₹{total_pl:,.2f}", delta=f"₹{total_pl:,.2f} Profit", delta_color="normal")
        else:
            f3.metric("Net Profit/Loss", f"₹{total_pl:,.2f}", delta=f"₹{total_pl:,.2f} Loss", delta_color="inverse")

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
    st.info("💡 Dropdown me SKUs dekhne ke liye pehle upar dono files (CSV aur HTML) upload karein.")
