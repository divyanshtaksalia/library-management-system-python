from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS 
import firebase_admin
from firebase_admin import credentials, initialize_app, firestore
from dotenv import load_dotenv
import os
import uuid # To generate unique user IDs
import json # New import for loading credentials from JSON string

# 1. Load environment variables from the .env file
load_dotenv()

# Constants
USERS_COLLECTION = 'users'
BOOKS_COLLECTION = 'books'
ISSUE_COLLECTION = 'issues'
RETURN_COLLECTION = 'returns'

# Global Firebase and Firestore objects
firebase_app = None
db = None

def initialize_firebase():
    """Initializes the Firebase Admin SDK and returns the db object.

    It checks for FIREBASE_SA_JSON environment variable (for Vercel deployment)
    first, and falls back to FIREBASE_SA_FILE path (for local development).
    """
    global firebase_app, db

    try:
        # --- Vercel/Cloud Deployment Method (Preferred) ---
        sa_json_string = os.getenv("FIREBASE_SA_JSON")

        if sa_json_string:
            # Load credentials from the environment variable string
            # We must parse the JSON string into a Python dict first
            cred_dict = json.loads(sa_json_string)
            cred = credentials.Certificate(cred_dict)
            print("Firebase credentials loaded from environment variable (Vercel/Cloud).")

        else:
            # --- Local Development Method (Fallback) ---
            sa_file = os.getenv("FIREBASE_SA_FILE")

            if not sa_file or not os.path.exists(sa_file):
                print(f"ERROR: Service account file not found at path specified in .env: {sa_file}")
                return None, None

            # Load credentials from the local file path
            cred = credentials.Certificate(sa_file)
            print("Firebase credentials loaded from local file.")

        # Continue with initialization
        if not firebase_admin._apps:
            firebase_app = initialize_app(cred)
        else:
            firebase_app = firebase_admin.get_app()

        db = firestore.client()
        print("Firebase Admin SDK initialized successfully.")
        return firebase_app, db

    except Exception as e:
        print(f"ERROR: Failed to initialize Firebase: {e}")
        return None, None

firebase_app, db = initialize_firebase()

app = Flask(__name__)

# Define the upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the uploads folder if it doesn't exist (important for local development)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Allow CORS for development
CORS(app)

# ==============================================================================
# BASE ROUTE
# ==============================================================================

@app.route('/', methods=['GET'])
def home():
    """A simple route to confirm that the server is running."""
    if not firebase_app:
        return jsonify({
            "message": "Python backend is running, but Firebase failed to initialize! Check your firebase-service-account.json path or FIREBASE_SA_JSON environment variable.",
            "status": "error"
        }), 500

    return jsonify({
        "message": "Python backend is running! Firebase initialized successfully.",
        "status": "ok"
    })

# Route to serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==============================================================================
# USER MANAGEMENT & AUTHENTICATION (Simulated)
# ==============================================================================

@app.route('/api/register', methods=['POST'])
def register():
    """Simulates user registration."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password') # In a real app, hash this password!

    if not all([username, email, password]):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    try:
        # Check if user already exists
        users_ref = db.collection(USERS_COLLECTION)
        existing_user = users_ref.where('email', '==', email).limit(1).get()

        if existing_user:
            return jsonify({"success": False, "message": "User with this email already exists."}), 409

        # Generate unique ID (Simulating Firebase Auth UID)
        user_id = str(uuid.uuid4())

        # Create new user document
        user_data = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'password_hash': password, # Storing plaintext for simulation, DON'T do this in production!
            'role': 'student', # Default role
            'account_status': 'active',
            'created_at': firestore.SERVER_TIMESTAMP,
            'profile_picture_url': '' # Placeholder for profile picture
        }
        
        users_ref.document(user_id).set(user_data)

        return jsonify({"success": True, "message": "Registration successful! Please log in."}), 201

    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Simulates user login."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"success": False, "message": "Missing email or password."}), 400

    try:
        users_ref = db.collection(USERS_COLLECTION)
        
        # In a real app, Firebase Auth handles this securely. 
        # Here we simulate with Firestore query.
        query_ref = users_ref.where('email', '==', email).where('password_hash', '==', password).limit(1)
        user_docs = query_ref.get()

        if not user_docs:
            return jsonify({"success": False, "message": "Invalid credentials or user not found."}), 401

        user_doc = user_docs[0]
        user_data = user_doc.to_dict()

        if user_data.get('account_status') == 'blocked':
            return jsonify({"success": False, "message": "Your account has been blocked by the admin."}), 403

        # Prepare user info for frontend storage
        user_info = {
            "id": user_doc.id,
            "username": user_data.get('username'),
            "email": user_data.get('email'),
            "role": user_data.get('role'),
            "profile_picture_url": user_data.get('profile_picture_url', '')
        }

        return jsonify({"success": True, "message": "Login successful.", "user": user_info}), 200

    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users', methods=['GET'])
def get_all_users():
    """Get all users (admin only view)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        users = []
        for doc in db.collection(USERS_COLLECTION).stream():
            data = doc.to_dict()
            users.append({
                'user_id': doc.id,
                'username': data.get('username'),
                'email': data.get('email'),
                'role': data.get('role'),
                'account_status': data.get('account_status'),
            })
        
        # Sort users by role (admin first, then student) and then by username
        users.sort(key=lambda x: (0 if x['role'] == 'admin' else 1, x['username']))

        return jsonify({"success": True, "users": users}), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/status', methods=['POST'])
