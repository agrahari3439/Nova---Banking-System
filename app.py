from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3, os, random, time
from datetime import datetime
from werkzeug.utils import secure_filename

# ===== Twilio Setup =====
try:
    from twilio.rest import Client
except Exception:
    Client = None  # allow app to run even if Twilio isn't installed

otp_storage = {}  # { phone: { 'otp': 123456, 'expires': timestamp } }

app = Flask(__name__)
app.secret_key = "supersecretkey"
DB_NAME = "database.db"

# ---------------- Twilio credentials ---------------- #
# ⚠️ Replace with your real Twilio credentials (from https://www.twilio.com/console)
TWILIO_SID = os.getenv("TWILIO_SID", "AC5c3ae57eff6358cd03ed03c9416a1652")
TWILIO_AUTH = os.getenv("TWILIO_AUTH", "6772c2ce7399e1ab5b3ec50848eb7287")
TWILIO_WHATSAPP = os.getenv("TWILIO_WHATSAPP", "whatsapp:+14155238886")  # Twilio Sandbox number

# ---------------- Twilio connection check ---------------- #
twilio_client = None
if Client:
    try:
        twilio_client = Client(TWILIO_SID, TWILIO_AUTH)
        account = twilio_client.api.accounts(TWILIO_SID).fetch()
        print(f"✅ Twilio connected successfully — Account: {account.friendly_name}")
    except Exception as e:
        print("⚠️ Twilio connection failed — messages will be printed locally instead.")
        print("Error details:", e)
        twilio_client = None
else:
    print("ℹ️ Twilio library not installed — messages will be printed locally.")

# ---------------- WhatsApp message function ---------------- #
def send_whatsapp_message(phone: str, message: str):
    """Send WhatsApp message via Twilio. If fails, print to console."""
    try:
        phone = str(phone).strip()
        # Ensure correct format
        if not phone.startswith("+"):
            phone = f"+91{phone}"  # default country code India

        whatsapp_to = f"whatsapp:{phone}"

        if not twilio_client:
            print("📢 [Simulated WhatsApp Message]")
            print(f"To: {whatsapp_to}")
            print("Message:\n" + message)
            print("--------------------------------------------------")
            return

        print(f"📤 Sending WhatsApp message to {whatsapp_to}...")
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP,
            to=whatsapp_to,
            body=message
        )
        print(f"✅ WhatsApp message sent successfully to {phone}")

    except Exception as e:
        print(f"❌ WhatsApp message failed — printing instead:\n{e}")
        print("--------------------------------------------------")
        print(f"To: whatsapp:{phone}")
        print("Message:\n" + message)
        print("--------------------------------------------------")

# ---------------- DATABASE INITIALIZATION ---------------- #
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            account_number TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            dob TEXT NOT NULL,
            age INTEGER NOT NULL,
            address TEXT,
            profile TEXT,
            balance REAL DEFAULT 0.0,
            upi_pin TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT,
            type TEXT,
            amount REAL,
            receiver TEXT,
            date TEXT,
            FOREIGN KEY (account_number) REFERENCES users(account_number)
        )''')
        conn.commit()

# ---------------- HELPER FUNCTIONS ---------------- #
def generate_account_number():
    return str(random.randint(10**9, (10**10) - 1))

def get_user(identifier):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM users 
            WHERE username = ? OR email = ? OR phone = ?
        """, (identifier, identifier, identifier))
        return cur.fetchone()

# ---------------- ROUTES ---------------- #
@app.route('/')
def home():
    return redirect('/login')

# ---------------- REGISTER ---------------- #
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        dob = request.form['dob']
        address = request.form['address']
        username = request.form['username']
        password = request.form['password']
        upi_pin = request.form['upi_pin']

        birth_year = int(dob.split('-')[0])
        age = datetime.now().year - birth_year
        if age < 18:
            flash("❌ You must be at least 18 years old to open an account.")
            return redirect('/register')

        account_number = generate_account_number()
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            try:
                cur.execute('''INSERT INTO users 
                (account_number, username, password, name, email, phone, dob, age, address, profile, balance, upi_pin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (account_number, username, password, name, email, phone, dob, age, address, 'default.png', 0.0, upi_pin))
                conn.commit()
                flash(f"✅ Account created successfully! Your Account Number: {account_number}")
                return redirect('/login')
            except sqlite3.IntegrityError:
                flash("⚠️ Username, email, or phone already exists.")
                return redirect('/register')
    return render_template('register.html')

