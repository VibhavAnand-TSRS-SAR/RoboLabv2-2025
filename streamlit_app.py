import streamlit as st
import pandas as pd
import sqlite3
import time
import json
import uuid
import base64
import io
import altair as alt
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="RoboLab Inventory System", page_icon="🤖", layout="wide")

# --- THEME & CSS ---
THEMES = {
    "TSRS (Red/Grey)": {
        "primary": "#A6192E",
        "secondary": "#58595B",
        "bg_sidebar": "#F3F4F6",
        "text_sidebar": "#1F2937",
        "hover": "#E5E7EB",
        "active": "#A6192E",
        "active_text": "#FFFFFF"
    },
    "Night Mode": {
        "primary": "#3B82F6",
        "secondary": "#9CA3AF",
        "bg_sidebar": "#111827",
        "text_sidebar": "#E5E7EB",
        "hover": "#374151",
        "active": "#1D4ED8",
        "active_text": "#FFFFFF"
    }
}

if 'theme' not in st.session_state:
    st.session_state.theme = "TSRS (Red/Grey)"

current_theme = THEMES[st.session_state.theme]

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}
    
    section[data-testid="stSidebar"] {{ background-color: {current_theme['bg_sidebar']}; }}
    
    div[data-testid="stMetric"] {{
        background-color: white; padding: 20px; border-radius: 12px;
        border-left: 5px solid {current_theme['primary']};
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    
    .login-card {{
        background: white; padding: 2.5rem; border-radius: 1.5rem;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        width: 100%; max-width: 450px; border-top: 8px solid {current_theme['primary']};
    }}
    .login-header {{ text-align: center; margin-bottom: 2rem; }}
    .login-header h1 {{ color: {current_theme['primary']}; font-weight: 800; font-size: 2.5rem; margin: 0; }}
    .login-header p {{ color: #6b7280; font-size: 0.95rem; margin-top: 0.5rem; }}
    
    .logo-icon {{
        font-size: 80px;
        color: {current_theme['primary']};
        margin-bottom: 20px;
    }}
    
    .footer {{
        position: fixed; bottom: 0; left: 0; width: 100%;
        background-color: white; text-align: center; padding: 10px;
        font-size: 12px; color: #9CA3AF; border-top: 1px solid #E5E7EB;
        z-index: 999;
    }}
    
    .activity-card {{
        background: #f9fafb; padding: 10px 15px; border-radius: 8px;
        margin-bottom: 8px; border-left: 4px solid {current_theme['primary']};
    }}
    
    .procurement-item {{
        background: white; padding: 15px; border-radius: 10px;
        border: 1px solid #e5e7eb; margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    
    .step-indicator {{
        display: flex; justify-content: center; gap: 10px; margin-bottom: 20px;
    }}
    .step {{
        padding: 10px 20px; border-radius: 20px; font-weight: 600;
        background: #e5e7eb; color: #6b7280;
    }}
    .step.active {{
        background: {current_theme['primary']}; color: white;
    }}
    .step.completed {{
        background: #10b981; color: white;
    }}
    
    .po-card {{
        background: white; padding: 15px; border-radius: 10px;
        border: 1px solid #e5e7eb; margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    
    .category-tag {{
        display: inline-block;
        padding: 5px 12px;
        margin: 3px;
        border-radius: 15px;
        background: #e5e7eb;
        font-size: 14px;
    }}
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)

# --- DATABASE ENGINE ---

def get_db_connection():
    conn = sqlite3.connect('robolab_v2.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Existing Tables
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 emp_id TEXT UNIQUE NOT NULL,
                 name TEXT NOT NULL,
                 password TEXT NOT NULL,
                 role TEXT NOT NULL,
                 dob TEXT, gender TEXT, address TEXT, phone TEXT,
                 profile_pic TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS roles (name TEXT PRIMARY KEY, permissions TEXT)''')
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
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, expires_at DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_name TEXT,
                 action TEXT,
                 details TEXT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_orders (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 po_number TEXT UNIQUE NOT NULL,
                 created_by TEXT,
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                 required_by DATE,
                 status TEXT DEFAULT 'Draft',
                 items_json TEXT,
                 total_items INTEGER,
                 mode TEXT,
                 justification TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT UNIQUE NOT NULL,
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # --- TABLES FOR KIT MANAGEMENT ---
    # added in_circulation to kits for Fix #4
    c.execute('''CREATE TABLE IF NOT EXISTS kits (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 kit_ref TEXT UNIQUE NOT NULL,
                 name TEXT NOT NULL,
                 description TEXT,
                 created_by TEXT,
                 in_circulation INTEGER DEFAULT 0,
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Migration: Add in_circulation if missing
    try:
        c.execute("SELECT in_circulation FROM kits LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE kits ADD COLUMN in_circulation INTEGER DEFAULT 0")
        conn.commit()

    c.execute('''CREATE TABLE IF NOT EXISTS kit_items (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 kit_id INTEGER,
                 item_name TEXT,
                 quantity INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS kit_history (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 kit_ref TEXT,
                 action TEXT,
                 user TEXT,
                 qty_changed INTEGER,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Migration for kit_history
    try:
        c.execute("SELECT qty_changed FROM kit_history LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE kit_history ADD COLUMN qty_changed INTEGER DEFAULT 1")
        conn.commit()

    # Seed Default Categories
    c.execute("SELECT count(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_categories = ["Sensors", "Motors", "Microcontrollers", "Power", "Tools", "Passive", "Others"]
        for cat in default_categories:
            c.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
        conn.commit()

    # Seed Roles
    c.execute("SELECT count(*) FROM roles")
    if c.fetchone()[0] == 0:
        all_perms = json.dumps(["Dashboard", "Inventory", "Stock Operations", "Kit Management", "Reports", "Procurement List", "User Management", "Audit Logs", "Settings"])
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ('admin', all_perms))
        asst_perms = json.dumps(["Dashboard", "Inventory", "Stock Operations", "Reports", "Procurement List"])
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ('assistant', asst_perms))
        teach_perms = json.dumps(["Dashboard", "Inventory", "Stock Operations", "Kit Management", "Reports"])
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ('teacher', teach_perms))
        conn.commit()
    else:
        # Check permissions
        c.execute("SELECT name, permissions FROM roles")
        roles = c.fetchall()
        for role in roles:
            perms = json.loads(role[1])
            if role[0] in ['admin', 'teacher'] and "Kit Management" not in perms:
                perms.append("Kit Management")
                c.execute("UPDATE roles SET permissions = ? WHERE name = ?", (json.dumps(perms), role[0]))
        conn.commit()

    # Seed Users
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)", ('admin', 'System Admin', 'admin123', 'admin'))
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)", ('assistant', 'Lab Assistant', '123', 'assistant'))
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)", ('teacher', 'Physics Teacher', '123', 'teacher'))
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
            return [dict(row) for row in data]
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False

def log_activity(action, details):
    if 'user' in st.session_state and st.session_state.user:
        run_query("INSERT INTO activity_logs (user_name, action, details) VALUES (?, ?, ?)", 
                  (st.session_state.user['name'], action, details))

def get_image_base64(image_file):
    if image_file is not None:
        return base64.b64encode(image_file.read()).decode()
    return None

def image_from_base64(base64_str):
    if base64_str:
        return f"data:image/png;base64,{base64_str}"
    return "https://www.w3schools.com/howto/img_avatar.png"

def create_session(user_id):
    token = str(uuid.uuid4())
    expiry = datetime.now() + timedelta(minutes=5)
    run_query("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expiry))
    return token

def validate_session(token):
    run_query("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(),))
    data = run_query("SELECT user_id FROM sessions WHERE token = ? AND expires_at > ?", (token, datetime.now()), fetch=True)
    if data:
        run_query("UPDATE sessions SET expires_at = ? WHERE token = ?", (datetime.now() + timedelta(minutes=5), token))
        return run_query("SELECT * FROM users WHERE id = ?", (data[0]['user_id'],), fetch=True)[0]
    return None

def logout_user():
    if 'session_token' in st.query_params:
        run_query("DELETE FROM sessions WHERE token = ?", (st.query_params['session_token'],))
    st.query_params.clear()
    st.session_state.user = None
    st.rerun()

def generate_po_number():
    now = datetime.now()
    if now.month >= 4:
        academic_year = f"{now.year}-{str(now.year + 1)[2:]}"
    else:
        academic_year = f"{now.year - 1}-{str(now.year)[2:]}"
    
    if now.month >= 4:
        start_date = datetime(now.year, 4, 1)
    else:
        start_date = datetime(now.year - 1, 4, 1)
    
    existing = run_query("SELECT COUNT(*) as cnt FROM purchase_orders WHERE created_at >= ?", (start_date,), fetch=True)
    count = existing[0]['cnt'] + 1 if existing else 1
    return f"TSRS/RoboLab/PO/{academic_year}/PO{count:04d}"

def generate_kit_ref():
    now = datetime.now()
    if now.month >= 4:
        academic_year = f"{now.year}-{str(now.year + 1)[2:]}"
    else:
        academic_year = f"{now.year - 1}-{str(now.year)[2:]}"
    existing = run_query("SELECT COUNT(*) as cnt FROM kits", fetch=True)
    count = existing[0]['cnt'] + 1 if existing else 1
    return f"TSRS/RoboLab/KIT/{academic_year}/{count:03d}"

def get_categories():
    cats = run_query("SELECT name FROM categories ORDER BY name", fetch=True)
    return [c['name'] for c in cats] if cats else ["Others"]

def add_category(name):
    if name and name.strip():
        run_query("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name.strip(),))

def add_categories_from_list(category_list):
    added = 0
    for cat in category_list:
        if cat and str(cat).strip() and str(cat).lower() != 'nan':
            if run_query("INSERT OR IGNORE INTO categories (name) VALUES (?)", (str(cat).strip(),)):
                added += 1
    return added

# --- VIEWS ---

def view_dashboard():
    role = st.session_state.user['role']
    
    if role == 'admin':
        st.title("📊 Master Dashboard")
        df = pd.read_sql_query("SELECT * FROM inventory", get_db_connection())
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Items", int(df['quantity'].sum()) if not df.empty else 0)
        c2.metric("Inventory Value", f"₹{(df['quantity'] * df['price']).sum():,.0f}" if not df.empty else "₹0")
        c3.metric("Alerts", len(df[df['quantity'] <= df['min_stock']]) if not df.empty else 0)
        c4.metric("Categories", df['category'].nunique() if not df.empty else 0)
        
        col_chart, col_recent = st.columns([2, 1])
        with col_chart:
            st.subheader("Category Breakdown")
            if not df.empty:
                chart_data = df.groupby('category')['quantity'].sum().reset_index()
                chart = alt.Chart(chart_data).mark_arc(innerRadius=60).encode(
                    theta='quantity', color='category', tooltip=['category', 'quantity']
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No data available")
            
        with col_recent:
            st.subheader("System Logs")
            logs = pd.read_sql_query("SELECT user_name, action, timestamp FROM activity_logs ORDER BY timestamp DESC LIMIT 5", get_db_connection())
            st.dataframe(logs, use_container_width=True, hide_index=True)
    else:
        st.title(f"👋 Welcome, {st.session_state.user['name']}")
        conn = get_db_connection()
        my_trans = pd.read_sql_query("SELECT * FROM transactions WHERE user = ? ORDER BY timestamp DESC", conn, params=(st.session_state.user['name'],))
        conn.close()
        
        c1, c2 = st.columns(2)
        c1.metric("My Transactions", len(my_trans))
        last_active = my_trans.iloc[0]['timestamp'] if not my_trans.empty else "N/A"
        c2.metric("Last Active", str(last_active)[:10])
        
        st.subheader("My Recent Activity")
        if not my_trans.empty:
            st.dataframe(my_trans[['timestamp', 'type', 'item_name', 'quantity', 'notes']].head(10), use_container_width=True)
        else:
            st.info("No activity yet.")

def view_audit_logs():
    st.title("🛡️ Audit Logs")
    df = pd.read_sql_query("SELECT timestamp, user_name, action, details FROM activity_logs ORDER BY timestamp DESC", get_db_connection())
    st.dataframe(df, use_container_width=True)

def view_reports():
    st.title("📑 Reports")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    
    if df.empty:
        st.warning("No transaction data available.")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['year'] = df['timestamp'].dt.year
    df['month_num'] = df['timestamp'].dt.month
    
    years = sorted(df['year'].unique(), reverse=True)
    
    for year in years:
        with st.expander(f"📂 Year: {year}", expanded=(year==max(years))):
            year_data = df[df['year'] == year]
            
            # FIX 2: Preview for Reports
            st.write("👁️ **Preview Data (Annual)**")
            st.dataframe(year_data.head(50), use_container_width=True, height=200)
            
            buffer_annual = io.BytesIO()
            year_data.to_excel(buffer_annual, index=False, engine='openpyxl')
            buffer_annual.seek(0)
            
            col_main, col_months = st.columns([1, 3])
            with col_main:
                st.download_button(f"📥 Annual {year}", buffer_annual, f"Annual_{year}.xlsx")
            with col_months:
                st.write("**Monthly Reports:**")
                months_in_year = sorted(year_data['month_num'].unique(), reverse=True)
                cols = st.columns(4)
                for i, m_num in enumerate(months_in_year):
                    month_name = datetime(2000, m_num, 1).strftime('%B')
                    month_data = year_data[year_data['month_num'] == m_num]
                    buff = io.BytesIO()
                    month_data.to_excel(buff, index=False, engine='openpyxl')
                    buff.seek(0)
                    cols[i%4].download_button(f"📄 {month_name}", buff, f"{year}_{month_name}.xlsx")

def view_profile():
    st.title("👤 My Profile")
    user = st.session_state.user
    
    col_img, col_form = st.columns([1, 2])
    with col_img:
        img_src = image_from_base64(user.get('profile_pic'))
        st.markdown(f"<div style='text-align:center;'><img src='{img_src}' style='width:150px; height:150px; object-fit:cover; border-radius:50%; border: 4px solid {current_theme['primary']};'></div>", unsafe_allow_html=True)
        new_pic = st.file_uploader("Change Photo", type=['png', 'jpg', 'jpeg'])
        if new_pic:
            b64_pic = get_image_base64(new_pic)
            run_query("UPDATE users SET profile_pic = ? WHERE id = ?", (b64_pic, user['id']))
            st.session_state.user['profile_pic'] = b64_pic
            log_activity("Profile Update", "Changed profile picture")
            st.rerun()

    with col_form:
        with st.form("profile_edit"):
            st.subheader("Basic Details")
            c1, c2 = st.columns(2)
            curr = run_query("SELECT * FROM users WHERE id=?", (user['id'],), fetch=True)[0]
            name = c1.text_input("Full Name", value=curr['name'])
            password = c2.text_input("New Password (Optional)", type="password")
            dob_val = None
            if curr.get('dob'):
                try: dob_val = datetime.strptime(curr['dob'], '%Y-%m-%d')
                except: dob_val = None
            dob = c1.date_input("Date of Birth", value=dob_val)
            gender_options = ["Male", "Female", "Other"]
            gender_idx = gender_options.index(curr['gender']) if curr.get('gender') in gender_options else 0
            gender = c2.selectbox("Gender", gender_options, index=gender_idx)
            phone = c1.text_input("Phone", value=curr.get('phone') or "")
            address = c2.text_area("Address", value=curr.get('address') or "")
            
            if st.form_submit_button("Save Changes"):
                q = "UPDATE users SET name=?, dob=?, gender=?, phone=?, address=?"
                p = [name, str(dob), gender, phone, address]
                if password:
                    q += ", password=?"
                    p.append(password)
                q += " WHERE id=?"
                p.append(user['id'])
                run_query(q, tuple(p))
                st.session_state.user['name'] = name
                log_activity("Profile Update", "Updated personal details")
                st.success("Profile Updated")
                time.sleep(1)
                st.rerun()

def landing_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
            <div class="login-card">
                <div class="login-header">
                    <i class="fa-solid fa-robot logo-icon"></i>
                    <h1>TSRS</h1>
                    <p>Robotics Lab Inventory System</p>
                </div>
            </div>
        """, unsafe_allow_html=True)
        with st.form("login_form"):
            st.markdown("### Secure Sign In")
            u = st.text_input("Employee ID", placeholder="e.g. admin")
            p = st.text_input("Password", type="password", placeholder="•••••••")
            if st.form_submit_button("Login", type="primary", use_container_width=True):
                user = run_query("SELECT * FROM users WHERE emp_id = ? AND password = ?", (u, p), fetch=True)
                if user:
                    user_data = user[0]
                    st.session_state.user = dict(user_data)
                    token = create_session(user_data['id'])
                    st.query_params['session_token'] = token
                    log_activity("Login", "User logged in")
                    st.rerun()
                else:
                    st.error("Invalid Credentials")
    st.markdown("<div class='footer'>Created by <b>Blackquest</b></div>", unsafe_allow_html=True)

def view_inventory():
    st.title("📦 Inventory Management")
    tab1, tab2, tab3, tab4 = st.tabs(["🔎 View", "➕ Add Item", "📂 Bulk Upload", "🏷️ Manage Categories"])
    categories = get_categories()
    
    with tab1:
        df = pd.read_sql_query("SELECT * FROM inventory", get_db_connection())
        col_filter, col_search = st.columns([1, 2])
        with col_filter:
            filter_cat = st.selectbox("Filter by Category", ["All"] + categories, key="filter_cat")
        with col_search:
            search_term = st.text_input("Search Items", placeholder="Type to search...")
        
        if not df.empty:
            if filter_cat != "All": df = df[df['category'] == filter_cat]
            if search_term: df = df[df['name'].str.contains(search_term, case=False, na=False)]
        
        st.dataframe(df, use_container_width=True)
        if st.session_state.user['role'] == 'admin' and not df.empty:
            with st.expander("🗑️ Delete Item"):
                del_name = st.selectbox("Select Item", df['name'].tolist())
                if st.button("Delete"):
                    run_query("DELETE FROM inventory WHERE name = ?", (del_name,))
                    log_activity("Delete", f"Deleted {del_name}")
                    st.rerun()

    with tab2:
        with st.form("add_i"):
            n = st.text_input("Name")
            c = st.selectbox("Category", categories)
            q = st.number_input("Quantity", 0)
            ms = st.number_input("Min Stock", 5)
            p = st.number_input("Price", 0.0)
            l = st.text_input("Location", "Bin A")
            if st.form_submit_button("Add Item"):
                run_query("INSERT INTO inventory (name, category, quantity, min_stock, price, location) VALUES (?,?,?,?,?,?)", (n,c,q,ms,p,l))
                log_activity("Inventory", f"Added item {n}")
                st.success("Added!")
                st.rerun()

    with tab3:
        st.markdown("**Upload Excel (.xlsx)**")
        uploaded_file = st.file_uploader("Choose File", type=['xlsx'])
        if uploaded_file:
            df_upload = pd.read_excel(uploaded_file)
            st.dataframe(df_upload.head())
            if st.button("Confirm Import"):
                count = 0; new_categories = set()
                for _, row in df_upload.iterrows():
                    row_lower = {k.lower(): v for k, v in row.items()}
                    if 'name' in row_lower and pd.notna(row_lower['name']):
                        cat = row_lower.get('category', 'Others')
                        new_categories.add(str(cat))
                        run_query("INSERT INTO inventory (name, category, quantity, min_stock, price, location) VALUES (?,?,?,?,?,?)", 
                                  (row_lower['name'], cat, row_lower.get('quantity', 0), row_lower.get('min_stock', 5), row_lower.get('price', 0.0), row_lower.get('location', 'Unknown')))
                        count += 1
                add_categories_from_list(new_categories)
                log_activity("Bulk Upload", f"Imported {count} items")
                st.success(f"Imported {count} items!")
                st.rerun()

    with tab4:
        st.subheader("🏷️ Category Management")
        current_cats = get_categories()
        tags_html = "".join([f"<span class='category-tag'>{cat}</span>" for cat in current_cats])
        st.markdown(f"<div>{tags_html}</div>", unsafe_allow_html=True)
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col1: new_cat = st.text_input("New Category Name")
        with col2:
            st.write(""); st.write("")
            if st.button("➕ Add Category", use_container_width=True):
                if new_cat:
                    add_category(new_cat)
                    st.success("Added"); st.rerun()
        if st.session_state.user['role'] == 'admin':
            with st.expander("🗑️ Delete Category"):
                del_cat = st.selectbox("Select Category", current_cats)
                if st.button("Delete Category"):
                    run_query("DELETE FROM categories WHERE name = ?", (del_cat,))
                    st.rerun()

# --- KIT MANAGEMENT (REVAMPED FIX 3 & 4) ---
def view_kit_management():
    st.title("🧰 Kit Management")
    
    if 'kit_temp_items' not in st.session_state:
        st.session_state.kit_temp_items = []
        
    tab_create, tab_manage, tab_ops, tab_history = st.tabs(["➕ Create Kit", "📋 Manage Kits", "🔄 Kit Operations", "📜 History"])
    
    # 1. CREATE KIT
    with tab_create:
        st.subheader("Create New Activity Kit")
        col1, col2 = st.columns(2)
        with col1:
            kit_name = st.text_input("Activity Name")
            kit_desc = st.text_area("Description/Instructions")
        
        st.markdown("**Add Items to Kit**")
        df_inv = pd.read_sql_query("SELECT name, quantity, price FROM inventory", get_db_connection())
        
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            item_sel = st.selectbox("Select Item", df_inv['name'].tolist() if not df_inv.empty else [])
        with c2:
            qty_sel = st.number_input("Quantity needed per kit", min_value=1, value=1)
        with c3:
            st.write(""); st.write("")
            if st.button("Add to List"):
                if item_sel:
                    curr_price = df_inv[df_inv['name'] == item_sel]['price'].values[0]
                    st.session_state.kit_temp_items.append({"item": item_sel, "qty": qty_sel, "unit_price": curr_price})
        
        if st.session_state.kit_temp_items:
            temp_df = pd.DataFrame(st.session_state.kit_temp_items)
            temp_df['Total Cost'] = temp_df['qty'] * temp_df['unit_price']
            st.dataframe(temp_df, use_container_width=True)
            total_kit_cost = temp_df['Total Cost'].sum()
            st.metric("Estimated Cost per Kit", f"₹{total_kit_cost:,.2f}")
            
            if st.button("💾 Save Kit Configuration", type="primary"):
                if kit_name:
                    ref_no = generate_kit_ref()
                    run_query("INSERT INTO kits (kit_ref, name, description, created_by) VALUES (?, ?, ?, ?)", 
                              (ref_no, kit_name, kit_desc, st.session_state.user['name']))
                    kit_id = run_query("SELECT id FROM kits WHERE kit_ref = ?", (ref_no,), fetch=True)[0]['id']
                    for row in st.session_state.kit_temp_items:
                        run_query("INSERT INTO kit_items (kit_id, item_name, quantity) VALUES (?, ?, ?)", 
                                  (kit_id, row['item'], row['qty']))
                    log_activity("Kit Created", f"Created kit {kit_name} ({ref_no})")
                    st.session_state.kit_temp_items = []
                    st.success(f"Kit Created! Ref: {ref_no}"); time.sleep(1); st.rerun()
                else: st.error("Kit Name is required")
            if st.button("Clear List"): st.session_state.kit_temp_items = []; st.rerun()

    # 2. MANAGE KITS
    with tab_manage:
        kits = run_query("SELECT * FROM kits", fetch=True)
        if not kits: st.info("No kits created yet.")
        else:
            for k in kits:
                with st.expander(f"📦 {k['name']} ({k['kit_ref']})"):
                    st.write(f"**Description:** {k['description']}")
                    st.write(f"**Currently Issued:** {k['in_circulation']}")
                    k_items = run_query("SELECT item_name, quantity FROM kit_items WHERE kit_id = ?", (k['id'],), fetch=True)
                    k_df = pd.DataFrame(k_items)
                    if not k_df.empty:
                        inv_prices = df_inv.set_index('name')['price'].to_dict()
                        k_df['Current Unit Price'] = k_df['item_name'].map(inv_prices).fillna(0)
                        k_df['Subtotal'] = k_df['quantity'] * k_df['Current Unit Price']
                        st.dataframe(k_df, use_container_width=True)
                        st.metric("Current Cost to Build", f"₹{k_df['Subtotal'].sum():,.2f}")
                    if st.button(f"Delete {k['kit_ref']}", key=f"del_kit_{k['id']}"):
                        run_query("DELETE FROM kit_items WHERE kit_id = ?", (k['id'],))
                        run_query("DELETE FROM kits WHERE id = ?", (k['id'],))
                        log_activity("Kit Deleted", f"Deleted kit {k['kit_ref']}")
                        st.rerun()

    # 3. KIT OPERATIONS (FIX 3 & 4)
    with tab_ops:
        st.subheader("Issue or Return Kits")
        kit_opts = [f"{k['name']} ({k['kit_ref']})" for k in kits] if kits else []
        sel_kit_str = st.selectbox("Select Kit", kit_opts)
        
        if sel_kit_str:
            kit_ref = sel_kit_str.split('(')[1].replace(')', '')
            kit_data = run_query("SELECT * FROM kits WHERE kit_ref = ?", (kit_ref,), fetch=True)[0]
            kit_items = run_query("SELECT item_name, quantity FROM kit_items WHERE kit_id = ?", (kit_data['id'],), fetch=True)
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 📤 Issue Kit (Stock Out)")
                num_kits_issue = st.number_input("Number of Kits to Issue", min_value=1, value=1, key="iss_qty")
                issue_note = st.text_input("Reason / Student Name", key="k_out_note")
                
                if st.button("Issue Kits", type="primary"):
                    possible = True; missing = []
                    curr_inv = pd.read_sql_query("SELECT name, quantity FROM inventory", get_db_connection()).set_index('name')['quantity'].to_dict()
                    
                    # Check Inventory for ALL kits
                    for i in kit_items:
                        needed = i['quantity'] * num_kits_issue
                        avail = curr_inv.get(i['item_name'], 0)
                        if avail < needed:
                            possible = False; missing.append(f"{i['item_name']} (Need {needed}, Have {avail})")
                    
                    if possible:
                        for i in kit_items:
                            deduct = i['quantity'] * num_kits_issue
                            run_query("UPDATE inventory SET quantity = quantity - ? WHERE name = ?", (deduct, i['item_name']))
                            run_query("INSERT INTO transactions (item_name, type, quantity, user, notes) VALUES (?,?,?,?,?)",
                                      (i['item_name'], 'out', deduct, st.session_state.user['name'], f"Kit Issue: {num_kits_issue}x {kit_ref} - {issue_note}"))
                        
                        run_query("UPDATE kits SET in_circulation = in_circulation + ? WHERE id = ?", (num_kits_issue, kit_data['id']))
                        run_query("INSERT INTO kit_history (kit_ref, action, user, qty_changed) VALUES (?, ?, ?, ?)", (kit_ref, 'Issue', st.session_state.user['name'], num_kits_issue))
                        st.success(f"Issued {num_kits_issue} kits successfully!")
                        time.sleep(1); st.rerun()
                    else: st.error(f"Cannot issue. Missing: {', '.join(missing)}")

            with c2:
                st.markdown("#### 📥 Return Kit (Stock In)")
                st.info(f"Kits currently issued: {kit_data['in_circulation']}")
                num_kits_return = st.number_input("Number of Kits to Return", min_value=1, value=1, key="ret_qty")
                return_note = st.text_input("Return Note", key="k_in_note")
                
                if st.button("Return Kits"):
                    if num_kits_return > kit_data['in_circulation']:
                        st.error(f"Error: You are trying to return {num_kits_return} kits, but only {kit_data['in_circulation']} are issued.")
                    else:
                        for i in kit_items:
                            add_back = i['quantity'] * num_kits_return
                            run_query("UPDATE inventory SET quantity = quantity + ? WHERE name = ?", (add_back, i['item_name']))
                            run_query("INSERT INTO transactions (item_name, type, quantity, user, notes) VALUES (?,?,?,?,?)",
                                      (i['item_name'], 'in', add_back, st.session_state.user['name'], f"Kit Return: {num_kits_return}x {kit_ref} - {return_note}"))
                        
                        run_query("UPDATE kits SET in_circulation = in_circulation - ? WHERE id = ?", (num_kits_return, kit_data['id']))
                        run_query("INSERT INTO kit_history (kit_ref, action, user, qty_changed) VALUES (?, ?, ?, ?)", (kit_ref, 'Return', st.session_state.user['name'], num_kits_return))
                        st.success("Kits returned to inventory.")
                        time.sleep(1); st.rerun()

    with tab_history:
        st.subheader("Kit Usage Log")
        hist = pd.read_sql_query("SELECT timestamp, kit_ref, action, qty_changed, user FROM kit_history ORDER BY timestamp DESC", get_db_connection())
        st.dataframe(hist, use_container_width=True)

# --- REVAMPED STOCK OPERATIONS (WEIGHTED AVG) ---
def view_stock_ops():
    st.title("🔄 Stock Operations")
    
    df = pd.read_sql_query("SELECT * FROM inventory", get_db_connection())
    if df.empty:
        st.warning("No items in inventory.")
        return
    
    col_in, col_out = st.columns(2)
    
    with col_in:
        st.markdown(f"<div style='background:#ecfdf5; padding:20px; border-radius:12px; border:2px solid #10b981;'>", unsafe_allow_html=True)
        st.subheader("📥 Stock In (Restock)")
        with st.form("stock_in_form"):
            item_in = st.selectbox("Select Item", df['name'].tolist(), key="in_item")
            qty_in = st.number_input("Quantity to Add", min_value=1, value=1, key="in_qty")
            new_price = st.number_input("Unit Price of New Batch (₹)", min_value=0.0, value=0.0, step=1.0)
            notes_in = st.text_input("Notes (e.g., Purchase Order #)", key="in_notes")
            
            if st.form_submit_button("➕ Add Stock", use_container_width=True):
                curr_item = df[df['name'] == item_in].iloc[0]
                curr_qty = curr_item['quantity']; curr_price = curr_item['price']
                total_val = (curr_qty * curr_price) + (qty_in * new_price)
                total_qty = curr_qty + qty_in
                avg_price = total_val / total_qty if total_qty > 0 else 0
                run_query("UPDATE inventory SET quantity = ?, price = ? WHERE name = ?", (total_qty, avg_price, item_in))
                run_query("INSERT INTO transactions (item_name, type, quantity, user, notes) VALUES (?,?,?,?,?)", 
                          (item_in, 'in', qty_in, st.session_state.user['name'], notes_in))
                log_activity("Stock In", f"Added {qty_in} to {item_in} @ ₹{new_price}")
                st.success(f"Added {qty_in}. New Avg Price: ₹{avg_price:.2f}"); time.sleep(1); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_out:
        st.markdown(f"<div style='background:#fef2f2; padding:20px; border-radius:12px; border:2px solid #ef4444;'>", unsafe_allow_html=True)
        st.subheader("📤 Stock Out")
        with st.form("stock_out_form"):
            item_out = st.selectbox("Select Item", df['name'].tolist(), key="out_item")
            qty_out = st.number_input("Quantity to Remove", min_value=1, value=1, key="out_qty")
            notes_out = st.text_input("Notes (e.g., Project Name)", key="out_notes")
            if st.form_submit_button("➖ Remove Stock", use_container_width=True):
                current_qty = df[df['name'] == item_out]['quantity'].values[0]
                if qty_out > current_qty: st.error(f"Insufficient stock! Available: {current_qty}")
                else:
                    run_query("UPDATE inventory SET quantity = quantity - ? WHERE name = ?", (qty_out, item_out))
                    run_query("INSERT INTO transactions (item_name, type, quantity, user, notes) VALUES (?,?,?,?,?)", 
                              (item_out, 'out', qty_out, st.session_state.user['name'], notes_out))
                    log_activity("Stock Out", f"Removed {qty_out} from {item_out}")
                    st.success(f"Removed {qty_out}"); time.sleep(1); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📋 Recent Stock Activity")
    recent_trans = pd.read_sql_query("SELECT timestamp, item_name, type, quantity, user, notes FROM transactions ORDER BY timestamp DESC LIMIT 10", get_db_connection())
    if recent_trans.empty: st.info("No transactions recorded yet.")
    else:
        for _, row in recent_trans.iterrows():
            icon = "📥" if row['type'] == 'in' else "📤"
            color = "#10b981" if row['type'] == 'in' else "#ef4444"
            action = "Added" if row['type'] == 'in' else "Removed"
            st.markdown(f"""
                <div class="activity-card" style="border-left-color: {color};">
                    <strong>{icon} {action} {row['quantity']} × {row['item_name']}</strong><br>
                    <small style="color:#6b7280;">By {row['user']} | {row['timestamp']}</small>
                    {f"<br><small style='color:#9ca3af;'>Note: {row['notes']}</small>" if row['notes'] else ""}
                </div>
            """, unsafe_allow_html=True)

# --- PROCUREMENT LIST ---
def view_procurement():
    st.title("🛒 Procurement List")
    
    if 'procurement_step' not in st.session_state: st.session_state.procurement_step = 1
    if 'selected_items' not in st.session_state: st.session_state.selected_items = []
    if 'procurement_details' not in st.session_state: st.session_state.procurement_details = {}
    if 'global_justification' not in st.session_state: st.session_state.global_justification = ""
    if 'item_justifications' not in st.session_state: st.session_state.item_justifications = {}
    
    tab_new, tab_history = st.tabs(["📝 New Request", "📋 Purchase Order History"])
    
    with tab_new:
        step = st.session_state.procurement_step
        st.markdown(f"""
            <div class="step-indicator">
                <div class="step {'completed' if step > 1 else 'active' if step == 1 else ''}">1. Select</div>
                <div class="step {'completed' if step > 2 else 'active' if step == 2 else ''}">2. Details</div>
                <div class="step {'completed' if step > 3 else 'active' if step == 3 else ''}">3. Preview</div>
                <div class="step {'active' if step == 4 else ''}">4. Download</div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        
        if step == 1:
            st.subheader("Step 1: Select Items")
            df = pd.read_sql_query("SELECT * FROM inventory WHERE quantity < min_stock", get_db_connection())
            if df.empty: st.success("✅ All items are well-stocked!"); return
            st.warning(f"⚠️ {len(df)} items are below minimum stock level.")
            select_all = st.checkbox("Select All Items")
            selected = []
            for idx, row in df.iterrows():
                shortage = row['min_stock'] - row['quantity']
                c1, c2, c3, c4 = st.columns([0.5, 3, 1, 1])
                with c1: checked = st.checkbox("", value=select_all, key=f"check_{idx}")
                with c2: st.write(f"**{row['name']}** ({row['category']})")
                with c3: st.write(f"Stock: {row['quantity']}")
                with c4: st.write(f"🔴 Need: {shortage}")
                if checked:
                    selected.append({'id': row['id'], 'name': row['name'], 'category': row['category'], 'current_stock': row['quantity'], 'min_stock': row['min_stock'], 'shortage': shortage, 'price': row['price']})
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Proceed ➡️", type="primary", use_container_width=True):
                    if len(selected) > 0:
                        st.session_state.selected_items = selected
                        # Initialize only if not present to avoid overwrite on back
                        for item in selected:
                            if item['name'] not in st.session_state.item_justifications:
                                st.session_state.item_justifications[item['name']] = ""
                        st.session_state.procurement_step = 2; st.rerun()
                    else: st.error("Select at least one item.")
        
        elif step == 2:
            st.subheader("Step 2: Fill Details")
            selected_items = st.session_state.selected_items
            c1, c2 = st.columns(2)
            with c1: requested_by = st.text_input("Requested By", value=st.session_state.user['name'])
            with c2: required_by = st.date_input("Required By", value=datetime.now() + timedelta(days=7))
            c1, c2 = st.columns(2)
            with c1: mode = st.selectbox("Purchase Mode", ["Online", "Offline"])
            with c2: default_link = st.text_input("Default Link (Optional)") if mode == "Online" else ""
            
            st.markdown("### 📝 Justification")
            # FIX 1: Apply to all persistence
            global_val = st.text_area("Common Justification", value=st.session_state.global_justification, key="g_just")
            if st.button("✅ Apply to All", type="secondary"):
                st.session_state.global_justification = global_val
                for item in selected_items:
                    st.session_state.item_justifications[item['name']] = global_val
                st.rerun()
            
            item_details = []
            for idx, item in enumerate(selected_items):
                with st.expander(f"📦 {item['name']}", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1: qty = st.number_input(f"Quantity", min_value=1, value=int(item['shortage']), key=f"qty_{idx}")
                    with c2: link = st.text_input("Link", value=default_link, key=f"link_{idx}") if mode == "Online" else "N/A"
                    # Read from session state dictionary
                    curr_j = st.session_state.item_justifications.get(item['name'], "")
                    just = st.text_area("Justification", value=curr_j, key=f"just_{idx}", height=80)
                    # Update back to session state manually to ensure it saves
                    st.session_state.item_justifications[item['name']] = just
                    
                    item_details.append({'Item Name': item['name'], 'Category': item['category'], 'Current Stock': item['current_stock'], 'Min Stock': item['min_stock'], 'Quantity Requested': qty, 'Unit Price': item['price'], 'Estimated Cost': qty * item['price'], 'Justification': just, 'Mode': mode, 'Purchase Link': link})
            
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button("⬅️ Back"): st.session_state.procurement_step = 1; st.rerun()
            with c3:
                if st.button("Preview ➡️", type="primary"):
                    st.session_state.procurement_details = {'requested_by': requested_by, 'required_by': str(required_by), 'mode': mode, 'items': item_details}
                    st.session_state.procurement_step = 3; st.rerun()
        
        elif step == 3:
            st.subheader("Step 3: Preview")
            details = st.session_state.procurement_details
            st.write(f"**Requested By:** {details['requested_by']} | **Required By:** {details['required_by']} | **Mode:** {details['mode']}")
            st.dataframe(pd.DataFrame(details['items']), use_container_width=True)
            st.metric("Total Cost", f"₹{sum([i['Estimated Cost'] for i in details['items']]):,.2f}")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button("⬅️ Edit"): st.session_state.procurement_step = 2; st.rerun()
            with c3:
                if st.button("Generate PO ➡️", type="primary"):
                    po = generate_po_number()
                    run_query("INSERT INTO purchase_orders (po_number, created_by, required_by, status, items_json, total_items, mode, justification) VALUES (?,?,?,?,?,?,?,?)", (po, details['requested_by'], details['required_by'], 'Generated', json.dumps(details['items']), len(details['items']), details['mode'], details['items'][0]['Justification'] if details['items'] else ''))
                    log_activity("Procurement", f"Generated PO: {po}")
                    st.session_state.generated_po = po
                    st.session_state.procurement_step = 4
                    st.rerun()
        
        elif step == 4:
            st.subheader("Step 4: Download")
            po = st.session_state.get('generated_po', 'N/A')
            st.success("✅ PO Generated!")
            st.markdown(f"<div class='po-card' style='text-align:center'><h2>{po}</h2></div>", unsafe_allow_html=True)
            
            items_df = pd.DataFrame(st.session_state.procurement_details['items'])
            items_df.insert(0, 'PO Number', po)
            items_df['Requested By'] = st.session_state.procurement_details['requested_by']
            items_df['Required By'] = st.session_state.procurement_details['required_by']
            
            buff = io.BytesIO()
            items_df.to_excel(buff, index=False, engine='openpyxl')
            buff.seek(0)
            
            st.download_button("📥 Download Excel", buff, f"{po.replace('/','_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            if st.button("🔄 New Request"):
                st.session_state.procurement_step = 1
                st.session_state.selected_items = []
                st.session_state.procurement_details = {}
                st.session_state.global_justification = ""
                st.session_state.item_justifications = {}
                st.rerun()

    with tab_history:
        st.subheader("📋 History")
        pos = run_query("SELECT * FROM purchase_orders ORDER BY created_at DESC", fetch=True)
        if not pos: st.info("No POs yet.")
        else:
            for po in pos:
                with st.expander(f"📄 {po['po_number']} - {po['status']}"):
                    st.write(f"**Created By:** {po['created_by']} | **Date:** {po['created_at'][:10]}")
                    if po['items_json']:
                        idf = pd.DataFrame(json.loads(po['items_json']))
                        st.dataframe(idf, use_container_width=True)
                        buff = io.BytesIO()
                        idf.to_excel(buff, index=False, engine='openpyxl'); buff.seek(0)
                        c1, c2 = st.columns([1, 1])
                        c1.download_button("📥 Re-download", buff, f"{po['po_number'].replace('/','_')}.xlsx", key=f"dl_{po['id']}")
                        if c2.button("🗑️ Delete", key=f"del_{po['id']}"):
                            run_query("DELETE FROM purchase_orders WHERE id = ?", (po['id'],))
                            st.success("Deleted"); time.sleep(1); st.rerun()

def view_users():
    st.title("👥 User & Role Management")
    t1, t2 = st.tabs(["👤 Users", "🔐 Roles"])
    with t1:
        st.dataframe(pd.read_sql_query("SELECT emp_id, name, role FROM users", get_db_connection()), use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            with st.expander("➕ Add User"):
                with st.form("u_add"):
                    uid = st.text_input("ID"); name = st.text_input("Name"); pwd = st.text_input("Pass", type="password")
                    role = st.selectbox("Role", [r['name'] for r in run_query("SELECT name FROM roles", fetch=True)])
                    if st.form_submit_button("Create"):
                        if run_query("INSERT INTO users (emp_id, name, password, role) VALUES (?,?,?,?)", (uid, name, pwd, role)):
                            st.success("Created"); st.rerun()
                        else: st.error("ID Exists")
        with c2:
            with st.expander("✏️ Edit User"):
                u_sel = st.selectbox("Select", [u['emp_id'] for u in run_query("SELECT emp_id FROM users", fetch=True)])
                if u_sel:
                    curr = run_query("SELECT * FROM users WHERE emp_id=?", (u_sel,), fetch=True)[0]
                    with st.form("u_edit"):
                        en = st.text_input("Name", curr['name']); er = st.selectbox("Role", [r['name'] for r in run_query("SELECT name FROM roles", fetch=True)], index=0)
                        ep = st.text_input("New Pass (Opt)", type="password")
                        if st.form_submit_button("Update"):
                            q = "UPDATE users SET name=?, role=?"; p = [en, er]
                            if ep: q+=", password=?"; p.append(ep)
                            q+=" WHERE emp_id=?"; p.append(u_sel)
                            run_query(q, tuple(p)); st.success("Updated"); st.rerun()
    with t2:
        roles = run_query("SELECT * FROM roles", fetch=True)
        for r in roles:
            with st.expander(f"🔑 {r['name'].upper()}"):
                with st.form(f"r_{r['name']}"):
                    perms = json.loads(r['permissions'])
                    new_p = []
                    cols = st.columns(4)
                    pages = ["Dashboard", "Inventory", "Stock Operations", "Kit Management", "Reports", "Procurement List", "User Management", "Audit Logs", "Settings"]
                    for i, page in enumerate(pages):
                        if cols[i%4].checkbox(page, page in perms, key=f"{r['name']}_{page}"): new_p.append(page)
                    if st.form_submit_button("Save"):
                        run_query("UPDATE roles SET permissions=? WHERE name=?", (json.dumps(new_p), r['name'])); st.success("Saved"); st.rerun()
        st.markdown("---")
        with st.form("new_role"):
            nr = st.text_input("New Role Name").lower().replace(" ","_")
            if st.form_submit_button("Create Role") and nr:
                run_query("INSERT INTO roles (name, permissions) VALUES (?,?)", (nr, json.dumps([]))); st.success("Created"); st.rerun()

def view_settings():
    st.title("⚙️ Settings")
    t = st.selectbox("Theme", list(THEMES.keys()))
    if t != st.session_state.theme: st.session_state.theme = t; st.rerun()

# --- MAIN ---
def main():
    init_db()
    if 'user' not in st.session_state: st.session_state.user = None
    if st.session_state.user is None and 'session_token' in st.query_params:
        u = validate_session(st.query_params['session_token'])
        if u: st.session_state.user = dict(u)

    if st.session_state.user is None: landing_page()
    else:
        perms = json.loads(run_query("SELECT permissions FROM roles WHERE name=?", (st.session_state.user['role'],), fetch=True)[0]['permissions'])
        with st.sidebar:
            st.image(image_from_base64(st.session_state.user.get('profile_pic')), width=80)
            st.write(f"**{st.session_state.user['name']}** ({st.session_state.user['role'].upper()})")
            st.markdown("---")
            nav = {"Dashboard": "📊", "Inventory": "📦", "Stock Operations": "🔄", "Kit Management": "🧰", "Reports": "📑", "Audit Logs": "🛡️", "Procurement List": "🛒", "User Management": "👥", "Settings": "⚙️"}
            
            if st.button("👤 My Profile", use_container_width=True): st.session_state.current_view = "My Profile"; st.rerun()
            for k, v in nav.items():
                if k in perms and st.button(f"{v} {k}", use_container_width=True):
                    st.session_state.current_view = k
                    if k == "Procurement List": st.session_state.procurement_step = 1
                    st.rerun()
            st.markdown("---"); 
            if st.button("🚪 Logout"): logout_user()

        if 'current_view' not in st.session_state: st.session_state.current_view = "Dashboard"
        v = st.session_state.current_view
        
        if v == "My Profile": view_profile()
        elif v == "Dashboard": view_dashboard()
        elif v == "Inventory" and v in perms: view_inventory()
        elif v == "Stock Operations" and v in perms: view_stock_ops()
        elif v == "Kit Management" and v in perms: view_kit_management()
        elif v == "Reports" and v in perms: view_reports()
        elif v == "Audit Logs" and v in perms: view_audit_logs()
        elif v == "Procurement List" and v in perms: view_procurement()
        elif v == "User Management" and v in perms: view_users()
        elif v == "Settings" and v in perms: view_settings()
        elif v not in perms: st.error("⛔ Access Denied")

if __name__ == '__main__': main()
