"""MochiAtlasDesigns integrated development starter. Not production-ready."""
import os, sqlite3, secrets, hmac, smtplib, ssl, sys
from datetime import datetime, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from flask import Flask, request, session, redirect, url_for, abort, render_template_string, flash
from werkzeug.security import generate_password_hash, check_password_hash

BASE=Path(__file__).resolve().parent
DB=Path(os.getenv('DATABASE_PATH',str(BASE/'studio.sqlite3')))
app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('HTTPS_ONLY')=='1',MAX_CONTENT_LENGTH=1024*1024)
EMAIL='MochiAtlasDesigns@gmail.com'

SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','customer')));
CREATE TABLE IF NOT EXISTS commissions(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,description TEXT NOT NULL,stage TEXT NOT NULL DEFAULT 'Request received',quote_cents INTEGER NOT NULL DEFAULT 0,deposit_paid INTEGER NOT NULL DEFAULT 0,final_paid INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,commission_id INTEGER NOT NULL REFERENCES commissions(id),sender_id INTEGER NOT NULL REFERENCES users(id),body TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,event TEXT NOT NULL,commission_id INTEGER,created_at TEXT NOT NULL,delivered INTEGER NOT NULL DEFAULT 0);
'''
def db():
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    return con

def now():return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
def notify(con,event,cid):
    con.execute('INSERT INTO notifications(event,commission_id,created_at) VALUES(?,?,?)',(event,cid,now()))

def current_user():
    if not session.get('uid'):return None
    with db() as con:return con.execute('SELECT id,email,role FROM users WHERE id=?',(session['uid'],)).fetchone()

def login_required(fn):
    @wraps(fn)
    def inner(*args,**kwargs):
        if not current_user():return redirect(url_for('login'))
        return fn(*args,**kwargs)
    return inner

def csrf():
    if not session.get('csrf'):session['csrf']=secrets.token_urlsafe(32)
    return session['csrf']
@app.before_request
def protect():
    if request.method=='POST' and not hmac.compare_digest(request.form.get('csrf',''),csrf()):abort(400)

BASE_HTML='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MochiAtlasDesigns</title><style>
:root{font-family:system-ui;color:#f9eae1;background:#160b12}body{margin:0}header{padding:22px 5%;border-bottom:1px solid #76485b;background:#29131e}header a{color:#e8c18c;margin-right:16px}main{max-width:960px;margin:35px auto;padding:0 18px}h1,h2{font-family:Georgia;color:#f0d4aa}article{padding:22px;background:#2d1823;border:1px solid #70495b;border-radius:12px;margin:16px 0}input,textarea,select{display:block;width:100%;max-width:570px;margin:9px 0 16px;padding:12px;background:#fdf7f2;color:#211;border-radius:6px;border:0;box-sizing:border-box}button{padding:12px 18px;background:#e8c18c;color:#211;border:0;border-radius:7px;font-weight:bold;cursor:pointer}a{color:#f1c99b}small,.muted{color:#d2b9c3}.alert{border-left:4px solid #e8c18c;padding:10px;background:#472536}.tag{color:#edc38c}li{margin:9px 0}</style></head><body><header><strong style="font-family:Georgia;font-size:24px">✦ MochiAtlasDesigns</strong><nav style="margin-top:12px"><a href="/">Home</a><a href="/shop">Shop preview</a><a href="/dashboard">Dashboard</a>{% if user %}<a href="/logout">Log out ({{user.email}})</a>{% else %}<a href="/login">Sign in</a><a href="/register">Customer sign up</a>{% endif %}</nav></header><main><p class="muted">Development starter — do not use with real customer information until security review and deployment.</p>{% for message in get_flashed_messages() %}<p class="alert">{{message}}</p>{% endfor %}{{content|safe}}</main></body></html>'''
def page(content,**kwargs):
    inner=render_template_string(content,**kwargs,csrf=csrf())
    return render_template_string(BASE_HTML,content=inner,user=current_user())

@app.route('/')
def home():
    return app.send_static_file('index.html')

@app.route('/preview/customer')
def customer_preview():
    return app.send_static_file('customer-portal-preview.html')

@app.route('/preview/studio')
def studio_preview():
    return app.send_static_file('dashboard-preview.html')

