import os
import uuid
from dotenv import load_dotenv
# --- Removing send_from_directory and redirect ---
from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.utils import secure_filename
import json

# --- Initialization ---

# 1. Load environment variables from .env file
load_dotenv()

# --- Removing Base Directory Logic (Vercel handles this now) ---
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# STATIC_FOLDER = os.path.join(BASE_DIR, 'public')


def initialize_firebase():
    """
    Initializes the Firebase Admin SDK using credentials
    from an environment variable.
    """
    try:
        # Check for Vercel's environment variable first
        sa_json_str = os.getenv("FIREBASE_SA_JSON")

        if sa_json_str:
            print("Found FIREBASE_SA_JSON env. Initializing from string.")
            sa_json_dict = json.loads(sa_json_str)
            cred = credentials.Certificate(sa_json_dict)
        else:
            # Fallback to local file path for local development
            print("FIREBASE_SA_JSON not found. Looking for FIREBASE_SA_FILE path.")
            sa_file_path = os.getenv("FIREBASE_SA_FILE")
            if not sa_file_path or not os.path.exists(sa_file_path):
                print(f"ERROR: Service account file not found.")
                print(f"Please set FIREBASE_SA_FILE or FIREBASE_SA_JSON environment variable.")
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
        print(f"ERROR: Could not parse Firebase credentials. Check JSON format. {ve}")
        return None, None
    except Exception as e:
        print(f"ERROR: Failed to initialize Firebase: {e}")
        return None, None

# 2. Initialize Firebase
firebase_app, db = initialize_firebase()

# 3. Create Flask App
app = Flask(__name__)
CORS(app)

# 4. Firestore Collection Names
USERS_COLLECTION = 'users'
BOOKS_COLLECTION = 'books'
ISSUE_RECORDS_COLLECTION = 'issue_records'

# --- Helper Function ---

def check_db():
    """Helper to check if DB is initialized."""
    if not db:
        return jsonify({"success": False, "message": "Backend database not initialized. Check server logs."}), 500
    return None

# --- API Routes ---
# (All your /api/... routes go here)

@app.route('/api/register', methods=['POST'])
def register_user():
    """Registers a new user and saves them to Firestore."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data or 'password' not in data:
        return jsonify({"success": False, "message": "Missing required fields (username, email, password)."}), 400

    username = data['username']
    email = data['email']
    password = data['password'] 

    try:
        user_ref = db.collection(USERS_COLLECTION).where('email', '==', email).limit(1).get()
        if user_ref:
            return jsonify({"success": False, "message": "This email is already registered."}), 409

        new_user_id = str(uuid.uuid4())
        
        user_data = {
            'user_id': new_user_id,
            'username': username,
            'email': email,
            'password': password, # Note: Passwords should be hashed in a real app
            'role': 'student',          
            'account_status': 'active', 
            'profile_picture_url': None,
            'created_at': firestore.SERVER_TIMESTAMP,
        }

        db.collection(USERS_COLLECTION).document(new_user_id).set(user_data)

        return jsonify({
            "success": True, 
            "message": "Registration successful! You can now log in.",
            "user_id": new_user_id
        }), 201

    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/login', methods=['POST'])
def login_user():
    """Authenticates a user based on email and password."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"success": False, "message": "Missing email or password."}), 400

    email = data['email']
    password = data['password']

    try:
        users_ref = db.collection(USERS_COLLECTION).where('email', '==', email).limit(1).get()

        if not users_ref:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

        user_doc = users_ref[0]
        user_data = user_doc.to_dict()

        if user_data.get('account_status') == 'blocked':
            return jsonify({"success": False, "message": "Your account has been blocked. Please contact an administrator."}), 403

        if user_data.get('password') != password:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

        return jsonify({
            "success": True,
            "message": "Login successful!",
            "user": {
                "id": user_data.get('user_id'),
                "username": user_data.get('username'),
                "role": user_data.get('role'),
                "profile_picture_url": user_data.get('profile_picture_url')
            }
        }), 200

    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books', methods=['GET'])
