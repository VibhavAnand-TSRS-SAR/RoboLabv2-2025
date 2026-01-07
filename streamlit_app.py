import streamlit as st
import pandas as pd
import sqlite3
import time
import math
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="RoboLab Inventory", page_icon="🤖", layout="wide")

# --- THEME CONFIGURATION ---
THEMES = {
    "TSRS (Red/Grey)": {
        "primary": "#A6192E",       # TSRS Red
        "secondary": "#58595B",     # Grey
        "bg_sidebar": "#F3F4F6",    # Light Grey
        "text_sidebar": "#1F2937",  # Dark Grey
        "hover": "#E5E7EB",         # Light Hover
        "active": "#A6192E",        # Red Active
        "active_text": "#FFFFFF"
    },
    "Night Mode (Dark/Blue)": {
        "primary": "#3B82F6",       # Blue
        "secondary": "#9CA3AF",     # Light Grey
        "bg_sidebar": "#111827",    # Dark BG
        "text_sidebar": "#E5E7EB",  # White Text
        "hover": "#374151",         # Dark Hover
        "active": "#1D4ED8",        # Blue Active
        "active_text": "#FFFFFF"
    }
}

# Initialize Session State for Theme and Navigation
if 'theme' not in st.session_state:
    st.session_state.theme = "TSRS (Red/Grey)"
if 'current_view' not in st.session_state:
    st.session_state.current_view = "Dashboard"

# Apply CSS based on current theme
current_theme = THEMES[st.session_state.theme]

st.markdown(f"""
<style>
    /* Global Styles */
    .stApp {{
        font-family: 'Inter', sans-serif;
    }}
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: {current_theme['bg_sidebar']};
    }}
    
    /* Custom Navigation Buttons */
    .nav-btn {{
        width: 100%;
        text-align: left;
        padding: 12px 15px;
        margin: 5px 0;
        border: none;
        border-radius: 8px;
        background-color: transparent;
        color: {current_theme['text_sidebar']};
        font-size: 16px;
        cursor: pointer;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .nav-btn:hover {{
        background-color: {current_theme['hover']};
    }}
    .nav-btn.active {{
        background-color: {current_theme['active']};
        color: {current_theme['active_text']};
        font-weight: 600;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    
    /* Metrics Styling */
    div[data-testid="stMetric"] {{
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid {current_theme['primary']};
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }}
    
    /* Headers */
    h1, h2, h3 {{
        color: {current_theme['secondary']};
    }}
    h1 {{
        color: {current_theme['primary']};
        border-bottom: 2px solid #E5E7EB;
        padding-bottom: 10px;
    }}

    /* Login Screen Box */
    .login-box {{
        background: white;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        border-top: 6px solid {current_theme['primary']};
    }}
</style>
""", unsafe_allow_html=True)

# --- DATABASE FUNCTIONS ---

