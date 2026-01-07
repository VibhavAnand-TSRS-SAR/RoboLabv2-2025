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
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 emp_id TEXT UNIQUE NOT NULL,
                 name TEXT NOT NULL,
                 password TEXT NOT NULL,
                 role TEXT NOT NULL,
                 dob TEXT, gender TEXT, address TEXT, phone TEXT,
                 profile_pic TEXT)''')
    
    try:
        c.execute("SELECT profile_pic FROM users LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT")
        conn.commit()

    c.execute('''CREATE TABLE IF NOT EXISTS roles (
                 name TEXT PRIMARY KEY,
                 permissions TEXT)''')
    
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
    
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
                 token TEXT PRIMARY KEY,
                 user_id INTEGER,
                 expires_at DATETIME)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_name TEXT,
                 action TEXT,
                 details TEXT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Seed Roles
    c.execute("SELECT count(*) FROM roles")
    if c.fetchone()[0] == 0:
        all_perms = json.dumps(["Dashboard", "Inventory", "Stock Operations", "Reports", "Procurement List", "User Management", "Audit Logs", "Settings"])
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ('admin', all_perms))
        
        asst_perms = json.dumps(["Dashboard", "Inventory", "Stock Operations", "Reports", "Procurement List"])
        c.execute("INSERT INTO roles (name, permissions) VALUES (?, ?)", ('assistant', asst_perms))
        conn.commit()

    # Seed Users
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)", ('admin', 'System Admin', 'admin123', 'admin'))
        c.execute("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)", ('assistant', 'Lab Assistant', '123', 'assistant'))
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
        st.error(f"DB Error: {e}")
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
        img_src = image_from_base64(user['profile_pic'])
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
            if curr['dob']:
                try:
                    dob_val = datetime.strptime(curr['dob'], '%Y-%m-%d')
                except:
                    dob_val = None

            dob = c1.date_input("Date of Birth", value=dob_val)
            gender = c2.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(curr['gender']) if curr['gender'] in ["Male", "Female", "Other"] else 0)
            phone = c1.text_input("Phone", value=curr['phone'] if curr['phone'] else "")
            address = c2.text_area("Address", value=curr['address'] if curr['address'] else "")
            
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

# --- LANDING PAGE WITH LOGO ---
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
    
    tab1, tab2, tab3 = st.tabs(["🔎 View", "➕ Add Item", "📂 Bulk Upload"])
    
    with tab1:
        df = pd.read_sql_query("SELECT * FROM inventory", get_db_connection())
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
            c = st.selectbox("Category", ["Sensors", "Motors", "Microcontrollers", "Power", "Tools", "Others"])
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
        st.markdown("**Upload Excel (.xlsx)** with columns: `name`, `category`, `quantity`, `price`, `min_stock`, `location`")
        uploaded_file = st.file_uploader("Choose File", type=['xlsx'])
        
        if uploaded_file:
            df_upload = pd.read_excel(uploaded_file)
            st.dataframe(df_upload.head())
            
            if st.button("Confirm Import"):
                count = 0
                for _, row in df_upload.iterrows():
                    row_lower = {k.lower(): v for k, v in row.items()}
                    if 'name' in row_lower and pd.notna(row_lower['name']):
                        run_query("INSERT INTO inventory (name, category, quantity, min_stock, price, location) VALUES (?,?,?,?,?,?)", 
                                  (row_lower['name'], row_lower.get('category', 'Others'), row_lower.get('quantity', 0), row_lower.get('min_stock', 5), row_lower.get('price', 0.0), row_lower.get('location', 'Unknown')))
                        count += 1
                log_activity("Bulk Upload", f"Imported {count} items")
                st.success(f"Imported {count} items!")
                st.rerun()

def view_stock_ops():
    st.title("🔄 Stock Operations")
    
    df = pd.read_sql_query("SELECT * FROM inventory", get_db_connection())
    if df.empty:
        st.warning("No items in inventory. Add items first.")
        return
    
    col_in, col_out = st.columns(2)
    
    with col_in:
        st.markdown(f"<div style='background:#ecfdf5; padding:20px; border-radius:12px; border:2px solid #10b981;'>", unsafe_allow_html=True)
        st.subheader("📥 Stock In")
        with st.form("stock_in_form"):
            item_in = st.selectbox("Select Item", df['name'].tolist(), key="in_item")
            qty_in = st.number_input("Quantity to Add", min_value=1, value=1, key="in_qty")
            notes_in = st.text_input("Notes (e.g., Purchase Order #)", key="in_notes")
            
            if st.form_submit_button("➕ Add Stock", use_container_width=True):
                run_query("UPDATE inventory SET quantity = quantity + ? WHERE name = ?", (qty_in, item_in))
                run_query("INSERT INTO transactions (item_name, type, quantity, user, notes) VALUES (?,?,?,?,?)", 
                          (item_in, 'in', qty_in, st.session_state.user['name'], notes_in))
                log_activity("Stock In", f"Added {qty_in} to {item_in}")
                st.success(f"Added {qty_in} units to {item_in}")
                time.sleep(1)
                st.rerun()
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
                if qty_out > current_qty:
                    st.error(f"Insufficient stock! Available: {current_qty}")
                else:
                    run_query("UPDATE inventory SET quantity = quantity - ? WHERE name = ?", (qty_out, item_out))
                    run_query("INSERT INTO transactions (item_name, type, quantity, user, notes) VALUES (?,?,?,?,?)", 
                              (item_out, 'out', qty_out, st.session_state.user['name'], notes_out))
                    log_activity("Stock Out", f"Removed {qty_out} from {item_out}")
                    st.success(f"Removed {qty_out} units from {item_out}")
                    time.sleep(1)
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📋 Recent Stock Activity")
    
    recent_trans = pd.read_sql_query("SELECT timestamp, item_name, type, quantity, user, notes FROM transactions ORDER BY timestamp DESC LIMIT 10", get_db_connection())
    
    if recent_trans.empty:
        st.info("No transactions recorded yet.")
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

# --- REVAMPED PROCUREMENT LIST ---
def view_procurement():
    st.title("🛒 Procurement List")
    st.caption("Generate a procurement request for items below minimum stock levels.")
    
    # Get low stock items
    df = pd.read_sql_query("SELECT * FROM inventory WHERE quantity < min_stock", get_db_connection())
    
    if df.empty:
        st.success("✅ All items are well-stocked! No procurement needed.")
        return
    
    st.warning(f"⚠️ {len(df)} items are below minimum stock level.")
    
    # Initialize session state for procurement data
    if 'procurement_data' not in st.session_state:
        st.session_state.procurement_data = {}
    
    st.markdown("---")
    st.subheader("📝 Fill Procurement Details")
    
    # Global fields
    col1, col2 = st.columns(2)
    with col1:
        requested_by = st.text_input("Requested By", value=st.session_state.user['name'])
    with col2:
        required_by_date = st.date_input("Required By Date", value=datetime.now() + timedelta(days=7))
    
    st.markdown("---")
    
    # Item-wise form
    procurement_items = []
    
    for idx, row in df.iterrows():
        item_name = row['name']
        shortage = row['min_stock'] - row['quantity']
        
        st.markdown(f"""
            <div class="procurement-item">
                <strong style="color:{current_theme['primary']};">📦 {item_name}</strong>
                <span style="float:right; background:#fef2f2; color:#dc2626; padding:2px 8px; border-radius:10px; font-size:12px;">
                    Shortage: {shortage}
                </span>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            qty = st.number_input(f"Quantity", min_value=1, value=int(shortage), key=f"qty_{idx}")
        
        with col2:
            mode = st.selectbox("Mode", ["Online", "Offline"], key=f"mode_{idx}")
        
        with col3:
            if mode == "Online":
                link = st.text_input("Purchase Link", placeholder="https://...", key=f"link_{idx}")
            else:
                link = ""
        
        justification = st.text_area("Justification", placeholder="Why is this item needed?", key=f"just_{idx}", height=68)
        
        procurement_items.append({
            "Item Name": item_name,
            "Current Stock": row['quantity'],
            "Min Stock": row['min_stock'],
            "Quantity Requested": qty,
            "Justification": justification,
            "Mode": mode,
            "Purchase Link": link if mode == "Online" else "N/A",
            "Requested By": requested_by,
            "Required By": str(required_by_date)
        })
        
        st.markdown("---")
    
    # Generate Excel
    st.subheader("📤 Generate Procurement Request")
    
    if st.button("Generate Excel for Admin", type="primary", use_container_width=True):
        # Create DataFrame
        procurement_df = pd.DataFrame(procurement_items)
        
        # Create Excel file
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            procurement_df.to_excel(writer, sheet_name='Procurement Request', index=False)
            
            # Auto-adjust column width
            worksheet = writer.sheets['Procurement Request']
            for i, col in enumerate(procurement_df.columns):
                max_length = max(len(str(col)), procurement_df[col].astype(str).map(len).max())
                worksheet.column_dimensions[chr(65 + i)].width = min(max_length + 2, 50)
        
        buffer.seek(0)
        
        # Log activity
        log_activity("Procurement Request", f"Generated procurement request for {len(procurement_items)} items")
        
        # Download button
        st.download_button(
            label="📥 Download Procurement Request Excel",
            data=buffer,
            file_name=f"Procurement_Request_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.success("✅ Procurement request generated! Download and send to Admin for approval.")

def view_users():
    st.title("👥 User & Role Management")
    
    tab_users, tab_roles = st.tabs(["👤 Manage Users", "🔐 Manage Roles"])
    
    with tab_users:
        users_df = pd.read_sql_query("SELECT emp_id, name, role FROM users", get_db_connection())
        st.dataframe(users_df, use_container_width=True)
        
        col_add, col_edit = st.columns(2)
        
        with col_add:
            with st.expander("➕ Add New User", expanded=False):
                with st.form("create_user_form"):
                    roles_list = [r['name'] for r in run_query("SELECT name FROM roles", fetch=True)]
                    
                    new_emp = st.text_input("Employee ID")
                    new_name = st.text_input("Full Name")
                    new_pass = st.text_input("Password", type="password")
                    new_role = st.selectbox("Assign Role", roles_list)
                    
                    if st.form_submit_button("Create User"):
                        if run_query("INSERT INTO users (emp_id, name, password, role) VALUES (?, ?, ?, ?)", (new_emp, new_name, new_pass, new_role)):
                            log_activity("User Created", f"Created user {new_emp}")
                            st.success("User created!")
                            st.rerun()
                        else:
                            st.error("Error: Employee ID may already exist.")

        with col_edit:
            with st.expander("✏️ Edit User", expanded=False):
                user_to_edit = st.selectbox("Select User", users_df['emp_id'].tolist())
                
                if user_to_edit:
                    curr_user = run_query("SELECT * FROM users WHERE emp_id = ?", (user_to_edit,), fetch=True)[0]
                    roles_list = [r['name'] for r in run_query("SELECT name FROM roles", fetch=True)]
                    
                    with st.form("edit_user_form"):
                        edit_name = st.text_input("Name", value=curr_user['name'])
                        edit_role = st.selectbox("Role", roles_list, index=roles_list.index(curr_user['role']) if curr_user['role'] in roles_list else 0)
                        edit_pass = st.text_input("Reset Password (leave blank to keep)", type="password")
                        
                        if st.form_submit_button("Update User"):
                            q = "UPDATE users SET name=?, role=?"
                            p = [edit_name, edit_role]
                            if edit_pass:
                                q += ", password=?"
                                p.append(edit_pass)
                            q += " WHERE emp_id=?"
                            p.append(user_to_edit)
                            
                            run_query(q, tuple(p))
                            log_activity("User Updated", f"Updated user {user_to_edit}")
                            st.success("Updated!")
                            st.rerun()

    with tab_roles:
        st.info("Define custom roles and select which pages each role can access.")
        
        ALL_PAGES = ["Dashboard", "Inventory", "Stock Operations", "Reports", "Procurement List", "User Management", "Audit Logs", "Settings"]
        
        roles_data = run_query("SELECT * FROM roles", fetch=True)
        
        for role in roles_data:
            with st.expander(f"🔑 Role: {role['name'].upper()}", expanded=False):
                current_perms = json.loads(role['permissions'])
                
                with st.form(f"edit_role_{role['name']}"):
                    st.write(f"**Permissions for {role['name']}**")
                    
                    new_perms = []
                    cols = st.columns(4)
                    for i, page in enumerate(ALL_PAGES):
                        with cols[i % 4]:
                            if st.checkbox(page, value=(page in current_perms), key=f"perm_{role['name']}_{page}"):
                                new_perms.append(page)
                    
                    if st.form_submit_button("Save Permissions"):
                        run_query("UPDATE roles SET permissions = ? WHERE name = ?", (json.dumps(new_perms), role['name']))
                        log_activity("Role Updated", f"Updated permissions for {role['name']}")
                        st.success("Permissions updated!")
                        st.rerun()

        st.markdown("---")
        with st.form("new_role_form"):
            st.subheader("➕ Create New Role")
            new_role_name = st.text_input("Role Name (e.g., student_leader)").lower().replace(" ", "_")
            
            st.write("**Select Permissions:**")
            nr_perms = []
            cols = st.columns(4)
            for i, page in enumerate(ALL_PAGES):
                with cols[i % 4]:
                    if st.checkbox(page, key=f"new_role_{page}"):
                        nr_perms.append(page)
            
            if st.form_submit_button("Create Role"):
                if new_role_name:
                    run_query("INSERT INTO roles (name, permissions) VALUES (?, ?)", (new_role_name, json.dumps(nr_perms)))
                    log_activity("Role Created", f"Created role {new_role_name}")
                    st.success(f"Role '{new_role_name}' created!")
                    st.rerun()

def view_settings():
    st.title("⚙️ Settings")
    t = st.selectbox("Theme", list(THEMES.keys()))
    if t != st.session_state.theme:
        st.session_state.theme = t
        st.rerun()

# --- MAIN ---
def main():
    init_db()
    
    if 'user' not in st.session_state:
        st.session_state.user = None
    if st.session_state.user is None and 'session_token' in st.query_params:
        user = validate_session(st.query_params['session_token'])
        if user:
            st.session_state.user = dict(user)

    if st.session_state.user is None:
        landing_page()
    else:
        perms_json = run_query("SELECT permissions FROM roles WHERE name = ?", (st.session_state.user['role'],), fetch=True)[0]['permissions']
        perms = json.loads(perms_json)
        
        with st.sidebar:
            img_src = image_from_base64(st.session_state.user['profile_pic'])
            st.markdown(f"<div style='text-align:center; margin-bottom:10px;'><img src='{img_src}' style='width:80px; height:80px; border-radius:50%; object-fit:cover; border:2px solid {current_theme['primary']};'></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='text-align:center'><b>{st.session_state.user['name']}</b><br><small>{st.session_state.user['role'].upper()}</small></div>", unsafe_allow_html=True)
            st.markdown("---")
            
            # Updated nav_map with Procurement List
            nav_map = {
                "Dashboard": "📊", "Inventory": "📦", "Stock Operations": "🔄", 
                "Reports": "📑", "Audit Logs": "🛡️", "Procurement List": "🛒", 
                "User Management": "👥", "Settings": "⚙️"
            }
            
            if st.button("👤 My Profile", use_container_width=True):
                st.session_state.current_view = "My Profile"
                st.rerun()
                
            for p, icon in nav_map.items():
                if p in perms:
                    if st.button(f"{icon} {p}", use_container_width=True):
                        st.session_state.current_view = p
                        st.rerun()
                        
            st.markdown("---")
            if st.button("🚪 Logout"):
                logout_user()

        if 'current_view' not in st.session_state:
            st.session_state.current_view = "Dashboard"
        v = st.session_state.current_view
        
        if v == "My Profile": view_profile()
        elif v == "Dashboard": view_dashboard()
        elif v == "Inventory" and v in perms: view_inventory()
        elif v == "Stock Operations" and v in perms: view_stock_ops()
        elif v == "Reports" and v in perms: view_reports()
        elif v == "Audit Logs" and v in perms: view_audit_logs()
        elif v == "Procurement List" and v in perms: view_procurement()
        elif v == "User Management" and v in perms: view_users()
        elif v == "Settings" and v in perms: view_settings()
        elif v not in perms: st.error("⛔ Access Denied")

if __name__ == '__main__':
    main()
