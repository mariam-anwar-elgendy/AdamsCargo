# ==================== app.py ====================
import os
import threading
import time
import schedule
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   jsonify, send_file, session, flash)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# ==================== CONFIGURATION ====================
app = Flask(__name__, template_folder='templates', static_folder='static')

app.config['SECRET_KEY'] = 'shipping-company-secret-key-2024'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# التعديل الأهم هنا - سنعتمد فقط على متغير البيئة
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("❌ ERROR: DATABASE_URL environment variable is not set!")
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL

BACKUP_FOLDER_NAME = 'ShippingCompany_Backups'
BACKUP_FOLDER_ID = None

db = SQLAlchemy(app)

# ==================== MODELS ====================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200))
    role = db.Column(db.String(20), default='user')
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Car(db.Model):
    __tablename__ = 'cars'
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), unique=True, nullable=False)
    bank_installment = db.Column(db.Float, default=0)
    remaining_bank = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    phone = db.Column(db.String(20))
    date_added = db.Column(db.DateTime, default=datetime.now)

class Trip(db.Model):
    __tablename__ = 'trips'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'))
    driver_name = db.Column(db.String(100), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    from_location = db.Column(db.String(200))
    to_location = db.Column(db.String(200))
    nauloon = db.Column(db.Float, default=0)
    solar = db.Column(db.Float, default=0)
    expenses = db.Column(db.Float, default=0)
    driver_pay = db.Column(db.Float, default=0)
    net_profit = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    car = db.relationship('Car', backref='trips')
    customer = db.relationship('Customer', backref='trips')
    creator = db.relationship('User', backref='trips')

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    trip = db.relationship('Trip', backref='payments')
    customer = db.relationship('Customer', backref='payments')

class Installment(db.Model):
    __tablename__ = 'installments'
    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('cars.id'))
    due_date = db.Column(db.Date)
    amount = db.Column(db.Float)
    paid = db.Column(db.Boolean, default=False)
    payment_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.now)

    car = db.relationship('Car', backref='installments')

class BankTransaction(db.Model):
    __tablename__ = 'bank_transactions'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    loan_id = db.Column(db.Integer, db.ForeignKey('bank_loans.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    loan = db.relationship('BankLoan', backref='transactions')
    creator = db.relationship('User', backref='bank_transactions')

class BankLoan(db.Model):
    __tablename__ = 'bank_loans'
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    total_amount = db.Column(db.Float, nullable=False)
    monthly_installment = db.Column(db.Float, nullable=False)
    total_paid = db.Column(db.Float, default=0)
    remaining = db.Column(db.Float)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

class LoanPayment(db.Model):
    __tablename__ = 'loan_payments'
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('bank_loans.id'))
    date = db.Column(db.Date, nullable=False, default=date.today)
    amount = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)

    loan = db.relationship('BankLoan', backref='payments')

# ==================== DECORATORS ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يجب تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يجب تسجيل الدخول أولاً', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('غير مصرح لك بالدخول لهذه الصفحة', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== GOOGLE DRIVE ====================
def get_drive():
    gauth = GoogleAuth()
    if os.path.exists('client_secrets.json'):
        gauth.LoadClientConfigFile('client_secrets.json')
    if os.path.exists('token.pickle'):
        gauth.LoadCredentialsFile('token.pickle')
    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
        gauth.SaveCredentialsFile('token.pickle')
    elif gauth.access_token_expired:
        gauth.Refresh()
        gauth.SaveCredentialsFile('token.pickle')
    else:
        gauth.Authorize()
    return GoogleDrive(gauth)

def get_backup_folder(drive):
    global BACKUP_FOLDER_ID
    if BACKUP_FOLDER_ID:
        return BACKUP_FOLDER_ID
    lst = drive.ListFile({'q': f"title='{BACKUP_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false"}).GetList()
    if lst:
        BACKUP_FOLDER_ID = lst[0]['id']
        return BACKUP_FOLDER_ID
    folder = drive.CreateFile({'title': BACKUP_FOLDER_NAME, 'mimeType': 'application/vnd.google-apps.folder'})
    folder.Upload()
    BACKUP_FOLDER_ID = folder['id']
    return BACKUP_FOLDER_ID