@app.route('/preview/notifications')
def notifications_preview():
    return app.send_static_file('notifications-preview.html')

@app.route('/shop')
def shop():return page('''<h1>Shop preview</h1><p>The existing shopping cart is available as a <a href="/static/storefront-preview.html">separate storefront demo</a>. It is not connected to real Stripe or PayPal payments.</p><p>Ready-made product inventory and secure checkout will require additional integration.</p>''')
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); pw=request.form.get('password','')
        if '@' not in email or len(email)>254 or len(pw)<12:flash('Enter a valid email and a password of at least 12 characters.')
        else:
            try:
                with db() as con:con.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(email,generate_password_hash(pw),'customer'))
                flash('Account created. Please sign in.');return redirect('/login')
            except sqlite3.IntegrityError:flash('This email is already registered.')
    return page('''<h1>Create customer account</h1><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>Email<input name="email" type="email" required></label><label>Password (12+ characters)<input name="password" type="password" minlength="12" required></label><button>Create account</button></form>''')
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()
        with db() as con:u=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if u and check_password_hash(u['password_hash'],request.form.get('password','')):
            session.clear();session['uid']=u['id'];csrf();return redirect('/dashboard')
        flash('Invalid credentials.')
    return page('''<h1>Sign in</h1><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>Email<input type="email" name="email" required></label><label>Password<input type="password" name="password" required></label><button>Sign in</button></form>''')
@app.route('/logout')
def logout():session.clear();return redirect('/')
@app.route('/dashboard')
@login_required
def dashboard():
    u=current_user()
    with db() as con:
        if u['role']=='admin':rows=con.execute('SELECT c.*,u.email customer FROM commissions c JOIN users u ON c.customer_id=u.id ORDER BY c.id DESC').fetchall()
        else:rows=con.execute('SELECT c.*,u.email customer FROM commissions c JOIN users u ON c.customer_id=u.id WHERE c.customer_id=? ORDER BY c.id DESC',(u['id'],)).fetchall()
    return page('''<h1>{{'Studio dashboard' if admin else 'My commissions'}}</h1><p><a href="/request">+ Request a custom commission</a></p>{% for c in rows %}<article><h2><a href="/commission/{{c.id}}">#{{c.id}} · {{c.title}}</a></h2><p class="tag">{{c.stage}}</p><small>Customer: {{c.customer}} · Quote: ${{'%.2f'|format(c.quote_cents/100)}} · Deposit: {{'Paid' if c.deposit_paid else 'Pending'}} · Final: {{'Paid' if c.final_paid else 'Pending'}}</small></article>{% else %}<p>No commissions yet.</p>{% endfor %}''',rows=rows,admin=u['role']=='admin')
@app.route('/request',methods=['GET','POST'])
@login_required
def new_request():
    if request.method=='POST':
        title=request.form.get('title','').strip()[:150];desc=request.form.get('description','').strip()[:3000]
        if title and desc:
            with db() as con:
                cid=con.execute('INSERT INTO commissions(customer_id,title,description,created_at) VALUES(?,?,?,?)',(current_user()['id'],title,desc,now())).lastrowid
                notify(con,'New commission request',cid)
            return redirect(f'/commission/{cid}')
        flash('Please complete both fields.')
    return page('''<h1>Request a commission</h1><p>Cosplay props, costumes, and life-size figures. Quotes are reviewed before any deposit is due.</p><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><label>Project title<input name="title" maxlength="150" required></label><label>Describe dimensions, budget, deadline, and references<textarea name="description" rows="7" maxlength="3000" required></textarea></label><button>Submit request</button></form>''')
