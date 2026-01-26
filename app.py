"""
RigBooks v4 - Smart Bookkeeping for Oilfield Contractors
NEW: Revenue input, Receipt tracking, Mileage log, T2125 export, Date filters
"""
import streamlit as st
import pandas as pd
import re
from datetime import datetime, date

st.set_page_config(page_title="RigBooks", page_icon="⛽", layout="wide")

CATEGORIES = ['Revenue - Oilfield Services','Fuel & Petroleum','Rent - Work Accommodation','Utilities','Vehicle Repairs','Equipment & Tools','Safety Gear & PPE','Meals (50%)','Entertainment (50%)','Professional Fees','Office Supplies','Phone & Communications','Internet','Bank Fees','Loan - Business Vehicle','Training & Certifications','Software & Subscriptions','Travel & Accommodations','Insurance','Donations','Other Business','Shareholder Distribution','Personal Expense','Tax Payment','Exclude']
ITC_RATES = {'Fuel & Petroleum':1,'Rent - Work Accommodation':1,'Utilities':1,'Vehicle Repairs':1,'Equipment & Tools':1,'Safety Gear & PPE':1,'Professional Fees':1,'Office Supplies':1,'Phone & Communications':1,'Internet':1,'Training & Certifications':1,'Software & Subscriptions':1,'Travel & Accommodations':1,'Other Business':1,'Loan - Business Vehicle':1,'Meals (50%)':0.5,'Entertainment (50%)':0.5}
STATUSES = ['business','personal','exclude']

# Date filter helper
def filter_by_date(data_list, date_key, start_date, end_date):
    if not data_list: return data_list
    filtered = []
    for item in data_list:
        try:
            item_date = pd.to_datetime(item.get(date_key, '2025-01-01')).date()
            if start_date <= item_date <= end_date:
                filtered.append(item)
        except: filtered.append(item)
    return filtered

def get_status(cat):
    if cat in ['Revenue - Oilfield Services','Shareholder Distribution','Tax Payment','Exclude']: return 'exclude'
    if cat == 'Personal Expense': return 'personal'
    return 'business'

def classify(desc):
    d = desc.upper()
    if re.search(r'WIRE TSF.*PRICE|LONG RUN|MOBILE DEPOSIT',d): return 'Revenue - Oilfield Services'
    if re.search(r'PAULA GOUR|1695784 ALBERTA',d): return 'Exclude'
    if re.search(r'GOVERNMENT CANADA',d): return 'Tax Payment'
    if re.search(r'INTERNET TRANSFER.*TO:.*00099|E-TRANSFER.*LILIBETH|ATM WITHDR|ABM WITHDR|BANKING CENTRE|BRANCH.*WITHDR',d): return 'Shareholder Distribution'
    if re.search(r'TD ON-LINE LOANS|LOAN PAYMENT.*TD|SCOTIA BANK.*LOAN|LOAN.*SCOTIA',d): return 'Loan - Business Vehicle'
    if re.search(r'RENT@|REALTY|FOCUS@',d): return 'Rent - Work Accommodation'
    if re.search(r'EPCOR|ATCO|DIRECT ENERGY|ENMAX',d): return 'Utilities'
    if re.search(r'ACCOUNT FEE|SERVICE CHARGE|MONTHLY.*FEE',d): return 'Bank Fees'
    if re.search(r'MANULIFE',d): return 'Insurance'
    if re.search(r'KOODO|TELUS|BELL|ROGERS|FIDO',d): return 'Phone & Communications'
    if re.search(r'SHAW',d): return 'Internet'
    if re.search(r'PETRO|SHELL|ESSO|CHEVRON|CENTEX|MOBIL|FAS GA|FGP|CIRCLE K|CO-OP|BOYLE|DOMO|HUSKY',d): return 'Fuel & Petroleum'
    if re.search(r'OK TIRE|NAPA|PART SOURCE|JIFFY|KEEPS MECH|GOODBRAND|SOUTH.?FORT|CANADIAN TIRE|VET',d): return 'Vehicle Repairs'
    if re.search(r'PRINCESS AUTO|HOME HARDWARE',d): return 'Equipment & Tools'
    if re.search(r'NOTARY|LAWYER|ACCOUNTANT|WORKERS COMP|COSTCO BUSINESS',d): return 'Professional Fees'
    if re.search(r'DOLLARAMA|IKEA|STAPLES',d): return 'Office Supplies'
    if re.search(r'COMMUNITY|DONATION',d): return 'Donations'
    if re.search(r'TIM HORTON|A&W |MCDONALD|SUBWAY|ACHTI|RAINBOW|UPTOWN|KICKS|LILY|SNOW VALLEY|KIM|JOEY|IGA|WALMART|SUPERSTORE|SAFEWAY',d): return 'Meals (50%)'
    if re.search(r'GOLF',d): return 'Entertainment (50%)'
    if re.search(r'LIQUOR|CANNA|GREEN SOLUTION',d): return 'Personal Expense'
    if re.search(r'LITTLE STEPS|DAYCARE|BARBER|UPMEN',d): return 'Personal Expense'
    return 'Other Business'

def calc_itc(debit,credit,cat,status):
    if status != 'business' or credit > 0: return 0.0
    return round((debit * 0.05 / 1.05) * ITC_RATES.get(cat,0), 2)

