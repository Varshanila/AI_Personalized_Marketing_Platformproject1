# app_aws_full.py - MERGED AWS + MOCK ADMIN VERSION
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from uuid import uuid4
import boto3
import hashlib

app = Flask(__name__)
app.secret_key = 'aws-ai-marketing-platform-2026-super-secret-key'

# ---------------- AWS CONFIG ---------------- #
REGION = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client('sns', region_name=REGION)

# DynamoDB Tables (must exist in your AWS account)
users_table = dynamodb.Table('Users')
admin_table = dynamodb.Table('Admin')
products_table = dynamodb.Table('Products')
campaigns_table = dynamodb.Table('Campaigns')

# SNS Topic ARN (replace with your ARN)
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:539247489202:aws_ai'

def send_sns_notification(subject, message):
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
    except Exception as e:
        print(f"SNS Error: {e}")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- MOCK DATABASES ---------------- #
mock_users_db = {
    " ": {"password": generate_password_hash(" "), "name": "Varsha", "role": "user"}
}
mock_admin_db = {"admin@company.com": generate_password_hash("admin2026")}
mock_campaigns_db = []
mock_products = []

# ---------------- DECORATORS ---------------- #
def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapped

# ---------------- DIRECT ADMIN ACCESS ---------------- #
@app.route("/login_to_dashboard")
@app.route("/admin_direct")
def direct_admin_login():
    session["user_id"] = "admin@company.com"
    session["role"] = "admin"
    return redirect(url_for("admin_home"))

# ---------------- BASIC ROUTES ---------------- #
@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")

@app.route("/about.html")
def about():
    return render_template("about.html")

@app.route("/login.html")
def login():
    return render_template("login.html")

@app.route("/signup.html")
def signup():
    return render_template("signup.html")

# ---------------- USER FLOW ---------------- #
@app.route("/home.html")
@login_required
def home():
    # Try DynamoDB first, else mock
    user_email = session.get("user_id")
    try:
        resp = users_table.get_item(Key={'email': user_email})
        user = resp.get('Item', mock_users_db.get(user_email))
    except:
        user = mock_users_db.get(user_email)
    return render_template("home.html", user=user)

@app.route("/dashboard.html")
@login_required
def dashboard():
    user_email = session.get("user_id")
    try:
        campaigns = campaigns_table.scan()['Items']
        user_campaigns = [c for c in campaigns if c.get('user') == user_email]
    except:
        user_campaigns = [c for c in mock_campaigns_db if c['user'] == user_email]
    return render_template("dashboard.html", campaigns=user_campaigns)

@app.route("/campaign.html")
@login_required
def campaign():
    return render_template("campaign.html")

@app.route("/campaign_history.html")
@login_required
def campaign_history():
    user_email = session.get("user_id")
    try:
        campaigns = campaigns_table.scan()['Items']
        user_campaigns = [c for c in campaigns if c.get('user') == user_email]
    except:
        user_campaigns = [c for c in mock_campaigns_db if c['user'] == user_email]
    return render_template("campaign_history.html", campaigns=user_campaigns)

# ---------------- ADMIN FLOW ---------------- #
@app.route("/admin_login.html")
def admin_login():
    return render_template("admin_login.html")

@app.route("/admin_home.html")
@app.route("/admin_home")
def admin_home():
    if session.get("role") == "admin":
        try:
            users = users_table.scan()['Items']
            campaigns = campaigns_table.scan()['Items']
            products = products_table.scan()['Items']
        except:
            users = mock_users_db
            campaigns = mock_campaigns_db
            products = mock_products
        return render_template("admin_home.html", campaigns=campaigns, users=users, products=products)
    else:
        # Auto login for demo
        session["user_id"] = "admin@company.com"
        session["role"] = "admin"
        return redirect(url_for("admin_home"))

# ---------------- AUTHENTICATION ---------------- #
@app.route("/api/login-submit", methods=["POST"])
def login_submit():
    email = request.form.get("email", "").lower()
    password = request.form.get("password", "")
    try:
        resp = users_table.get_item(Key={'email': email})
        if 'Item' in resp and resp['Item']['password'] == hash_password(password):
            session["user_id"] = email
            session["role"] = "user"
            return redirect(url_for("home"))
    except:
        if email in mock_users_db and check_password_hash(mock_users_db[email]["password"], password):
            session["user_id"] = email
            session["role"] = "user"
            return redirect(url_for("home"))

    try:
        resp = admin_table.get_item(Key={'email': email})
        if 'Item' in resp and resp['Item']['password'] == hash_password(password):
            session["user_id"] = email
            session["role"] = "admin"
            return redirect(url_for("admin_home"))
    except:
        if email in mock_admin_db and check_password_hash(mock_admin_db[email], password):
            session["user_id"] = email
            session["role"] = "admin"
            return redirect(url_for("admin_home"))

    flash("Invalid credentials", "error")
    return redirect(url_for("login"))

