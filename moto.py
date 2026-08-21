import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

# ---------------------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------------------
DB_FILE = "moto_nzuri.sqlite"

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        );

        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kp_number TEXT,
            mn_number TEXT,
            shop_name TEXT NOT NULL,
            location TEXT,
            latitude TEXT,
            longitude TEXT,
            branding TEXT DEFAULT 'Not Done',
            phone_numbers TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            ip TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # ---- MIGRATION: ensure new columns exist ----
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(records)").fetchall()}

    # Rename old columns if present
    if "code" in existing_columns and "kp_number" not in existing_columns:
        conn.execute("ALTER TABLE records RENAME COLUMN code TO kp_number")
        existing_columns.discard("code")
        existing_columns.add("kp_number")

    if "business_name" in existing_columns and "shop_name" not in existing_columns:
        conn.execute("ALTER TABLE records RENAME COLUMN business_name TO shop_name")
        existing_columns.discard("business_name")
        existing_columns.add("shop_name")

    # Add all missing columns
    columns_to_add = {
        "kp_number": "TEXT",
        "mn_number": "TEXT",
        "shop_name": "TEXT NOT NULL",
        "branding": "TEXT DEFAULT 'Not Done'",
        "phone_numbers": "TEXT",
        "version": "TEXT",           # NEW
        "asset_number": "TEXT",      # NEW
        "owner": "TEXT",             # NEW
        "status": "TEXT",            # NEW
        "agent": "TEXT",             # NEW
    }
    for col, col_type in columns_to_add.items():
        if col not in existing_columns:
            conn.execute(f"ALTER TABLE records ADD COLUMN {col} {col_type}")
            existing_columns.add(col)

    # Seed users if empty
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        admin_pass = hash_password("Admin@0912")
        user_pass = hash_password("motoSana00")
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                     ("motoAdministrator", admin_pass, "admin"))
        conn.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                     ("usermoto", user_pass, "user"))
        conn.commit()

    # Seed records if empty
    record_count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    if record_count == 0:
        seed_records(conn)

    conn.close()