def parse_csv(file):
    try:
        content = file.read().decode('utf-8')
        data = []
        for line in content.strip().split('\n'):
            parts, cur, inq = [], '', False
            for c in line:
                if c == '"': inq = not inq
                elif c == ',' and not inq: parts.append(cur.strip()); cur = ''
                else: cur += c
            parts.append(cur.strip())
            if len(parts) >= 3:
                dt, desc = parts[0], parts[1]
                if 'date' in dt.lower(): continue
                clean = lambda s: float((s or '').replace('$','').replace(',','').strip() or 0)
                debit, credit = clean(parts[2]) if len(parts)>2 else 0, clean(parts[3]) if len(parts)>3 else 0
                if debit == 0 and credit == 0: continue
                cat = classify(desc)
                status = get_status(cat)
                data.append({'Date':dt,'Description':desc,'Debit':debit,'Credit':credit,'Category':cat,'Status':status,'ITC':calc_itc(debit,credit,cat,status)})
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# Session State - ADDED: revenue, mileage, date_filter
for key, default in [('transactions',pd.DataFrame()),('phone_bills',[]),('cash_expenses',[]),('personal_expenses',[]),('other_expenses',[]),('vehicle_expenses',[]),('home_office',{'rent':0,'property_tax':0,'insurance':0,'electricity':0,'gas':0,'water':0,'internet':0,'pct':10}),('revenue',[]),('mileage',[]),('date_filter','Tax Year (Jan-Dec)'),('custom_start',date(2025,1,1)),('custom_end',date(2025,12,31))]:
    if key not in st.session_state: st.session_state[key] = default

# Sidebar
with st.sidebar:
    st.markdown("## ⛽ RigBooks v4")
    st.markdown("*Smart Contractor Bookkeeping*")
    st.markdown("---")
    
    # DATE FILTER (Feature 5)
    st.markdown("##### 📅 Date Range")
    st.session_state.date_filter = st.selectbox("Period",["Monthly","Tax Year (Jan-Dec)","Custom"],index=["Monthly","Tax Year (Jan-Dec)","Custom"].index(st.session_state.date_filter))
    
    if st.session_state.date_filter == "Monthly":
        month = st.selectbox("Month",["January","February","March","April","May","June","July","August","September","October","November","December"])
        year = st.number_input("Year",value=2025,min_value=2020,max_value=2030)
        month_num = ["January","February","March","April","May","June","July","August","September","October","November","December"].index(month) + 1
        import calendar
        last_day = calendar.monthrange(year, month_num)[1]
        start_date = date(year, month_num, 1)
        end_date = date(year, month_num, last_day)
    elif st.session_state.date_filter == "Tax Year (Jan-Dec)":
        year = st.number_input("Tax Year",value=2025,min_value=2020,max_value=2030)
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
    else:
        start_date = st.date_input("From",value=st.session_state.custom_start)
        end_date = st.date_input("To",value=st.session_state.custom_end)
        st.session_state.custom_start = start_date
        st.session_state.custom_end = end_date
    
    st.caption(f"📆 {start_date} to {end_date}")
    st.markdown("---")
    
    page = st.radio("Navigation",["📤 Upload CSV","💵 Revenue","📋 Transactions","📱 Phone Bills","💳 Cash Expenses","🏦 Personal Account","🏠 Home Office","🚗 Vehicle & Mileage","📚 Other Expenses","💰 GST Filing","👥 Shareholder","📊 Accountant Summary","🛡️ CRA Guide"],label_visibility="collapsed")
    st.markdown("---")
    sh1 = st.text_input("Shareholder 1",value="Greg")
    sh1_pct = st.number_input("Ownership %",value=49,min_value=0,max_value=100)
    sh2 = st.text_input("Shareholder 2",value="Lilibeth")
    st.caption(f"{sh2}: {100-sh1_pct}%")

# ==================== PAGES ====================

# UPLOAD CSV
if page == "📤 Upload CSV":
    st.header("📤 Upload Bank Statement")
    file = st.file_uploader("Choose CSV",type=['csv'])
    if file:
        df = parse_csv(file)
        if not df.empty:
            st.session_state.transactions = df
            st.success(f"✅ Loaded {len(df)} transactions!")
            st.dataframe(df.head(10),use_container_width=True,hide_index=True)
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Transactions",len(df))
            c2.metric("Revenue",f"${df[df['Category']=='Revenue - Oilfield Services']['Credit'].sum():,.0f}")
            c3.metric("Expenses",f"${df[df['Status']=='business']['Debit'].sum():,.0f}")
            c4.metric("ITCs",f"${df['ITC'].sum():,.2f}")

# REVENUE (Feature 1)
elif page == "💵 Revenue":
    st.header("💵 Revenue - Hauling Tickets & Oilfield Jobs")
    st.info("💡 Enter all income from oilfield services, hauling, consulting, etc.")
    
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Add Revenue Entry")
        with st.form("revenue_form",clear_on_submit=True):
            r_date = st.date_input("Date",key="rev_date")
            r_client = st.text_input("Client",placeholder="e.g., Long Run Exploration, PwC")
            r_job = st.text_input("Job/Service",placeholder="e.g., Hotshot to Redwater, Consulting")
            r_amount = st.number_input("Amount ($)",min_value=0.0,step=0.01)
            r_gst = st.selectbox("GST Included?",["Yes","No"])
            r_notes = st.text_input("Notes",placeholder="e.g., Invoice #1234")
            
            if st.form_submit_button("➕ Add Revenue",type="primary") and r_amount > 0:
                gst_amt = r_amount * 0.05 / 1.05 if r_gst == "Yes" else 0
                st.session_state.revenue.append({
                    'date': str(r_date),
                    'client': r_client,
                    'job': r_job,
                    'amount': r_amount,
                    'gst_included': r_gst,
                    'gst_amount': round(gst_amt, 2),
                    'notes': r_notes
                })
                st.rerun()
    
    with c2:
        st.subheader("Revenue Entries")
        # Filter by date
        filtered_rev = filter_by_date(st.session_state.revenue, 'date', start_date, end_date)
        
        if filtered_rev:
            rev_df = pd.DataFrame(filtered_rev)
            st.dataframe(rev_df[['date','client','job','amount','gst_included']],use_container_width=True,hide_index=True)
            
            total_rev = sum(r['amount'] for r in filtered_rev)
            total_gst = sum(r['gst_amount'] for r in filtered_rev)
            
            c1,c2 = st.columns(2)
            c1.metric("Total Revenue",f"${total_rev:,.2f}")
            c2.metric("GST Collected",f"${total_gst:,.2f}")
            
            if st.button("🗑️ Clear All Revenue"):
                st.session_state.revenue = []
                st.rerun()
        else:
            st.caption("No revenue entries yet for selected period")

