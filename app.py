from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3
import os
import random
import time
import smtplib
from datetime import datetime
from werkzeug.utils import secure_filename
from email.message import EmailMessage
from io import BytesIO

# PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")
DB_NAME = "database.db"

# ---------------- OTP / Pending Transfer Stores ----------------
# otp_storage: keyed by identifier (email) -> { otp, expires, attempts, purpose, identifier, meta }
otp_storage = {}
# pending_transfers: keyed by sender_username -> { sender_acc, receiver_acc, receiver_name, amount, created_at }
pending_transfers = {}

OTP_TTL_SECONDS = 300         # 5 minutes
MAX_OTP_ATTEMPTS = 5

# ---------------- Email sending ----------------
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = "priyanshuagrahari0561@gmail.com"  # set to enable real email sending
EMAIL_PASS = "gohcmapignmvwxpf"

# ---------------- File uploads ----------------
UPLOAD_FOLDER = os.path.join("static", "profile_pics")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # 4MB max upload

# ---------------- Date helper ----------------
def now():
    """Return current time formatted consistently (no microseconds)."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------------- Email helper ----------------
def send_email(to_email: str, subject: str, body: str):
    to_email = str(to_email).strip()
    if not to_email:
        app.logger.warning("No recipient email provided — email skipped.")
        return False

    if not EMAIL_USER or not EMAIL_PASS:
        # Simulation mode for local dev
        print("---------- SIMULATED EMAIL ----------")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(body)
        print("---------- END SIMULATED EMAIL ----------")
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_USER
        msg["To"] = to_email
        msg.set_content(body)

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)

        app.logger.info(f"Email sent to {to_email}")
        return True
    except Exception as e:
        app.logger.exception("Email failed, falling back to console")
        print("FALLBACK: printing email to console.")
        print("To:", to_email)
        print("Subject:", subject)
        print(body)
        return False

# ---------------- OTP helpers ----------------
def generate_and_store_otp(identifier, purpose, meta=None):
    otp = random.randint(100000, 999999)
    otp_storage[identifier] = {
        "otp": otp,
        "expires": time.time() + OTP_TTL_SECONDS,
        "attempts": 0,
        "purpose": purpose,
        "identifier": identifier,
        "meta": meta or {}
    }
    return otp

def verify_otp(identifier, entered_otp, expected_purpose):
    data = otp_storage.get(identifier)
    if not data:
        return False, "OTP not requested or expired.", None

    if data.get("purpose") != expected_purpose:
        return False, "OTP purpose mismatch.", None

    if time.time() > data.get("expires", 0):
        otp_storage.pop(identifier, None)
        return False, "OTP expired.", None

    if data.get("attempts", 0) >= MAX_OTP_ATTEMPTS:
        otp_storage.pop(identifier, None)
        return False, "Too many incorrect attempts. OTP invalidated.", None

    if str(data.get("otp")) == str(entered_otp):
        meta = data.get("meta", {})
        otp_storage.pop(identifier, None)
        return True, "OTP validated.", meta
    else:
        data["attempts"] = data.get("attempts", 0) + 1
        return False, f"Incorrect OTP. Attempts left: {MAX_OTP_ATTEMPTS - data['attempts']}", None

# ---------------- DB helpers ----------------
def get_user(identifier):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM users 
            WHERE username = ? OR email = ? OR phone = ?
        """, (identifier, identifier, identifier))
        return cur.fetchone()

def get_user_by_phone(phone):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE phone=?", (phone,))
        return cur.fetchone()

def get_user_by_account(account_number):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE account_number=?", (account_number,))
        return cur.fetchone()

# ---------------- File validation ----------------
from PIL import Image, ImageOps
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_image_file(path):
    try:
        Image.open(path).verify()
        return True
    except Exception:
        return False
    