def backup_database():
    try:
        print("🔄 Backup...")
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        fn = f'backup_{ts}.xlsx'
        with pd.ExcelWriter(fn, engine='openpyxl') as w:
            trips = Trip.query.all()
            if trips:
                pd.DataFrame([{'التاريخ':str(t.date),'العربية':t.car.plate_number if t.car else '','السائق':t.driver_name,'العميل':t.customer.name if t.customer else '','من':t.from_location,'إلى':t.to_location,'النولون':t.nauloon,'السولار':t.solar,'المصاريف':t.expenses,'أجرة السائق':t.driver_pay,'الصافي':t.net_profit} for t in trips]).to_excel(w,sheet_name='الرحلات',index=False)
            cust = Customer.query.all()
            if cust:
                pd.DataFrame([{'الاسم':c.name,'التليفون':c.phone} for c in cust]).to_excel(w,sheet_name='العملاء',index=False)
            cars = Car.query.all()
            if cars:
                pd.DataFrame([{'اللوحة':c.plate_number,'قسط البنك':c.bank_installment,'المتبقي':c.remaining_bank} for c in cars]).to_excel(w,sheet_name='العربيات',index=False)
            pays = Payment.query.all()
            if pays:
                pd.DataFrame([{'التاريخ':str(p.date),'العميل':p.customer.name if p.customer else '','المبلغ':p.amount} for p in pays]).to_excel(w,sheet_name='الدفعات',index=False)
            insts = Installment.query.all()
            if insts:
                pd.DataFrame([{'العربية':i.car.plate_number if i.car else '','الاستحقاق':str(i.due_date),'المبلغ':i.amount,'تم':i.paid} for i in insts]).to_excel(w,sheet_name='الأقساط',index=False)
            btx = BankTransaction.query.all()
            if btx:
                pd.DataFrame([{'التاريخ':str(b.date),'النوع':b.type,'المبلغ':b.amount,'الوصف':b.description} for b in btx]).to_excel(w,sheet_name='البنك',index=False)
        drive = get_drive()
        fid = get_backup_folder(drive)
        f = drive.CreateFile({'title':fn,'parents':[{'id':fid}],'mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        f.SetContentFile(fn)
        f.Upload()
        cutoff = datetime.now() - timedelta(days=30)
        for fl in drive.ListFile({'q':f"'{fid}' in parents and trashed=false"}).GetList():
            try:
                cd = datetime.strptime(fl['createdDate'],"%Y-%m-%dT%H:%M:%S.%fZ")
                if cd < cutoff: fl.Delete()
            except: pass
        os.remove(fn)
        print(f"✅ Backup: {fn}")
    except Exception as e:
        print(f"❌ Backup error: {e}")

def scheduler_loop():
    schedule.every().day.at("23:00").do(backup_database)
    schedule.every(6).hours.do(backup_database)
    while True:
        schedule.run_pending()
        time.sleep(60)

# ==================== AUTH ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username','').strip()
        p = request.form.get('password','')
        user = User.query.filter_by(username=u, active=True).first()
        if user and user.check_password(p):
            session.update(user_id=user.id, username=user.username, full_name=user.full_name, role=user.role)
            flash(f'مرحباً {user.full_name}!','success')
            return redirect(url_for('dashboard'))
        flash('خطأ في الدخول','danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('تم الخروج','info')
    return redirect(url_for('login'))

# ==================== DASHBOARD ====================
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    tt = Trip.query.count()
    tcust = Customer.query.count()
    tcar = Car.query.count()
    today_tr = Trip.query.filter_by(date=date.today()).all()
    today_net = sum(t.net_profit for t in today_tr)
    today_nau = sum(t.nauloon for t in today_tr)
    dep = db.session.query(db.func.sum(BankTransaction.amount)).filter(BankTransaction.type=='deposit').scalar() or 0
    wit = db.session.query(db.func.sum(BankTransaction.amount)).filter(BankTransaction.type=='withdraw').scalar() or 0
    loans = BankLoan.query.filter(BankLoan.remaining>0).all()
    loan_rem = sum(l.remaining for l in loans)
    bal = dep - wit
    recent = Trip.query.order_by(Trip.date.desc()).limit(10).all()
    pending = []
    for c in Customer.query.all():
        tn = db.session.query(db.func.sum(Trip.nauloon)).filter(Trip.customer_id==c.id).scalar() or 0
        tp = db.session.query(db.func.sum(Payment.amount)).filter(Payment.customer_id==c.id).scalar() or 0
        r = tn - tp
        if r > 0: pending.append({'customer':c,'remaining':r})
    upcoming = Installment.query.filter(Installment.paid==False, Installment.due_date>=date.today()).order_by(Installment.due_date).limit(5).all()
    return render_template('dashboard.html', total_trips=tt, total_customers=tcust, total_cars=tcar,
                           today_net=today_net, today_nauloon=today_nau, today_trips_count=len(today_tr),
                           bank_balance=bal, total_loan_remaining=loan_rem, recent_trips=recent,
                           pending_payments=pending, upcoming_installments=upcoming)

# ==================== TRIPS ====================
@app.route('/trips/add', methods=['GET','POST'])
@login_required
def add_trip():
    if request.method == 'POST':
        try:
            pn = request.form.get('plate_number','').strip()
            dn = request.form.get('driver_name','').strip()
            cn = request.form.get('customer_name','').strip()
            cp = request.form.get('customer_phone','').strip()
            
            car = Car.query.filter_by(plate_number=pn).first()
            if not car and pn:
                car = Car(plate_number=pn)
                db.session.add(car)
                db.session.flush()
                
            cust = Customer.query.filter_by(name=cn).first()
            if not cust and cn:
                cust = Customer(name=cn, phone=cp)
                db.session.add(cust)
                db.session.flush()
                
            nau = float(request.form.get('nauloon', 0) or 0)
            sol = float(request.form.get('solar', 0) or 0)
            exp = float(request.form.get('expenses', 0) or 0)
            dp = float(request.form.get('driver_pay', 0) or 0)
            net = nau - sol - exp - dp
            
            trip_date = datetime.strptime(request.form.get('date', str(date.today())), '%Y-%m-%d').date()
            
            trip = Trip(
                date=trip_date,
                car_id=car.id if car else None,
                driver_name=dn,
                customer_id=cust.id if cust else None,
                from_location=request.form.get('from_location',''),
                to_location=request.form.get('to_location',''),
                nauloon=nau,
                solar=sol,
                expenses=exp,
                driver_pay=dp,
                net_profit=net,
                notes=request.form.get('notes',''),
                created_by=session['user_id']
            )
            db.session.add(trip)
            db.session.flush()
            
            paid = float(request.form.get('paid_now', 0) or 0)
            if paid > 0:
                db.session.add(Payment(
                    date=trip_date,
                    trip_id=trip.id,
                    customer_id=cust.id if cust else None,
                    amount=paid,
                    notes='دفعة مع الرحلة'
                ))
                
            db.session.commit()
            flash('تمت الإضافة بنجاح', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ: {str(e)}', 'danger')
            print(f"Error: {e}")
            
        return redirect(url_for('add_trip'))
    
    return render_template(
        'add_trip.html', 
        cars=Car.query.order_by(Car.plate_number).all(), 
        customers=Customer.query.order_by(Customer.name).all(),
        today=date.today()
    )

@app.route('/trips')
@login_required
def trips_list():
    return render_template('trips.html', trips=Trip.query.order_by(Trip.date.desc()).limit(100).all())

@app.route('/api/trips/<int:tid>/delete', methods=['POST'])
@admin_required
def delete_trip(tid):
    t = Trip.query.get_or_404(tid)
    Payment.query.filter_by(trip_id=tid).delete()
    db.session.delete(t)
    db.session.commit()
    flash('تم الحذف','success')
    return redirect(url_for('trips_list'))

# ==================== CUSTOMERS ====================
@app.route('/customers')
@login_required
def customers():
    sm = []
    for c in Customer.query.order_by(Customer.name).all():
        tn = db.session.query(db.func.sum(Trip.nauloon)).filter(Trip.customer_id==c.id).scalar() or 0
        tp = db.session.query(db.func.sum(Payment.amount)).filter(Payment.customer_id==c.id).scalar() or 0
        sm.append({'customer':c,'total_nauloon':tn,'total_paid':tp,'remaining':tn-tp})
    return render_template('customers.html', customers_summary=sm)

@app.route('/customers/<int:cid>')
@login_required
def customer_report(cid):
    c = Customer.query.get_or_404(cid)
    tr = Trip.query.filter_by(customer_id=cid).order_by(Trip.date.desc()).all()
    ps = Payment.query.filter_by(customer_id=cid).order_by(Payment.date.desc()).all()
    tn = sum(t.nauloon for t in tr)
    tp = sum(p.amount for p in ps)
    return render_template('customer_report.html', customer=c, trips=tr, payments=ps, total_nauloon=tn, total_paid=tp, remaining=tn-tp)

@app.route('/api/customers/<int:cid>/delete', methods=['POST'])
@admin_required
def delete_customer(cid):
    c = Customer.query.get_or_404(cid)
    Payment.query.filter_by(customer_id=cid).delete()
    Trip.query.filter_by(customer_id=cid).delete()
    db.session.delete(c)
    db.session.commit()
    flash('تم الحذف','success')
    return redirect(url_for('customers'))

@app.route('/payments/add', methods=['POST'])
@login_required
def add_payment():
    cid = request.form.get('customer_id')
    tid = request.form.get('trip_id')
    amt = float(request.form.get('amount', 0) or 0)
    db.session.add(Payment(
        date=datetime.strptime(request.form['date'],'%Y-%m-%d').date(),
        trip_id=tid if tid else None,
        customer_id=cid,
        amount=amt,
        notes=request.form.get('notes','')
    ))
    db.session.commit()
    flash('تمت الإضافة','success')
    return redirect(url_for('customer_report', cid=cid))

# ==================== CARS ====================
@app.route('/cars')
@login_required
def cars():
    return render_template('cars.html', cars=Car.query.order_by(Car.plate_number).all())

@app.route('/cars/<int:cid>')
@login_required
def car_report(cid):
    c = Car.query.get_or_404(cid)
    tr = Trip.query.filter_by(car_id=cid).order_by(Trip.date.desc()).all()
    drivers = {}
    for t in tr:
        drivers[t.driver_name] = drivers.get(t.driver_name, 0) + 1
    insts = Installment.query.filter_by(car_id=cid).order_by(Installment.due_date).all()
    return render_template('car_report.html', car=c, trips=tr, trip_count=len(tr),
                           total_nauloon=sum(t.nauloon for t in tr),
                           total_solar=sum(t.solar for t in tr),
                           total_expenses=sum(t.expenses for t in tr),
                           total_driver_pay=sum(t.driver_pay for t in tr),
                           total_net=sum(t.net_profit for t in tr),
                           drivers=drivers, installments=insts)

@app.route('/api/cars/<int:cid>/delete', methods=['POST'])
@admin_required
def delete_car(cid):
    c = Car.query.get_or_404(cid)
    Trip.query.filter_by(car_id=cid).delete()
    Installment.query.filter_by(car_id=cid).delete()
    db.session.delete(c)
    db.session.commit()
    flash('تم الحذف','success')
    return redirect(url_for('cars'))

# ==================== INSTALLMENTS ====================
@app.route('/installments')
@login_required
def installments():
    return render_template('installments.html', cars=Car.query.all())

@app.route('/installments/add', methods=['POST'])
@login_required
def add_installment():
    cid = request.form['car_id']
    amt = float(request.form['amount'] or 0)
    inst = Installment(
        car_id=cid,
        due_date=datetime.strptime(request.form['due_date'],'%Y-%m-%d').date(),
        amount=amt
    )
    car = Car.query.get(cid)
    if car:
        car.remaining_bank += amt
    db.session.add(inst)
    db.session.commit()
    flash('تمت الإضافة','success')
    return redirect(url_for('installments'))

@app.route('/installments/<int:iid>/pay')
@login_required
def pay_installment(iid):
    inst = Installment.query.get_or_404(iid)
    inst.paid = True
    inst.payment_date = date.today()
    car = Car.query.get(inst.car_id)
    if car:
        car.remaining_bank -= inst.amount
    db.session.commit()
    flash('تم السداد','success')
    return redirect(url_for('installments'))

# ==================== BANK (ADMIN) ====================
@app.route('/bank')
@admin_required
def bank():
    dep = db.session.query(db.func.sum(BankTransaction.amount)).filter(BankTransaction.type=='deposit').scalar() or 0
    wit = db.session.query(db.func.sum(BankTransaction.amount)).filter(BankTransaction.type=='withdraw').scalar() or 0
    loans = BankLoan.query.filter(BankLoan.remaining>0).all()
    return render_template('bank.html', balance=dep-wit, deposits=dep, withdraws=wit,
                           total_loan_remaining=sum(l.remaining for l in loans),
                           active_loans=loans,
                           recent_transactions=BankTransaction.query.order_by(BankTransaction.date.desc()).limit(20).all(),
                           date=date.today())

@app.route('/bank/transaction/add', methods=['POST'])
@admin_required
def add_bank_transaction():
    db.session.add(BankTransaction(
        date=datetime.strptime(request.form['date'],'%Y-%m-%d').date(),
        type=request.form['type'],
        amount=float(request.form['amount'] or 0),
        description=request.form.get('description',''),
        created_by=session['user_id']
    ))
    db.session.commit()
    flash('تمت الإضافة','success')
    return redirect(url_for('bank'))

@app.route('/bank/loans')
@admin_required
def bank_loans():
    return render_template('bank_loans.html', loans=BankLoan.query.order_by(BankLoan.start_date.desc()).all())

@app.route('/bank/loans/add', methods=['POST'])
@admin_required
def add_bank_loan():
    amt = float(request.form['total_amount'] or 0)
    mon = float(request.form['monthly_installment'] or 0)
    loan = BankLoan(
        start_date=datetime.strptime(request.form['start_date'],'%Y-%m-%d').date(),
        total_amount=amt,
        monthly_installment=mon,
        remaining=amt,
        description=request.form.get('description','')
    )
    db.session.add(loan)
    db.session.flush()
    db.session.add(BankTransaction(
        date=loan.start_date,
        type='loan',
        amount=amt,
        description=f'قرض جديد - {loan.description or ""}',
        loan_id=loan.id,
        created_by=session['user_id']
    ))
    db.session.commit()
    flash('تمت الإضافة','success')
    return redirect(url_for('bank_loans'))

@app.route('/bank/loans/<int:lid>/pay', methods=['POST'])
@admin_required
def pay_loan_installment(lid):
    loan = BankLoan.query.get_or_404(lid)
    amt = float(request.form['amount'] or 0)
    db.session.add(LoanPayment(
        loan_id=lid,
        date=datetime.strptime(request.form['date'],'%Y-%m-%d').date(),
        amount=amt,
        notes=request.form.get('notes','')
    ))
    loan.total_paid += amt
    loan.remaining = loan.total_amount - loan.total_paid
    db.session.add(BankTransaction(
        date=datetime.strptime(request.form['date'],'%Y-%m-%d').date(),
        type='withdraw',
        amount=amt,
        description=f'سداد قرض #{lid}',
        loan_id=lid,
        created_by=session['user_id']
    ))
    db.session.commit()
    flash('تم السداد','success')
    return redirect(url_for('bank_loans'))

# ==================== USERS (ADMIN) ====================
@app.route('/users')
@admin_required
def users():
    return render_template('users.html', users=User.query.order_by(User.full_name).all())

@app.route('/users/add', methods=['GET','POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        un = request.form.get('username','').strip()
        if User.query.filter_by(username=un).first():
            flash('اسم المستخدم موجود بالفعل','danger')
            return redirect(url_for('add_user'))
        u = User(
            username=un,
            full_name=request.form.get('full_name','').strip(),
            role=request.form.get('role','user')
        )
        u.set_password(request.form.get('password',''))
        db.session.add(u)
        db.session.commit()
        flash('تمت الإضافة','success')
        return redirect(url_for('users'))
    return render_template('add_user.html')

@app.route('/api/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    u = User.query.get_or_404(uid)
    if u.role == 'admin' and User.query.filter_by(role='admin').count() <= 1:
        flash('لا يمكن حذف آخر أدمن','danger')
        return redirect(url_for('users'))
    db.session.delete(u)
    db.session.commit()
    flash('تم الحذف','success')
    return redirect(url_for('users'))

@app.route('/api/users/<int:uid>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(uid):
    u = User.query.get_or_404(uid)
    u.set_password(request.form.get('new_password',''))
    db.session.commit()
    flash(f'تم تغيير كلمة المرور لـ {u.full_name}','success')
    return redirect(url_for('users'))

# ==================== DAILY REPORT ====================
@app.route('/reports/daily')
@login_required
def daily_report():
    rd = request.args.get('date', date.today().isoformat())
    rd = datetime.strptime(rd, '%Y-%m-%d').date()
    tr = Trip.query.filter_by(date=rd).order_by(Trip.id).all()
    return render_template('daily_report.html', report_date=rd, trips=tr,
                           total_nauloon=sum(t.nauloon for t in tr),
                           total_solar=sum(t.solar for t in tr),
                           total_expenses=sum(t.expenses for t in tr),
                           total_driver_pay=sum(t.driver_pay for t in tr),
                           total_net=sum(t.net_profit for t in tr))

@app.route('/reports/daily/export/<rd>')
@login_required
def export_daily_report(rd):
    rd = datetime.strptime(rd, '%Y-%m-%d').date()
    tr = Trip.query.filter_by(date=rd).order_by(Trip.id).all()
    df = pd.DataFrame([{'التاريخ':str(t.date),'العربية':t.car.plate_number if t.car else '','السائق':t.driver_name,
                        'العميل':t.customer.name if t.customer else '','من':t.from_location,'إلى':t.to_location,
                        'النولون':t.nauloon,'السولار':t.solar,'المصاريف':t.expenses,
                        'أجرة السائق':t.driver_pay,'الصافي':t.net_profit} for t in tr])
    if not df.empty:
        tot = {'التاريخ':'الإجمالي','العربية':'','السائق':'','العميل':'','من':'','إلى':''}
        for col in ['النولون','السولار','المصاريف','أجرة السائق','الصافي']:
            tot[col] = df[col].sum()
        df.loc['الإجمالي'] = tot
    fn = f'trips_report_{rd}.xlsx'
    df.to_excel(fn, index=False, engine='openpyxl')
    return send_file(fn, as_attachment=True)

@app.route('/api/backup', methods=['POST'])
@admin_required
def manual_backup():
    try:
        backup_database()
        flash('تم النسخ الاحتياطي','success')
    except Exception as e:
        flash(f'فشل: {e}','danger')
    return redirect(url_for('dashboard'))

# ==================== API ====================
@app.route('/api/cars')
@login_required
def api_cars():
    q = request.args.get('search','')
    return jsonify([{'id':c.id,'plate_number':c.plate_number} for c in Car.query.filter(Car.plate_number.contains(q)).all()])

@app.route('/api/customers')
@login_required
def api_customers():
    q = request.args.get('search','')
    return jsonify([{'id':c.id,'name':c.name,'phone':c.phone or ''} for c in Customer.query.filter(Customer.name.contains(q)).all()])

@app.route('/api/customer_trips')
@login_required
def api_customer_trips():
    cid = request.args.get('customer_id','')
    if cid:
        return jsonify([{'id':t.id,'date':str(t.date),'nauloon':t.nauloon,'from_location':t.from_location,'to_location':t.to_location}
                        for t in Trip.query.filter_by(customer_id=cid).order_by(Trip.date.desc()).all()])
    return jsonify([])

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found(e):
    return render_template('login.html'), 404

# ==================== INIT ====================
def init_db():
    with app.app_context():
        db.create_all()

        # 1. إنشاء الأدمن
        if not User.query.filter_by(username='admin').first():
            a = User(username='admin', full_name='مدير النظام', role='admin')
            a.set_password('admin123')
            db.session.add(a)
            db.session.commit()
            print("✅ Admin: admin / admin123")

        # 2. إضافة عربيات تجريبية (عشان نبدأ بشوية بيانات)
        if Car.query.count() == 0:
            car1 = Car(plate_number='1234 أ ب ج', bank_installment=5000, remaining_bank=20000)
            car2 = Car(plate_number='5678 د ه و', bank_installment=7000, remaining_bank=35000)
            db.session.add_all([car1, car2])
            db.session.commit()
            print("✅ تمت إضافة 2 عربية تجريبية")

            # 3. إضافة أقساط للعربيات
            inst1 = Installment(car_id=car1.id, due_date=date(2026, 9, 1), amount=5000, paid=False)
            inst2 = Installment(car_id=car1.id, due_date=date(2026, 10, 1), amount=5000, paid=True, payment_date=date.today())
            inst3 = Installment(car_id=car2.id, due_date=date(2026, 8, 15), amount=7000, paid=False)
            db.session.add_all([inst1, inst2, inst3])
            db.session.commit()
            print("✅ تمت إضافة 3 أقساط تجريبية (قسط واحد مدفوع)")

if __name__ == '__main__':
    init_db()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    print("✅ Scheduler running")
    # تم إزالة app.run() لأن Render سيشغله عبر gunicorn