@app.route("/api/signup-submit", methods=["POST"])
def signup_submit():
    email = request.form.get("signupEmail", "").lower()
    password = request.form.get("signupPassword", "")
    confirm = request.form.get("confirmPassword", "")
    if password != confirm:
        flash("Passwords do not match", "error")
        return redirect(url_for("signup"))

    try:
        resp = users_table.get_item(Key={'email': email})
        if 'Item' in resp:
            flash("User already exists", "error")
            return redirect(url_for("signup"))
        users_table.put_item(Item={
            'email': email,
            'password': hash_password(password),
            'name': email.split("@")[0],
            'role': 'user',
            'created_at': datetime.now().isoformat()
        })
    except:
        if email in mock_users_db:
            flash("User already exists", "error")
            return redirect(url_for("signup"))
        mock_users_db[email] = {"password": generate_password_hash(password), "name": email.split("@")[0], "role": "user"}

    flash("Signup successful. Please login.", "success")
    return redirect(url_for("login"))

# ---------------- CAMPAIGN GENERATION ---------------- #
@app.route("/api/generate-campaign", methods=["POST"])
@login_required
def generate_campaign():
    interest = request.form.get("userInterests", "")
    campaign = {
        "id": str(uuid4()),
        "user": session["user_id"],
        "interest": interest,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "Active"
    }
    try:
        campaigns_table.put_item(Item=campaign)
        send_sns_notification("New Campaign", f"{session['user_id']} created campaign {interest}")
    except:
        mock_campaigns_db.insert(0, campaign)
    return jsonify(campaign)

# ---------------- PRODUCT CRUD ---------------- #
@app.route('/api/admin/products', methods=['GET'])
@admin_required
def get_products():
    try:
        return jsonify(products_table.scan()['Items'])
    except:
        return jsonify(mock_products)

@app.route('/api/admin/products', methods=['POST'])
@admin_required
def add_product():
    data = request.json
    product = {
        "id": str(uuid4()),
        "name": data["name"],
        "price": data["price"],
        "category": data["category"],
        "description": data.get("description"),
        "icon": data.get("icon", "📦"),
        "badge": data.get("badge"),
        "status": data.get("status", "active"),
        "url": data.get("url"),
        "searches": 0
    }
    try:
        products_table.put_item(Item=product)
    except:
        mock_products.append(product)
    return jsonify({"message": "Product added"}), 201

@app.route('/api/admin/products/<pid>', methods=['PUT'])
@admin_required
def update_product(pid):
    data = request.json
    updated = False
    try:
        products_table.update_item(
            Key={'id': pid},
            UpdateExpression="SET " + ", ".join([f"#{k}=:{k}" for k in data.keys()]),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k,v in data.items()}
        )
        updated = True
    except:
        for p in mock_products:
            if p["id"] == pid:
                p.update(data)
                updated = True
    if updated:
        return jsonify({"message": "Updated"})
    return "Not found", 404

@app.route('/api/admin/products/<pid>', methods=['DELETE'])
@admin_required
def delete_product(pid):
    try:
        products_table.delete_item(Key={'id': pid})
    except:
        global mock_products
        mock_products = [p for p in mock_products if p["id"] != pid]
    return jsonify({"message": "Deleted"})

@app.route('/api/products', methods=['GET'])
@login_required
def user_products():
    try:
        return jsonify([p for p in products_table.scan()['Items'] if p.get("status") == "active"])
    except:
        return jsonify([p for p in mock_products if p.get("status") == "active"])

# ---------------- LOGOUT ---------------- #
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------------- RUN ---------------- #
if __name__ == "__main__":
    print("🚀 AWS AI Marketing Platform running at http://127.0.0.1:5000")
    print("👑 Direct admin demo: http://127.0.0.1:5000/login_to_dashboard")
    app.run(host='0.0.0.0', port=5000, debug=True)
