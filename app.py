from flask import Flask,render_template,request,redirect,url_for,session,flash
import os
import secrets
import sqlite3
import hmac
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from functools import wraps
from werkzeug.security import check_password_hash,generate_password_hash

app=Flask(__name__)
secret_key=os.environ.get("SECRET_KEY")
if not secret_key and os.environ.get("RENDER"):
 raise RuntimeError("Set SECRET_KEY in the deployment environment.")
app.config.update(
 SECRET_KEY=secret_key or secrets.token_hex(32),
 SESSION_COOKIE_HTTPONLY=True,
 SESSION_COOKIE_SAMESITE="Lax",
 SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE","").lower()=="true",
)
DB=Path(os.environ.get("DATABASE_PATH",Path(__file__).with_name("store.db")))
@contextmanager
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 try:
  yield c
  c.commit()
 except Exception:
  c.rollback()
  raise
 finally:
  c.close()
def init():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with conn() as c:
  c.executescript("""
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,password TEXT,role TEXT);
  CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,code TEXT UNIQUE,name TEXT,category TEXT,cost REAL,price REAL,quantity INTEGER,reorder INTEGER);
  CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,address TEXT);
  CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY,supplier TEXT,date TEXT,total REAL);
  CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY,date TEXT,cashier TEXT,total REAL,payment TEXT);
  CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,product_id INTEGER,name TEXT,qty INTEGER,price REAL,line_total REAL);
  """)
  if not c.execute("SELECT 1 FROM users").fetchone():
   admin_username=os.environ.get("ADMIN_USERNAME","").strip()
   admin_password=os.environ.get("ADMIN_PASSWORD","")
   if not admin_username or not admin_password:
    raise RuntimeError("Set ADMIN_USERNAME and ADMIN_PASSWORD before initializing an empty database.")
   initial_users=[(admin_username,generate_password_hash(admin_password),"Admin")]
   cashier_username=os.environ.get("CASHIER_USERNAME","").strip()
   cashier_password=os.environ.get("CASHIER_PASSWORD","")
   if bool(cashier_username)!=bool(cashier_password):
    raise RuntimeError("Set both CASHIER_USERNAME and CASHIER_PASSWORD, or leave both unset.")
   if cashier_username:
    initial_users.append((cashier_username,generate_password_hash(cashier_password),"Cashier"))
   c.executemany("INSERT INTO users(username,password,role) VALUES(?,?,?)",initial_users)
  if not c.execute("SELECT 1 FROM products").fetchone():
   c.executemany("INSERT INTO products(code,name,category,cost,price,quantity,reorder) VALUES(?,?,?,?,?,?,?)",[("GRO001","Rice 1 kg","Groceries",45,55,40,8),("HOM001","Dish Wash","Household",30,40,12,4),("PER001","Bath Soap","Personal Care",22,30,20,5),("SNK001","Biscuits","Snacks",8,10,3,10)])
def logged(f):
 @wraps(f)
 def w(*a,**k):
  if not session.get("user"): return redirect(url_for("login"))
  return f(*a,**k)
 return w
def admin(f):
 @wraps(f)
 def w(*a,**k):
  if session.get("role")!="Admin": flash("Admin access required.","error"); return redirect(url_for("dashboard"))
  return f(*a,**k)
 return w
@app.route("/")
def home(): return redirect(url_for("dashboard") if session.get("user") else url_for("login"))
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  with conn() as c:
   u=c.execute("SELECT * FROM users WHERE username=?",(request.form["username"],)).fetchone()
   if u:
    if u["password"].startswith(("scrypt:","pbkdf2:")):
     valid=check_password_hash(u["password"],request.form["password"])
     legacy_password=False
    else:
     valid=hmac.compare_digest(u["password"].encode(),request.form["password"].encode())
     legacy_password=True
    if valid:
     if legacy_password:
      c.execute("UPDATE users SET password=? WHERE id=?",(generate_password_hash(request.form["password"]),u["id"]))
     session["user"]=u["username"]; session["role"]=u["role"]; return redirect(url_for("dashboard"))
  flash("Invalid login details.","error")
 return render_template("login.html")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))
@app.route("/dashboard")
@logged
def dashboard():
 with conn() as c:
  pc=c.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]; stock=c.execute("SELECT COALESCE(SUM(quantity),0) n FROM products").fetchone()["n"]
  low=c.execute("SELECT COUNT(*) n FROM products WHERE quantity<=reorder").fetchone()["n"]; today=c.execute("SELECT COALESCE(SUM(total),0) n FROM sales WHERE date(date)=date('now','localtime')").fetchone()["n"]
  lows=c.execute("SELECT * FROM products WHERE quantity<=reorder ORDER BY quantity").fetchall(); sales=c.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 5").fetchall()
 return render_template("dashboard.html",pc=pc,stock=stock,low=low,today=today,lows=lows,sales=sales)
