#!/usr/bin/python3
"""
The GitLens WebApp Backend using Flask for Website functionalities.
"""
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_sqlite_db():
    conn = sqlite3.connect('database.db')
    print("Opened database successfully")

    conn.execute('CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT, email TEXT, contact_link TEXT)')
    print("Table created successfully")
    # Check if 'is_verified' column exists before adding it
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pragma_table_info('users') WHERE name='is_verified'")
    exists = cursor.fetchone()
    if not exists:
        conn.execute('ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE')
        print("Verified Users Table created successfully")

    # Check if 'contact_link' column exists before adding it
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pragma_table_info('users') WHERE name='contact_link'")
    exists = cursor.fetchone()
    if not exists:
        conn.execute('ALTER TABLE users ADD COLUMN contact_link TEXT')
        print("Contact link column added successfully")
    
    conn.close()

init_sqlite_db()

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/register_page/')
def register_page():
    return render_template('register.html')

@app.route('/login_page/')
def login_page():
    return render_template('index.html')

@app.route('/register/', methods=['POST'])
def register():
    msg = ''
    try:
        post_data = request.form
        username = post_data['username']
        password = post_data['password']
        email = post_data['email']

        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, password, email))
            con.commit()
            msg = "User successfully registered."
    except Exception as e:
        con.rollback()
        msg = "Error occurred: " + str(e)
    finally:
        con.close()
        return redirect(url_for('home'))

@app.route('/login/', methods=['POST'])
def login():
    post_data = request.form
    username = post_data['username']
    password = post_data['password']

    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        account = cur.fetchone()

        if account:
            session['loggedin'] = True
            session['username'] = account[0]
            return redirect(url_for('dashboard'))
        else:
            msg = "Incorrect username or password."
            return render_template('index.html', msg=msg)

@app.route('/logout/', methods=['POST'])
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    return redirect(url_for('home'))

@app.route('/profile')
def profile():
    if 'loggedin' in session:
        username = session['username']
        user = get_user_from_db(username)
        if user:
            return render_template('profile.html', username=username, email=user['email'], contact_link=user.get('contact_link', ''))
        else:
            return "User not found."
    return redirect(url_for('home'))

@app.route('/save_profile', methods=['POST'])
def save_profile():
    if 'loggedin' in session:
        username = session['username']
        new_email = request.form['email']
        new_contact_link = request.form['contact_link']

        with sqlite3.connect('database.db') as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET email = ?, contact_link = ? WHERE username = ?", (new_email, new_contact_link, username))
            con.commit()

            # Optionally update session data or handle verification logic

        return redirect(url_for('profile'))
    else:
        return redirect(url_for('home'))

@app.route('/user/<username>')
def user_profile(username):
    user = get_user_from_db(username)  # Function to get user data from the database
    if user:
        return render_template('profile.html', username=username, email=user['email'], contact_link=user.get('contact_link', ''), is_verified=user['is_verified'])
    else:
        return "User not found."

def verify_user(username):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("UPDATE users SET is_verified = TRUE WHERE username = ?", (username,))
        con.commit()

def check_if_user_is_verified(username):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("SELECT is_verified FROM users WHERE username = ?", (username,))
        result = cur.fetchone()
        return result[0] if result else False

@app.route('/admin/')
def admin():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return render_template('admin.html', users=users)

@app.route('/verify_user/<username>', methods=['POST'])
def verify_user_route(username):
    if 'loggedin' in session:
        verify_user(username)
        return redirect(url_for('admin'))
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        username = session['username']
        is_verified = check_if_user_is_verified(username)
        user = get_user_from_db(username)
        if user:
            contact_link = user.get('contact_link', '')
            # Create a user dictionary with the username and contact_link
            user_data = {'username': username, 'contact_link': contact_link}
            # Pass the user dictionary to the template
            return render_template('dashboard.html', user=user_data, is_verified=is_verified)
        else:
            return "User not found."
    return redirect(url_for('home'))

@app.route('/github_search', methods=['POST'])
def github_search():
    data = request.json
    username = data.get('github_username')
    headers = {
        'Authorization': 'token INSERT_YOUR_TOKEN_HERE'
    }
    user_url = f'https://api.github.com/users/{username}'
    repos_url = f'https://api.github.com/users/{username}/repos'

    user_response = requests.get(user_url, headers=headers)
    repos_response = requests.get(repos_url, headers=headers)

    if user_response.status_code == 200 and repos_response.status_code == 200:
        user_data = user_response.json()
        repos_data = repos_response.json()

        stars = 0
        repo_badges = []
        all_languages = {}

        for repo in repos_data:
            stars += repo.get('stargazers_count', 0)
            badge_url = f"https://img.shields.io/github/stars/{username}/{repo['name']}.svg?style=social&label=Star"
            repo_badges.append(badge_url)
            
            # Fetch languages for each repo
            languages_url = repo['languages_url']
            languages_response = requests.get(languages_url)
            if languages_response.status_code == 200:
                repo_languages = languages_response.json()
                for lang, bytes in repo_languages.items():
                    if lang in all_languages:
                        all_languages[lang] += bytes
                    else:
                        all_languages[lang] = bytes

        # Sort languages by bytes of code
        sorted_languages = sorted(all_languages.items(), key=lambda item: item[1], reverse=True)

        response = {
            'avatar_url': user_data['avatar_url'],
            'name': user_data.get('name', ''),
            'login': user_data['login'],
            'public_repos': user_data['public_repos'],
            'followers': user_data['followers'],
            'following': user_data['following'],
            'html_url': user_data['html_url'],
            'stars': stars,
            'repo_badges': repo_badges,
            'languages': [lang for lang, _ in sorted_languages],
        }
        return jsonify(response)
    else:
        return jsonify({'error': 'User not found'}), 404

def get_user_from_db(username):
    with sqlite3.connect('database.db') as con:
        cur = con.cursor()
        cur.execute("SELECT username, email, is_verified, contact_link FROM users WHERE username = ?", (username,))
        result = cur.fetchone()
        if result:
            return {'username': result[0], 'email': result[1], 'is_verified': result[2], 'contact_link': result[3]}
        return None

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
