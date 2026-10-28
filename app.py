import os
from datetime import date, datetime
from decimal import Decimal
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-only-change-before-production')
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

def connect():
    return pymysql.connect(host=os.getenv('MYSQL_HOST','127.0.0.1'), port=int(os.getenv('MYSQL_PORT','3306')),
      user=os.getenv('MYSQL_USER','autocare_app'), password=os.getenv('MYSQL_PASSWORD',''),
      database=os.getenv('MYSQL_DATABASE','autocare_db'), charset='utf8mb4', cursorclass=DictCursor,
      autocommit=False)

def query(sql, args=(), one=False):
    conn=connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql,args)
            return cur.fetchone() if one else cur.fetchall()
    finally: conn.close()

def execute(sql,args=()):
    conn=connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql,args)
            result=cur.lastrowid
        conn.commit()
        return result
    except Exception:
        conn.rollback(); raise
    finally: conn.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to continue.','error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def owned_vehicle(vid):
    row=query('SELECT * FROM vehicles WHERE id=%s AND user_id=%s',(vid,session['user_id']),True)
    if not row: abort(404)
    return row

def owned_service(sid):
    row=query('SELECT s.* FROM service_records s JOIN vehicles v ON v.id=s.vehicle_id WHERE s.id=%s AND v.user_id=%s',(sid,session['user_id']),True)
    if not row: abort(404)
    return row

def owned_reminder(rid):
    row=query('SELECT r.* FROM service_reminders r JOIN vehicles v ON v.id=r.vehicle_id WHERE r.id=%s AND v.user_id=%s',(rid,session['user_id']),True)
    if not row: abort(404)
    return row

def positive_int(raw, field, allow_zero=True):
    try: value=int(raw)
    except (ValueError, TypeError): raise ValueError(f'{field} must be a whole number.')
    if value < (0 if allow_zero else 1): raise ValueError(f'{field} must be positive.')
    return value

def cost_value(raw):
    try: value=Decimal(str(raw))
    except Exception: raise ValueError('Cost must be a valid number.')
    if not value.is_finite() or value < 0 or value > Decimal('9999999999.99'): raise ValueError('Enter a valid nonnegative cost.')
    return value

@app.context_processor
def globals_for_templates(): return {'today':date.today(), 'app_name':'AutoCare', 'current_user':session.get('name')}

@app.route('/')
def home(): return redirect(url_for('dashboard') if session.get('user_id') else url_for('login'))

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not name or len(name)>100 or len(email)>190 or '@' not in email or len(password)<8:
            flash('Enter a name, valid email and password of at least 8 characters.','error')
        else:
            try:
                execute('INSERT INTO users(name,email,password_hash) VALUES(%s,%s,%s)',(name,email,generate_password_hash(password)))
                flash('Account created. Please sign in.','success'); return redirect(url_for('login'))
            except pymysql.err.IntegrityError: flash('This email is already registered.','error')
    return render_template('auth.html',mode='register')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        user=query('SELECT * FROM users WHERE email=%s',(request.form.get('email','').strip().lower(),),True)
        if user and check_password_hash(user['password_hash'],request.form.get('password','')):
            session.clear(); session['user_id']=user['id']; session['name']=user['name'];
            return redirect(url_for('dashboard'))
        flash('Incorrect email or password.','error')
    return render_template('auth.html',mode='login')

@app.post('/logout')
@login_required
def logout(): session.clear(); flash('Signed out.','success'); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    uid=session['user_id']
    stats=query('''SELECT (SELECT COUNT(*) FROM vehicles WHERE user_id=%s) AS vehicles,
      (SELECT COUNT(*) FROM service_records s JOIN vehicles v ON s.vehicle_id=v.id WHERE v.user_id=%s) AS services,
      (SELECT COALESCE(SUM(s.cost),0) FROM service_records s JOIN vehicles v ON s.vehicle_id=v.id WHERE v.user_id=%s) AS spending,
      (SELECT COUNT(*) FROM service_reminders r JOIN vehicles v ON r.vehicle_id=v.id WHERE v.user_id=%s AND r.status='Pending') AS reminders''',(uid,uid,uid,uid),True)
    vehicles=query('SELECT * FROM vw_vehicle_expenses WHERE user_id=%s ORDER BY vehicle_id DESC LIMIT 6',(uid,))
    recent=query('''SELECT s.*,v.registration_no,v.make,v.model FROM service_records s JOIN vehicles v ON v.id=s.vehicle_id WHERE v.user_id=%s ORDER BY s.service_date DESC,s.id DESC LIMIT 6''',(uid,))
    reminders=query('''SELECT r.*,v.registration_no,v.odometer FROM service_reminders r JOIN vehicles v ON v.id=r.vehicle_id WHERE v.user_id=%s AND r.status='Pending' ORDER BY (r.due_date IS NULL),r.due_date LIMIT 6''',(uid,))
    months=query('''SELECT DATE_FORMAT(s.service_date,'%%Y-%%m') AS month, SUM(s.cost) AS total FROM service_records s JOIN vehicles v ON v.id=s.vehicle_id WHERE v.user_id=%s GROUP BY DATE_FORMAT(s.service_date,'%%Y-%%m') ORDER BY month DESC LIMIT 8''',(uid,))
    months.reverse()
    return render_template('dashboard.html',stats=stats,vehicles=vehicles,recent=recent,reminders=reminders,months=months)