def update_user_status():
    """Update user account status (active/blocked)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
        
    data = request.get_json()
    user_id = data.get('userId')
    status = data.get('status') # 'active' or 'blocked'

    if not all([user_id, status]):
        return jsonify({"success": False, "message": "Missing user ID or status."}), 400

    if status not in ['active', 'blocked']:
        return jsonify({"success": False, "message": "Invalid status value."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        
        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404
        
        user_ref.update({'account_status': status})
        
        message = f"User account successfully {'activated' if status == 'active' else 'blocked'}."
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/user/delete/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user document and their corresponding Firestore collection by their ID."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)

        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        user_ref.delete()

        return jsonify({"success": True, "message": "User deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# ==============================================================================
# PROFILE PICTURE
# ==============================================================================

@app.route('/api/user/update-profile-picture', methods=['POST'])
def update_profile_picture():
    """Handles profile picture upload and saves the file path to Firestore."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    if 'image' not in request.files:
        return jsonify({"success": False, "message": "No image file provided."}), 400
    
    file = request.files['image']
    user_id = request.form.get('userId')

    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400

    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file."}), 400

    if file:
        # Create a unique filename using the user ID
        file_extension = os.path.splitext(file.filename)[1]
        filename = f"{user_id}_profile{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        try:
            # Save the file to the 'uploads' directory
            file.save(filepath)
            
            # The URL to serve the file (Vercel will map /uploads/ to the folder)
            image_url = f"/uploads/{filename}"

            # Update the user's profile picture URL in Firestore
            user_ref = db.collection(USERS_COLLECTION).document(user_id)
            user_ref.update({'profile_picture_url': image_url})
            
            return jsonify({"success": True, "message": "Profile picture updated.", "image_url": image_url}), 200

        except Exception as e:
            print(f"Error updating profile picture: {e}")
            return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# ==============================================================================
# BOOK MANAGEMENT (CRUD)
# ==============================================================================

