# 🏦 MyBank – Secure Banking Web App (Flask + SQLite + Twilio WhatsApp)

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-Framework-black?logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue?logo=sqlite)
![Twilio](https://img.shields.io/badge/Twilio-WhatsApp-green?logo=whatsapp)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple?logo=bootstrap)
![License](https://img.shields.io/badge/License-MIT-yellow)

> A full-featured **Bank Management Web App** built using Flask and SQLite, with real-time **WhatsApp notifications via Twilio API**.

---

## ✨ Features

### 👤 User Account Management
- Register new accounts with **age verification (18+)**
- Login using **Username / Email / Phone**
- Upload or update profile picture  
- Secure logout

### 💸 Banking Operations
- **Deposit Money**
- **Withdraw Money** (requires UPI PIN)
- **Transfer Money** (account to account)
- **Transaction History** (Deposit, Withdraw, Transfer, Received)
- View all transaction details — amount, date, type, sender/receiver

### 🔐 Security & Authentication
- Set / Reset **6-digit UPI PIN** (with OTP verification)
- Reset password via **WhatsApp OTP verification**
- Verifies receiver name and account number before transfers

### 💬 WhatsApp Notifications (Powered by Twilio)
- Instant alerts for:
  - Deposit confirmations 💰
  - Withdrawals 🏧
  - Transfers 💸
  - Received funds 💵
  - OTPs for password or UPI reset 🔐

---

## 🧰 Tech Stack

| Layer | Technology |
|--------|-------------|
| **Backend** | Flask (Python) |
| **Database** | SQLite3 |
| **Frontend** | HTML, CSS, Bootstrap 5, Jinja2 |
| **Messaging API** | Twilio WhatsApp |
| **File Handling** | Werkzeug (secure file uploads) |

---

## 📁 Project Structure

MyBank/
│
├── app.py # Main Flask application
├── database.db # SQLite database file
│
├── templates/ # HTML templates
│ ├── base.html
│ ├── login.html
│ ├── register.html
│ ├── dashboard.html
│ ├── set_upi_pin.html
│ ├── forgot_password.html
│ ├── verify_otp.html
│ └── reset_password.html
│
├── static/
│ ├── css/
│ │ └── style.css
│ └── profile_pics/
│ ├── default.png
│ └── (uploaded profile pictures)
│
└── README.md

🧩 Future Enhancements

📊 Download transaction history as CSV or PDF

🔔 Email notifications alongside WhatsApp

🧾 Admin dashboard for managing users

🧠 AI-powered fraud detection alerts