@app.route('/vehicles',methods=['GET','POST'])
@login_required
def vehicles():
    if request.method=='POST':
        try:
            registration=request.form.get('registration_no','').strip().upper(); make=request.form.get('make','').strip(); model=request.form.get('model','').strip()
            if not registration or not make or not model: raise ValueError('Registration, make and model are required.')
            kind=request.form.get('vehicle_type','Car')
            if kind not in ('Car','Bike','Scooter','Other'): raise ValueError('Invalid vehicle type.')
            year=positive_int(request.form['manufacture_year'],'Year') if request.form.get('manufacture_year') else None
            if year and not 1900<=year<=2100: raise ValueError('Year is out of range.')
            execute('INSERT INTO vehicles(user_id,registration_no,make,model,vehicle_type,manufacture_year,odometer,fuel_type) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (session['user_id'],registration,make,model,kind,year,positive_int(request.form.get('odometer'),'Odometer'),request.form.get('fuel_type','Petrol').strip()[:30]))
            flash('Vehicle added.','success'); return redirect(url_for('vehicles'))
        except (ValueError,pymysql.err.IntegrityError) as e: flash('Unable to add vehicle: '+str(e),'error')
    rows=query('SELECT * FROM vw_vehicle_expenses WHERE user_id=%s ORDER BY vehicle_id DESC',(session['user_id'],))
    details=query('SELECT id,vehicle_type,odometer,fuel_type,manufacture_year FROM vehicles WHERE user_id=%s',(session['user_id'],))
    by_id={v['id']:v for v in details}
    for v in rows: v.update(by_id[v['vehicle_id']])
    return render_template('vehicles.html',vehicles=rows)

@app.post('/vehicles/<int:vid>/delete')
@login_required
def vehicle_delete(vid):
    owned_vehicle(vid)
    execute('DELETE FROM vehicles WHERE id=%s AND user_id=%s',(vid,session['user_id']))
    flash('Vehicle and its related records removed.','success'); return redirect(url_for('vehicles'))

@app.route('/services',methods=['GET','POST'])
@login_required
def services():
    uid=session['user_id']
    if request.method=='POST':
        try:
            vid=positive_int(request.form.get('vehicle_id'),'Vehicle',False); owned_vehicle(vid)
            workshop_id=positive_int(request.form['workshop_id'],'Workshop',False) if request.form.get('workshop_id') else None
            if workshop_id and not query('SELECT id FROM workshops WHERE id=%s AND user_id=%s',(workshop_id,uid),True): raise ValueError('Invalid workshop.')
            odometer=positive_int(request.form.get('odometer'),'Odometer')
            service_type=request.form.get('service_type','').strip()
            if not service_type: raise ValueError('Service type is required.')
            service_date=date.fromisoformat(request.form.get('service_date',''))
            conn=connect()
            try:
                with conn.cursor() as cur:
                    # Row lock protects concurrent mileage updates; both statements commit atomically.
                    cur.execute('SELECT odometer FROM vehicles WHERE id=%s AND user_id=%s FOR UPDATE',(vid,uid))
                    vehicle=cur.fetchone()
                    if not vehicle: raise ValueError('Vehicle not found.')
                    cur.execute('INSERT INTO service_records(vehicle_id,workshop_id,service_type,service_date,odometer,cost,notes) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                        (vid,workshop_id,service_type[:80],service_date,odometer,cost_value(request.form.get('cost','0')),request.form.get('notes','').strip()))
                    cur.execute('UPDATE vehicles SET odometer=GREATEST(odometer,%s) WHERE id=%s',(odometer,vid))
                conn.commit()
            except Exception: conn.rollback(); raise
            finally: conn.close()
            flash('Service saved and vehicle mileage updated.','success'); return redirect(url_for('services'))
        except (ValueError,pymysql.MySQLError) as e: flash('Unable to save service: '+str(e),'error')
    records=query('''SELECT s.*,v.registration_no,v.make,v.model,w.name AS workshop FROM service_records s JOIN vehicles v ON v.id=s.vehicle_id LEFT JOIN workshops w ON w.id=s.workshop_id WHERE v.user_id=%s ORDER BY s.service_date DESC,s.id DESC''',(uid,))
    vehicle_options=query('SELECT id,registration_no,make,model,odometer FROM vehicles WHERE user_id=%s ORDER BY make',(uid,))
    workshops=query('SELECT * FROM workshops WHERE user_id=%s ORDER BY name',(uid,))
    return render_template('services.html',records=records,vehicles=vehicle_options,workshops=workshops)

@app.post('/services/<int:sid>/delete')
@login_required
def service_delete(sid):
    owned_service(sid); execute('DELETE FROM service_records WHERE id=%s',(sid,))
    flash('Service deleted. Audit entry retained.','success'); return redirect(url_for('services'))

@app.route('/workshops',methods=['GET','POST'])
@login_required
def workshops():
    if request.method=='POST':
        name=request.form.get('name','').strip()
        if not name: flash('Workshop name is required.','error')
        else:
            execute('INSERT INTO workshops(user_id,name,city,phone) VALUES(%s,%s,%s,%s)',(session['user_id'],name[:120],request.form.get('city','').strip()[:90],request.form.get('phone','').strip()[:30]))
            flash('Workshop added.','success'); return redirect(url_for('workshops'))
    items=query('SELECT * FROM workshops WHERE user_id=%s ORDER BY id DESC',(session['user_id'],))
    return render_template('workshops.html',workshops=items)

@app.route('/reminders',methods=['GET','POST'])
@login_required
def reminders():
    uid=session['user_id']
    if request.method=='POST':
        try:
            vid=positive_int(request.form.get('vehicle_id'),'Vehicle',False); owned_vehicle(vid)
            title=request.form.get('title','').strip(); due_date=request.form.get('due_date') or None
            due_odometer=positive_int(request.form['due_odometer'],'Due odometer') if request.form.get('due_odometer') else None
            if not title or (not due_date and due_odometer is None): raise ValueError('Provide a title and at least one due date/mileage.')
            if due_date: date.fromisoformat(due_date)
            execute('INSERT INTO service_reminders(vehicle_id,title,due_date,due_odometer) VALUES(%s,%s,%s,%s)',(vid,title[:120],due_date,due_odometer))
            flash('Reminder created.','success'); return redirect(url_for('reminders'))
        except (ValueError,pymysql.MySQLError) as e: flash(str(e),'error')
    records=query('''SELECT r.*,v.registration_no,v.make,v.model,v.odometer FROM service_reminders r JOIN vehicles v ON v.id=r.vehicle_id WHERE v.user_id=%s ORDER BY (r.status='Completed'), (r.due_date IS NULL),r.due_date,r.id DESC''',(uid,))
    vehicle_options=query('SELECT id,registration_no,make,model FROM vehicles WHERE user_id=%s',(uid,))
    return render_template('reminders.html',reminders=records,vehicles=vehicle_options)

@app.post('/reminders/<int:rid>/complete')
@login_required
def reminder_complete(rid):
    owned_reminder(rid); execute("UPDATE service_reminders SET status='Completed' WHERE id=%s",(rid,))
    flash('Reminder completed.','success'); return redirect(url_for('reminders'))

@app.post('/reminders/<int:rid>/delete')
@login_required
def reminder_delete(rid):
    owned_reminder(rid); execute('DELETE FROM service_reminders WHERE id=%s',(rid,))
    flash('Reminder deleted.','success'); return redirect(url_for('reminders'))

@app.route('/reports')
@login_required
def reports():
    uid=session['user_id']
    summary=query('SELECT * FROM vw_vehicle_expenses WHERE user_id=%s ORDER BY total_spend DESC',(uid,))
    kinds=query('''SELECT s.service_type,COUNT(*) AS visits,SUM(s.cost) AS total,AVG(s.cost) AS average FROM service_records s JOIN vehicles v ON v.id=s.vehicle_id WHERE v.user_id=%s GROUP BY s.service_type ORDER BY total DESC''',(uid,))
    audit=query('''SELECT a.*,v.registration_no FROM service_audit a JOIN service_records s ON s.id=a.service_id JOIN vehicles v ON v.id=s.vehicle_id WHERE v.user_id=%s ORDER BY a.id DESC LIMIT 20''',(uid,))
    return render_template('reports.html',summary=summary,kinds=kinds,audit=audit)

@app.errorhandler(404)
def not_found(e): return render_template('error.html'),404

if __name__=='__main__':
    app.run(debug=os.getenv('FLASK_DEBUG')=='1')