# ---------------- LOGIN ---------------- #
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
    return render_template('login.html', lock_remaining=None)

# ---------------- DASHBOARD ---------------- #
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        flash("⏳ Your session expired. Please log in again.")
        return redirect('/login')

    user = get_user(session['user'])
    user = list(user)
    user[10] = float(user[10] or 0.0)

    # Default filters
    query = "SELECT * FROM transactions WHERE account_number = ?"
    params = [user[0]]

    if request.method == 'POST':
        # Get filters from form
        txn_type = request.form.get('txn_type')
        date_from = request.form.get('date_from')
        date_to = request.form.get('date_to')
        min_amount = request.form.get('min_amount')
        max_amount = request.form.get('max_amount')
        account_search = request.form.get('account_search')

        # Build SQL filters dynamically
        if txn_type and txn_type != "All":
            query += " AND type = ?"
            params.append(txn_type)

        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date <= ?"
            params.append(date_to + " 23:59:59")

        if min_amount:
            query += " AND amount >= ?"
            params.append(float(min_amount))

        if max_amount:
            query += " AND amount <= ?"
            params.append(float(max_amount))

        if account_search:
            query += " AND receiver LIKE ?"
            params.append(f"%{account_search}%")

    query += " ORDER BY id DESC"

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        transactions = cur.fetchall()

    return render_template('dashboard.html', user=user, transactions=transactions)