def get_books():
    """Fetches all books from the Firestore collection."""
    if (db_error := check_db()): return db_error

    user_id = request.args.get('userId')

    try:
        books_ref = db.collection(BOOKS_COLLECTION).order_by('created_at', direction=firestore.Query.DESCENDING).stream()

        books_list = []
        for book in books_ref:
            book_data = book.to_dict()
            if 'created_at' in book_data and hasattr(book_data['created_at'], 'isoformat'):
                 book_data['created_at'] = book_data['created_at'].isoformat()

            # Determine display_status based on user
            if user_id:
                issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('book_id', '==', book_data['book_id']).where('return_status', 'in', ['pending_issue', 'issued']).limit(1).get()
                if issue_ref:
                    issue_data = issue_ref[0].to_dict()
                    if issue_data['return_status'] == 'pending_issue':
                        book_data['display_status'] = 'pending_issue'
                    elif issue_data['return_status'] == 'issued':
                        book_data['display_status'] = 'issued'
                else:
                    book_data['display_status'] = 'available' if book_data.get('copies_available', 0) > 0 else 'not_available'
            else:
                book_data['display_status'] = 'available' if book_data.get('copies_available', 0) > 0 else 'not_available'

            books_list.append(book_data)

        return jsonify({"success": True, "books": books_list}), 200

    except Exception as e:
        print(f"Error fetching books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books', methods=['POST'])
def add_book():
    """(Admin) Adds a new book (text only)."""
    if (db_error := check_db()): return db_error

    try:
        # Using request.form because frontend might still send FormData
        if 'title' not in request.form or 'author' not in request.form:
             # Fallback to JSON if not FormData
            data = request.get_json()
            if not data or 'title' not in data or 'author' not in data:
                return jsonify({"success": False, "message": "Missing required fields (title, author)."}), 400
            title = data['title']
            author = data['author']
            category = data.get('category', 'Uncategorized')
            total_copies = int(data.get('copies', 1))
        else:
            title = request.form['title']
            author = request.form['author']
            category = request.form.get('category', 'Uncategorized')
            total_copies = int(request.form.get('copies', 1))


        book_id = str(uuid.uuid4())

        book_data = {
            'book_id': book_id, 'title': title, 'author': author,
            'category': category, 'total_copies': total_copies,
            'copies_available': total_copies, 'image_url': None,
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        db.collection(BOOKS_COLLECTION).document(book_id).set(book_data)

        return jsonify({
            "success": True,
            "message": "Book added successfully!",
            "book_id": book_id
        }), 201

    except Exception as e:
        print(f"Error adding book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books/<string:book_id>', methods=['DELETE'])
def delete_book(book_id):
    """(Admin) Deletes a book from Firestore."""
    if (db_error := check_db()): return db_error

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404
        
        book_ref.delete()

        return jsonify({"success": True, "message": "Book deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books/<string:book_id>', methods=['PUT'])
def update_book_details(book_id):
    """(Admin) Updates a book's details (title, author, category)."""
    if (db_error := check_db()): return db_error

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided."}), 400

        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        update_data = {}
        if 'title' in data and data['title']:
            update_data['title'] = data['title']
        if 'author' in data and data['author']:
            update_data['author'] = data['author']
        if 'category' in data and data['category']:
            update_data['category'] = data['category']

        book_ref.update(update_data)

        return jsonify({"success": True, "message": "Book details updated successfully."}), 200
    except Exception as e:
        print(f"Error updating book details: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/update-copies', methods=['POST'])
def update_book_copies():
    """(Admin) Updates the total and available copies of a book."""
    if (db_error := check_db()): return db_error

    try:
        data = request.get_json()
        if not data or 'bookId' not in data or 'copies' not in data:
            return jsonify({"success": False, "message": "Missing bookId or copies."}), 400

        book_id = data['bookId']
        new_total_copies = int(data['copies'])

        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_data = book_doc.to_dict()
        issued_copies = book_data.get('total_copies', 0) - book_data.get('copies_available', 0)

        if new_total_copies < issued_copies:
            return jsonify({"success": False, "message": f"Cannot set copies lower than the number of currently issued books ({issued_copies})."}), 400

        new_available_copies = new_total_copies - issued_copies

        book_ref.update({
            'total_copies': new_total_copies,
            'copies_available': new_available_copies
        })
        return jsonify({"success": True, "message": "Book copies updated successfully."}), 200
    except Exception as e:
        print(f"Error updating book copies: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/issue-book', methods=['POST'])
def issue_book_request():
    """(Student) Creates a request to issue a book."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'userId' not in data or 'bookId' not in data:
        return jsonify({"success": False, "message": "User ID or Book ID is missing."}), 400

    user_id = data['userId']
    book_id = data['bookId']

    try:
        existing_request = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('book_id', '==', book_id).where('return_status', 'in', ['pending_issue', 'issued']).limit(1).get()
        if existing_request:
            return jsonify({"success": False, "message": "You have already requested or issued this book."}), 409

        issue_id = str(uuid.uuid4())
        issue_data = {
            'issue_id': issue_id,
            'user_id': user_id,
            'book_id': book_id,
            'request_date': firestore.SERVER_TIMESTAMP,
            'issue_date': None,
            'return_date': None,
            'return_status': 'pending_issue' # Statuses: pending_issue, issued, returned, pending_return
        }
        db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id).set(issue_data)
        return jsonify({"success": True, "message": "Book issue request sent successfully."}), 201

    except Exception as e:
        print(f"Error creating issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/issue-requests', methods=['GET'])
def get_issue_requests():
    """(Admin) Fetches all pending book issue requests."""
    if (db_error := check_db()): return db_error

    try:
        requests_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('return_status', '==', 'pending_issue').stream()
        requests_list = []
        for req in requests_ref:
            req_data = req.to_dict()
            
            user_doc = db.collection(USERS_COLLECTION).document(req_data['user_id']).get()
            book_doc = db.collection(BOOKS_COLLECTION).document(req_data['book_id']).get()

            if user_doc.exists and book_doc.exists:
                req_data['username'] = user_doc.to_dict().get('username', 'N/A')
                req_data['title'] = book_doc.to_dict().get('title', 'N/A')
                req_data['author'] = book_doc.to_dict().get('author', 'N/A')
                if 'request_date' in req_data and hasattr(req_data['request_date'], 'isoformat'):
                    req_data['request_date'] = req_data['request_date'].isoformat()
                requests_list.append(req_data)

        return jsonify({"success": True, "requests": requests_list}), 200
    except Exception as e:
        print(f"Error fetching issue requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-request', methods=['POST'])
def handle_issue_request():
    """(Admin) Handles decision (accept/reject) on an issue request."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'issueId' not in data or 'action' not in data:
        return jsonify({"success": False, "message": "Missing issueId or action."}), 400

    issue_id = data['issueId']
    action = data['action']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)

        if action == 'accept':
            book_id = data.get('bookId')
            if not book_id:
                 return jsonify({"success": False, "message": "Missing bookId for accept action."}), 400
                 
            book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

            @firestore.transactional
            def update_in_transaction(transaction, book_ref, issue_ref):
                book_snapshot = book_ref.get(transaction=transaction)
                if not book_snapshot.exists:
                    return "Book not found."
                
                if book_snapshot.to_dict().get('copies_available', 0) > 0:
                    transaction.update(book_ref, {'copies_available': firestore.Increment(-1)})
                    transaction.update(issue_ref, {'return_status': 'issued', 'issue_date': firestore.SERVER_TIMESTAMP})
                    return True
                return "Book is out of stock."

            transaction = db.transaction()
            result = update_in_transaction(transaction, book_ref, issue_ref)
            
            if result is True:
                return jsonify({"success": True, "message": "Request accepted and book issued."}), 200
            else:
                return jsonify({"success": False, "message": str(result)}), 400

        elif action == 'reject':
            issue_ref.delete()
            return jsonify({"success": True, "message": "Request rejected."}), 200
        else:
            return jsonify({"success": False, "message": "Invalid action."}), 400

    except Exception as e:
        print(f"Error handling issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/my-orders', methods=['GET'])
def get_my_orders():
    """(Student) Fetches all issued and pending books for the user."""
    if (db_error := check_db()): return db_error
    
    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400

    try:
        orders_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('return_status', 'in', ['issued', 'pending_issue', 'pending_return']).stream()
        orders_list = []
        for order in orders_ref:
            order_data = order.to_dict()
            book_doc = db.collection(BOOKS_COLLECTION).document(order_data['book_id']).get()
            if book_doc.exists:
                order_data['title'] = book_doc.to_dict().get('title', 'N/A')
                order_data['author'] = book_doc.to_dict().get('author', 'N/A')
                order_data['image_url'] = book_doc.to_dict().get('image_url')
                if 'issue_date' in order_data and order_data['issue_date']:
                    order_data['issue_date'] = order_data['issue_date'].isoformat()
                if 'request_date' in order_data and order_data['request_date']:
                    order_data['request_date'] = order_data['request_date'].isoformat()
                orders_list.append(order_data)

        return jsonify({"success": True, "orders": orders_list}), 200
    except Exception as e:
        print(f"Error fetching my orders: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/cancel-request', methods=['POST'])
def cancel_request():
    """(Student) Allows a student to cancel their pending issue request."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'issueId' not in data:
        return jsonify({"success": False, "message": "Issue ID is missing."}), 400

    issue_id = data['issueId']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists:
            return jsonify({"success": False, "message": "Request not found."}), 404

        issue_data = issue_doc.to_dict()
        if issue_data.get('return_status') != 'pending_issue':
            return jsonify({"success": False, "message": "Only pending requests can be cancelled."}), 400

        issue_ref.delete()
        return jsonify({"success": True, "message": "Request cancelled successfully."}), 200

    except Exception as e:
        print(f"Error cancelling request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/returned-books', methods=['GET'])
def get_returned_books():
    """(Student) Fetches all returned books for the user."""
    if (db_error := check_db()): return db_error

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400

    try:
        returned_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('return_status', '==', 'returned').stream()
        returned_list = []
        for record in returned_ref:
            record_data = record.to_dict()
            book_doc = db.collection(BOOKS_COLLECTION).document(record_data['book_id']).get()
            if book_doc.exists:
                record_data['title'] = book_doc.to_dict().get('title', 'N/A')
                record_data['author'] = book_doc.to_dict().get('author', 'N/A')
                record_data['image_url'] = book_doc.to_dict().get('image_url')
                if 'issue_date' in record_data and record_data['issue_date']:
                    record_data['issue_date'] = record_data['issue_date'].isoformat()
                if 'return_date' in record_data and record_data['return_date']:
                    record_data['return_date'] = record_data['return_date'].isoformat()
                returned_list.append(record_data)

        return jsonify({"success": True, "returned_books": returned_list}), 200
    except Exception as e:
        print(f"Error fetching returned books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-book', methods=['POST'])
def return_book_request():
    """(Student) Creates a return request for an issued book."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'issueId' not in data:
        return jsonify({"success": False, "message": "Issue ID is missing."}), 400

    issue_id = data['issueId']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists:
            return jsonify({"success": False, "message": "Issue record not found."}), 404

        issue_data = issue_doc.to_dict()
        if issue_data.get('return_status') != 'issued':
            return jsonify({"success": False, "message": "Only issued books can be returned."}), 400

        issue_ref.update({'return_status': 'pending_return', 'return_request_date': firestore.SERVER_TIMESTAMP})
        return jsonify({"success": True, "message": "Return request sent successfully."}), 201

    except Exception as e:
        print(f"Error creating return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-requests', methods=['GET'])
def get_return_requests():
    """(Admin) Fetches all pending return requests."""
    if (db_error := check_db()): return db_error

    try:
        requests_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('return_status', '==', 'pending_return').stream()
        requests_list = []
        for req in requests_ref:
            req_data = req.to_dict()

            user_doc = db.collection(USERS_COLLECTION).document(req_data['user_id']).get()
            book_doc = db.collection(BOOKS_COLLECTION).document(req_data['book_id']).get()

            if user_doc.exists and book_doc.exists:
                req_data['username'] = user_doc.to_dict().get('username', 'N/A')
                req_data['title'] = book_doc.to_dict().get('title', 'N/A')
                req_data['author'] = book_doc.to_dict().get('author', 'N/A')
                if 'return_request_date' in req_data and hasattr(req_data['return_request_date'], 'isoformat'):
                    req_data['return_request_date'] = req_data['return_request_date'].isoformat()
                requests_list.append(req_data)

        return jsonify({"success": True, "requests": requests_list}), 200
    except Exception as e:
        print(f"Error fetching return requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-return', methods=['POST'])
def handle_return_request():
    """(Admin) Handles decision (accept/reject) on a return request."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'issueId' not in data or 'action' not in data:
        return jsonify({"success": False, "message": "Missing issueId or action."}), 400

    issue_id = data['issueId']
    action = data['action']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)

        if action == 'accept':
            book_id = data.get('bookId')
            if not book_id:
                 return jsonify({"success": False, "message": "Missing bookId for accept action."}), 400

            book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

            @firestore.transactional
            def update_in_transaction(transaction, book_ref, issue_ref):
                book_snapshot = book_ref.get(transaction=transaction)
                if not book_snapshot.exists:
                    return "Book not found."
                
                transaction.update(book_ref, {'copies_available': firestore.Increment(1)})
                transaction.update(issue_ref, {'return_status': 'returned', 'return_date': firestore.SERVER_TIMESTAMP})
                return True
            
            transaction = db.transaction()
            result = update_in_transaction(transaction, book_ref, issue_ref)

            if result is True:
                return jsonify({"success": True, "message": "Return accepted and book returned."}), 200
            else:
                return jsonify({"success": False, "message": str(result)}), 400

        elif action == 'reject':
            issue_ref.update({'return_status': 'issued'})  # Reset to issued
            return jsonify({"success": True, "message": "Return request rejected."}), 200
        else:
            return jsonify({"success": False, "message": "Invalid action."}), 400

    except Exception as e:
        print(f"Error handling return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    """(Admin) Fetches all student users."""
    if (db_error := check_db()): return db_error

    try:
        users_ref = db.collection(USERS_COLLECTION).where('role', '==', 'student').stream()

        users_list = []
        for user in users_ref:
            user_data = user.to_dict()
            if 'created_at' in user_data and hasattr(user_data['created_at'], 'isoformat'):
                 user_data['created_at'] = user_data['created_at'].isoformat()
            users_list.append(user_data)

        return jsonify({"success": True, "users": users_list}), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/status', methods=['POST'])
def update_user_status():
    """(Admin) Updates a user's account status (block/unblock)."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or 'userId' not in data or 'status' not in data:
        return jsonify({"success": False, "message": "Missing userId or status."}), 400

    user_id = data['userId']
    new_status = data['status']

    if new_status not in ['active', 'blocked']:
        return jsonify({"success": False, "message": "Invalid status. Must be 'active' or 'blocked'."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        user_ref.update({'account_status': new_status})
        action_text = "blocked" if new_status == "blocked" else "activated"
        return jsonify({"success": True, "message": f"User account {action_text} successfully."}), 200

    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """(Admin) Deletes a user from Firestore."""
    if (db_error := check_db()): return db_error

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)

        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404
        
        user_ref.delete()

        return jsonify({"success": True, "message": "User deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500



if not db:
    print("---")
    print("CRITICAL: Firebase DB not initialized. Server is running but API calls will fail.")
    print("Please check your FIREBASE_SA_JSON environment variable.")
    print("---")
else:
    print("Flask app object created. Ready for Vercel.")