def seed_records(conn):
    data = [
        # --- Original records (with empty new fields) ---
        ("", "", "Abijan Shop", "Kibera", "-1.310586", "36.787133", "Not Done", "", "", "", "", "", ""),
        ("KP-1930", "", "Amani shop", "Huruma", "", "", "Not Done", "", "", "", "", "", ""),
        ("", "", "Angel's Fresh Dairy", "Athi River", "-1.458793", "36.977203", "Not Done", "0714093892", "", "", "", "", ""),
        ("", "", "Blessed Gas sabaki", "Mlolongo", "-1.38895", "36.941642", "Not Done", "", "", "", "", "", ""),
        ("KP-1047", "", "Big fish enterprises", "Kayole", "-1.2613752", "36.9305628", "Not Done", "", "v6.2", "KA194S0161", "Geoffrey Njoronge Ginjithi", "Accept", "Eunice"),
        ("", "", "Birkilis Cosmetic", "Kibera", "-1.31452", "36.782948", "Not Done", "", "", "", "", "", ""),
        ("", "", "Blessed butchery", "Mlolongo", "-1.388893", "36.94172", "Not Done", "", "", "", "", "", ""),
        ("", "", "Bliss Uniforms", "Athi River", "-1.457159", "36.974133", "Not Done", "0720896008", "", "", "", "", ""),
        ("", "", "Brivis urban venture", "Mathare", "-1.2615747", "36.8599967", "Not Done", "", "", "", "", "", ""),
        ("", "", "By God's Grace", "Mlolongo", "-1.388873", "36.948883", "Not Done", "", "", "", "", "", ""),
        ("", "", "Calecoom beauty", "Kibera", "-1.309563", "36.77335", "Not Done", "", "", "", "", "", ""),
        ("", "", "Copious gas", "Mlolongo", "-1.393821", "36.950152", "Not Done", "", "", "", "", "", ""),
        ("KP-0993", "", "Collo shop", "Kibera", "-1.31661", "36.794928", "Not Done", "", "", "", "", "", ""),
        ("", "", "Copious gas and kerosene", "Mlolongo", "-1.393743", "36.950183", "Not Done", "0727740815", "", "", "", "", ""),
        ("", "", "Dama", "Mathare North", "", "", "Not Done", "718341033", "", "", "", "", ""),
        ("", "", "Diaper city", "Mwiki", "-1.232946", "36.935549", "Not Done", "", "", "", "", "", ""),
        ("", "", "Dojam joy shop", "Mathare", "-1.2619573", "36.8571768", "Not Done", "", "", "", "", "", ""),
        ("", "", "Double progressive shop", "Komarock", "", "", "Not Done", "", "", "", "", "", ""),
        ("", "", "GLAMSO ENTERPRISE", "MAGOROFANI", "-1.315291", "36.796922", "Not Done", "", "", "", "", "", ""),
        ("", "", "Favoured Bookshop", "Pipeline", "-1.32208", "36.89427", "Not Done", "", "", "", "", "", ""),
        ("", "", "Gateway Cereals", "Dandora", "-1.2585631", "36.890297", "Not Done", "0721226420", "", "", "", "", ""),
        ("", "", "Real Traders", "Kiserian", "", "", "Not Done", "0740140033", "", "", "", "", ""),
        ("", "", "Genesis Home Decor", "kasarani", "-1.222002", "36.929835", "Not Done", "", "", "", "", "", ""),
        ("", "", "GLORY TABA", "OLYMPIC", "-1.313074", "36.777652", "Not Done", "", "", "", "", "", ""),
        ("", "", "HARDVIC SUPERSTORE SHOP", "KANGEMI", "-1.266196", "36.751161", "Not Done", "", "", "", "", "", ""),
        ("", "", "Hm mwomboko", "Kariobangi South", "-1.265122", "36.889443", "Not Done", "", "", "", "", "", ""),
        ("KP-3542", "", "Home Care shop", "Thika", "-1.07017", "37.0561", "Not Done", "", "", "", "", "", ""),
        ("KP-2346", "", "Imani Shop", "Athi River", "-1.460744", "36.984521", "Not Done", "0715805011", "", "", "", "", ""),
        ("", "", "Jamwa Electronics", "Mwiki", "-1.2347475", "36.9347514", "Not Done", "", "", "", "", "", ""),
        ("", "", "Jikaze Investment", "Kibera", "-1.314937", "36.785422", "Not Done", "717230724", "", "", "", "", ""),
        ("", "", "Karanja enterprise", "Pangani", "-1.2671861", "36.8433984", "Not Done", "", "", "", "", "", ""),
        ("", "", "Kazi ni dawa sasa", "Huruma", "", "", "Not Done", "", "", "", "", "", ""),
        ("", "", "Lian hopeful cereals", "Mathare", "-1.253795", "36.866896", "Not Done", "", "", "", "", "", ""),
        ("", "", "Lucky stores", "Mlolongo", "-1.391872", "36.941972", "Not Done", "", "", "", "", "", ""),
        ("", "", "Mama Abby shop", "Mlolongo", "-1.39167", "36.94149", "Not Done", "0722855846", "", "", "", "", ""),
        ("KP-0926", "", "Menengai stores", "Athi River", "-1.457404", "36.974278", "Not Done", "0720900705", "", "", "", "", ""),
        ("", "", "Milano shop", "Mukuru kwa Reuben", "-1.3162", "36.875773", "Not Done", "", "", "", "", "", ""),
        ("", "", "Merlu shop", "Mlolongo", "-1.39618", "36.93701", "Not Done", "", "", "", "", "", ""),
        ("", "", "Motherland beauty", "Kibera", "-1.312407", "36.79765", "Not Done", "", "", "", "", "", ""),
        ("", "", "Mullar Gas", "Mlolongo", "-1.390114", "36.9431014", "Not Done", "", "", "", "", "", ""),
        ("", "", "Mutheru Gases", "Kasarani", "-1.223382", "36.921152", "Not Done", "", "", "", "", "", ""),
        ("", "", "Mzoori supermarket", "Pipeline", "-1.31393", "36.89028", "Not Done", "", "", "", "", "", ""),
        ("", "", "Mwangaza Cereals Shop", "Umoja 3", "", "", "Not Done", "", "", "", "", "", ""),
        ("", "", "Ombasade Shop", "Kasarani", "-1.204682", "36.913431", "Not Done", "", "", "", "", "", ""),
        ("", "", "Pavilet Kerosene", "Githurai 45", "-1.207128", "36.955872", "Not Done", "", "", "", "", "", ""),
        ("", "", "RAINDRIP COLLECTINGS", "NJIRU", "-1.250821", "36.939777", "Not Done", "", "", "", "", "", ""),
        ("", "", "Remo", "Kibera", "-1.312826", "36.795949", "Not Done", "", "", "", "", "", ""),
        ("", "", "Rivercop gas", "Mlolongo", "-1.390545", "36.947243", "Not Done", "0727740815", "", "", "", "", ""),
        ("", "", "Rivercop gas", "Mlolongo", "-1.390545", "36.941425", "Not Done", "0727740815", "", "", "", "", ""),
        ("", "", "Rifro", "Githu 45", "-1.31393", "36.89028", "Not Done", "0796409019", "", "", "", "", ""),
        ("", "", "Rob investment", "Mlolongo", "-1.390808", "36.941425", "Not Done", "", "", "", "", "", ""),
        ("", "", "SIRDAWA", "Rongai", "-1.390808", "36.941425", "Not Done", "", "", "", "", "", ""),
        ("", "", "Shop Achievers", "Kibera", "-1.312049", "36.788509", "Not Done", "717885421", "", "", "", "", ""),
        ("KP-3134", "", "Al Nasib Shop", "Huruma", "-1.25692", "36.87523", "Not Done", "", "v6.2", "KA194S2378", "Nasibo Mohamed", "", ""),
        ("", "", "Shop matt", "Mwiki", "-1.2329551", "36.9317764", "Not Done", "", "", "", "", "", ""),
        ("", "", "Summer shop", "Molem Gatundu", "-1.080659", "36.97513", "Not Done", "0794433547", "", "", "", "", ""),
        ("", "", "Terriconn Investment", "Kaloleni", "1.301119", "36.847894", "Not Done", "0737006387", "", "", "", "", ""),
        ("", "", "Uncle sam", "Kibera", "-1.313074", "36.777652", "Not Done", "0707284936", "", "", "", "", ""),
        ("", "", "Variety Shop", "Kasarani", "-1.204682", "36.913431", "Not Done", "", "", "", "", "", ""),
        ("KP-1794", "", "Victory Shop", "Kariobangi South", "-1.273933", "36.88509", "Not Done", "0110521497 / 0757733253", "", "", "", "", ""),
        ("", "", "Viewsasa Grocery", "Athi River", "-1.460744", "36.970823", "Not Done", "07119968909", "", "", "", "", ""),
        ("KP-1222", "", "VIRGY SHOP", "GATAKA", "-1.376791", "36.725131", "Not Done", "CARRY OUR BRANDING AND SWAP OF KPC AND TABLET", "", "", "", "", ""),
        ("KP-0210", "", "Wawira shop", "Kayole", "-1.27943", "36.91705", "Not Done", "0706274155", "v6.1", "KA56S0768", "Consolata Wawira", "Accept", "Eunice"),
        ("", "", "Nyambura Shop", "KISERIAN", "-1.4246", "36.67832", "Not Done", "", "", "", "", "", ""),

        # --- NEW records from Felix (additional) ---
        ("KP-0200", "", "Eagle S. Shop", "Kayole", "-1.276037583", "36.91202905", "Not Done", "", "v6.1", "KA56S0192", "Kijana Laizer", "", "Eunice"),
        ("KP-0441", "", "Catherine's shop", "Kayole", "-1.2685813", "36.9250503", "Not Done", "", "v6.1", "KA56S0051", "Catherine Muthoni", "Declined", "Eunice"),
        ("KP-0464", "", "Step one shop", "Kayole", "-1.286516667", "36.91223", "Not Done", "", "v6.1", "KA56S0224", "Kennedy Kudia", "", "Eunice"),
        ("KP-0475", "", "Blessing Shop-Kayole", "Kayole", "-1.28047", "36.91558", "Not Done", "", "v6.1", "KA56S0000", "Nick Owuor", "Declined", "Eunice"),
        ("KP-0557", "", "Royson Dairies", "Kayole", "-1.25812", "36.92756", "Not Done", "", "v6.1", "KA56S0407", "Micheal Mwaniki", "Accept", "Eunice"),
        ("KP-0832", "", "Kogi General Shop", "Kayole", "-1.2768005", "36.9173183", "Not Done", "", "v6.1", "KA56SO641", "Nelson Maina", "Accept", "Eunice"),
        ("KP-0956", "", "Smart general shop", "Kayole", "-1.27746", "36.91324", "Not Done", "", "v6.2", "KA194S0181", "Joseph mwangi", "Accept", "Eunice"),
        ("KP-0987", "", "Fireworks Creation", "Kayole", "-1.27564", "36.91126", "Not Done", "", "v6.2", "KA194S0147", "Lydia Mwakwida", "Accept", "Eunice"),
        ("KP-0999", "", "Denis Shop", "Kayole", "-1.28906", "36.90993", "Not Done", "", "v6.2", "KA194S0226", "Denis Aminga", "Accept", "Eunice"),
        ("KP-1017", "", "Super Fresh Shop 2", "Kayole", "-1.263665", "36.93121", "Not Done", "", "v6.2", "KA194S1696", "David ngigi", "Declined", "Eunice"),
        ("KP-1067", "", "Becky shop", "Kayole", "-1.27529", "36.91575", "Not Done", "", "v6.2", "KA194S0187", "Rebecca Wanjiru kibe", "Accept", "Eunice"),
        ("KP-0894", "", "TALISHA -F", "Huruma", "-1.25642", "36.87299", "Not Done", "", "v6.2", "KA194S2367", "Edison Oteyo", "", ""),
        ("KP-2167", "", "Holdings 2", "Mathare", "-1.265808333", "36.85127667", "Not Done", "", "v6.2", "KA194S1374W", "Purity Muthoni", "", ""),
        ("KP-1003", "", "Welcome to base", "Mathare North", "-1.2552832", "36.8624338", "Not Done", "", "v6.2", "KA194S0289", "Damaris kimeu", "", ""),
        ("KP-0098", "", "PAMOJA EXPRESS SUPERMARKET", "Mathare slum", "-1.262471667", "36.86068833", "Not Done", "", "v6.1", "KA56S0119", "Naumi W. Kamau", "", "Eunice sauli"),
        ("KP-0188", "", "Duchcom shop", "Mathare Slum", "-1.261554", "36.85998", "Not Done", "", "v6.1", "KA56S0423", "Peter Ndunde Dush", "", "Eunice sauli"),
        ("KP-0363", "", "Glorious Communication", "Mathare Slum", "-1.26368", "36.85697", "Not Done", "", "v6.1", "KA56S0060", "Wickliffe Simwa lilumbi", "", "Eunice sauli"),
        ("KP-3251", "", "Lemiz Inter-Traders.", "Mathare Slum", "-1.26185", "36.85445", "Not Done", "", "v6.2", "KA194S1154", "Patrick Wekesa", "", ""),
        ("", "", "Mt Kenya 1 & 2", "Githurai 45", "-1.2152", "36.92261", "Not Done", "", "", "", "", "", ""),
        ("", "", "God's Favour Shop", "Githurai 45", "-1.21288", "36.92243", "Not Done", "", "", "", "", "", ""),
        ("", "", "Delight Beauty", "Thika", "-1.05605", "37.11084", "Not Done", "", "", "", "", "", ""),
        ("", "", "Sammar shop", "Thika", "-1.0412", "37.08409", "Not Done", "", "", "", "", "", ""),
        ("", "", "Wakini general", "Witeithie Thika", "-1.071685", "37.05801", "Not Done", "", "", "", "", "", ""),
    ]

    conn.executemany(
        """INSERT INTO records 
           (kp_number, mn_number, shop_name, location, latitude, longitude, branding, phone_numbers,
            version, asset_number, owner, status, agent)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        data
    )
    conn.commit()  
#################
def generate_pdf(dataframe):
    """Generate a PDF file from a DataFrame and return bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=20, bottomMargin=20)
    elements = []
    styles = getSampleStyleSheet()
    title = Paragraph("moto nzuri ops. - Business Records", styles['Title'])
    elements.append(title)

    # Prepare data for table
    header = list(dataframe.columns)
    data = [header] + dataframe.values.tolist()

    # Create table
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------
# SECURITY HELPERS
# ---------------------------------------------------------------------
def hash_password(password):
    salt = secrets.token_hex(16)
    hash = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 100000)
    return f"{salt}${hash.hex()}"

