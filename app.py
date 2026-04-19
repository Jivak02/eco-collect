import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, abort
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from models import db, User, Request

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ecocollect-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecocollect.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

# ─── Hardcoded admin credentials ────────────────────────────────────────
ADMIN_EMAIL = 'admin'
ADMIN_PASSWORD = 'admin123'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─── Admin auth decorator ───────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ─── Landing page ────────────────────────────────────────────────────────
@app.route('/')
def index():
    total_pickups = Request.query.count()
    recycled = Request.query.filter_by(status='Recycled').count()
    total_qty = db.session.query(db.func.sum(Request.quantity)).scalar() or 0
    co2_saved = round(total_qty * 0.8, 1)  # rough estimate
    recycle_rate = int((recycled / total_pickups * 100)) if total_pickups else 89
    return render_template('index.html',
                           total_pickups=total_pickups or 142,
                           co2_saved=co2_saved or 3.8,
                           recycle_rate=recycle_rate)


# ─── Auth routes ─────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()

        if not email or not password:
            flash('Email and password are required.', 'danger')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid email or password.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('is_admin', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ─── User Dashboard ─────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user_requests = Request.query.filter_by(user_id=current_user.id)\
        .order_by(Request.submitted_at.desc()).all()
    total = len(user_requests)
    total_qty = sum(r.quantity for r in user_requests)
    co2 = round(total_qty * 0.8, 1)
    recycled = sum(1 for r in user_requests if r.status == 'Recycled')
    points = total_qty * 10
    return render_template('dashboard.html',
                           requests=user_requests,
                           total=total,
                           co2=co2,
                           recycled=recycled,
                           points=points)


# ─── New Pickup Request ─────────────────────────────────────────────────
@app.route('/request/new', methods=['GET', 'POST'])
@login_required
def new_request():
    if request.method == 'POST':
        waste_type = request.form.get('waste_type')
        quantity = request.form.get('quantity', type=int)
        area = request.form.get('area', '').strip()
        pickup_date_str = request.form.get('pickup_date')
        time_slot = request.form.get('time_slot')
        notes = request.form.get('notes', '').strip()

        if not all([waste_type, quantity, area, pickup_date_str, time_slot]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('new_request'))

        try:
            pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format.', 'danger')
            return redirect(url_for('new_request'))

        centers = [
            'EcoCollect Central Hub',
            'GreenTech Recycling Center',
            'UrbanMine E-Waste Facility',
            'CleanEarth Processing Unit',
            'ReCircle Collection Point'
        ]
        import random
        assigned = random.choice(centers)

        req = Request(
            user_id=current_user.id,
            waste_type=waste_type,
            quantity=quantity,
            area=area,
            pickup_date=pickup_date,
            time_slot=time_slot,
            notes=notes,
            assigned_center=assigned
        )
        db.session.add(req)
        db.session.commit()
        flash('Pickup request submitted successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('new_request.html')


# ─── Collection Centers ─────────────────────────────────────────────────
@app.route('/centers')
@login_required
def centers():
    centers_data = [
        {
            'name': 'EcoCollect Central Hub',
            'address': '12 Green Avenue, Hinjewadi IT Park, Pune',
            'distance': 2.3,
            'categories': ['Smartphones', 'Laptops', 'Batteries', 'Circuit Boards'],
            'hours': 'Mon–Sat: 9:00 AM – 6:00 PM',
            'coords': (35, 45)
        },
        {
            'name': 'GreenTech Recycling Center',
            'address': '45 EON Free Zone, Kharadi, Pune',
            'distance': 5.1,
            'categories': ['Printers', 'Cables', 'Laptops', 'Desktops'],
            'hours': 'Mon–Fri: 8:00 AM – 5:00 PM',
            'coords': (60, 30)
        },
        {
            'name': 'UrbanMine E-Waste Facility',
            'address': '78 MIDC Industrial Area, Pimpri-Chinchwad, Pune',
            'distance': 8.7,
            'categories': ['All Categories'],
            'hours': 'Mon–Sat: 7:00 AM – 7:00 PM',
            'coords': (25, 65)
        },
        {
            'name': 'CleanEarth Processing Unit',
            'address': '22 North Main Road, Koregaon Park, Pune',
            'distance': 3.4,
            'categories': ['Batteries', 'Circuit Boards', 'Smartphones'],
            'hours': 'Tue–Sun: 10:00 AM – 6:00 PM',
            'coords': (70, 55)
        },
        {
            'name': 'ReCircle Collection Point',
            'address': '9 Magarpatta Road, Hadapsar, Pune',
            'distance': 4.2,
            'categories': ['Cables', 'Chargers', 'Tablets', 'Printers'],
            'hours': 'Mon–Sun: 9:00 AM – 8:00 PM',
            'coords': (50, 70)
        }
    ]
    return render_template('centers.html', centers=centers_data)


# ─── Track Request ───────────────────────────────────────────────────────
@app.route('/track/<int:request_id>')
@login_required
def track(request_id):
    req = Request.query.get_or_404(request_id)
    if req.user_id != current_user.id and not session.get('is_admin'):
        abort(403)

    status_order = ['Pending', 'Collected', 'Processing', 'Recycled']
    steps = [
        {'label': 'Request Submitted', 'status': 'Pending'},
        {'label': 'Pickup Confirmed', 'status': 'Pending'},
        {'label': 'Collected by Agent', 'status': 'Collected'},
        {'label': 'Segregation & Processing', 'status': 'Processing'},
        {'label': 'Recycled', 'status': 'Recycled'},
    ]

    current_idx = status_order.index(req.status) if req.status in status_order else 0
    for i, step in enumerate(steps):
        step_idx = status_order.index(step['status']) if step['status'] in status_order else 0
        step['completed'] = step_idx <= current_idx

    return render_template('track.html', req=req, steps=steps)


# ─── Admin routes ────────────────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Welcome, Admin!', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin credentials.', 'danger')
        return redirect(url_for('admin_login'))
    return render_template('admin_login.html')


@app.route('/admin')
@admin_required
def admin_dashboard():
    all_requests = Request.query.order_by(Request.submitted_at.desc()).all()
    total = len(all_requests)
    pending = sum(1 for r in all_requests if r.status == 'Pending')
    recycled = sum(1 for r in all_requests if r.status == 'Recycled')

    # Data for Chart.js
    waste_types = ['Smartphone/Tablet', 'Laptop/Desktop', 'Batteries',
                   'Circuit Boards', 'Printer/Scanner', 'Cables/Chargers', 'Other']
    chart_data = {wt: 0 for wt in waste_types}
    for r in all_requests:
        if r.waste_type in chart_data:
            chart_data[r.waste_type] += 1

    return render_template('admin.html',
                           requests=all_requests,
                           total=total,
                           pending=pending,
                           recycled=recycled,
                           chart_labels=list(chart_data.keys()),
                           chart_values=list(chart_data.values()))


@app.route('/admin/update_status/<int:request_id>', methods=['POST'])
@admin_required
def update_status(request_id):
    req = Request.query.get_or_404(request_id)
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Collected', 'Processing', 'Recycled']:
        req.status = new_status
        db.session.commit()
        flash(f'Request #{req.id} status updated to {new_status}.', 'success')
    else:
        flash('Invalid status.', 'danger')
    return redirect(url_for('admin_dashboard'))


# ─── Init DB ─────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
