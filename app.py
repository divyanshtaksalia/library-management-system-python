import os
import uuid
import json
from io import BytesIO
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, storage
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta

# --- Initialization ---

# 1. Load environment variables from .env file (for local testing)
load_dotenv()

# Firebase Collection Names (Best Practice)
USERS_COLLECTION = os.getenv("USERS_COLLECTION", "users")
BOOKS_COLLECTION = os.getenv("BOOKS_COLLECTION", "books")
ISSUES_COLLECTION = os.getenv("ISSUES_COLLECTION", "issues")
RETURNS_COLLECTION = os.getenv("RETURNS_COLLECTION", "returns")

# Vercel-friendly approach: Read JSON credentials from an environment variable
def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using JSON credentials 
    from a FIREBASE_SERVICE_ACCOUNT_JSON environment variable.
    """
    try:
        # Get the raw JSON string from the Vercel/environment variable
        service_account_json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")

        if not service_account_json_str or not storage_bucket:
            # If initialization fails, print error and return None
            print("ERROR: FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_STORAGE_BUCKET environment variable is not set.")
            return None, None, None

        # Load the JSON string into a dictionary
        service_account_info = json.loads(service_account_json_str)

        # Create credentials object from the dict
        cred = credentials.Certificate(service_account_info)
        
        # Check if the app is already initialized
        if not firebase_admin._apps:
            firebase_app = firebase_admin.initialize_app(cred, {
                'storageBucket': storage_bucket # Use the bucket name from environment variable
            })
        else:
            firebase_app = firebase_admin.get_app()

        db_client = firestore.client()
        storage_client = storage.bucket() # Initialize storage client
        print("Firebase Admin SDK initialized successfully.")
        return firebase_app, db_client, storage_client
        
    except Exception as e:
        print(f"FATAL ERROR: Failed to initialize Firebase. Details: {e}")
        return None, None, None

# Initialize Firebase globally
firebase_app, db, bucket = initialize_firebase()

# Configure Flask app
app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# --- Firebase Storage Helper Functions ---

def upload_file_to_storage(file, folder):
    """Uploads a file object to Firebase Storage and returns the public URL."""
    if not bucket:
        raise Exception("Firebase Storage not initialized.")

    # Generate a unique filename and path
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'png'
    filename = f"{uuid.uuid4()}.{ext}"
    blob_path = f"{folder}/{filename}"
    blob = bucket.blob(blob_path)

    # Use BytesIO to handle the file content without saving to disk
    file_bytes = file.read()
    blob.upload_from_string(file_bytes, content_type=file.content_type)
    
    # Make the file publicly accessible
    blob.make_public()
    
    return blob.public_url

def delete_file_from_storage(image_url):
    """Deletes a file from Firebase Storage using its public URL."""
    if not bucket:
        print("Warning: Firebase Storage not initialized, cannot delete file.")
        return

    # Extract the path from the public URL
    # Example URL format: https://storage.googleapis.com/<bucket_name>/<path/to/file>
    try:
        path_segments = image_url.split(bucket.name + '/')
        if len(path_segments) > 1:
            blob_path = path_segments[1]
            blob = bucket.blob(blob_path)
            if blob.exists():
                blob.delete()
                print(f"Deleted file: {blob_path}")
            else:
                print(f"File not found in storage: {blob_path}")
    except Exception as e:
        print(f"Error deleting file from storage: {e}")


# --- Authentication Routes (Updated for Vercel and Default Profile URL) ---

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
        return jsonify({"success": False, "message": "Missing fields."}), 400

    try:
        # Check if user already exists (using email as unique key)
        user_query = db.collection(USERS_COLLECTION).where('email', '==', email).limit(1).get()
        if user_query:
            return jsonify({"success": False, "message": "Email already registered."}), 409

        # Basic password hash (In a real app, use a proper hashing library like bcrypt)
        # For simplicity and environment constraints, we will just use it as is for this demo.
        user_id = str(uuid.uuid4())
        
        db.collection(USERS_COLLECTION).document(user_id).set({
            "user_id": user_id,
            "username": username,
            "email": email,
            "password": password, # Insecure for a real application
            "role": "student",
            "account_status": "active",
            "profile_picture_url": "https://placehold.co/100x100/3283f5/ffffff?text=U" # Default placeholder
        })

        return jsonify({"success": True, "message": "Registration successful. You can now log in."}), 201

    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Handles user login and returns user details on success."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    try:
        # Find user by email
        user_query = db.collection(USERS_COLLECTION).where('email', '==', email).limit(1).get()

        if not user_query:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

        user_doc = user_query[0]
        user_data = user_doc.to_dict()

        # Check password (Insecure check for this demo)
        if user_data['password'] != password:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401
        
        # Check account status
        if user_data.get('account_status') != 'active':
            return jsonify({"success": False, "message": "Your account is blocked. Please contact admin."}), 403

        # Prepare user object for frontend
        user = {
            "id": user_doc.id,
            "username": user_data['username'],
            "email": user_data['email'],
            "role": user_data['role'],
            "profile_picture_url": user_data.get('profile_picture_url', "https://placehold.co/100x100/3283f5/ffffff?text=U")
        }

        return jsonify({"success": True, "message": "Login successful.", "user": user}), 200

    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- User Profile Picture Update Route (Using Firebase Storage) ---

@app.route('/api/user/update-profile-picture', methods=['POST'])
def update_profile_picture():
    """Handles profile picture upload using Firebase Storage."""
    if not db or not bucket:
        return jsonify({"success": False, "message": "Backend or Storage not initialized."}), 500
    
    # Check if a file was sent
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "No image file provided."}), 400

    file = request.files['image']
    user_id = request.form.get('userId')

    if not user_id:
        return jsonify({"success": False, "message": "Missing User ID."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"success": False, "message": "User not found."}), 404
            
        user_data = user_doc.to_dict()
        old_image_url = user_data.get('profile_picture_url')
        
        # 1. Upload new image
        new_image_url = upload_file_to_storage(file, folder="profile_pictures")

        # 2. Update user document
        user_ref.update({
            'profile_picture_url': new_image_url
        })

        # 3. Delete old image (optional cleanup, skip default placeholder)
        default_placeholder = "https://placehold.co/100x100/3283f5/ffffff?text=U"
        if old_image_url and old_image_url != new_image_url and old_image_url != default_placeholder:
            delete_file_from_storage(old_image_url)

        return jsonify({"success": True, "message": "Profile picture updated successfully.", "image_url": new_image_url}), 200

    except Exception as e:
        print(f"Error updating profile picture: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Book Management Routes (Updated for Firebase Storage) ---

@app.route('/api/books', methods=['POST'])
def add_book():
    """Handles adding a new book, including image upload to storage."""
    if not db or not bucket:
        return jsonify({"success": False, "message": "Backend or Storage not initialized."}), 500
    
    # Use request.form for form data and request.files for the file
    title = request.form.get('title')
    author = request.form.get('author')
    isbn = request.form.get('isbn')
    category = request.form.get('category')
    total_copies = request.form.get('totalCopies')
    
    if not all([title, author, isbn, category, total_copies]):
        return jsonify({"success": False, "message": "Missing book fields."}), 400

    try:
        book_id = str(uuid.uuid4())
        image_url = None
        
        # Handle image upload
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # Upload the image to Firebase Storage
                image_url = upload_file_to_storage(file, folder="book_covers")

        # Prepare book data
        book_data = {
            "book_id": book_id,
            "title": title,
            "author": author,
            "isbn": isbn,
            "category": category,
            "total_copies": int(total_copies),
            "available_copies": int(total_copies), # Initially all are available
            "image_url": image_url if image_url else "https://placehold.co/100x140/f6e05e/1a202c?text=Book" # Default placeholder
        }

        # Save to Firestore
        db.collection(BOOKS_COLLECTION).document(book_id).set(book_data)

        return jsonify({"success": True, "message": "Book added successfully.", "book": book_data}), 201

    except Exception as e:
        print(f"Error adding book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books', methods=['GET'])
def get_books():
    """Fetches all books from the database."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        books_ref = db.collection(BOOKS_COLLECTION)
        books_list = [doc.to_dict() for doc in books_ref.stream()]
        
        return jsonify({"success": True, "books": books_list}), 200

    except Exception as e:
        print(f"Error fetching books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/<book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Deletes a book and its image from storage."""
    if not db or not bucket:
        return jsonify({"success": False, "message": "Backend or Storage not initialized."}), 500

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_data = book_doc.to_dict()
        image_url = book_data.get('image_url')
        
        # 1. Delete book document from Firestore
        book_ref.delete()
        
        # 2. Delete image from Firebase Storage (if it's not the default placeholder)
        default_placeholder = "https://placehold.co/100x140/f6e05e/1a202c?text=Book"
        if image_url and image_url != default_placeholder:
            delete_file_from_storage(image_url)

        return jsonify({"success": True, "message": "Book deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- User Management Routes ---

@app.route('/api/users', methods=['GET'])
def get_users():
    """Fetches all users for admin view."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        users_ref = db.collection(USERS_COLLECTION).where('role', '!=', 'admin') # Exclude admin from the list
        users_list = [
            {**doc.to_dict(), 'user_id': doc.id} 
            for doc in users_ref.stream()
        ]
        
        # Remove sensitive data like password
        for user in users_list:
            user.pop('password', None)
        
        return jsonify({"success": True, "users": users_list}), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/users/status', methods=['POST'])
def update_user_status():
    """Updates the status (active/blocked) of a user."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    user_id = data.get('userId')
    status = data.get('status') # 'active' or 'blocked'

    if not all([user_id, status]):
        return jsonify({"success": False, "message": "Missing User ID or Status."}), 400
    
    if status not in ['active', 'blocked']:
        return jsonify({"success": False, "message": "Invalid status value."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        user_ref.update({'account_status': status})

        message = f"User account is now {status}."
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# --- Book Issue/Return Request Routes ---

@app.route('/api/issue-request', methods=['POST'])
def request_issue():
    """Handles a student requesting to issue a book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    book_id = data.get('bookId')
    user_id = data.get('userId')

    if not all([book_id, user_id]):
        return jsonify({"success": False, "message": "Missing book ID or user ID."}), 400

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        
        book_doc = book_ref.get()
        user_doc = user_ref.get()

        if not book_doc.exists or not user_doc.exists:
            return jsonify({"success": False, "message": "Book or User not found."}), 404

        book_data = book_doc.to_dict()
        user_data = user_doc.to_dict()

        if book_data.get('available_copies', 0) <= 0:
            return jsonify({"success": False, "message": "Book is currently out of stock."}), 400
        
        if user_data.get('account_status') != 'active':
            return jsonify({"success": False, "message": "Your account is blocked. Cannot request a book."}), 403

        # Check if book is already requested or issued by the user
        existing_request = db.collection(ISSUES_COLLECTION).where('user_id', '==', user_id).where('book_id', '==', book_id).limit(1).get()
        if existing_request:
            return jsonify({"success": False, "message": "You have already requested or issued this book."}), 400

        # Create a new issue request document
        issue_id = str(uuid.uuid4())
        db.collection(ISSUES_COLLECTION).document(issue_id).set({
            'issue_id': issue_id,
            'book_id': book_id,
            'user_id': user_id,
            'status': 'pending', # 'pending' or 'issued'
            'request_date': datetime.now().isoformat()
        })

        return jsonify({"success": True, "message": "Book issue request sent successfully."}), 200

    except Exception as e:
        print(f"Error requesting book issue: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/orders/<user_id>', methods=['GET'])
def get_user_orders(user_id):
    """Fetches a student's currently issued and pending books."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        # Get all issues/requests for this user
        issues_query = db.collection(ISSUES_COLLECTION).where('user_id', '==', user_id).stream()
        
        issued_books = []
        pending_books = []
        
        for doc in issues_query:
            issue_data = doc.to_dict()
            book_id = issue_data['book_id']
            book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
            
            if book_doc.exists:
                book_data = book_doc.to_dict()
                
                # Create a combined object
                item = {
                    'issue_id': issue_data['issue_id'],
                    'book_id': book_id,
                    'title': book_data['title'],
                    'author': book_data['author'],
                    'image_url': book_data.get('image_url', "https://placehold.co/100x140/f6e05e/1a202c?text=Book")
                }
                
                if issue_data['status'] == 'issued':
                    item['issue_date'] = issue_data['issue_date']
                    item['due_date'] = issue_data.get('due_date')
                    issued_books.append(item)
                elif issue_data['status'] == 'pending':
                    item['request_date'] = issue_data['request_date']
                    pending_books.append(item)

        return jsonify({
            "success": True, 
            "issued_books": issued_books, 
            "pending_books": pending_books
        }), 200

    except Exception as e:
        print(f"Error fetching user orders: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/issue-requests', methods=['GET'])
def get_issue_requests():
    """Admin route to fetch all pending issue requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        # Fetch all pending issue requests
        requests_query = db.collection(ISSUES_COLLECTION).where('status', '==', 'pending').stream()
        
        requests_list = []
        
        for doc in requests_query:
            issue_data = doc.to_dict()
            book_id = issue_data['book_id']
            user_id = issue_data['user_id']
            
            # Fetch book and user details
            book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
            user_doc = db.collection(USERS_COLLECTION).document(user_id).get()
            
            if book_doc.exists and user_doc.exists:
                book_data = book_doc.to_dict()
                user_data = user_doc.to_dict()

                requests_list.append({
                    'issue_id': issue_data['issue_id'],
                    'book_title': book_data['title'],
                    'user_name': user_data['username'],
                    'request_date': issue_data['request_date']
                })

        return jsonify({"success": True, "requests": requests_list}), 200

    except Exception as e:
        print(f"Error fetching issue requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/issue-requests/<issue_id>', methods=['POST'])
def handle_issue_request(issue_id):
    """Admin route to approve or reject a book issue request."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    action = data.get('action') # 'approve' or 'reject'

    if action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Invalid action."}), 400

    try:
        issue_ref = db.collection(ISSUES_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists:
            return jsonify({"success": False, "message": "Issue request not found."}), 404

        issue_data = issue_doc.to_dict()
        book_id = issue_data['book_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if action == 'approve':
            # Use a transaction for safe stock decrease
            @firestore.transactional
            def update_book_and_issue_in_transaction(transaction, book_ref, issue_ref):
                book_doc = book_ref.get(transaction=transaction)
                if not book_doc.exists:
                    raise Exception("Book not found during transaction.")
                
                book_data = book_doc.to_dict()
                available_copies = book_data.get('available_copies', 0)

                if available_copies <= 0:
                    raise Exception("Book is out of stock.")

                new_available_copies = available_copies - 1
                
                # Update book copies
                transaction.update(book_ref, {'available_copies': new_available_copies})

                # Update issue status
                issue_date = datetime.now().isoformat()
                due_date = (datetime.now() + timedelta(days=14)).isoformat() # Due in 14 days
                transaction.update(issue_ref, {
                    'status': 'issued',
                    'issue_date': issue_date,
                    'due_date': due_date
                })

            transaction = db.transaction()
            update_book_and_issue_in_transaction(transaction, book_ref, issue_ref)

            return jsonify({"success": True, "message": "Book issue approved and book issued successfully."}), 200
            
        elif action == 'reject':
            # Simply delete the pending request
            issue_ref.delete()
            return jsonify({"success": True, "message": "Book issue request rejected."}), 200

    except Exception as e:
        print(f"Error handling issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/return-request', methods=['POST'])
def request_return():
    """Handles a student requesting to return an issued book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    issue_id = data.get('issueId')
    user_id = data.get('userId') # For verification

    if not all([issue_id, user_id]):
        return jsonify({"success": False, "message": "Missing issue ID or user ID."}), 400

    try:
        issue_ref = db.collection(ISSUES_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists or issue_doc.to_dict().get('user_id') != user_id or issue_doc.to_dict().get('status') != 'issued':
            return jsonify({"success": False, "message": "Invalid or unissued book ID."}), 400

        # Create a new return request document
        # We store the return request data separately, or update the issue doc status
        issue_ref.update({
            'status': 'return_pending', # New status for return
            'return_request_date': datetime.now().isoformat()
        })

        return jsonify({"success": True, "message": "Book return request sent successfully."}), 200

    except Exception as e:
        print(f"Error requesting book return: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-requests', methods=['GET'])
def get_return_requests():
    """Admin route to fetch all pending return requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        # Fetch all pending return requests
        requests_query = db.collection(ISSUES_COLLECTION).where('status', '==', 'return_pending').stream()
        
        requests_list = []
        
        for doc in requests_query:
            return_data = doc.to_dict()
            book_id = return_data['book_id']
            user_id = return_data['user_id']
            
            # Fetch book and user details
            book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
            user_doc = db.collection(USERS_COLLECTION).document(user_id).get()
            
            if book_doc.exists and user_doc.exists:
                book_data = book_doc.to_dict()
                user_data = user_doc.to_dict()

                requests_list.append({
                    'issue_id': return_data['issue_id'],
                    'book_title': book_data['title'],
                    'user_name': user_data['username'],
                    'request_date': return_data['return_request_date']
                })

        return jsonify({"success": True, "requests": requests_list}), 200

    except Exception as e:
        print(f"Error fetching return requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-requests/<issue_id>', methods=['POST'])
def handle_return_request(issue_id):
    """Admin route to approve or reject a book return request."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    action = data.get('action') # 'approve' or 'reject'

    if action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Invalid action."}), 400

    try:
        issue_ref = db.collection(ISSUES_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists:
            return jsonify({"success": False, "message": "Return request not found."}), 404

        issue_data = issue_doc.to_dict()
        book_id = issue_data['book_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if action == 'approve':
            # Use a transaction for safe stock increase
            @firestore.transactional
            def update_book_and_issue_in_transaction(transaction, book_ref, issue_ref):
                book_doc = book_ref.get(transaction=transaction)
                if not book_doc.exists:
                    raise Exception("Book not found during transaction.")
                
                book_data = book_doc.to_dict()
                available_copies = book_data.get('available_copies', 0)

                new_available_copies = available_copies + 1
                
                # Update book copies
                transaction.update(book_ref, {'available_copies': new_available_copies})

                # Delete the issue record as the return is complete
                transaction.delete(issue_ref)

            transaction = db.transaction()
            update_book_and_issue_in_transaction(transaction, book_ref, issue_ref)

            return jsonify({"success": True, "message": "Book return approved. Copy added back to stock."}), 200
            
        elif action == 'reject':
            # If rejected, set status back to 'issued' and remove return request date
            issue_ref.update({
                'status': 'issued',
                'return_request_date': firestore.DELETE_FIELD
            })
            return jsonify({"success": True, "message": "Return request rejected. Status reset to Issued."}), 200

    except Exception as e:
        print(f"Error handling return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# --- Root and Static File Serving ---

@app.route('/', methods=['GET'])
def home():
    """Returns a status message or redirects to login.html."""
    if not firebase_app:
        # This will be the response if initialization failed globally
        return jsonify({
            "message": "Python backend is running, but Firebase failed to initialize! Check your FIREBASE_SERVICE_ACCOUNT_JSON environment variable.",
            "status": "error"
        }), 500
    
    # If successful, redirect to the login page (or serve the login page)
    # Assuming 'login.html' is served from the Vercel static public directory
    return redirect('/login.html')

@app.route('/<path:path>')
def serve_public_files(path):
    """Serves static files from the root directory on Vercel."""
    # Note: On Vercel, static files should be in the root, and the vercel.json configuration 
    # handles routing, but this is a fallback for testing local directory structure.
    # In Vercel deployment, static files are served directly, not via Flask.
    # We keep this simple for Vercel's default behavior.
    return send_from_directory(os.getcwd(), path)


# --- Error Handling ---

@app.errorhandler(404)
def resource_not_found(e):
    return jsonify({"success": False, "message": "Resource Not Found"}), 404

# --- Run Application ---

# Vercel will import the 'app' object and run it.
if not db:
    print("---")
    print("CRITICAL WARNING: Firebase initialization FAILED.")
    print("Check FIREBASE_SERVICE_ACCOUNT_JSON and FIREBASE_STORAGE_BUCKET environment variables.")
    print("---")