@app.route('/')
def home():
    return redirect('/login')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        dob = request.form['dob']
        address = request.form.get('address', '')
        username = request.form['username']
        password = request.form['password']
        upi_pin = request.form.get('upi_pin', '')

        try:
            birth_year = int(dob.split('-')[0])
        except Exception:
            flash("⚠️ Invalid DOB format. Use YYYY-MM-DD.")
            return redirect('/register')

        age = datetime.now().year - birth_year
        if age < 18:
            flash("❌ You must be at least 18 years old.")
            return redirect('/register')

        account_number = str(random.randint(10**9, 10**10 - 1))

        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            try:
                cur.execute("""INSERT INTO users 
                    (account_number, username, password, name, email, phone, dob, age, address, profile, balance, upi_pin)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (account_number, username, password, name, email, phone, dob, age, address, 'default.png', 0.0, upi_pin))
                conn.commit()
                flash(f"✅ Account created! Your A/C Number: {account_number}")
                return redirect('/login')
            except sqlite3.IntegrityError:
                flash("⚠️ Username, email or phone already exists.")
                return redirect('/register')

    return render_template('register.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']

        user = get_user(identifier)
        if user and user[2] == password:
            session['user'] = user[1]
            flash("✅ Login successful!")
            return redirect('/dashboard')
        else:
            flash("❌ Invalid username/email/phone or password.")
    return render_template('login.html')

# ---------------- FORGOT PASSWORD (send email OTP) ----------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form['identifier'].strip()
        user = get_user(identifier)
        # generic response to avoid enumeration
        if not user:
            flash("If this account exists, an OTP has been sent to the registered email.")
            return redirect('/login')

        user_email = user[4]
        otp = generate_and_store_otp(user_email, purpose="reset_password", meta={"username": user[1]})
        subject = "MyBank - Password Reset OTP"
        body = f"Your MyBank password reset OTP is: {otp}\nIt expires in 5 minutes."
        send_email(user_email, subject, body)
        flash("✅ If this account exists, an OTP has been sent to the registered email.")
        return render_template('verify_reset_otp.html', email_hint=user_email)

    return render_template('forgot_password.html')

# ---------------- VERIFY RESET OTP ----------------
@app.route('/verify_reset_otp', methods=['POST'])
def verify_reset_otp():
    identifier = request.form.get('email').strip()
    entered_otp = request.form.get('otp').strip()
    ok, msg, meta = verify_otp(identifier, entered_otp, expected_purpose="reset_password")
    if not ok:
        flash("❌ " + msg)
        return render_template('verify_reset_otp.html', email_hint=identifier)

    flash("✅ OTP verified. Set your new password now.")
    return render_template('reset_password.html', email_hint=identifier)

# ---------------- RESET PASSWORD (after OTP) ----------------
@app.route('/reset_password', methods=['POST'])
def reset_password():
    identifier = request.form.get('email').strip()
    new_password = request.form.get('new_password')
    if not new_password:
        flash("⚠️ Provide a valid new password.")
        return render_template('reset_password.html', email_hint=identifier)

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password=? WHERE email=?", (new_password, identifier))
        conn.commit()

    flash("✅ Password updated successfully! Please log in.")
    return redirect('/login')

# Dashboard and transaction view

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        flash("⏳ Session expired. Please log in again.")
        return redirect('/login')

    user = get_user(session['user'])
    user = list(user)
    user[10] = float(user[10] or 0.0)

    # Default query
    query = "SELECT * FROM transactions WHERE account_number = ?"
    params = [user[0]]

    if request.method == 'POST':
        txn_type = request.form.get('txn_type')
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        min_amount = request.form.get('min_amount')
        max_amount = request.form.get('max_amount')
        account_search = request.form.get('account_search')

        if txn_type and txn_type != "All":
            query += " AND type = ?"
            params.append(txn_type)

        if date_from:
            query += " AND date >= ?"
            params.append(date_from + " 00:00:00")

        if date_to:
            query += " AND date <= ?"
            params.append(date_to + " 23:59:59")

        if min_amount:
            try:
                query += " AND amount >= ?"
                params.append(float(min_amount))
            except:
                pass

        if max_amount:
            try:
                query += " AND amount <= ?"
                params.append(float(max_amount))
            except:
                pass

        if account_search:
            query += " AND receiver LIKE ?"
            params.append(f"%{account_search}%")

    query += " ORDER BY id DESC"

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        transactions = cur.fetchall()

    return render_template('dashboard.html', user=user, transactions=transactions)

# Deposit, Withdraw, Transfer + verify transfer OTP

# ---------------- DEPOSIT ----------------
@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user' not in session:
        return redirect('/login')

    try:
        amount = float(request.form['amount'])
    except:
        flash("⚠️ Invalid deposit amount.")
        return redirect('/dashboard')

    if amount <= 0:
        flash("⚠️ Invalid deposit amount.")
        return redirect('/dashboard')

    user = get_user(session['user'])
    new_balance = float(user[10] or 0.0) + amount

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (new_balance, user[0]))
        cur.execute("INSERT INTO transactions (account_number, type, amount, date) VALUES (?, ?, ?, ?)",
                    (user[0], "Deposit", amount, now()))
        conn.commit()

    flash(f"💰 ₹{amount:.2f} deposited successfully!")
    return redirect('/dashboard')

# ---------------- WITHDRAW ----------------
@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user' not in session:
        return redirect('/login')

    user = get_user(session['user'])
    try:
        amount = float(request.form['amount'])
    except:
        flash("⚠️ Invalid amount entered.")
        return redirect('/dashboard')

    upi_pin = request.form['upi_pin']

    if upi_pin != user[11]:
        flash("❌ Incorrect UPI PIN!")
        return redirect('/dashboard')

    if amount <= 0:
        flash("⚠️ Invalid amount entered.")
        return redirect('/dashboard')

    current_balance = float(user[10] or 0.0)
    if amount > current_balance:
        flash("⚠️ Insufficient balance!")
        return redirect('/dashboard')

    new_balance = current_balance - amount
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (new_balance, user[0]))
        cur.execute("INSERT INTO transactions (account_number, type, amount, date) VALUES (?, ?, ?, ?)",
                    (user[0], "Withdraw", amount, now()))
        conn.commit()

    flash(f"💸 ₹{amount:.2f} withdrawn successfully!")
    return redirect('/dashboard')

# ---------------- TRANSFER (generate OTP and create pending) ----------------
@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user' not in session:
        return redirect('/login')

    sender = get_user(session['user'])
    sender_email = sender[4]  # email column
    receiver_name = request.form['receiver_name'].strip()
    receiver_acc = request.form['receiver_account'].strip()
    upi_pin = request.form['upi_pin'].strip()

    try:
        amount = float(request.form['amount'])
    except:
        flash("⚠️ Invalid transfer amount!")
        return redirect('/dashboard')

    # Validate UPI PIN
    if upi_pin != sender[11]:
        flash("❌ Incorrect UPI PIN!")
        return redirect('/dashboard')

    # Validate balance
    if amount <= 0 or amount > float(sender[10] or 0.0):
        flash("⚠️ Invalid or insufficient balance!")
        return redirect('/dashboard')

    # Check receiver exists and name matches
    receiver = get_user_by_account(receiver_acc)
    if not receiver or receiver[3].lower() != receiver_name.lower():
        flash("❌ Receiver not found or name mismatch!")
        return redirect('/dashboard')

    # Create pending transfer (do not commit yet)
    pending_transfers[sender[1]] = {
        "sender_acc": sender[0],
        "receiver_acc": receiver[0],
        "receiver_name": receiver[3],
        "amount": amount,
        "created_at": time.time()
    }

    # Generate OTP, store keyed by sender email
    identifier = sender_email
    otp = generate_and_store_otp(identifier, purpose="transfer", meta={"sender_username": sender[1]})

    # Send OTP to sender's email
    subject = "MyBank - Transfer Confirmation OTP"
    body = f"Your MyBank transfer OTP is: {otp}\n\nThis code will expire in 5 minutes."
    send_email(identifier, subject, body)

    flash("✅ OTP sent to your registered email. Enter it to confirm the transfer.")
    return render_template('verify_transfer_otp.html', email_hint=identifier)

# ---------------- VERIFY TRANSFER OTP (perform pending transfer) ----------------
@app.route('/verify_transfer_otp', methods=['POST'])
def verify_transfer_otp():
    if 'user' not in session:
        return redirect('/login')

    entered_otp = request.form.get('otp', '').strip()
    user = get_user(session['user'])
    identifier = user[4]  # email

    ok, msg, meta = verify_otp(identifier, entered_otp, expected_purpose="transfer")
    if not ok:
        flash("❌ " + msg)
        return render_template('verify_transfer_otp.html', email_hint=identifier)

    pending = pending_transfers.pop(user[1], None)
    if not pending:
        flash("❌ No pending transfer found or already processed.")
        return redirect('/dashboard')

    sender = get_user(user[1])  # re-fetch
    receiver = get_user_by_account(pending["receiver_acc"])
    amount = pending["amount"]

    # Re-check balance
    if amount > float(sender[10] or 0.0):
        flash("❌ Insufficient balance. Transfer cancelled.")
        return redirect('/dashboard')

    sender_new = float(sender[10] or 0.0) - amount
    receiver_new = float(receiver[10] or 0.0) + amount

    timestamp = now()
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (sender_new, sender[0]))
        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (receiver_new, receiver[0]))
        cur.execute("INSERT INTO transactions (account_number, type, amount, receiver, date) VALUES (?, ?, ?, ?, ?)",
                    (sender[0], "Transfer", amount, receiver[0], timestamp))
        cur.execute("INSERT INTO transactions (account_number, type, amount, receiver, date) VALUES (?, ?, ?, ?, ?)",
                    (receiver[0], "Received", amount, sender[0], timestamp))
        conn.commit()

    app.logger.info(f"Transfer complete: {amount} from {sender[0]} to {receiver[0]} at {timestamp}")
    flash(f"✅ ₹{amount:.2f} transferred successfully to {pending['receiver_name']}!")
    return redirect('/dashboard')

# Set/Reset UPI PIN (via Email OTP) and profile upload

# ---------------- SET / RESET UPI PIN (via Email OTP) ---------------- #
@app.route('/set_upi_pin', methods=['GET', 'POST'])
def set_upi_pin():
    if 'user' not in session:
        return redirect('/login')

    user = get_user(session['user'])
    user_email = user[4]  # email column

    if request.method == 'POST':
        old_pin = request.form['old_pin'].strip()
        new_pin = request.form['new_pin'].strip()
        confirm_pin = request.form['confirm_pin'].strip()

        # Validate old UPI PIN
        if old_pin != user[11]:
            flash("❌ Old UPI PIN is incorrect!")
            return redirect('/set_upi_pin')

        # Validate new UPI PIN format
        if len(new_pin) != 6 or not new_pin.isdigit():
            flash("⚠️ New UPI PIN must be exactly 6 digits.")
            return redirect('/set_upi_pin')

        if new_pin != confirm_pin:
            flash("❌ New PIN and Confirm PIN do not match.")
            return redirect('/set_upi_pin')

        # Generate & store OTP
        otp = generate_and_store_otp(
            user_email,
            purpose="set_upi_pin",
            meta={"username": user[1], "new_pin": new_pin}
        )

        # Email the OTP
        subject = "MyBank – UPI PIN Change Verification OTP"
        body = (
            f"Hello {user[3]},\n\n"
            f"Your OTP for changing your MyBank UPI PIN is: {otp}\n"
            f"This OTP expires in 5 minutes.\n\n"
            f"If you did not request this, please ignore this email."
        )
        send_email(user_email, subject, body)

        flash("📩 OTP sent to your registered email.")
        return render_template("verify_upi_pin_otp.html", email_hint=user_email)

    return render_template("set_upi_pin.html", user=user)

@app.route('/verify_upi_pin_otp', methods=['POST'])
def verify_upi_pin_otp():
    if 'user' not in session:
        return redirect('/login')

    user = get_user(session['user'])
    identifier = user[4]  # email
    entered_otp = request.form['otp'].strip()

    ok, msg, meta = verify_otp(identifier, entered_otp, expected_purpose="set_upi_pin")

    if not ok:
        flash("❌ " + msg)
        return render_template("verify_upi_pin_otp.html", email_hint=identifier)

    new_pin = meta.get("new_pin")
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET upi_pin=? WHERE email=?", (new_pin, identifier))
        conn.commit()

    flash("🔐 UPI PIN updated successfully!")
    return redirect('/dashboard')

#------------------Admin-login---------------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        admin_user = request.form['username']
        admin_pass = request.form['password']

        # Hardcoded (or use database later)
        if admin_user == "agrahari2025Nova" and admin_pass == "7081578058#Pa":
            session['admin'] = True
            flash("Admin login successful!")
            return redirect('/admin_dashboard')

        flash("Invalid admin credentials")
        return redirect('/admin_login')

    return render_template('admin_login.html')

#--------------Admin Dashboard-----------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin_login')

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT account_number, name, email, phone, balance FROM users")
        all_users = cur.fetchall()

    return render_template("admin_dashboard.html", users=all_users)

#--------------Admin Deposit-----------------------
# ---------------- ADMIN DEPOSIT (STEP 1: ASK PASSWORD) ----------------
@app.route('/admin_deposit_request', methods=['POST'])
def admin_deposit_request():
    if 'admin' not in session:
        return redirect('/admin_login')

    account_no = request.form['account_number']
    amount = request.form['amount']

    # Pass data to confirmation page
    return render_template(
        "admin_deposit_confirm.html",
        account_no=account_no,
        amount=amount
    )
# ---------------- ADMIN DEPOSIT (STEP 2: VERIFY PASSWORD & DEPOSIT) ----------------
@app.route('/admin_deposit_confirm', methods=['POST'])
def admin_deposit_confirm():
    if 'admin' not in session:
        return redirect('/admin_login')

    account_no = request.form['account_number']
    amount = float(request.form['amount'])
    admin_password = request.form['admin_password']

    # Replace with your admin password
    if admin_password != "7081578058#Pa":
        flash("❌ Incorrect admin password!")
        return redirect('/admin_dashboard')

    user = get_user_by_account(account_no)
    if not user:
        flash("❌ Account not found!")
        return redirect('/admin_dashboard')

    new_balance = float(user[10]) + amount

    timestamp = now()

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (new_balance, account_no))
        cur.execute("""
            INSERT INTO transactions (account_number, type, amount, receiver, date) 
            VALUES (?, ?, ?, ?, ?)
        """, (account_no, "Admin Deposit", amount, "BANK-ADMIN", timestamp))
        conn.commit()

    flash(f"✅ Successfully deposited ₹{amount} to {user[3]}'s account!")
    return redirect('/admin_dashboard')

# ---------------- ADMIN VIEW ALL TRANSACTIONS WITH FILTERS ----------------
@app.route('/admin_transactions', methods=['GET', 'POST'])
def admin_transactions():
    if 'admin' not in session:
        return redirect('/admin_login')

    query = "SELECT id, account_number, type, amount, receiver, date FROM transactions WHERE 1=1"
    params = []

    if request.method == 'POST':
        txn_type = request.form.get('txn_type')
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        min_amount = request.form.get('min_amount')
        max_amount = request.form.get('max_amount')
        acc_search = request.form.get('acc_search')

        # Type filter
        if txn_type and txn_type != "All":
            query += " AND type = ?"
            params.append(txn_type)

        # Date From
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        # Date To
        if date_to:
            query += " AND date <= ?"
            params.append(date_to + " 23:59:59")

        # Min Amount
        if min_amount:
            query += " AND amount >= ?"
            params.append(float(min_amount))

        # Max Amount
        if max_amount:
            query += " AND amount <= ?"
            params.append(float(max_amount))

        # Account search
        if acc_search:
            query += " AND account_number LIKE ?"
            params.append(f"%{acc_search}%")

    query += " ORDER BY id DESC"

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        all_txn = cur.fetchall()

    return render_template("admin_transactions.html", transactions=all_txn)

# ---------------- PROFILE UPLOAD ----------------
@app.route('/upload_profile', methods=['POST'])
def upload_profile():
    if 'user' not in session:
        return redirect('/login')

    user = get_user(session['user'])

    if 'profile_pic' not in request.files:
        flash("⚠️ No file selected.")
        return redirect('/dashboard')

    file = request.files['profile_pic']
    if file.filename == '':
        flash("⚠️ Please select an image file.")
        return redirect('/dashboard')

    if file and allowed_file(file.filename):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = secure_filename(user[1] + "_" + file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # verify real image
        if not is_image_file(filepath):
            try:
                os.remove(filepath)
            except: pass
            flash("❌ Uploaded file is not a valid image.")
            return redirect('/dashboard')

        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET profile=? WHERE username=?", (filename, user[1]))
            conn.commit()

        flash("🖼️ Profile picture updated successfully!")
        return redirect('/dashboard')

    flash("❌ Only PNG, JPG, or JPEG files are allowed.")
    return redirect('/dashboard')

# Mini-statement PDF with watermark, logout, and run

@app.route('/download_statement')
def download_statement():
    if 'user' not in session:
        flash("Session expired. Please log in.")
        return redirect('/login')

    user = get_user(session['user'])
    account_number = user[0]

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, type, amount, receiver, date 
            FROM transactions 
            WHERE account_number=? 
            ORDER BY id DESC 
            LIMIT 20
        """, (account_number,))
        transactions = cur.fetchall()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf_width, pdf_height = letter
    pdf.setTitle("Mini Statement - Nova-Bank")

    # WATERMARK
    watermark_text = "Nova-Bank"
    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 80)
    # light grey simulate opacity
    pdf.setFillColorRGB(0.85, 0.85, 0.85)
    pdf.translate(pdf_width / 2, pdf_height / 2)
    pdf.rotate(45)
    pdf.drawCentredString(0, 0, watermark_text)
    pdf.restoreState()

    # HEADER
    pdf.setFont("Helvetica-Bold", 22)
    pdf.setFillColor(colors.HexColor("#0052CC"))
    pdf.drawString(240, 760, "■ Nova-Bank")

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, 720, "Official Mini Statement")

    # USER INFO
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 690, "Name:")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(120, 690, user[3])

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 670, "Account No:")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(140, 670, str(account_number))

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, 650, "Date:")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(100, 650, now())

    # TABLE
    table_data = [["Txn ID", "Type", "Amount (₹)", "Receiver", "Date"]]
    for txn in transactions:
        table_data.append([
            str(txn[0]),
            txn[1],
            f"{txn[2]:.2f}",
            txn[3] if txn[3] else "-",
            txn[4]
        ])

    table = Table(table_data, colWidths=[60, 80, 100, 120, 150])
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.7, colors.grey),
    ])
    table.setStyle(style)
    table.wrapOn(pdf, 50, 500)
    table.drawOn(pdf, 50, 500)

    # FOOTER
    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawString(50, 80, "This is a system-generated statement. No physical signature required.")
    pdf.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="MiniStatement.pdf",
        mimetype="application/pdf"
    )

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("👋 Logged out successfully!")
    return redirect('/login')

# ---------------- RUN APP ----------------
if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        print("Database not found. Run setup_db.py first to create the database.")
    app.run(debug=True)