# ---------------- DEPOSIT ---------------- #
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
                    (user[0], "Deposit", amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    msg = (
        f"💰 *Deposit Successful!*\n\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"New Balance: ₹{new_balance:.2f}\n\n"
        f"Thank you for banking with MyBank 🏦"
    )
    send_whatsapp_message(user[5], msg)
    flash(f"💰 ₹{amount:.2f} deposited successfully!")
    return redirect('/dashboard')

# ---------------- WITHDRAW MONEY ---------------- #
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

    # Check UPI PIN
    if upi_pin != user[11]:
        flash("❌ Incorrect UPI PIN!")
        return redirect('/dashboard')

    # Check amount
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
                    (user[0], "Withdraw", amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    # WhatsApp alert
    msg = (
        f"🏧 *Withdrawal Alert!*\n\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Remaining Balance: ₹{new_balance:.2f}\n\n"
        f"MyBank 🏦 — Keep your UPI PIN secure 🔒"
    )
    send_whatsapp_message(user[5], msg)

    flash(f"💸 ₹{amount:.2f} withdrawn successfully!")
    return redirect('/dashboard')


# ---------------- TRANSFER MONEY ---------------- #
@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user' not in session:
        return redirect('/login')

    sender = get_user(session['user'])
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
    if amount <= 0 or amount > sender[10]:
        flash("⚠️ Invalid or insufficient balance!")
        return redirect('/dashboard')

    # Check receiver
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE account_number=?", (receiver_acc,))
        receiver = cur.fetchone()

        if not receiver or receiver[3].lower() != receiver_name.lower():
            flash("❌ Receiver not found or name mismatch!")
            return redirect('/dashboard')

        # Update balances
        new_sender_balance = sender[10] - amount
        new_receiver_balance = receiver[10] + amount

        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (new_sender_balance, sender[0]))
        cur.execute("UPDATE users SET balance=? WHERE account_number=?", (new_receiver_balance, receiver[0]))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("INSERT INTO transactions (account_number, type, amount, receiver, date) VALUES (?, ?, ?, ?, ?)",
                    (sender[0], "Transfer", amount, receiver[0], now))
        cur.execute("INSERT INTO transactions (account_number, type, amount, receiver, date) VALUES (?, ?, ?, ?, ?)",
                    (receiver[0], "Received", amount, sender[0], now))
        conn.commit()

    # WhatsApp alerts
    sender_msg = (
        f"💸 *Transfer Successful!*\n\n"
        f"To: {receiver_name}\n"
        f"Account No: {receiver_acc}\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Date: {now}\n"
        f"Remaining Balance: ₹{new_sender_balance:.2f}\n\n"
        f"Thank you for banking with MyBank 🏦"
    )
    send_whatsapp_message(sender[5], sender_msg)

    receiver_msg = (
        f"💰 *Money Received!*\n\n"
        f"From: {sender[3]}\n"
        f"Account No: {sender[0]}\n"
        f"Amount: ₹{amount:.2f}\n"
        f"Date: {now}\n"
        f"New Balance: ₹{new_receiver_balance:.2f}\n\n"
        f"MyBank 🏦"
    )
    send_whatsapp_message(receiver[5], receiver_msg)

    flash(f"✅ ₹{amount:.2f} transferred successfully to {receiver_name}!")
    return redirect('/dashboard')

# ---------------- SET/RESET UPI PIN (with OTP) ---------------- #
@app.route('/set_upi_pin', methods=['GET', 'POST'])
def set_upi_pin():
    if 'user' not in session:
        return redirect('/login')

    user = get_user(session['user'])

    if request.method == 'POST':
        new_pin = request.form['new_pin']
        confirm_pin = request.form['confirm_pin']

        # Validate PINs
        if len(new_pin) != 6 or not new_pin.isdigit():
            flash("⚠️ UPI PIN must be 6 digits.")
            return redirect('/set_upi_pin')

        if new_pin != confirm_pin:
            flash("❌ UPI PINs do not match.")
            return redirect('/set_upi_pin')

        # Step 1️⃣ Generate OTP
        otp = random.randint(100000, 999999)
        otp_storage[user[5]] = {'otp': otp, 'expires': time.time() + 300, 'new_pin': new_pin}  # store OTP + new pin

        # Step 2️⃣ Send OTP via WhatsApp
        msg = (
            f"🔐 *MyBank UPI PIN Reset OTP*\n\n"
            f"Your OTP is: {otp}\n"
            f"It expires in 5 minutes.\n\n"
            f"If you did not request this, please ignore this message."
        )
        send_whatsapp_message(user[5], msg)

        flash("✅ OTP sent to your registered WhatsApp number!")
        return render_template('verify_upi_otp.html', phone=user[5])

    return render_template('set_upi_pin.html', user=user)

# ---------------- VERIFY OTP FOR UPI PIN ---------------- #
@app.route('/verify_upi_otp', methods=['POST'])
def verify_upi_otp():
    phone = request.form['phone']
    entered_otp = request.form['otp']

    if phone not in otp_storage:
        flash("⚠️ OTP expired or not requested.")
        return redirect('/set_upi_pin')

    otp_data = otp_storage[phone]

    # Check expiry
    if time.time() > otp_data['expires']:
        del otp_storage[phone]
        flash("⚠️ OTP expired. Please request again.")
        return redirect('/set_upi_pin')

    # Validate OTP
    if str(otp_data['otp']) == entered_otp:
        new_pin = otp_data['new_pin']

        # ✅ Update the UPI PIN in the database
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET upi_pin = ? WHERE phone = ?", (new_pin, phone))
            conn.commit()

        del otp_storage[phone]

        flash("🔑 UPI PIN updated successfully!")
        return redirect('/dashboard')
    else:
        flash("❌ Incorrect OTP.")
        return render_template('verify_upi_otp.html', phone=phone)


# ---------------- FORGOT PASSWORD ---------------- #
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        phone = request.form['phone'].strip()

        # Check if phone exists
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE phone=?", (phone,))
            user = cur.fetchone()

        if not user:
            flash("❌ Phone number not registered!")
            return redirect('/forgot_password')

        # Generate OTP
        otp = random.randint(100000, 999999)
        otp_storage[phone] = {'otp': otp, 'expires': time.time() + 300}  # 5 minutes expiry

        # Send OTP via WhatsApp
        msg = (
            f"🔐 MyBank Password Reset OTP: {otp}\n"
            f"It expires in 5 minutes.\n"
            f"If you didn’t request this, please ignore this message."
        )
        send_whatsapp_message(phone, msg)

        flash("✅ OTP sent to your WhatsApp number!")
        return render_template('verify_otp.html', phone=phone)

    return render_template('forgot_password.html')


# ---------------- VERIFY OTP ---------------- #
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    phone = request.form['phone'].strip()
    entered_otp = request.form['otp'].strip()

    if phone not in otp_storage:
        flash("⚠️ OTP expired or not requested!")
        return redirect('/forgot_password')

    otp_data = otp_storage[phone]

    if time.time() > otp_data['expires']:
        del otp_storage[phone]
        flash("⚠️ OTP expired! Please request a new one.")
        return redirect('/forgot_password')

    if str(otp_data['otp']) == entered_otp:
        del otp_storage[phone]
        flash("✅ OTP verified! You can now reset your password.")
        return render_template('reset_password.html', phone=phone)
    else:
        flash("❌ Incorrect OTP!")
        return render_template('verify_otp.html', phone=phone)


# ---------------- RESET PASSWORD ---------------- #
@app.route('/reset_password', methods=['POST'])
def reset_password():
    phone = request.form['phone'].strip()
    new_password = request.form['new_password']

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password=? WHERE phone=?", (new_password, phone))
        conn.commit()

    flash("✅ Password updated successfully! Please log in.")
    return redirect('/login')


# ---------------- TEST TWILIO ROUTE ---------------- #
@app.route('/test_twilio')
def test_twilio():
    test_number = "+91YOURNUMBER"  # <-- Replace this with your WhatsApp number
    msg = "🧩 This is a test WhatsApp message from MyBank Flask app!"
    send_whatsapp_message(test_number, msg)
    return "✅ Test message sent — check your WhatsApp or console output."

# ---------------- PROFILE PICTURE UPLOAD ---------------- #
UPLOAD_FOLDER = os.path.join("static", "profile_pics")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    """Check if file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload_profile', methods=['POST'])
def upload_profile():
    if 'user' not in session:
        return redirect('/login')

    user = get_user(session['user'])

    # Check if a file was uploaded
    if 'profile_pic' not in request.files:
        flash("⚠️ No file selected.")
        return redirect('/dashboard')

    file = request.files['profile_pic']

    if file.filename == '':
        flash("⚠️ Please select an image file.")
        return redirect('/dashboard')

    if file and allowed_file(file.filename):
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # Create a unique filename (username_filename)
        filename = secure_filename(user[1] + "_" + file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Save filename in DB
        with sqlite3.connect(DB_NAME) as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET profile=? WHERE username=?", (filename, user[1]))
            conn.commit()

        flash("🖼️ Profile picture updated successfully!")
    else:
        flash("❌ Only PNG, JPG, or JPEG files are allowed.")

    return redirect('/dashboard')

# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    if 'user' in session:
        username = session['user']
        session.pop('user', None)
        flash("👋 Logged out successfully!")

        # Optional: WhatsApp logout alert
        # user = get_user(username)
        # if user:
        #     msg = f"👋 You have successfully logged out of MyBank account ({user[1]}). Stay secure and never share your password!"
        #     send_whatsapp_message(user[5], msg)

    return redirect('/login')

# ---------------- RUN APP ---------------- #
if __name__ == '__main__':
    if not os.path.exists(DB_NAME):
        init_db()
    app.run(debug=True)