def verify_password(password, password_hash):
    try:
        salt, hash = password_hash.split('$')
        test_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 100000)
        return secrets.compare_digest(test_hash.hex(), hash)
    except:
        return False

def log_action(conn, action, details=""):
    user = st.session_state.get('user')
    conn.execute(
        "INSERT INTO logs (user_id, username, action, details, ip) VALUES (?, ?, ?, ?, ?)",
        (
            user['id'] if user else None,
            user['username'] if user else 'guest',
            action,
            details,
            st.session_state.get('client_ip', 'unknown')
        )
    )
    conn.commit()

def get_client_ip():
    return "streamlit-client"

# ---------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------
def login(username, password):
    conn = get_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and verify_password(password, user['password_hash']):
            st.session_state['user'] = {
                'id': user['id'],
                'username': user['username'],
                'role': user['role']
            }
            st.session_state['client_ip'] = get_client_ip()
            log_action(conn, 'LOGIN', f"User {username} logged in")
            return True
        else:
            log_action(conn, 'LOGIN_FAILED', f"Failed login for {username}")
            return False
    finally:
        conn.close()

def logout():
    if 'user' in st.session_state:
        conn = get_connection()
        log_action(conn, 'LOGOUT', f"User {st.session_state['user']['username']} logged out")
        conn.close()
    st.session_state.pop('user', None)
    st.session_state.pop('client_ip', None)