# TRANSACTIONS
elif page == "📋 Transactions":
    st.header("📋 Transactions - Edit Category, Status, ITC")
    if st.session_state.transactions.empty:
        st.warning("Upload CSV first")
    else:
        df = st.session_state.transactions.copy()
        c1,c2 = st.columns(2)
        cat_f = c1.selectbox("Filter Category",["All"]+sorted(df['Category'].unique().tolist()))
        stat_f = c2.selectbox("Filter Status",["All"]+STATUSES)
        fdf = df.copy()
        if cat_f != "All": fdf = fdf[fdf['Category']==cat_f]
        if stat_f != "All": fdf = fdf[fdf['Status']==stat_f]
        edited = st.data_editor(fdf,column_config={"Category":st.column_config.SelectboxColumn("Category",options=CATEGORIES),"Status":st.column_config.SelectboxColumn("Status",options=STATUSES),"ITC":st.column_config.NumberColumn("ITC",format="$%.2f")},use_container_width=True,hide_index=True)
        if st.button("💾 Save Changes",type="primary"):
            for _,row in edited.iterrows():
                mask = (st.session_state.transactions['Date']==row['Date'])&(st.session_state.transactions['Description']==row['Description'])&(st.session_state.transactions['Debit']==row['Debit'])
                if mask.any():
                    st.session_state.transactions.loc[mask,'Category'] = row['Category']
                    st.session_state.transactions.loc[mask,'Status'] = row['Status']
                    st.session_state.transactions.loc[mask,'ITC'] = calc_itc(row['Debit'],row['Credit'],row['Category'],row['Status'])
            st.success("✅ Saved!")
            st.rerun()

# PHONE BILLS
elif page == "📱 Phone Bills":
    st.header("📱 Phone Bills - Track Each Person Separately")
    st.info("💡 CRA: Cannot deduct 100%. Claim only substantiated business-use portion (50-80% typical)")
    st.subheader("⚡ Quick Add Your Data")
    c1,c2 = st.columns(2)
    if c1.button(f"➕ {sh2}: $1,081.42 (12mo @ 60%)",type="secondary"):
        st.session_state.phone_bills.append({'owner':sh2,'period':'Dec 2024-Nov 2025','amount':1081.42,'biz_pct':60,'notes':'12mo, $90.12/mo avg'})
        st.rerun()
    if c2.button(f"➕ {sh1}: $944.85 (12mo @ 60%)",type="secondary"):
        st.session_state.phone_bills.append({'owner':sh1,'period':'Dec 2024-Nov 2025','amount':944.85,'biz_pct':60,'notes':'12mo, $78.88/mo avg'})
        st.rerun()
    st.markdown("---")
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Add Phone Bill")
        with st.form("phone",clear_on_submit=True):
            owner = st.selectbox("Whose Phone?",[sh1,sh2])
            period = st.text_input("Period",placeholder="e.g., Jan 2025 or Dec'24-Nov'25")
            amt = st.number_input("Amount ($)",min_value=0.0,step=0.01)
            biz = st.slider("Business Use %",0,100,60)
            notes = st.text_input("Notes",placeholder="e.g., monthly avg, carrier")
            if st.form_submit_button("➕ Add",type="primary") and amt > 0:
                st.session_state.phone_bills.append({'owner':owner,'period':period,'amount':amt,'biz_pct':biz,'notes':notes})
                st.rerun()
    with c2:
        st.subheader("Phone Bills Added")
        if st.session_state.phone_bills:
            for person in [sh1,sh2]:
                bills = [p for p in st.session_state.phone_bills if p['owner']==person]
                if bills:
                    st.markdown(f"**{person}:**")
                    for i,b in enumerate(st.session_state.phone_bills):
                        if b['owner']==person:
                            ded = b['amount']*b['biz_pct']/100
                            itc = ded*0.05/1.05
                            col1,col2,col3 = st.columns([3,2,1])
                            col1.write(f"{b['period']}: ${b['amount']:.2f}")
                            col2.write(f"ITC: ${itc:.2f}")
                            if col3.button("🗑️",key=f"dp{i}"):
                                st.session_state.phone_bills.pop(i)
                                st.rerun()
                    tot = sum(x['amount'] for x in bills)
                    tot_itc = sum(x['amount']*x['biz_pct']/100*0.05/1.05 for x in bills)
                    st.caption(f"Subtotal: ${tot:.2f} | ITC: ${tot_itc:.2f}")
                    st.markdown("---")
            grand_itc = sum(p['amount']*p['biz_pct']/100*0.05/1.05 for p in st.session_state.phone_bills)
            st.metric("📱 Total Phone ITC",f"${grand_itc:.2f}")