@app.route('/commission/<int:cid>',methods=['GET','POST'])
@login_required
def commission(cid):
    u=current_user()
    with db() as con:
        c=con.execute('SELECT c.*,u.email customer FROM commissions c JOIN users u ON c.customer_id=u.id WHERE c.id=?',(cid,)).fetchone()
        if not c:abort(404)
        if u['role']!='admin' and c['customer_id']!=u['id']:abort(403)
        if request.method=='POST':
            if request.form.get('action')=='message':
                body=request.form.get('body','').strip()[:3000]
                if body:
                    con.execute('INSERT INTO messages(commission_id,sender_id,body,created_at) VALUES(?,?,?,?)',(cid,u['id'],body,now()))
                    notify(con,'New project message',cid)
            elif request.form.get('action')=='update' and u['role']=='admin':
                stage=request.form.get('stage','')
                if stage not in ['Request received','Quoted','Deposit pending','In production','Review','Completed','Delivered']:abort(400)
                try:quote=int(round(float(request.form.get('quote','0'))*100))
                except ValueError:abort(400)
                if not 0<=quote<=100000000:abort(400)
                con.execute('UPDATE commissions SET stage=?,quote_cents=? WHERE id=?',(stage,quote,cid))
                notify(con,'Project updated',cid)
            return redirect(f'/commission/{cid}')
        msgs=con.execute('SELECT m.*,u.email sender FROM messages m JOIN users u ON m.sender_id=u.id WHERE commission_id=? ORDER BY m.id',(cid,)).fetchall()
    return page('''<p><a href="/dashboard">← Dashboard</a></p><h1>#{{c.id}} · {{c.title}}</h1><p>{{c.description}}</p><article><h2>Progress & payments</h2><p class="tag">{{c.stage}}</p><p>Quote: ${{'%.2f'|format(c.quote_cents/100)}} · 50% deposit: {{'Paid' if c.deposit_paid else 'Not recorded'}} · Remaining balance: {{'Paid' if c.final_paid else 'Not recorded'}}</p><small>Payment status is informational only. No card checkout or automated payment verification is enabled.</small></article>{% if admin %}<article><h2>Admin project settings</h2><form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="update"><label>Stage<select name="stage">{% for s in stages %}<option {{'selected' if c.stage==s else ''}}>{{s}}</option>{% endfor %}</select></label><label>Quote amount in USD<input name="quote" type="number" min="0" step="0.01" value="{{'%.2f'|format(c.quote_cents/100)}}"></label><button>Save update</button></form></article>{% endif %}<article><h2>Project messages</h2>{% for m in msgs %}<p><strong>{{m.sender}}</strong> <small>{{m.created_at}}</small><br>{{m.body}}</p><hr>{% else %}<p>No messages yet.</p>{% endfor %}<form method="post"><input type="hidden" name="csrf" value="{{csrf}}"><input type="hidden" name="action" value="message"><label>New message<textarea name="body" rows="4" maxlength="3000" required></textarea></label><button>Send message</button></form></article>''',c=c,msgs=msgs,admin=u['role']=='admin',stages=['Request received','Quoted','Deposit pending','In production','Review','Completed','Delivered'])

@app.cli.command('create-admin')
def create_admin():
    import getpass
    email=input('Admin email: ').strip().lower();pw=getpass.getpass('Password (12+ characters): ')
    if '@' not in email or len(pw)<12:raise SystemExit('Invalid email or short password')
    with db() as con:
        con.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(email,generate_password_hash(pw),'admin'))
    print('Admin account created')

@app.cli.command('send-notifications')
def send_notifications():
    """Send queued notifications via configured SMTP; run from a trusted scheduler."""
    host=os.getenv('SMTP_HOST');user=os.getenv('SMTP_USER');password=os.getenv('SMTP_PASSWORD');sender=os.getenv('SMTP_FROM')
    if not all([host,user,password,sender]):raise SystemExit('Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM')
    port=int(os.getenv('SMTP_PORT','465'))
    with db() as con:
        rows=con.execute('SELECT * FROM notifications WHERE delivered=0 ORDER BY id LIMIT 50').fetchall()
        with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context()) as smtp:
            smtp.login(user,password)
            for row in rows:
                msg=EmailMessage();msg['From']=sender;msg['To']=EMAIL;msg['Subject']='MochiAtlasDesigns: '+row['event']
                msg.set_content(f"Event: {row['event']}\nCommission ID: {row['commission_id']}\nSign in to the studio dashboard for details.\n")
                smtp.send_message(msg)
                con.execute('UPDATE notifications SET delivered=1 WHERE id=?',(row['id'],))
                con.commit()
    print('Processed notifications')

with db() as con:con.executescript(SCHEMA)
if __name__=='__main__':
    app.run(debug=False,host='127.0.0.1',port=5000)