@app.route("/products",methods=["GET","POST"])
@logged
def products():
 if request.method=="POST":
  if session["role"]!="Admin": flash("Only admin can add products.","error"); return redirect(url_for("products"))
  try:
   vals=(request.form["code"].strip(),request.form["name"].strip(),request.form["category"].strip(),float(request.form["cost"]),float(request.form["price"]),int(request.form["quantity"]),int(request.form["reorder"]))
   if not vals[0] or not vals[1] or min(vals[3:])<0: raise ValueError()
   with conn() as c: c.execute("INSERT INTO products(code,name,category,cost,price,quantity,reorder) VALUES(?,?,?,?,?,?,?)",vals)
   flash("Product added.","success")
  except sqlite3.IntegrityError: flash("Product code already exists.","error")
  except (ValueError,KeyError): flash("Enter valid product details.","error")
  return redirect(url_for("products"))
 q=request.args.get("q","")
 with conn() as c: rows=c.execute("SELECT * FROM products WHERE code LIKE ? OR name LIKE ? OR category LIKE ? ORDER BY name",(f"%{q}%",)*3).fetchall()
 return render_template("products.html",rows=rows,q=q)
@app.route("/suppliers",methods=["GET","POST"])
@logged
@admin
def suppliers():
 if request.method=="POST":
  with conn() as c: c.execute("INSERT INTO suppliers(name,phone,address) VALUES(?,?,?)",(request.form["name"],request.form.get("phone",""),request.form.get("address","")))
  flash("Supplier saved.","success"); return redirect(url_for("suppliers"))
 with conn() as c: rows=c.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
 return render_template("suppliers.html",rows=rows)
@app.route("/purchases",methods=["GET","POST"])
@logged
@admin
def purchases():
 if request.method=="POST":
  try:
   pid=int(request.form["product_id"]); qty=int(request.form["qty"]); supplier=request.form["supplier"].strip()
   if qty<=0 or not supplier: raise ValueError()
   with conn() as c:
    p=c.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
    if not p: raise ValueError()
    c.execute("INSERT INTO purchases(supplier,date,total) VALUES(?,?,?)",(supplier,datetime.now().strftime("%Y-%m-%d %H:%M"),p["cost"]*qty))
    c.execute("UPDATE products SET quantity=quantity+? WHERE id=?",(qty,pid))
   flash("Purchase saved; stock increased.","success")
  except (ValueError,KeyError): flash("Check supplier, product and quantity.","error")
  return redirect(url_for("purchases"))
 with conn() as c:
  ps=c.execute("SELECT * FROM products ORDER BY name").fetchall(); rows=c.execute("SELECT * FROM purchases ORDER BY id DESC").fetchall()
 return render_template("purchases.html",ps=ps,rows=rows)
@app.route("/billing",methods=["GET","POST"])
@logged
def billing():
 if request.method=="POST":
  try:
   ids=request.form.getlist("pid"); qs=request.form.getlist("qty"); lines=[]; total=0
   with conn() as c:
    for pid,qt in zip(ids,qs):
     p=c.execute("SELECT * FROM products WHERE id=?",(int(pid),)).fetchone(); q=int(qt)
     if not p or q<1 or p["quantity"]<q: raise ValueError()
     amount=p["price"]*q; total+=amount; lines.append((p,q,amount))
    if not lines: raise ValueError()
    cur=c.execute("INSERT INTO sales(date,cashier,total,payment) VALUES(?,?,?,?)",(datetime.now().strftime("%Y-%m-%d %H:%M"),session["user"],total,request.form.get("payment","Cash"))); sid=cur.lastrowid
    for p,q,amount in lines:
     c.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,price,line_total) VALUES(?,?,?,?,?,?)",(sid,p["id"],p["name"],q,p["price"],amount)); c.execute("UPDATE products SET quantity=quantity-? WHERE id=?",(q,p["id"]))
   return redirect(url_for("receipt",sid=sid))
  except (ValueError,KeyError): flash("Invalid quantity or insufficient stock.","error"); return redirect(url_for("billing"))
 with conn() as c: ps=c.execute("SELECT * FROM products WHERE quantity>0 ORDER BY name").fetchall()
 return render_template("billing.html",ps=ps)
@app.route("/receipt/<int:sid>")
@logged
def receipt(sid):
 with conn() as c: sale=c.execute("SELECT * FROM sales WHERE id=?",(sid,)).fetchone(); items=c.execute("SELECT * FROM sale_items WHERE sale_id=?",(sid,)).fetchall()
 if not sale: return redirect(url_for("dashboard"))
 return render_template("receipt.html",sale=sale,items=items)
@app.route("/reports")
@logged
@admin
def reports():
 with conn() as c: rows=c.execute("SELECT * FROM sales ORDER BY id DESC").fetchall(); total=c.execute("SELECT COALESCE(SUM(total),0) n FROM sales").fetchone()["n"]
 return render_template("reports.html",rows=rows,total=total)
init()

if __name__=="__main__": app.run(debug=False)