def get_db_connection():
    conn = sqlite3.connect('robolab.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Create Tables if not exist
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 emp_id TEXT UNIQUE NOT NULL,
                 name TEXT NOT NULL,
                 password TEXT NOT NULL,
                 role TEXT NOT NULL,
                 dob TEXT,
                 gender TEXT,
                 address TEXT,
                 phone TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL,
                 category TEXT,
                 location TEXT,
                 quantity INTEGER DEFAULT 0,
                 min_stock INTEGER DEFAULT 5,
                 price REAL DEFAULT 0.0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 item_id INTEGER,
                 item_name TEXT,
                 type TEXT,
                 quantity INTEGER,
                 user TEXT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 notes TEXT)''')
    
    # 2. Migration: Check for missing columns in existing DB (for Profile update)
    # This prevents crashes if user runs this code on an old DB file
    try:
        c.execute("SELECT dob FROM users LIMIT 1")
    except sqlite3.OperationalError:
        # Columns missing, add them
        c.execute("ALTER TABLE users ADD COLUMN dob TEXT")
        c.execute("ALTER TABLE users ADD COLUMN gender TEXT")
        c.execute("ALTER TABLE users ADD COLUMN address TEXT")
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        conn.commit()

    # 3. Seed Admin
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)",
                  ('admin', 'System Admin', 'admin123', 'admin'))
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)",
                  ('assistant', 'Lab Assistant', '123', 'assistant'))
        conn.commit()
    
    conn.close()

def run_query(query, params=(), fetch=False):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetch:
            data = c.fetchall()
            conn.close()
            return [dict(row) for row in data] # Return as dicts
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database Error: {e}")
        conn.close()
        return False

def get_inventory_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

# --- AUTHENTICATION ---

def login_user(emp_id, password):
    user = run_query("SELECT * FROM users WHERE emp_id = ? AND password = ?", (emp_id, password), fetch=True)
    if user:
        return user[0]
    return None

# --- UI COMPONENTS ---

def render_sidebar():
    with st.sidebar:
        # TSRS Style Header
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <h1 style="border:none; color:{current_theme['primary']}; font-size: 28px; margin:0;">TSRS</h1>
                <p style="color:{current_theme['secondary']}; font-size: 14px; margin:0;">Robotics Lab Inventory</p>
            </div>
        """, unsafe_allow_html=True)
        
        # User Badge
        st.info(f"👤 {st.session_state.user['name']} ({st.session_state.user['role'].upper()})")
        
        st.markdown("---")
        
        # Custom Nav Buttons
        nav_options = [
            ("Dashboard", "📊"),
            ("Inventory", "📦"),
            ("Stock Operations", "🔄"),
            ("Reports", "📈"),
            ("Shopping List", "🛒"),
            ("User Management", "👥"),
            ("My Profile", "👤"),
            ("Settings", "⚙️")
        ]
        
        for page, icon in nav_options:
            # Highlight active button
            is_active = st.session_state.current_view == page
            active_class = "active" if is_active else ""
            
            # We use a button but style it with CSS above
            if st.button(f"{icon}  {page}", key=f"nav_{page}", use_container_width=True):
                st.session_state.current_view = page
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Log Out", use_container_width=True):
            st.session_state.user = None
            st.rerun()

# --- VIEWS ---

def view_dashboard():
    st.title("📊 Lab Overview")
    df = get_inventory_df()
    
    if df.empty:
        st.info("Inventory is empty. Go to Inventory tab to add items.")
        return

    # Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Components", int(df['quantity'].sum()))
    col2.metric("Total Value", f"₹{df.apply(lambda x: x['quantity'] * x['price'], axis=1).sum():,.2f}")
    
    low_stock_count = df[df['quantity'] <= df['min_stock']].shape[0]
    col3.metric("Action Required", f"{low_stock_count} Items Low", delta_color="inverse")

    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.subheader("⚠️ Low Stock Alerts")
        low_stock = df[df['quantity'] <= df['min_stock']][['name', 'quantity', 'min_stock', 'location']]
        if not low_stock.empty:
            st.dataframe(low_stock, use_container_width=True)
        else:
            st.success("✅ All stock levels are healthy.")

    with col_right:
        st.subheader("Recent Logs")
        conn = get_db_connection()
        trans_df = pd.read_sql_query("SELECT item_name, type, quantity FROM transactions ORDER BY timestamp DESC LIMIT 5", conn)
        conn.close()
        if not trans_df.empty:
            # Custom formatting for logs
            for _, row in trans_df.iterrows():
                color = "green" if row['type'] == 'in' else "red"
                icon = "📥" if row['type'] == 'in' else "📤"
                st.markdown(f"<div style='padding:10px; border-bottom:1px solid #eee;'>{icon} <span style='color:{color}; font-weight:bold'>{row['type'].upper()}</span> <b>{row['quantity']}</b> {row['item_name']}</div>", unsafe_allow_html=True)
        else:
            st.write("No activity yet.")

def view_inventory():
    st.title("📦 Inventory Manager")
    
    tab1, tab2, tab3 = st.tabs(["🔎 Search & Edit", "➕ Add Item", "📂 Bulk Upload"])
    
    with tab1:
        df = get_inventory_df()
        col1, col2 = st.columns(2)
        search = col1.text_input("Search Item", placeholder="e.g. Arduino")
        category = col2.selectbox("Category", ["All"] + list(df['category'].unique()) if not df.empty else ["All"])
        
        if not df.empty:
            if search:
                df = df[df['name'].str.contains(search, case=False)]
            if category != "All":
                df = df[df['category'] == category]
            
            st.dataframe(df, use_container_width=True)
            
            # Admin Delete
            if st.session_state.user['role'] == 'admin':
                with st.expander("🗑️ Delete Item"):
                    del_id = st.selectbox("Select Item to Delete", df['name'].tolist())
                    if st.button("Confirm Delete", type="primary"):
                        item_id = df[df['name'] == del_id]['id'].values[0]
                        run_query("DELETE FROM inventory WHERE id = ?", (int(item_id),))
                        st.rerun()

    with tab2:
        st.subheader("Add Single Component")
        with st.form("add_item_form"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Item Name*")
            category = col2.selectbox("Category", ["Microcontrollers", "Sensors", "Motors", "Power", "Passive", "Tools", "Others"])
            location = col1.text_input("Location (Shelf/Bin)")
            price = col2.number_input("Unit Price (₹)", min_value=0.0)
            
            st.markdown("---")
            st.write("**Stock Configuration**")
            c1, c2, c3 = st.columns(3)
            qty = c1.number_input("Initial Quantity", min_value=0, value=0)
            
            # FEATURE 1: MIN STOCK PERCENTAGE
            use_percent = c2.checkbox("Set Min Stock by %?")
            if use_percent:
                percent = c3.number_input("Alert Percentage (%)", min_value=1, max_value=100, value=20)
                min_stock = math.floor(qty * (percent/100))
                st.caption(f"Min Stock will be set to: **{min_stock}**")
            else:
                min_stock = c3.number_input("Min Stock Threshold", min_value=0, value=5)
            
            if st.form_submit_button("Save Item"):
                if name:
                    run_query("INSERT INTO inventory (name, category, location, quantity, min_stock, price) VALUES (?, ?, ?, ?, ?, ?)",
                              (name, category, location, qty, min_stock, price))
                    st.success(f"Successfully added {name}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Item Name is required.")

    with tab3:
        st.write("Upload an Excel file (.xlsx) with columns: `Name`, `Category`, `Location`, `Quantity`, `MinStock`, `Price`")
        uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
        if uploaded_file:
            try:
                excel_data = pd.read_excel(uploaded_file)
                st.dataframe(excel_data.head())
                if st.button("Process Upload"):
                    count = 0
                    for index, row in excel_data.iterrows():
                        item_name = row.get('Name') or row.get('name')
                        if item_name:
                            run_query("INSERT INTO inventory (name, category, location, quantity, min_stock, price) VALUES (?, ?, ?, ?, ?, ?)",
                                      (item_name, 
                                       row.get('Category', 'Others'), 
                                       row.get('Location', 'Unknown'), 
                                       row.get('Quantity', 0), 
                                       row.get('MinStock', 5), 
                                       row.get('Price', 0.0)))
                            count += 1
                    st.success(f"Imported {count} items!")
                    time.sleep(1)
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

def view_stock_actions():
    st.title("🔄 Stock In / Stock Out")
    
    df = get_inventory_df()
    if df.empty:
        st.warning("Inventory empty.")
        return

    # Use columns to separate In/Out clearly
    col_in, col_mid, col_out = st.columns([1, 0.1, 1])
    
    with col_in:
        st.markdown(f"<div style='background:#ecfdf5; padding:20px; border-radius:10px; border:1px solid #10b981;'>", unsafe_allow_html=True)
        st.subheader("📥 Check In (Add)")
        with st.form("stock_in"):
            item_in = st.selectbox("Select Item", df['name'].tolist(), key="in_select")
            qty_in = st.number_input("Quantity", min_value=1, key="in_qty")
            notes_in = st.text_input("Notes / PO Number", key="in_notes")
            
            if st.form_submit_button("Confirm Add", type="primary"):
                curr_item = df[df['name'] == item_in].iloc[0]
                new_qty = int(curr_item['quantity'] + qty_in)
                run_query("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, int(curr_item['id'])))
                run_query("INSERT INTO transactions (item_id, item_name, type, quantity, user, notes) VALUES (?, ?, ?, ?, ?, ?)",
                          (int(curr_item['id']), curr_item['name'], 'in', qty_in, st.session_state.user['name'], notes_in))
                st.success("Stock Added!")
                time.sleep(0.5)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_out:
        st.markdown(f"<div style='background:#fef2f2; padding:20px; border-radius:10px; border:1px solid #ef4444;'>", unsafe_allow_html=True)
        st.subheader("📤 Check Out (Deduct)")
        with st.form("stock_out"):
            item_out = st.selectbox("Select Item", df['name'].tolist(), key="out_select")
            qty_out = st.number_input("Quantity", min_value=1, key="out_qty")
            notes_out = st.text_input("Reason / Student Name", key="out_notes")
            
            if st.form_submit_button("Confirm Deduct", type="primary"):
                curr_item = df[df['name'] == item_out].iloc[0]
                if curr_item['quantity'] < qty_out:
                    st.error("Insufficient Stock!")
                else:
                    new_qty = int(curr_item['quantity'] - qty_out)
                    run_query("UPDATE inventory SET quantity = ? WHERE id = ?", (new_qty, int(curr_item['id'])))
                    run_query("INSERT INTO transactions (item_id, item_name, type, quantity, user, notes) VALUES (?, ?, ?, ?, ?, ?)",
                              (int(curr_item['id']), curr_item['name'], 'out', qty_out, st.session_state.user['name'], notes_out))
                    st.success("Stock Deducted!")
                    time.sleep(0.5)
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

def view_reports():
    st.title("📈 Reports & Logs")
    
    conn = get_db_connection()
    trans_df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    
    if trans_df.empty:
        st.info("No transactions found.")
        return
        
    trans_df['timestamp'] = pd.to_datetime(trans_df['timestamp'])
    
    # Visuals
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Stock Movements")
        st.bar_chart(trans_df['type'].value_counts())
    with c2:
        st.subheader("Most Used Items")
        st.bar_chart(trans_df['item_name'].value_counts().head(5))
    
    # Detailed Log
    st.subheader("Transaction History")
    
    # Filter by type
    filter_type = st.radio("Filter Log", ["All", "Stock In", "Stock Out"], horizontal=True)
    
    display_df = trans_df.copy()
    if filter_type == "Stock In":
        display_df = display_df[display_df['type'] == 'in']
    elif filter_type == "Stock Out":
        display_df = display_df[display_df['type'] == 'out']
        
    st.dataframe(
        display_df[['timestamp', 'item_name', 'type', 'quantity', 'user', 'notes']].sort_values('timestamp', ascending=False),
        use_container_width=True
    )

def view_shopping_list():
    st.title("🛒 Procurement List")
    df = get_inventory_df()
    to_buy = df[df['quantity'] < df['min_stock']].copy()
    
    if to_buy.empty:
        st.success("✅ No shortages. Inventory is healthy.")
        return
        
    to_buy['Required'] = to_buy['min_stock'] - to_buy['quantity']
    to_buy['Cost'] = to_buy['Required'] * to_buy['price']
    
    st.metric("Estimated Budget Required", f"₹{to_buy['Cost'].sum():,.2f}")
    
    st.dataframe(to_buy[['name', 'quantity', 'min_stock', 'Required', 'price', 'Cost']], use_container_width=True)
    
    # Generate CSV
    csv = to_buy.to_csv(index=False).encode('utf-8')
    st.download_button("Download Order List", csv, "procurement_list.csv", "text/csv")

def view_users():
    st.title("👥 User Administration")
    if st.session_state.user['role'] != 'admin':
        st.error("Restricted Area")
        return

    conn = get_db_connection()
    users_df = pd.read_sql_query("SELECT id, emp_id, name, role, phone FROM users", conn)
    conn.close()
    
    st.dataframe(users_df, use_container_width=True)
    
    with st.expander("Add New Employee"):
        with st.form("add_user"):
            c1, c2 = st.columns(2)
            new_emp_id = c1.text_input("Employee ID*")
            new_name = c2.text_input("Full Name*")
            new_pass = c1.text_input("Password*", type="password")
            new_role = c2.selectbox("Role", ["assistant", "admin"])
            # Feature 4: Basic Details
            new_dob = c1.date_input("Date of Birth")
            new_phone = c2.text_input("Phone Number")
            
            if st.form_submit_button("Create Account"):
                if run_query("INSERT INTO users (emp_id, name, password, role, dob, phone) VALUES (?, ?, ?, ?, ?, ?)", 
                             (new_emp_id, new_name, new_pass, new_role, str(new_dob), new_phone)):
                    st.success("User added.")
                    st.rerun()
                else:
                    st.error("Error: ID may already exist.")

def view_profile():
    st.title("👤 Employee Profile")
    user = st.session_state.user
    
    # FEATURE 4: EXTENDED PROFILE UI
    col_l, col_r = st.columns([1, 2])
    
    with col_l:
        st.image("https://ui-avatars.com/api/?name=" + user['name'].replace(" ", "+") + "&background=random&size=200", width=150)
        st.write(f"**ID:** {user['emp_id']}")
        st.write(f"**Role:** {user['role'].capitalize()}")
    
    with col_r:
        with st.form("edit_profile"):
            st.subheader("Edit Details")
            c1, c2 = st.columns(2)
            
            # Fetch fresh data
            curr_user = run_query("SELECT * FROM users WHERE id=?", (user['id'],), fetch=True)[0]
            
            name = c1.text_input("Full Name", value=curr_user['name'])
            password = c2.text_input("New Password (Optional)", type="password")
            
            dob = c1.text_input("Date of Birth (YYYY-MM-DD)", value=curr_user['dob'] if curr_user['dob'] else "")
            gender = c2.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"], index=0 if not curr_user['gender'] else ["Male", "Female", "Other", "Prefer not to say"].index(curr_user['gender']))
            
            phone = c1.text_input("Phone", value=curr_user['phone'] if curr_user['phone'] else "")
            address = c2.text_area("Address", value=curr_user['address'] if curr_user['address'] else "")
            
            if st.form_submit_button("Save Changes"):
                query = "UPDATE users SET name=?, dob=?, gender=?, phone=?, address=?"
                params = [name, dob, gender, phone, address]
                
                if password:
                    query += ", password=?"
                    params.append(password)
                
                query += " WHERE id=?"
                params.append(user['id'])
                
                run_query(query, tuple(params))
                
                # Update Session
                st.session_state.user['name'] = name
                st.success("Profile updated successfully!")
                time.sleep(1)
                st.rerun()

def view_settings():
    st.title("⚙️ Settings")
    
    st.subheader("Appearance")
    
    # FEATURE 2 & 3: THEME SELECTOR
    selected_theme = st.selectbox("Select Application Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme))
    
    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme
        st.success("Theme updated! Reloading...")
        time.sleep(0.5)
        st.rerun()
    
    st.info(f"Current Theme: {st.session_state.theme}")
    
    st.markdown("---")
    st.caption("RoboLab Inventory System v2.0 | TSRS Edition")

# --- MAIN APP ---

def main():
    init_db()
    
    if 'user' not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        # LOGIN SCREEN - TSRS THEMED
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown(f"""
                <div class="login-box" style="text-align: center;">
                    <h1 style="color:{current_theme['primary']}; border:none;">TSRS</h1>
                    <h3 style="margin-top:-10px;">Robotics Lab</h3>
                    <p style="color:grey; font-size:14px; margin-bottom:20px;">Inventory Management Portal</p>
                </div>
            """, unsafe_allow_html=True)
            
            with st.form("login"):
                u = st.text_input("Employee ID")
                p = st.text_input("Password", type="password")
                
                if st.form_submit_button("Secure Login", type="primary", use_container_width=True):
                    user = login_user(u, p)
                    if user:
                        st.session_state.user = dict(user) # Convert Row to Dict
                        st.rerun()
                    else:
                        st.error("Access Denied")
            
            st.markdown("<div style='text-align:center; margin-top:20px; color:grey; font-size:12px;'>Authorized Personnel Only</div>", unsafe_allow_html=True)

    else:
        render_sidebar()
        
        # Routing
        page = st.session_state.current_view
        
        if page == "Dashboard": view_dashboard()
        elif page == "Inventory": view_inventory()
        elif page == "Stock Operations": view_stock_actions()
        elif page == "Reports": view_reports()
        elif page == "Shopping List": view_shopping_list()
        elif page == "User Management": view_users()
        elif page == "My Profile": view_profile()
        elif page == "Settings": view_settings()

if __name__ == '__main__':
    main()
