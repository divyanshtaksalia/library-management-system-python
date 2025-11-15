import os
import uuid
import json
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# --- Constants ---
USERS_COLLECTION = 'users'
BOOKS_COLLECTION = 'books'
ISSUES_COLLECTION = 'issues'
RETURN_REQUESTS_COLLECTION = 'return_requests'

# --- Initialization ---

# 1. Load environment variables from .env file
load_dotenv()

def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using credentials
    from an environment variable.
    """
    try:
        sa_file_path = os.getenv("FIREBASE_SA_FILE")
        if not sa_file_path or not os.path.exists(sa_file_path):
            print(f"ERROR: Service account file not found. Path: {sa_file_path}")
            print(f"Please set the FIREBASE_SA_FILE environment variable to the path of your JSON key file.")
            return None, None

        cred = credentials.Certificate(sa_file_path)
        
        # Check if the app is already initialized
        if not firebase_admin._apps:
            firebase_app = firebase_admin.initialize_app(cred)
        else:
            firebase_app = firebase_admin.get_app()

        db_client = firestore.client()
        print("Firebase Admin SDK initialized successfully.")
        return firebase_app, db_client
        
    except ValueError as ve:
        # This catches "The default Firebase app already exists." if called multiple times
        try:
            firebase_app = firebase_admin.get_app()
            db_client = firestore.client()
            print("Firebase Admin SDK retrieved existing app successfully.")
            return firebase_app, db_client
        except Exception as e:
            print(f"ERROR: Failed to retrieve existing Firebase app: {e}")
            return None, None
    except Exception as e:
        print(f"ERROR: Failed to initialize Firebase: {e}")
        return None, None

firebase_app, db = initialize_firebase()

# Create Flask app instance
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# Define the upload folder and ensure it exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Utility Functions ---

def is_admin(user_id):
    """Checks if a user has admin role."""
    if not db:
        return False
    user_doc = db.collection(USERS_COLLECTION).document(user_id).get()
    return user_doc.exists and user_doc.to_dict().get('role') == 'admin'

def get_book_details(book_id):
    """Retrieves book details by ID."""
    if not db:
        return None
    book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
    if book_doc.exists:
        book_data = book_doc.to_dict()
        book_data['id'] = book_doc.id
        return book_data
    return None

# --- User/Auth API Routes ---

@app.route('/api/register', methods=['POST'])
def register():
    """Handles user registration."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not all([username, email, password]):
        return jsonify({"success": False, "message": "Missing required fields."}), 400

    try:
        # Check if user already exists
        users_ref = db.collection(USERS_COLLECTION)
        existing_user = users_ref.where('email', '==', email).limit(1).get()

        if existing_user:
            return jsonify({"success": False, "message": "User with this email already exists."}), 409

        # Determine role (first user is admin, all others are students)
        if not users_ref.limit(1).get():
            role = 'admin'
        else:
            role = 'student'

        # Create new user
        user_data = {
            'username': username,
            'email': email,
            'password_hash': generate_password_hash(password),
            'role': role,
            'account_status': 'active',
            'created_at': firestore.SERVER_TIMESTAMP,
            'profile_picture_url': None
        }

        users_ref.add(user_data)
        return jsonify({"success": True, "message": "Registration successful. You can now log in."}), 201

    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """Handles user login."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"success": False, "message": "Missing email or password."}), 400

    try:
        users_ref = db.collection(USERS_COLLECTION)
        query = users_ref.where('email', '==', email).limit(1).get()

        if not query:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

        user_doc = query[0]
        user_data = user_doc.to_dict()

        if user_data.get('account_status') == 'blocked':
            return jsonify({"success": False, "message": "Your account has been blocked by the admin."}), 403

        if check_password_hash(user_data['password_hash'], password):
            user_info = {
                'id': user_doc.id,
                'username': user_data['username'],
                'role': user_data['role'],
                'profile_picture_url': user_data.get('profile_picture_url')
            }
            return jsonify({"success": True, "message": "Login successful.", "user": user_info}), 200
        else:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/user/update-profile-picture', methods=['POST'])
def update_profile_picture():
    """Updates the user's profile picture and returns the new URL."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        user_id = request.form.get('userId')
        image_file = request.files.get('image')

        if not user_id or not image_file:
            return jsonify({"success": False, "message": "Missing user ID or image file."}), 400
        
        # Simple admin check - only the user or admin can change the profile picture
        # For production, proper token-based authorization is needed.

        # Save the file
        filename = f"{user_id}_{uuid.uuid4().hex}_{secure_filename(image_file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        
        # Generate the public URL (relative path for Vercel/Flask static serving)
        image_url = f"/uploads/{filename}"

        # Update Firestore
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        user_ref.update({'profile_picture_url': image_url})

        return jsonify({"success": True, "message": "Profile picture updated.", "image_url": image_url}), 200

    except Exception as e:
        print(f"Error updating profile picture: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Admin Routes (Books/Users) ---

@app.route('/api/books', methods=['POST'])
def add_book():
    """Admin: Adds a new book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    # Simple auth check (assuming Admin ID is passed in the request or token)
    # For now, we'll assume the client handles the admin role check
    
    try:
        title = request.form.get('title')
        author = request.form.get('author')
        category = request.form.get('category')
        copies = int(request.form.get('copies', 0))
        image_file = request.files.get('image')

        if not all([title, author, category]) or copies <= 0:
            return jsonify({"success": False, "message": "Missing required fields or invalid copies count."}), 400

        image_url = None
        if image_file:
            # Save the image file
            filename = f"book_{uuid.uuid4().hex}_{secure_filename(image_file.filename)}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image_url = f"/uploads/{filename}"

        book_data = {
            'title': title,
            'author': author,
            'category': category,
            'copies': copies,
            'available_copies': copies,
            'image_url': image_url,
            'created_at': firestore.SERVER_TIMESTAMP
        }

        db.collection(BOOKS_COLLECTION).add(book_data)
        return jsonify({"success": True, "message": "Book added successfully."}), 201

    except Exception as e:
        print(f"Error adding book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/<book_id>', methods=['PUT'])
def update_book(book_id):
    """Admin: Updates an existing book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    # Note: Handling image update logic is complex, for simplicity, this only updates metadata and copies.

    try:
        data = request.get_json()
        title = data.get('title')
        author = data.get('author')
        category = data.get('category')
        copies = data.get('copies')

        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        update_data = {}
        if title: update_data['title'] = title
        if author: update_data['author'] = author
        if category: update_data['category'] = category
        if copies is not None:
            # Simple copies update logic
            old_copies = book_doc.to_dict().get('copies', 0)
            old_available = book_doc.to_dict().get('available_copies', old_copies)
            copies = int(copies)
            
            diff = copies - old_copies
            new_available = old_available + diff

            if new_available < 0:
                return jsonify({"success": False, "message": "Cannot reduce copies below the number of currently issued books."}), 400
            
            update_data['copies'] = copies
            update_data['available_copies'] = new_available

        if update_data:
            book_ref.update(update_data)
            return jsonify({"success": True, "message": "Book updated successfully."}), 200
        else:
            return jsonify({"success": False, "message": "No data provided for update."}), 400

    except Exception as e:
        print(f"Error updating book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/<book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Admin: Deletes a book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_ref.delete()
        return jsonify({"success": True, "message": "Book deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    """Admin: Gets a list of all non-admin users."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    try:
        users_ref = db.collection(USERS_COLLECTION)
        users = users_ref.where('role', '!=', 'admin').get()
        
        user_list = []
        for doc in users:
            data = doc.to_dict()
            user_list.append({
                'user_id': doc.id,
                'username': data.get('username'),
                'email': data.get('email'),
                'account_status': data.get('account_status', 'active'),
                'profile_picture_url': data.get('profile_picture_url')
            })

        return jsonify({"success": True, "users": user_list}), 200

    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/status', methods=['POST'])
def update_user_status():
    """Admin: Blocks or unblocks a user."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    user_id = data.get('userId')
    status = data.get('status') # 'block' or 'unblock'

    if not user_id or status not in ['block', 'unblock']:
        return jsonify({"success": False, "message": "Missing user ID or invalid status action."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        
        new_status = 'blocked' if status == 'block' else 'active'
        user_ref.update({'account_status': new_status})

        return jsonify({"success": True, "message": f"User account successfully {new_status}."}), 200

    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- General Routes (Student/All) ---

@app.route('/api/books', methods=['GET'])
def get_all_books():
    """Gets a list of all available books."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        books_ref = db.collection(BOOKS_COLLECTION)
        books = books_ref.get()
        
        book_list = []
        for doc in books:
            data = doc.to_dict()
            book_list.append({
                'id': doc.id,
                'title': data.get('title'),
                'author': data.get('author'),
                'category': data.get('category'),
                'copies': data.get('copies'),
                'available_copies': data.get('available_copies'),
                'image_url': data.get('image_url')
            })

        return jsonify({"success": True, "books": book_list}), 200

    except Exception as e:
        print(f"Error getting books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/issue-book', methods=['POST'])
def issue_book_request():
    """Student: Requests to issue a book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    user_id = data.get('userId')
    book_id = data.get('bookId')

    if not all([user_id, book_id]):
        return jsonify({"success": False, "message": "Missing user or book ID."}), 400

    try:
        # Check if book is available
        book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
        if not book_doc.exists or book_doc.to_dict().get('available_copies', 0) <= 0:
            return jsonify({"success": False, "message": "Book is currently out of stock or does not exist."}), 400

        # Check if user already has a pending request for this book
        pending_request = db.collection(ISSUES_COLLECTION)\
                            .where('user_id', '==', user_id)\
                            .where('book_id', '==', book_id)\
                            .where('status', '==', 'pending')\
                            .limit(1).get()
        
        if pending_request:
            return jsonify({"success": False, "message": "You already have a pending request for this book."}), 400

        # Create the issue request
        issue_data = {
            'user_id': user_id,
            'book_id': book_id,
            'status': 'pending',
            'request_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        db.collection(ISSUES_COLLECTION).add(issue_data)
        
        return jsonify({"success": True, "message": "Book issue request submitted successfully. Waiting for admin approval."}), 200

    except Exception as e:
        print(f"Error submitting issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/issue-requests', methods=['GET'])
def get_issue_requests():
    """Admin: Gets a list of all pending issue requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        requests = db.collection(ISSUES_COLLECTION).where('status', '==', 'pending').get()
        
        request_list = []
        for doc in requests:
            data = doc.to_dict()
            book_details = get_book_details(data['book_id'])
            user_details = db.collection(USERS_COLLECTION).document(data['user_id']).get().to_dict()
            
            if book_details and user_details:
                request_list.append({
                    'id': doc.id,
                    'book_title': book_details['title'],
                    'user_name': user_details['username'],
                    'request_date': data['request_date']
                })
        
        return jsonify({"success": True, "requests": request_list}), 200

    except Exception as e:
        print(f"Error getting issue requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-issue-request', methods=['POST'])
def handle_issue_request():
    """Admin: Handles approval/rejection of issue requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    request_id = data.get('requestId')
    action = data.get('action') # 'approve' or 'reject'

    if not all([request_id, action]):
        return jsonify({"success": False, "message": "Missing request ID or action."}), 400

    try:
        issue_ref = db.collection(ISSUES_COLLECTION).document(request_id)
        issue_doc = issue_ref.get()
        
        if not issue_doc.exists or issue_doc.to_dict().get('status') != 'pending':
            return jsonify({"success": False, "message": "Request not found or already processed."}), 404

        book_id = issue_doc.to_dict()['book_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if action == 'approve':
            # Decrement available copies
            book_doc = book_ref.get()
            current_available = book_doc.to_dict().get('available_copies', 0)
            if current_available > 0:
                book_ref.update({'available_copies': firestore.Increment(-1)})
                # Update issue status
                issue_ref.update({
                    'status': 'issued',
                    'issue_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'return_request_date': firestore.DELETE_FIELD # Ensure this field is removed if present
                })
                return jsonify({"success": True, "message": "Book issued successfully."}), 200
            else:
                return jsonify({"success": False, "message": "Book is no longer available."}), 400

        elif action == 'reject':
            # Delete the request
            issue_ref.delete()
            return jsonify({"success": True, "message": "Issue request rejected."}), 200
        else:
            return jsonify({"success": False, "message": "Invalid action."}), 400

    except Exception as e:
        print(f"Error handling issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/my-orders', methods=['GET'])
def get_my_orders():
    """Student: Gets currently issued and pending books."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "Missing user ID."}), 400

    try:
        all_issues = db.collection(ISSUES_COLLECTION).where('user_id', '==', user_id).get()
        
        issued_books = []
        pending_requests = []

        for doc in all_issues:
            data = doc.to_dict()
            book_details = get_book_details(data['book_id'])
            
            if not book_details:
                continue # Skip if book details are missing

            book_info = {
                'issue_id': doc.id,
                'book_id': data['book_id'],
                'title': book_details['title'],
                'author': book_details['author'],
                'image_url': book_details['image_url']
            }

            if data['status'] == 'issued':
                book_info['issue_date'] = data['issue_date']
                book_info['has_return_request'] = 'return_request_date' in data
                issued_books.append(book_info)
            elif data['status'] == 'pending':
                book_info['request_date'] = data['request_date']
                pending_requests.append(book_info)

        return jsonify({
            "success": True, 
            "issued_books": issued_books,
            "pending_requests": pending_requests
        }), 200

    except Exception as e:
        print(f"Error getting my orders: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-book', methods=['POST'])
def return_book_request():
    """Student: Requests to return an issued book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    issue_id = data.get('issueId')

    if not issue_id:
        return jsonify({"success": False, "message": "Missing issue ID."}), 400

    try:
        issue_ref = db.collection(ISSUES_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists or issue_doc.to_dict().get('status') != 'issued':
            return jsonify({"success": False, "message": "Issued record not found or book is not currently issued."}), 404

        # Check if a return request already exists
        if 'return_request_date' in issue_doc.to_dict():
            return jsonify({"success": False, "message": "A return request has already been submitted for this book."}), 400
        
        # Submit return request (by adding a timestamp to the issue document)
        issue_ref.update({
            'return_request_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

        return jsonify({"success": True, "message": "Return request submitted successfully. Waiting for admin approval."}), 200

    except Exception as e:
        print(f"Error submitting return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-requests', methods=['GET'])
def get_return_requests():
    """Admin: Gets a list of all pending return requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        # Find all issued books that have a return request date set
        requests = db.collection(ISSUES_COLLECTION).where('status', '==', 'issued')\
                     .where('return_request_date', '!=', None).get()
        
        request_list = []
        for doc in requests:
            data = doc.to_dict()
            book_details = get_book_details(data['book_id'])
            user_details = db.collection(USERS_COLLECTION).document(data['user_id']).get().to_dict()
            
            if book_details and user_details:
                request_list.append({
                    'id': doc.id,
                    'book_title': book_details['title'],
                    'user_name': user_details['username'],
                    'request_date': data['return_request_date']
                })
        
        return jsonify({"success": True, "requests": request_list}), 200

    except Exception as e:
        print(f"Error getting return requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-return-request', methods=['POST'])
def handle_return_request():
    """Admin: Handles approval/rejection of return requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    issue_id = data.get('requestId')
    action = data.get('action') # 'approve' or 'reject'

    if not all([issue_id, action]):
        return jsonify({"success": False, "message": "Missing request ID or action."}), 400

    try:
        issue_ref = db.collection(ISSUES_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()
        
        if not issue_doc.exists or 'return_request_date' not in issue_doc.to_dict():
            return jsonify({"success": False, "message": "Return request not found or not pending."}), 404

        book_id = issue_doc.to_dict()['book_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if action == 'approve':
            # Increment available copies
            book_ref.update({'available_copies': firestore.Increment(1)})
            # Update issue status (marks as returned) and record return date
            issue_ref.update({
                'status': 'returned',
                'return_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'return_request_date': firestore.DELETE_FIELD
            })
            return jsonify({"success": True, "message": "Book return approved. Copies updated."}), 200

        elif action == 'reject':
            # Remove the return request marker
            issue_ref.update({'return_request_date': firestore.DELETE_FIELD})
            return jsonify({"success": True, "message": "Return request rejected."}), 200
        else:
            return jsonify({"success": False, "message": "Invalid action."}), 400

    except Exception as e:
        print(f"Error handling return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Static File Serving (For Vercel and Local) ---

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serves files from the UPLOAD_FOLDER."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Root/Home Route ---

@app.route('/', methods=['GET'])
def home():
    """A simple route to confirm that the server is running."""
    if not firebase_app:
        return jsonify({
            "message": "Python backend is running, but Firebase failed to initialize! Check your firebase-service-account.json path.",
            "status": "error"
        }), 500

    return jsonify({
        "message": "Python backend is running! Firebase initialized successfully.",
        "status": "ok"
    })

# --- Vercel Requirement ---
# The server run block is intentionally removed here.
# Vercel will import the 'app' object directly.

if not db:
    print("---")
    print("CRITICAL: Firebase database not initialized. All Firestore operations will fail.")
    print("---")