# CASH EXPENSES (Feature 2 - Added Receipt #)
elif page == "💳 Cash Expenses":
    st.header("💳 Cash Expenses")
    st.info("Under $30=no receipt. $30-$150=keep receipt. Over $150=required")
    c1,c2 = st.columns(2)
    with c1:
        with st.form("cash",clear_on_submit=True):
            dt = st.date_input("Date")
            desc = st.text_input("Description")
            amt = st.number_input("Amount ($)",min_value=0.0,step=0.01)
            cat = st.selectbox("Category",["Fuel & Petroleum","Vehicle Repairs","Equipment & Tools","Safety Gear & PPE","Meals (50%)","Office Supplies","Other Business"])
            who = st.selectbox("Paid By",[sh1,sh2])
            receipt = st.text_input("Receipt # or Link",placeholder="e.g., R-001 or Dropbox link")  # NEW
            if st.form_submit_button("➕ Add",type="primary") and amt > 0:
                rate = 0.5 if '50%' in cat else 1.0
                st.session_state.cash_expenses.append({'date':str(dt),'desc':desc,'amount':amt,'category':cat,'paid_by':who,'receipt':receipt,'itc':amt*0.05/1.05*rate})
                st.rerun()
    with c2:
        filtered_cash = filter_by_date(st.session_state.cash_expenses, 'date', start_date, end_date)
        if filtered_cash:
            st.dataframe(pd.DataFrame(filtered_cash)[['date','desc','amount','category','paid_by','receipt']],use_container_width=True,hide_index=True)
            st.metric("Cash ITC",f"${sum(e['itc'] for e in filtered_cash):.2f}")
            if st.button("🗑️ Clear All"): st.session_state.cash_expenses = []; st.rerun()

# PERSONAL ACCOUNT (Feature 2 - Added Receipt #)
elif page == "🏦 Personal Account":
    st.header("🏦 Personal Bank/CC Expenses")
    st.warning("⚠️ Corp should reimburse OR track as shareholder loan")
    c1,c2 = st.columns(2)
    with c1:
        with st.form("pers",clear_on_submit=True):
            dt = st.date_input("Date",key="pd")
            desc = st.text_input("Description",key="pdesc")
            amt = st.number_input("Amount ($)",min_value=0.0,step=0.01,key="pamt")
            cat = st.selectbox("Category",[c for c in CATEGORIES if c not in ['Revenue - Oilfield Services','Shareholder Distribution','Personal Expense','Tax Payment','Exclude']])
            who = st.selectbox("Paid From",[f"{sh1}'s Personal",f"{sh2}'s Personal"])
            receipt = st.text_input("Receipt # or Link",placeholder="e.g., R-001 or Google Drive link")  # NEW
            if st.form_submit_button("➕ Add",type="primary") and amt > 0:
                rate = 0.5 if '50%' in cat else 1.0
                st.session_state.personal_expenses.append({'date':str(dt),'desc':desc,'amount':amt,'category':cat,'paid_from':who,'receipt':receipt,'itc':amt*0.05/1.05*rate})
                st.rerun()
    with c2:
        filtered_pers = filter_by_date(st.session_state.personal_expenses, 'date', start_date, end_date)
        if filtered_pers:
            st.dataframe(pd.DataFrame(filtered_pers)[['date','desc','amount','category','paid_from','receipt']],use_container_width=True,hide_index=True)
            st.metric("Personal Acct ITC",f"${sum(e['itc'] for e in filtered_pers):.2f}")
            if st.button("🗑️ Clear"): st.session_state.personal_expenses = []; st.rerun()

# HOME OFFICE
elif page == "🏠 Home Office":
    st.header("🏠 Home Office - Detailed Breakdown")
    st.info("💡 CRA: Utilities ARE claimable! Calculate: Office sq ft ÷ Total sq ft × Expenses")
    ho = st.session_state.home_office
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Housing Costs (Annual)")
        ho['rent'] = st.number_input("Rent OR Mortgage Interest ($)",value=float(ho['rent']),step=100.0)
        ho['property_tax'] = st.number_input("Property Tax ($)",value=float(ho['property_tax']),step=100.0)
        ho['insurance'] = st.number_input("Home Insurance ($)",value=float(ho['insurance']),step=50.0)
    with c2:
        st.subheader("Utilities (Annual) ✅ Claimable!")
        ho['electricity'] = st.number_input("Electricity ($)",value=float(ho['electricity']),step=50.0)
        ho['gas'] = st.number_input("Gas/Heating ($)",value=float(ho['gas']),step=50.0)
        ho['water'] = st.number_input("Water ($)",value=float(ho['water']),step=50.0)
        ho['internet'] = st.number_input("Internet ($)",value=float(ho['internet']),step=50.0)
    ho['pct'] = st.slider("Office % of Home",0,50,ho['pct'])
    st.markdown("---")
    st.subheader("📊 Breakdown for Accountant")
    items = [('Rent/Mortgage Interest',ho['rent']),('Property Tax',ho['property_tax']),('Home Insurance',ho['insurance']),('Electricity',ho['electricity']),('Gas/Heating',ho['gas']),('Water',ho['water']),('Internet',ho['internet'])]
    data = []
    for name,amt in items:
        if amt > 0:
            ded = amt*ho['pct']/100
            data.append({'Expense':name,'Annual':f"${amt:,.2f}",f"Business ({ho['pct']}%)":f"${ded:,.2f}",'ITC':f"${ded*0.05/1.05:.2f}"})
    if data: st.table(pd.DataFrame(data))
    total = sum(x[1] for x in items)
    total_ded = total*ho['pct']/100
    c1,c2,c3 = st.columns(3)
    c1.metric("Total Home Costs",f"${total:,.2f}")
    c2.metric(f"Deductible ({ho['pct']}%)",f"${total_ded:,.2f}")
    c3.metric("Home Office ITC",f"${total_ded*0.05/1.05:.2f}")
    if st.button("💾 Save",type="primary"): st.session_state.home_office = ho; st.success("Saved!")

