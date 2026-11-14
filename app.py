from flask import Flask, render_template, request, redirect, url_for, session, flash
import random
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "number_guessing_secret_key"

# Database configuration
os.makedirs(app.instance_path, exist_ok=True)
DATABASE = os.path.join(app.instance_path, "game.db")


# Create database
def init_db():
    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE COLLATE NOCASE,
            password TEXT,
            best_score INTEGER DEFAULT 0,
            total_games INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


init_db()


# Get leaderboard
def get_leaderboard():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    players = conn.execute("""
        SELECT username, best_score, total_games
        FROM users
        WHERE best_score > 0
        ORDER BY best_score DESC, total_games ASC
        LIMIT 5
    """).fetchall()

    conn.close()
    return players


# Home page
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "index.html",
        page="game",
        game=session.get("game"),
        leaderboard=get_leaderboard()
    )


# Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3:
            flash("Username must contain at least 3 characters.", "error")
            return render_template("index.html", page="register")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return render_template("index.html", page="register")

        conn = sqlite3.connect(DATABASE)

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Username already exists!", "error")

        finally:
            conn.close()

    return render_template("index.html", page="register")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row

        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Welcome! Login successful.", "success")
            return redirect(url_for("home"))

        flash("Invalid username or password!", "error")

    return render_template("index.html", page="login")


# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("login"))


# Start a new game
@app.route("/new_game", methods=["POST"])
def new_game():
    if "user_id" not in session:
        return redirect(url_for("login"))

    difficulty = request.form.get("difficulty", "easy").lower()

    levels = {
        "easy": 50,
        "medium": 100,
        "hard": 200
    }

    if difficulty not in levels:
        difficulty = "easy"

    maximum = levels[difficulty]

    session["game"] = {
        "difficulty": difficulty.capitalize(),
        "max_number": maximum,
        "target": random.randint(1, maximum),
        "attempts": 0,
        "won": False,
        "score": 0,
        "message": "Game started! Enter your guess."
    }

    return redirect(url_for("home"))


# Check the guessed number
@app.route("/guess", methods=["POST"])
def guess():
    if "user_id" not in session:
        return redirect(url_for("login"))

    game = session.get("game")

    if not game:
        flash("Please start a new game first.", "error")
        return redirect(url_for("home"))

    if game["won"]:
        return redirect(url_for("home"))

    value = request.form.get("guess", "").strip()

    try:
        number = int(value)
    except ValueError:
        game["message"] = "Please enter a valid number."
        session["game"] = game
        return redirect(url_for("home"))

    if number < 1 or number > game["max_number"]:
        game["message"] = (
            f"Enter a number between 1 and {game['max_number']}."
        )
        session["game"] = game
        return redirect(url_for("home"))

    game["attempts"] += 1

    if number < game["target"]:
        game["message"] = "Too Low! Try a higher number."

    elif number > game["target"]:
        game["message"] = "Too High! Try a lower number."

    else:
        game["won"] = True
        game["score"] = max(10, 100 - (game["attempts"] - 1) * 10)
        game["message"] = (
            f"Congratulations! You guessed the correct number: {number}"
        )

        conn = sqlite3.connect(DATABASE)
        conn.execute("""
            UPDATE users
            SET best_score = MAX(best_score, ?),
                total_games = total_games + 1
            WHERE id = ?
        """, (game["score"], session["user_id"]))
        conn.commit()
        conn.close()

    session["game"] = game
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
