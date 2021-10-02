import os

from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

        list_stocks = []

        rows_users = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session["user_id"])

        current_cash = round(float(rows_users[0]["cash"]), 2)

        rows = db.execute("SELECT * FROM currentstocks WHERE id = :user_id", user_id = session["user_id"])

        total = 0

        for row in rows:

            symbol = row["symbol"]
            shares = int(row["shares"])
            name = lookup(symbol)["name"]
            current_price = round(float(lookup(symbol)["price"]), 2)
            current_total = round(float(current_price * shares), 2)

            list_stocks.append (
                {
                    "symbol" : symbol,
                    "shares" : shares,
                    "name" : name,
                    "current_price" : current_price,
                    "current_total" : current_total,
                }
            )

        for key in list_stocks:
            total = total + key["current_total"]

        total = total + current_cash

        return render_template("/index.html", list_stocks = list_stocks, current_cash = current_cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    if request.method == "POST":

        #Get symbol from customer
        symbol = request.form.get("symbol")

        #Get price from lookup function
        price = round(float(lookup(symbol)["price"]), 2)

        #Get number of shares to buy from customer
        shares = int(request.form.get("shares"))

        #Calculate total price of shares to buy
        total_price = round(float(price * shares), 2)

        #Get the name of the stock via lookup function
        name = lookup(symbol)["name"]

        #Get timestamp
        date = datetime.now()

        #Get user info from users table
        rows_users = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session["user_id"])

        #Get current cash from users table
        current_cash = round(float(rows_users[0]["cash"]), 2)

        #Get info from currentstocks table
        rows_currentstocks = db.execute("SELECT * FROM currentstocks WHERE id = :user_id", user_id = session["user_id"])

        existing_shares = db.execute("SELECT shares FROM currentstocks WHERE id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol = symbol)

        if not symbol:
            return apology("Please enter a stock symbol", 403)

        if lookup(symbol) == None:
            return apology("Stock doesn't exist", 403)

        if shares <= 0:
            return apology("Enter a valid number of shares", 403)

        if total_price > current_cash:
            return apology("You can't aford this shares", 403)

        if not existing_shares:

            db.execute("INSERT INTO currentstocks (id, symbol, name, shares) VALUES (:user_id, :symbol, :name, :shares)", user_id=session["user_id"], symbol=symbol, name=name, shares=shares)

        else:

            db.execute("UPDATE currentstocks SET shares = :shares WHERE id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol=symbol, shares = shares + int(existing_shares[0]["shares"]))

        current_cash = current_cash - total_price

        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", user_id = session["user_id"], cash = current_cash)

        db.execute("INSERT INTO buysell (id, symbol, name, price, total, shares, date) VALUES (:user_id, :symbol, :name, :price, :total, :shares, :date)", user_id=session["user_id"], symbol=symbol, name=name, price=price, total = total_price, shares=shares, date=date)

        return redirect("/")

    else:

        return render_template("buy.html")


@app.route("/history")
@login_required
def history():

    rows = db.execute("SELECT * FROM buysell WHERE id = :user_id", user_id = session["user_id"])

    return render_template("/history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    if request.method == "POST":

        input_symbol = request.form.get("symbol")
        name = lookup(input_symbol)["name"]
        price = lookup(input_symbol)["price"]
        symbol = lookup(input_symbol)["symbol"]

        return render_template("quoted.html", name=name, price=price, symbol=symbol)

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            return apology("enter a valid username", 403)

        elif (db.execute("SELECT username FROM users WHERE username = :username",
                          username=username)):
            return apology("username already taken", 403)

        elif not password:
            return apology("must provide password", 403)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 403)

        elif password != request.form.get("confirmation"):
            return apology("enter confirmation again", 403)

        password = generate_password_hash(password, method='pbkdf2:sha256', salt_length=8)

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)", username=username, password=password)

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username)

        session["user_id"] = rows[0]["id"]

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    rows_currentstocks = db.execute("SELECT * FROM currentstocks WHERE id = :user_id", user_id = session["user_id"])

    if request.method == "POST":

        #Get symbol from customer
        symbol = request.form.get("symbol")

        #Get price from lookup function
        price = round(float(lookup(symbol)["price"]), 2)

        #Get number of shares to buy from customer
        shares = int(request.form.get("shares"))

        #Calculate total price of shares to buy
        total_price = round(float(price * shares), 2)

        #Get the name of the stock via lookup function
        name = lookup(symbol)["name"]

        #Get timestamp
        date = datetime.now()

        #Get user info from users table
        rows_users = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session["user_id"])

        #Get current cash from users table
        current_cash = round(float(rows_users[0]["cash"]), 2)

        #Get info from currentstocks table

        existing_shares = db.execute("SELECT shares FROM currentstocks WHERE id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol = symbol)

        if not symbol:
            return apology("Please enter a stock symbol", 403)

        if shares > existing_shares[0]["shares"]:
            return apology("Enter valid amount of shares", 403)

        db.execute("UPDATE currentstocks SET shares = :shares WHERE id = :user_id AND symbol = :symbol", user_id = session["user_id"], symbol=symbol, shares = existing_shares[0]["shares"] - shares)

        current_cash = current_cash + total_price

        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", user_id = session["user_id"], cash = current_cash)

        db.execute("INSERT INTO buysell (id, symbol, name, price, total, shares, date) VALUES (:user_id, :symbol, :name, :price, :total, :shares, :date)", user_id=session["user_id"], symbol=symbol, name=name, price=-price, total = -total_price, shares=-shares, date=date)

        for row in existing_shares:
                db.execute("DELETE FROM currentstocks WHERE id=:user_id AND shares=:shares", user_id=session["user_id"], shares=0)

        return redirect("/")

    else:

        return render_template("sell.html", rows=rows_currentstocks)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