# VEHICLE & MILEAGE (Feature 3)
elif page == "🚗 Vehicle & Mileage":
    st.header("🚗 Vehicle Expenses & Mileage Log")
    
    tab1, tab2 = st.tabs(["💳 Vehicle Expenses", "📏 Mileage Log"])
    
    with tab1:
        st.info("💡 Keep mileage log! Deduction = Total costs × Business %")
        c1,c2 = st.columns(2)
        with c1:
            with st.form("veh",clear_on_submit=True):
                desc = st.text_input("Description",placeholder="e.g., Mazda loan Jan 2025")
                vcat = st.selectbox("Type",["Loan/Lease Payment","Fuel","Insurance","Repairs","Registration","Other"])
                amt = st.number_input("Amount ($)",min_value=0.0,step=0.01)
                period = st.text_input("Period",placeholder="e.g., Jan 2025")
                vehicle = st.text_input("Vehicle",placeholder="e.g., 2019 Mazda CX-5")
                biz = st.slider("Business %",0,100,50)
                if st.form_submit_button("➕ Add",type="primary") and amt > 0:
                    ded = amt*biz/100
                    st.session_state.vehicle_expenses.append({'desc':desc,'type':vcat,'amount':amt,'period':period,'vehicle':vehicle,'biz_pct':biz,'deductible':ded,'itc':ded*0.05/1.05})
                    st.rerun()
        with c2:
            if st.session_state.vehicle_expenses:
                for i,v in enumerate(st.session_state.vehicle_expenses):
                    col1,col2,col3 = st.columns([3,2,1])
                    col1.write(f"{v['desc']}: ${v['amount']:.2f}")
                    col2.write(f"ITC: ${v['itc']:.2f}")
                    if col3.button("🗑️",key=f"dv{i}"): st.session_state.vehicle_expenses.pop(i); st.rerun()
                st.metric("Vehicle ITC",f"${sum(v['itc'] for v in st.session_state.vehicle_expenses):.2f}")
    
    with tab2:
        st.subheader("📏 Simple Mileage Log")
        st.info("💡 CRA Rates 2025: $0.72/km first 5,000km, $0.66/km after")
        
        # Dropbox link
        st.markdown("""
        📏 **[Detailed Mileage Log 2025 (Edit Access)](https://www.dropbox.com/scl/fo/7gpryeh93mgky0ybwn66c/AFgO-qdS7aSDhqNlXqX6bks?rlkey=529qzmdiamtdoxhpacfcxsn4v&st=mzzlyssr&dl=0)**  
        *(Accountant: Update KM anytime)*
        """)
        st.markdown("---")
        
        c1,c2 = st.columns(2)
        with c1:
            st.subheader("Add Mileage Entry")
            with st.form("mileage",clear_on_submit=True):
                m_date = st.date_input("Date",key="m_date")
                m_biz_km = st.number_input("Business KM",min_value=0,step=1)
                m_total_km = st.number_input("Total KM (odometer)",min_value=0,step=1)
                
                if st.form_submit_button("➕ Add",type="primary") and m_total_km > 0:
                    st.session_state.mileage.append({
                        'date': str(m_date),
                        'business_km': m_biz_km,
                        'total_km': m_total_km
                    })
                    st.rerun()
        
        with c2:
            st.subheader("Mileage Summary")
            filtered_mileage = filter_by_date(st.session_state.mileage, 'date', start_date, end_date)
            
            if filtered_mileage:
                total_biz_km = sum(m['business_km'] for m in filtered_mileage)
                total_km = max(m['total_km'] for m in filtered_mileage) - min(m['total_km'] for m in filtered_mileage) if len(filtered_mileage) > 1 else (filtered_mileage[0]['total_km'] if filtered_mileage else 0)
                
                # If only tracking business KM
                if total_km == 0:
                    total_km = sum(m['total_km'] for m in filtered_mileage)
                
                biz_pct = (total_biz_km / total_km * 100) if total_km > 0 else 0
                
                st.markdown(f"### Annual Totals ({start_date.year})")
                c1,c2,c3 = st.columns(3)
                c1.metric("Business KM",f"{total_biz_km:,}")
                c2.metric("Total KM",f"{total_km:,}")
                c3.metric("Business %",f"{biz_pct:.1f}%")
                
                # CRA deduction calc
                if total_biz_km <= 5000:
                    cra_ded = total_biz_km * 0.72
                else:
                    cra_ded = (5000 * 0.72) + ((total_biz_km - 5000) * 0.66)
                
                st.metric("CRA Mileage Deduction",f"${cra_ded:,.2f}")
                
                if st.button("🗑️ Clear Mileage"):
                    st.session_state.mileage = []
                    st.rerun()
            else:
                st.caption("No mileage entries yet")

# OTHER EXPENSES
elif page == "📚 Other Expenses":
    st.header("📚 Other Expenses - Training, PPE, Software")
    c1,c2 = st.columns(2)
    with c1:
        with st.form("other",clear_on_submit=True):
            dt = st.date_input("Date",key="od")
            desc = st.text_input("Description",placeholder="e.g., H2S Alive cert")
            cat = st.selectbox("Category",["Training & Certifications","Safety Gear & PPE","Software & Subscriptions","Professional Fees","Office Supplies","Travel & Accommodations","Other Business"])
            amt = st.number_input("Amount ($)",min_value=0.0,step=0.01,key="oamt")
            if st.form_submit_button("➕ Add",type="primary") and amt > 0:
                st.session_state.other_expenses.append({'date':str(dt),'desc':desc,'category':cat,'amount':amt,'itc':amt*0.05/1.05})
                st.rerun()
    with c2:
        filtered_other = filter_by_date(st.session_state.other_expenses, 'date', start_date, end_date)
        if filtered_other:
            st.dataframe(pd.DataFrame(filtered_other)[['date','desc','category','amount']],use_container_width=True,hide_index=True)
            st.markdown("**By Category:**")
            for cat in set(e['category'] for e in filtered_other):
                cat_tot = sum(e['amount'] for e in filtered_other if e['category']==cat)
                st.caption(f"{cat}: ${cat_tot:.2f}")
            st.metric("Other ITC",f"${sum(e['itc'] for e in filtered_other):.2f}")
            if st.button("🗑️ Clear"): st.session_state.other_expenses = []; st.rerun()