# ---------------------------------------------------------------------
# CRUD OPERATIONS
# ---------------------------------------------------------------------
def fetch_records(search=""):
    conn = get_connection()
    if search:
        like = f"%{search}%"
        rows = conn.execute(
            """SELECT * FROM records 
               WHERE kp_number LIKE ? OR mn_number LIKE ? OR shop_name LIKE ? 
                  OR location LIKE ? OR phone_numbers LIKE ?
               ORDER BY id DESC""",
            (like, like, like, like, like)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM records ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def create_record(conn, kp_number, mn_number, shop_name, location, latitude, longitude, branding, phone_numbers):
    conn.execute(
        """INSERT INTO records 
           (kp_number, mn_number, shop_name, location, latitude, longitude, branding, phone_numbers)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (kp_number, mn_number, shop_name, location, latitude, longitude, branding, phone_numbers)
    )
    conn.commit()
    log_action(conn, 'CREATE', f"Added record: {shop_name}")

def update_record(conn, record_id, kp_number, mn_number, shop_name, location, latitude, longitude, branding, phone_numbers):
    conn.execute(
        """UPDATE records 
           SET kp_number=?, mn_number=?, shop_name=?, location=?, latitude=?, longitude=?, 
               branding=?, phone_numbers=?, updated_at=CURRENT_TIMESTAMP
           WHERE id=?""",
        (kp_number, mn_number, shop_name, location, latitude, longitude, branding, phone_numbers, record_id)
    )
    conn.commit()
    log_action(conn, 'UPDATE', f"Updated record ID {record_id}: {shop_name}")

def delete_record(conn, record_id):
    row = conn.execute("SELECT shop_name FROM records WHERE id=?", (record_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM records WHERE id=?", (record_id,))
        conn.commit()
        log_action(conn, 'DELETE', f"Deleted record ID {record_id}: {row['shop_name']}")

# ---------------------------------------------------------------------
# ADMIN LOGS
# ---------------------------------------------------------------------
def fetch_logs():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 500").fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---------------------------------------------------------------------
# STREAMLIT UI
# ---------------------------------------------------------------------
st.set_page_config(page_title="moto nzuri ops.", layout="wide")

# Initialize database
init_db()

# Client IP (fake)
if 'client_ip' not in st.session_state:
    st.session_state['client_ip'] = get_client_ip()

# ---------------- SIDEBAR ----------------
with st.sidebar:
    if 'user' in st.session_state:
        user = st.session_state['user']
        st.write(f"**Logged in as:** {user['username']} ({user['role']})")
        if st.button("Logout"):
            logout()
            st.rerun()
        st.divider()
        st.write("**Navigation**")
        if user['role'] == 'admin':
            page = st.radio("Go to", ["Records", "Admin Dashboard"])
        else:
            page = "Records"
        st.caption("moto nzuri ops.")
    else:
        st.title("moto nzuri ops.")
        st.write("Please login to continue")
        login_form = st.form("login_form")
        username = login_form.text_input("Username")
        password = login_form.text_input("Password", type="password")
        submitted = login_form.form_submit_button("Login")
        if submitted:
            if login(username, password):
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.caption("Hint: motoAdministrator")
        st.caption("User Hint: usermoto")

# ---------------- MAIN CONTENT ----------------
if 'user' in st.session_state:
    user = st.session_state['user']
    if page == "Records":
        st.title("moto nzuri ops.")
        st.subheader("Business Records")

        # Search
        search_query = st.text_input("Search by KP, MN, shop name, location, or phone", "")

        # Load records from DB
        records = fetch_records(search_query)
        if records:
            df = pd.DataFrame(records)
            # Reorder columns for better UX (keep id as first, but hidden later)
            df = df[['id', 'kp_number', 'mn_number', 'shop_name', 'location', 'latitude', 'longitude', 'branding', 'phone_numbers']]
            # Save original IDs for later comparison
            original_ids = set(df['id'].tolist())
        else:
            # Create empty dataframe with correct columns
            df = pd.DataFrame(columns=['id', 'kp_number', 'mn_number', 'shop_name', 'location', 'latitude', 'longitude', 'branding', 'phone_numbers'])
            original_ids = set()

        # Display editable data editor
        st.markdown("**Edit records directly in the table. Add new rows at the bottom, or select a row and use the delete icon.**")
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            hide_index=True,
            column_config={
    "id": st.column_config.NumberColumn("ID", disabled=True),
    "kp_number": st.column_config.TextColumn("KP Number"),
    "mn_number": st.column_config.TextColumn("MN Number"),
    "shop_name": st.column_config.TextColumn("Shop Name", required=True),
    "location": st.column_config.TextColumn("Location"),
    "latitude": st.column_config.TextColumn("Latitude"),
    "longitude": st.column_config.TextColumn("Longitude"),
    "branding": st.column_config.TextColumn("Branding", default="Not Done"),
    "phone_numbers": st.column_config.TextColumn("Phone Numbers"),
    "version": st.column_config.TextColumn("Version"),
    "asset_number": st.column_config.TextColumn("Asset Number"),
    "owner": st.column_config.TextColumn("Owner"),
    "status": st.column_config.TextColumn("Status"),
    "agent": st.column_config.TextColumn("Agent"),
},
            use_container_width=True,
            key="records_editor"
        )

        # Buttons: Save Changes, Reset
        col1, col2, col3 = st.columns([1,1,3])
        with col1:
            save_btn = st.button("💾 Save Changes", type="primary")
        with col2:
            reset_btn = st.button("🔄 Reset")

        if reset_btn:
            # Clear the editor by re-running (we can just rerun)
            st.rerun()

        if save_btn:
            # Convert edited_df to list of dicts (drop rows with all empty cells)
            edited_records = edited_df.dropna(how='all').to_dict('records')
            # Remove rows where shop_name is empty (they are considered empty)
            edited_records = [r for r in edited_records if str(r.get('shop_name', '')).strip() != '']

            # Split into new, existing, and deleted
            new_records = []
            existing_records = []
            edited_ids = set()

            for rec in edited_records:
                rec_id = rec.get('id')
                if rec_id is None or pd.isna(rec_id):
                    new_records.append(rec)
                else:
                    rec_id = int(rec_id)
                    edited_ids.add(rec_id)
                    existing_records.append(rec)

            # Determine deleted: original IDs not in edited IDs
            deleted_ids = original_ids - edited_ids

            # Perform DB operations in a single connection
            conn = get_connection()
            try:
                # Delete
                for did in deleted_ids:
                    delete_record(conn, did)

                # Update existing
                for rec in existing_records:
                    rec_id = int(rec['id'])
                    update_record(
                        conn,
                        rec_id,
                        rec.get('kp_number', ''),
                        rec.get('mn_number', ''),
                        rec['shop_name'],
                        rec.get('location', ''),
                        rec.get('latitude', ''),
                        rec.get('longitude', ''),
                        rec.get('branding', 'Not Done'),
                        rec.get('phone_numbers', '')
                    )

                # Create new
                for rec in new_records:
                    create_record(
                        conn,
                        rec.get('kp_number', ''),
                        rec.get('mn_number', ''),
                        rec['shop_name'],
                        rec.get('location', ''),
                        rec.get('latitude', ''),
                        rec.get('longitude', ''),
                        rec.get('branding', 'Not Done'),
                        rec.get('phone_numbers', '')
                    )

                st.success("Changes saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving changes: {e}")
            finally:
                conn.close()

        # Export buttons and WhatsApp
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            # CSV download
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name="moto_nzuri_records.csv",
                mime="text/csv",
                key="csv_download"
            )
        with col2:
            # PDF download
            pdf_data = generate_pdf(df)
            st.download_button(
                label="📄 Download PDF",
                data=pdf_data,
                file_name="moto_nzuri_records.pdf",
                mime="application/pdf",
                key="pdf_download"
            )
        with col3:
            # WhatsApp share
            wa_text = f"moto nzuri ops. - {search_query if search_query else 'Full list'}"
            wa_link = f"https://wa.me/254702250123?text={wa_text}"
            st.markdown(f'<a href="{wa_link}" target="_blank" style="text-decoration:none;"><button style="padding:10px 20px; background:#25D366; color:white; border:none; border-radius:5px; cursor:pointer;">📱 Share to WhatsApp</button></a>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown("© innocent mwea moto nzuri intraweb")