@app.route('/api/books', methods=['POST'])
def add_book():
    """Adds a new book to the library."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    category = request.form.get('category')
    total_copies = int(request.form.get('total_copies', 0))
    image_file = request.files.get('image')

    if not all([title, author, isbn, category, total_copies > 0]):
        return jsonify({"success": False, "message": "Missing required book details."}), 400

    try:
        # Check if book already exists by ISBN
        books_ref = db.collection(BOOKS_COLLECTION)
        existing_book = books_ref.where('isbn', '==', isbn).limit(1).get()

        if existing_book:
            return jsonify({"success": False, "message": "Book with this ISBN already exists."}), 409

        # Generate unique ID for the book
        book_id = str(uuid.uuid4())
        image_url = ''

        if image_file:
            # Create a unique filename
            file_extension = os.path.splitext(image_file.filename)[1]
            filename = f"{book_id}_cover{file_extension}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image_url = f"/uploads/{filename}"

        book_data = {
            'book_id': book_id,
            'title': title,
            'author': author,
            'isbn': isbn,
            'category': category,
            'total_copies': total_copies,
            'available_copies': total_copies, # Initially all are available
            'image_url': image_url,
            'created_at': firestore.SERVER_TIMESTAMP,
        }

        books_ref.document(book_id).set(book_data)

        return jsonify({"success": True, "message": "Book added successfully!"}), 201

    except Exception as e:
        print(f"Error adding book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books', methods=['GET'])
def get_all_books():
    """Fetches all books from the library."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        books = []
        for doc in db.collection(BOOKS_COLLECTION).stream():
            data = doc.to_dict()
            books.append({
                'id': doc.id,
                'title': data.get('title'),
                'author': data.get('author'),
                'isbn': data.get('isbn'),
                'category': data.get('category'),
                'total_copies': data.get('total_copies'),
                'available_copies': data.get('available_copies'),
                'image_url': data.get('image_url', '')
            })
        
        return jsonify({"success": True, "books": books}), 200

    except Exception as e:
        print(f"Error fetching books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/<string:book_id>', methods=['PUT'])
def update_book(book_id):
    """Updates an existing book's details."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    # For simplicity, we are using get_json here, but a real update 
    # might use request.form/request.files if image is being updated.
    data = request.get_json()
    title = data.get('title')
    author = data.get('author')
    isbn = data.get('isbn')
    category = data.get('category')

    if not all([title, author, isbn, category]):
        return jsonify({"success": False, "message": "Missing required book details."}), 400

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        
        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_ref.update({
            'title': title,
            'author': author,
            'isbn': isbn,
            'category': category,
        })
        
        return jsonify({"success": True, "message": "Book updated successfully!"}), 200

    except Exception as e:
        print(f"Error updating book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books/<string:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Deletes a book from the library."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        
        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404
        
        # Check for any active issue requests/orders before deleting (simplistic check)
        active_issues = db.collection(ISSUE_COLLECTION).where('book_id', '==', book_id).where('status', 'in', ['pending', 'issued']).limit(1).get()
        if active_issues:
            return jsonify({"success": False, "message": "Cannot delete: This book has pending or active issue requests."}), 400
            
        book_ref.delete()
        
        return jsonify({"success": True, "message": "Book deleted successfully!"}), 200

    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/update-copies', methods=['POST'])
def update_book_copies():
    """Updates the total number of copies for a book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
        
    data = request.get_json()
    book_id = data.get('bookId')
    new_total_copies = int(data.get('totalCopies', 0))

    if not book_id or new_total_copies < 0:
        return jsonify({"success": False, "message": "Invalid book ID or copy count."}), 400

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_data = book_doc.to_dict()
        old_total_copies = book_data.get('total_copies', 0)
        available_copies = book_data.get('available_copies', 0)
        
        change_in_copies = new_total_copies - old_total_copies
        new_available_copies = available_copies + change_in_copies

        if new_available_copies < 0:
            return jsonify({"success": False, "message": "Cannot reduce copies. It would result in negative available copies."}), 400

        book_ref.update({
            'total_copies': new_total_copies,
            'available_copies': new_available_copies,
        })
        
        return jsonify({"success": True, "message": "Book copies updated successfully!"}), 200

    except Exception as e:
        print(f"Error updating book copies: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# ==============================================================================
# BOOK ISSUE/RETURN LOGIC
# ==============================================================================

@app.route('/api/issue-book', methods=['POST'])
def issue_book_request():
    """Student requests to issue a book (creates a 'pending' request)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    user_id = data.get('userId')
    book_id = data.get('bookId')

    if not all([user_id, book_id]):
        return jsonify({"success": False, "message": "Missing user ID or book ID."}), 400

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()
        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_data = book_doc.to_dict()

        if book_data.get('available_copies', 0) <= 0:
            return jsonify({"success": False, "message": "Book is currently out of stock."}), 400

        # Check for existing active/pending issue for this book by this user
        existing_request = db.collection(ISSUE_COLLECTION).where('user_id', '==', user_id).where('book_id', '==', book_id).where('status', 'in', ['pending', 'issued']).limit(1).get()
        if existing_request:
            return jsonify({"success": False, "message": "You already have this book issued or a request is pending."}), 400

        issue_id = str(uuid.uuid4())
        
        issue_data = {
            'issue_id': issue_id,
            'user_id': user_id,
            'book_id': book_id,
            'title': book_data.get('title'),
            'image_url': book_data.get('image_url', ''),
            'author': book_data.get('author'),
            'request_date': firestore.SERVER_TIMESTAMP,
            'status': 'pending'
        }
        
        db.collection(ISSUE_COLLECTION).document(issue_id).set(issue_data)
        
        return jsonify({"success": True, "message": "Book issue request submitted successfully and is pending admin approval."}), 201

    except Exception as e:
        print(f"Error submitting issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/issue-requests', methods=['GET'])
def get_issue_requests():
    """Admin fetches all pending issue requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        requests = []
        # Get only pending requests
        query = db.collection(ISSUE_COLLECTION).where('status', '==', 'pending').stream()
        
        for doc in query:
            data = doc.to_dict()
            
            # Fetch user info
            user_doc = db.collection(USERS_COLLECTION).document(data['user_id']).get()
            user_data = user_doc.to_dict() if user_doc.exists else {'username': 'Unknown User'}

            requests.append({
                'issue_id': doc.id,
                'book_id': data.get('book_id'),
                'title': data.get('title'),
                'author': data.get('author'),
                'username': user_data.get('username'),
                'user_id': data.get('user_id'),
                'request_date': data.get('request_date').isoformat() if data.get('request_date') else None,
            })
        
        return jsonify({"success": True, "requests": requests}), 200

    except Exception as e:
        print(f"Error fetching issue requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/handle-issue-request', methods=['POST'])
def handle_issue_request():
    """Admin approves or rejects an issue request."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    issue_id = data.get('issueId')
    action = data.get('action') # 'approve' or 'reject'

    if not all([issue_id, action]) or action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Missing ID or invalid action."}), 400

    try:
        issue_ref = db.collection(ISSUE_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists:
            return jsonify({"success": False, "message": "Issue request not found."}), 404

        issue_data = issue_doc.to_dict()
        book_id = issue_data['book_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if action == 'approve':
            # Check book availability inside a transaction for safety
            # Vercel environment may not fully support transactions as easily, so we use simpler update logic here:
            book_doc = book_ref.get()
            if not book_doc.exists:
                return jsonify({"success": False, "message": "Book not found."}), 404
            
            book_data = book_doc.to_dict()
            available_copies = book_data.get('available_copies', 0)
            
            if available_copies <= 0:
                return jsonify({"success": False, "message": "Book is no longer available for issue."}), 400

            # Update issue record
            issue_ref.update({
                'status': 'issued',
                'issue_date': firestore.SERVER_TIMESTAMP
            })

            # Decrement available copies
            book_ref.update({
                'available_copies': firestore.firestore.Increment(-1)
            })
            
            message = "Issue request approved. Book is now issued."
            
        elif action == 'reject':
            issue_ref.update({'status': 'rejected'})
            message = "Issue request rejected."

        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        print(f"Error handling issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/my-orders', methods=['GET'])
def get_my_orders():
    """Fetches a user's currently issued and pending books."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "User ID is missing."}), 400

    try:
        orders = []
        # Get issued and pending requests
        query = db.collection(ISSUE_COLLECTION).where('user_id', '==', user_id).where('status', 'in', ['pending', 'issued']).stream()
        
        for doc in query:
            data = doc.to_dict()
            
            # Fetch book details
            book_doc = db.collection(BOOKS_COLLECTION).document(data['book_id']).get()
            book_data = book_doc.to_dict() if book_doc.exists else {}

            orders.append({
                'issue_id': doc.id,
                'book_id': data.get('book_id'),
                'title': data.get('title', book_data.get('title')),
                'author': data.get('author', book_data.get('author')),
                'image_url': data.get('image_url', book_data.get('image_url')),
                'status': data.get('status'),
                'request_date': data.get('request_date').isoformat() if data.get('request_date') else None,
                'issue_date': data.get('issue_date').isoformat() if data.get('issue_date') else None,
            })
        
        return jsonify({"success": True, "orders": orders}), 200

    except Exception as e:
        print(f"Error fetching user orders: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-book', methods=['POST'])
def return_book_request():
    """Student requests to return an issued book (creates a return request)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    issue_id = data.get('issueId')
    user_id = data.get('userId')

    if not all([issue_id, user_id]):
        return jsonify({"success": False, "message": "Missing required IDs."}), 400

    try:
        issue_ref = db.collection(ISSUE_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists or issue_doc.to_dict().get('status') != 'issued':
            return jsonify({"success": False, "message": "Book is not currently issued or issue record not found."}), 400
            
        if issue_doc.to_dict().get('user_id') != user_id:
            return jsonify({"success": False, "message": "Not authorized to return this book."}), 403

        # Check if a return request is already pending
        existing_return_request = db.collection(RETURN_COLLECTION).where('issue_id', '==', issue_id).where('status', '==', 'pending').limit(1).get()
        if existing_return_request:
            return jsonify({"success": False, "message": "A return request for this book is already pending."}), 400

        issue_data = issue_doc.to_dict()
        return_id = str(uuid.uuid4())

        return_data = {
            'return_id': return_id,
            'issue_id': issue_id,
            'user_id': user_id,
            'book_id': issue_data['book_id'],
            'request_date': firestore.SERVER_TIMESTAMP,
            'status': 'pending'
        }

        db.collection(RETURN_COLLECTION).document(return_id).set(return_data)
        
        return jsonify({"success": True, "message": "Return request submitted. Pending admin approval."}), 201

    except Exception as e:
        print(f"Error submitting return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/return-requests', methods=['GET'])
def get_return_requests():
    """Admin fetches all pending return requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        requests = []
        # Get only pending requests
        query = db.collection(RETURN_COLLECTION).where('status', '==', 'pending').stream()
        
        for doc in query:
            data = doc.to_dict()
            issue_id = data['issue_id']
            user_id = data['user_id']
            book_id = data['book_id']

            # Fetch supplementary data
            user_doc = db.collection(USERS_COLLECTION).document(user_id).get()
            book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
            
            user_data = user_doc.to_dict() if user_doc.exists else {'username': 'Unknown User'}
            book_data = book_doc.to_dict() if book_doc.exists else {'title': 'Unknown Book', 'author': 'N/A'}

            requests.append({
                'return_id': doc.id,
                'issue_id': issue_id,
                'user_id': user_id,
                'book_id': book_id,
                'title': book_data.get('title'),
                'author': book_data.get('author'),
                'username': user_data.get('username'),
                'request_date': data.get('request_date').isoformat() if data.get('request_date') else None,
            })
        
        return jsonify({"success": True, "requests": requests}), 200

    except Exception as e:
        print(f"Error fetching return requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-return', methods=['POST'])
def handle_return_request():
    """Admin approves or rejects a return request."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    return_id = data.get('returnId')
    action = data.get('action') # 'approve' or 'reject'

    if not all([return_id, action]) or action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Missing ID or invalid action."}), 400

    try:
        return_ref = db.collection(RETURN_COLLECTION).document(return_id)
        return_doc = return_ref.get()

        if not return_doc.exists:
            return jsonify({"success": False, "message": "Return request not found."}), 404

        return_data = return_doc.to_dict()
        issue_id = return_data['issue_id']
        book_id = return_data['book_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        issue_ref = db.collection(ISSUE_COLLECTION).document(issue_id)

        if action == 'approve':
            # 1. Update return record
            return_ref.update({
                'status': 'approved',
                'return_date': firestore.SERVER_TIMESTAMP
            })

            # 2. Update the original issue record status to 'returned'
            issue_ref.update({'status': 'returned'})
            
            # 3. Increment available copies
            book_ref.update({
                'available_copies': firestore.firestore.Increment(1)
            })
            
            message = "Book return approved. Book is back in stock."
            
        elif action == 'reject':
            return_ref.update({'status': 'rejected'})
            message = "Book return request rejected."

        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        print(f"Error handling return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/returned-books', methods=['GET'])
def get_returned_books():
    """Fetches a user's return history (all 'returned' issues)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "User ID is missing."}), 400

    try:
        returned_history = []
        # Get only 'returned' issues
        issue_query = db.collection(ISSUE_COLLECTION).where('user_id', '==', user_id).where('status', '==', 'returned').stream()
        
        for doc in issue_query:
            data = doc.to_dict()
            
            # Find the corresponding return record for the return_date
            return_query = db.collection(RETURN_COLLECTION).where('issue_id', '==', doc.id).where('status', '==', 'approved').limit(1).get()
            return_date = None
            if return_query:
                return_date = return_query[0].to_dict().get('return_date')
            
            returned_history.append({
                'issue_id': doc.id,
                'title': data.get('title'),
                'author': data.get('author'),
                'issue_date': data.get('issue_date').isoformat() if data.get('issue_date') else None,
                'return_date': return_date.isoformat() if return_date else 'N/A',
                'image_url': data.get('image_url', '')
            })
        
        return jsonify({"success": True, "history": returned_history}), 200

    except Exception as e:
        print(f"Error fetching return history: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


if __name__ == '__main__':
    # Ensure this runs locally only
    app.run(debug=True, port=int(os.environ.get('SERVER_PORT', 5001)))