# GST FILING
elif page == "💰 GST Filing":
    st.header("💰 GST/HST Return (Form GST34)")
    st.caption(f"📆 Period: {start_date} to {end_date}")
    
    df = st.session_state.transactions
    ho = st.session_state.home_office
    
    # Revenue from manual entries + bank
    filtered_rev = filter_by_date(st.session_state.revenue, 'date', start_date, end_date)
    manual_revenue = sum(r['amount'] for r in filtered_rev)
    manual_gst = sum(r['gst_amount'] for r in filtered_rev)
    
    bank_revenue = df[df['Category']=='Revenue - Oilfield Services']['Credit'].sum() if not df.empty else 0
    bank_gst = bank_revenue * 0.05 / 1.05
    
    total_revenue = manual_revenue + bank_revenue
    gst_coll = manual_gst + bank_gst
    
    # ITCs
    itc_brk = {}
    if not df.empty:
        for cat in df['Category'].unique():
            v = df[df['Category']==cat]['ITC'].sum()
            if v > 0: itc_brk[f"Bank: {cat}"] = v
    
    for p in st.session_state.phone_bills:
        k = f"Phone: {p['owner']}"
        itc_brk[k] = itc_brk.get(k,0) + p['amount']*p['biz_pct']/100*0.05/1.05
    
    filtered_cash = filter_by_date(st.session_state.cash_expenses, 'date', start_date, end_date)
    for e in filtered_cash: itc_brk[f"Cash: {e['category']}"] = itc_brk.get(f"Cash: {e['category']}",0) + e['itc']
    
    filtered_pers = filter_by_date(st.session_state.personal_expenses, 'date', start_date, end_date)
    for e in filtered_pers: itc_brk[f"Personal: {e['category']}"] = itc_brk.get(f"Personal: {e['category']}",0) + e['itc']
    
    ho_tot = ho['rent']+ho['property_tax']+ho['insurance']+ho['electricity']+ho['gas']+ho['water']+ho['internet']
    ho_itc = ho_tot*ho['pct']/100*0.05/1.05
    if ho_itc > 0: itc_brk['Home Office'] = ho_itc
    
    for v in st.session_state.vehicle_expenses: itc_brk[f"Vehicle: {v['type']}"] = itc_brk.get(f"Vehicle: {v['type']}",0) + v['itc']
    
    filtered_other = filter_by_date(st.session_state.other_expenses, 'date', start_date, end_date)
    for e in filtered_other: itc_brk[f"Other: {e['category']}"] = itc_brk.get(f"Other: {e['category']}",0) + e['itc']
    
    total_itc = sum(itc_brk.values())
    net = gst_coll - total_itc
    
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("GST Collected")
        st.write(f"Manual Revenue: ${manual_revenue:,.2f}")
        st.write(f"Bank Revenue: ${bank_revenue:,.2f}")
        st.metric("Total Revenue",f"${total_revenue:,.2f}")
        st.metric("GST Collected (5%)",f"${gst_coll:,.2f}")
    with c2:
        st.subheader("ITCs by Source")
        for k,v in sorted(itc_brk.items(),key=lambda x:-x[1]):
            if v > 0.01: st.write(f"- {k}: **${v:,.2f}**")
        st.markdown(f"### TOTAL ITCs: ${total_itc:,.2f}")
    st.markdown("---")
    if net > 0: st.error(f"## 📤 GST OWING: ${net:,.2f}")
    else: st.success(f"## 📥 GST REFUND: ${abs(net):,.2f}")

# SHAREHOLDER
elif page == "👥 Shareholder":
    st.header("👥 Shareholder Loan")
    st.warning("⚠️ ITA 15(2): Must repay within 1 year or becomes taxable")
    df = st.session_state.transactions
    dist = df[df['Category']=='Shareholder Distribution']['Debit'].sum() if not df.empty else 0
    pers_corp = df[df['Status']=='personal']['Debit'].sum() if not df.empty else 0
    sh_owe = dist + pers_corp
    cash_tot = sum(e['amount'] for e in st.session_state.cash_expenses)
    pers_tot = sum(e['amount'] for e in st.session_state.personal_expenses)
    phone_tot = sum(p['amount']*p['biz_pct']/100 for p in st.session_state.phone_bills)
    corp_owe = cash_tot + pers_tot + phone_tot
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("💸 Corp Owes Shareholders")
        st.write(f"Cash expenses: ${cash_tot:,.2f}")
        st.write(f"Personal acct: ${pers_tot:,.2f}")
        st.write(f"Phone (biz): ${phone_tot:,.2f}")
        st.metric("Total",f"${corp_owe:,.2f}")
    with c2:
        st.subheader("💳 Shareholders Owe Corp")
        st.write(f"Distributions: ${dist:,.2f}")
        st.write(f"Personal on corp: ${pers_corp:,.2f}")
        st.metric("Total",f"${sh_owe:,.2f}")
    st.markdown("---")
    net = sh_owe - corp_owe
    if net > 0:
        st.warning(f"### Shareholders owe Corp: ${net:,.2f}")
        st.write(f"{sh1} ({sh1_pct}%): ${net*sh1_pct/100:,.2f}")
        st.write(f"{sh2} ({100-sh1_pct}%): ${net*(100-sh1_pct)/100:,.2f}")
    else: st.success(f"### Corp owes Shareholders: ${abs(net):,.2f}")

