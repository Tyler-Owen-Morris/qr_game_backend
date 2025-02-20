import os
import qrcode
import requests
from flask import Flask, render_template, session, redirect, url_for, request,jsonify
from flask_socketio import SocketIO, emit
import json
import base64
from io import BytesIO
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Default backend URL (can be modified dynamically)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'  # Required for Flask-SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def login_page():
    print('auth_token' in session, session)
    if 'auth_token' in session:
        return render_template('logged_in.html', token=session['auth_token'])
    
    try:
        # Request session ID from FastAPI backend
        response = requests.post(f"{BACKEND_URL}/auth/qr-login-init")
        if response.status_code != 200:
            logger.error(f"Failed to fetch session ID: {response.status_code} {response.text}")
            return "Error fetching session ID", 500
        
        session_data = response.json()
        session['session_id'] = session_data.get("session_id")
        if not session['session_id']:
            logger.error("Invalid response format from backend")
            return "Error: Invalid response from server", 500

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"arg://login.{session['session_id']}")
        qr.make(fit=True)

        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64 for displaying in HTML
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return render_template('login.html', qr_code=img_str, session_id=session['session_id'])
    except Exception as e:
        logger.error(f"Error generating QR code: {str(e)}")
        return f"Error generating QR code: {str(e)}", 500

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected to WebSocket")
    if 'session_id' in session:
        emit('listen_for_auth', {'session_id': session['session_id']})

@socketio.on('login_success')
def handle_login_success(data):
    if data.get('event') == 'login_success':
        auth_token = data.get('token')
        print("AUTH TOKEN:",auth_token)
        if auth_token:
            session['auth_token'] = auth_token
            logger.info(f"User authenticated with token: {auth_token}")

            # Notify the frontend that the user is authenticated
            emit('authenticated', {'message': 'Logged in successfully', 'token': auth_token}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected from WebSocket")

@app.route('/logout')
def logout():
    session.pop('auth_token', None)
    session.pop('session_id', None)
    return redirect(url_for('login_page'))

@app.route('/set-session', methods=['POST'])
def set_session():
    data = request.get_json()
    token = data.get("token")

    if token:
        session['auth_token'] = token  # Store in session instead of cookie
        return jsonify({"success": True})

    return jsonify({"success": False}), 400


if __name__ == '__main__':
    # Make sure the templates directory exists
    os.makedirs('templates', exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
