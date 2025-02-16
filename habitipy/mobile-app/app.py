from flask import Flask, render_template, session, redirect, url_for
from flask_socketio import SocketIO
from habitipy import api
import os

app = Flask(__name__)
# Add secret key for sessions
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app)

@app.route('/')
def index():
    # Add basic authentication
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return render_template('index.html')

if __name__ == '__main__':
    # Don't run debug mode in production
    socketio.run(app, debug=False) 