# ACCOUNTANT SUMMARY (Feature 4 - T2125 Export)
elif page == "📊 Accountant Summary":
    st.header("📊 Accountant Summary")
    st.caption(f"📆 Period: {start_date} to {end_date}")
    
    df = st.session_state.transactions
    ho = st.session_state.home_office
    
    # Revenue
    filtered_rev = filter_by_date(st.session_state.revenue, 'date', start_date, end_date)
    manual_revenue = sum(r['amount'] for r in filtered_rev)
    bank_revenue = df[df['Category']=='Revenue - Oilfield Services']['Credit'].sum() if not df.empty else 0
    total_revenue = manual_revenue + bank_revenue
    
    # Expenses
    bank_exp = df[df['Status']=='business']['Debit'].sum() if not df.empty else 0
    bank_itc = df['ITC'].sum() if not df.empty else 0
    
    filtered_cash = filter_by_date(st.session_state.cash_expenses, 'date', start_date, end_date)
    cash_exp = sum(e['amount'] for e in filtered_cash)
    cash_itc = sum(e['itc'] for e in filtered_cash)
    
    filtered_pers = filter_by_date(st.session_state.personal_expenses, 'date', start_date, end_date)
    pers_exp = sum(e['amount'] for e in filtered_pers)
    pers_itc = sum(e['itc'] for e in filtered_pers)
    
    phone_exp = sum(p['amount']*p['biz_pct']/100 for p in st.session_state.phone_bills)
    phone_itc = sum(p['amount']*p['biz_pct']/100*0.05/1.05 for p in st.session_state.phone_bills)
    
    ho_tot = ho['rent']+ho['property_tax']+ho['insurance']+ho['electricity']+ho['gas']+ho['water']+ho['internet']
    ho_exp = ho_tot*ho['pct']/100
    ho_itc = ho_exp*0.05/1.05
    
    veh_exp = sum(v['deductible'] for v in st.session_state.vehicle_expenses)
    veh_itc = sum(v['itc'] for v in st.session_state.vehicle_expenses)
    
    filtered_other = filter_by_date(st.session_state.other_expenses, 'date', start_date, end_date)
    other_exp = sum(e['amount'] for e in filtered_other)
    other_itc = sum(e['itc'] for e in filtered_other)
    
    total_exp = bank_exp+cash_exp+pers_exp+phone_exp+ho_exp+veh_exp+other_exp
    total_itc = bank_itc+cash_itc+pers_itc+phone_itc+ho_itc+veh_itc+other_itc
    
    # Metrics
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("💵 Revenue",f"${total_revenue:,.0f}")
    c2.metric("📉 Expenses",f"${total_exp:,.0f}")
    c3.metric("💰 ITCs",f"${total_itc:,.2f}")
    gst_coll = total_revenue*0.05/1.05
    net = gst_coll - total_itc
    c4.metric("GST Refund" if net<0 else "GST Owing",f"${abs(net):,.2f}")
    
    st.markdown("---")
    st.subheader("📋 Detailed Breakdown")
    data = [
        {'Source':'💵 Manual Revenue','Amount':f"${manual_revenue:,.2f}",'ITC':'N/A'},
        {'Source':'🏦 Bank Revenue','Amount':f"${bank_revenue:,.2f}",'ITC':'N/A'},
        {'Source':'🏦 Bank Expenses','Amount':f"${bank_exp:,.2f}",'ITC':f"${bank_itc:,.2f}"},
        {'Source':'💳 Cash Expenses','Amount':f"${cash_exp:,.2f}",'ITC':f"${cash_itc:,.2f}"},
        {'Source':'💳 Personal Account','Amount':f"${pers_exp:,.2f}",'ITC':f"${pers_itc:,.2f}"},
        {'Source':'📱 Phone Bills','Amount':f"${phone_exp:,.2f}",'ITC':f"${phone_itc:,.2f}"},
        {'Source':'🏠 Home Office','Amount':f"${ho_exp:,.2f}",'ITC':f"${ho_itc:,.2f}"},
        {'Source':'🚗 Vehicle','Amount':f"${veh_exp:,.2f}",'ITC':f"${veh_itc:,.2f}"},
        {'Source':'📚 Other','Amount':f"${other_exp:,.2f}",'ITC':f"${other_itc:,.2f}"},
        {'Source':'**TOTAL EXPENSES**','Amount':f"**${total_exp:,.2f}**",'ITC':f"**${total_itc:,.2f}**"},
    ]
    st.table(pd.DataFrame(data))
    
    # Mileage summary
    filtered_mileage = filter_by_date(st.session_state.mileage, 'date', start_date, end_date)
    if filtered_mileage:
        total_biz_km = sum(m['business_km'] for m in filtered_mileage)
        total_km = sum(m['total_km'] for m in filtered_mileage)
        biz_pct_km = (total_biz_km / total_km * 100) if total_km > 0 else 0
        st.markdown(f"### 📏 Mileage: Business KM: {total_biz_km:,} | Total KM: {total_km:,} | Business %: {biz_pct_km:.1f}%")
    
    st.markdown("---")
    
    # T2125 EXPORT BUTTON (Feature 4)
    st.subheader("📊 T2125 Export for Accountant")
    
    def generate_t2125_csv():
        rows = []
        
        # Revenue entries
        for r in filtered_rev:
            rows.append({
                'Date': r['date'],
                'Type': 'Revenue',
                'Category': 'Oilfield Services',
                'Client_Vendor': r['client'],
                'Amount': r['amount'],
                'Business_Pct': 100,
                'GST': r['gst_amount'],
                'Receipt_KM': r.get('notes', ''),
                'Notes': r['job']
            })
        
        # Bank transactions
        if not df.empty:
            for _, row in df[df['Status']=='business'].iterrows():
                rows.append({
                    'Date': row['Date'],
                    'Type': 'Expense',
                    'Category': row['Category'],
                    'Client_Vendor': row['Description'][:50],
                    'Amount': row['Debit'],
                    'Business_Pct': 100,
                    'GST': row['ITC'],
                    'Receipt_KM': '',
                    'Notes': 'Bank transaction'
                })
        
        # Cash expenses
        for e in filtered_cash:
            rows.append({
                'Date': e['date'],
                'Type': 'Expense',
                'Category': e['category'],
                'Client_Vendor': e['desc'],
                'Amount': e['amount'],
                'Business_Pct': 100,
                'GST': e['itc'],
                'Receipt_KM': e.get('receipt', ''),
                'Notes': f"Cash - {e['paid_by']}"
            })
        
        # Personal expenses
        for e in filtered_pers:
            rows.append({
                'Date': e['date'],
                'Type': 'Expense',
                'Category': e['category'],
                'Client_Vendor': e['desc'],
                'Amount': e['amount'],
                'Business_Pct': 100,
                'GST': e['itc'],
                'Receipt_KM': e.get('receipt', ''),
                'Notes': f"Personal Acct - {e['paid_from']}"
            })
        
        # Phone bills
        for p in st.session_state.phone_bills:
            rows.append({
                'Date': p['period'],
                'Type': 'Expense',
                'Category': 'Phone & Communications',
                'Client_Vendor': p['owner'],
                'Amount': p['amount'],
                'Business_Pct': p['biz_pct'],
                'GST': p['amount']*p['biz_pct']/100*0.05/1.05,
                'Receipt_KM': '',
                'Notes': p.get('notes', '')
            })
        
        # Home office
        if ho_exp > 0:
            rows.append({
                'Date': f"{start_date.year} Annual",
                'Type': 'Expense',
                'Category': 'Home Office',
                'Client_Vendor': 'Various utilities',
                'Amount': ho_tot,
                'Business_Pct': ho['pct'],
                'GST': ho_itc,
                'Receipt_KM': '',
                'Notes': f"Rent:{ho['rent']}, Elec:{ho['electricity']}, Gas:{ho['gas']}, Water:{ho['water']}, Internet:{ho['internet']}"
            })
        
        # Vehicle
        for v in st.session_state.vehicle_expenses:
            rows.append({
                'Date': v['period'],
                'Type': 'Expense',
                'Category': f"Vehicle - {v['type']}",
                'Client_Vendor': v['vehicle'],
                'Amount': v['amount'],
                'Business_Pct': v['biz_pct'],
                'GST': v['itc'],
                'Receipt_KM': '',
                'Notes': v['desc']
            })
        
        # Mileage row
        if filtered_mileage:
            total_biz_km = sum(m['business_km'] for m in filtered_mileage)
            total_km = sum(m['total_km'] for m in filtered_mileage)
            biz_pct_km = (total_biz_km / total_km * 100) if total_km > 0 else 0
            rows.append({
                'Date': f"{start_date.year} Annual",
                'Type': 'Vehicle',
                'Category': 'Mileage',
                'Client_Vendor': f"Business KM:{total_biz_km} Total KM:{total_km}",
                'Amount': 0,
                'Business_Pct': round(biz_pct_km, 1),
                'GST': 'N',
                'Receipt_KM': 'Detailed log: https://www.dropbox.com/scl/fo/7gpryeh93mgky0ybwn66c/AFgO-qdS7aSDhqNlXqX6bks?rlkey=529qzmdiamtdoxhpacfcxsn4v&st=mzzlyssr&dl=0',
                'Notes': 'See Dropbox for daily log'
            })
        
        # Other expenses
        for e in filtered_other:
            rows.append({
                'Date': e['date'],
                'Type': 'Expense',
                'Category': e['category'],
                'Client_Vendor': e['desc'],
                'Amount': e['amount'],
                'Business_Pct': 100,
                'GST': e['itc'],
                'Receipt_KM': '',
                'Notes': ''
            })
        
        return pd.DataFrame(rows)
    
    t2125_df = generate_t2125_csv()
    
    if not t2125_df.empty:
        st.download_button(
            "📊 Download T2125 CSV for Accountant",
            t2125_df.to_csv(index=False),
            f"T2125_RigBooks_{start_date.year}.csv",
            "text/csv",
            type="primary",
            use_container_width=True
        )
        
        with st.expander("Preview T2125 Export"):
            st.dataframe(t2125_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No data to export. Add revenue and expenses first.")

# CRA GUIDE
elif page == "🛡️ CRA Guide":
    st.header("🛡️ CRA Audit Guide")
    st.subheader("Receipt Requirements")
    st.table(pd.DataFrame({"Amount":["Under $30","$30-$150","Over $150","Fuel","Meals"],"Receipt?":["❌ No","⚠️ Recommended","✅ Required","❌ No","✅ Required"],"Accepted":["Bank statement","Statement+note","Original receipt","Mileage log","Receipt+attendees"]}))
    st.subheader("Home Office")
    st.info("Space must be used regularly for business. Calculate: Office sq ft ÷ Total sq ft. Apply % to rent/mortgage interest, utilities, insurance, property tax.")
    st.subheader("Phone Bills")
    st.info("Keep bills + usage log (business calls: date, who, duration, purpose). Calculate: Business usage ÷ Total = %. Typical: 50-80%")
    st.subheader("Vehicle & Mileage")
    st.info("CRA Rates 2025: $0.72/km first 5,000km, $0.66/km after. Log: date, destination, purpose, km, odometer start/end")
    st.markdown("""
    📏 **[Detailed Mileage Log 2025](https://www.dropbox.com/scl/fo/7gpryeh93mgky0ybwn66c/AFgO-qdS7aSDhqNlXqX6bks?rlkey=529qzmdiamtdoxhpacfcxsn4v&st=mzzlyssr&dl=0)**
    """)
    st.success("✅ With detailed records, you're audit-ready!")
