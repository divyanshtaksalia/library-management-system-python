import os
import uuid
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, redirect
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.utils import secure_filename

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
            print(f"ERROR: Service account file not found.")
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
        print(f"ERROR: Firebase initialization failed. Already initialized? {ve}")
        # Try to get the default app if it exists
        if firebase_admin._apps:
            return firebase_admin.get_app(), firestore.client()
        return None, None
    except Exception as e:
        print(f"ERROR: Failed to initialize Firebase: {e}")
        return None, None

# 2. Initialize Firebase
firebase_app, db = initialize_firebase()

# 3. Initialize Flask App
app = Flask(__name__)
CORS(app) # Enable Cross-Origin Resource Sharing

# 4. Configure Uploads
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 5. Firestore Collection Names
USERS_COLLECTION = 'users'
BOOKS_COLLECTION = 'books'
ISSUE_RECORDS_COLLECTION = 'issue_records'

# --- Helper Function ---

def check_db():
    """Checks if the database is initialized."""
    if not db:
        return jsonify({"success": False, "message": "Backend database not initialized. Check server logs."}), 500
    return None

# --- User & Auth Routes ---

@app.route('/api/register', methods=['POST'])
def register_user():
    """Registers a new user (student) in Firestore."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or not all(k in data for k in ('username', 'email', 'password')):
        return jsonify({"success": False, "message": "Missing required fields (username, email, password)."}), 400

    email = data['email']

    try:
        # Check if email already exists
        user_ref = db.collection(USERS_COLLECTION).where('email', '==', email).limit(1).get()
        if user_ref: # user_ref is a list of documents
            return jsonify({"success": False, "message": "This email is already registered."}), 409

        # Create new user
        new_user_id = str(uuid.uuid4())
        user_data = {
            'user_id': new_user_id,
            'username': data['username'],
            'email': email,
            'password': data['password'], # Note: Storing passwords in plain text is insecure. Use hashing in a real app.
            'role': 'student',
            'account_status': 'active',
            'profile_picture_url': None,
            'created_at': firestore.SERVER_TIMESTAMP,
        }

        db.collection(USERS_COLLECTION).document(new_user_id).set(user_data)

        return jsonify({
            "success": True, 
            "message": "Registration successful!",
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
    if not data or not all(k in data for k in ('email', 'password')):
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
            return jsonify({"success": False, "message": "Account is blocked. Contact administrator."}), 403

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

@app.route('/api/user/update-profile-picture', methods=['POST'])
def update_profile_picture():
    """Updates the profile picture for a specific user."""
    if (db_error := check_db()): return db_error

    try:
        if 'image' not in request.files or 'userId' not in request.form:
            return jsonify({"success": False, "message": "Missing image file or userId."}), 400

        image_file = request.files['image']
        user_id = request.form['userId']

        if image_file.filename == '':
            return jsonify({"success": False, "message": "No selected file."}), 400

        # Create a secure filename
        filename = f"profile_{user_id}_{secure_filename(image_file.filename)}"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)

        # Create the public URL for the image
        image_url = f"/uploads/{filename}" # Relative URL

        # Update the user document in Firestore
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        user_ref.update({'profile_picture_url': image_url})

        return jsonify({"success": True, "message": "Profile picture updated!", "image_url": image_url}), 200

    except Exception as e:
        print(f"Error updating profile picture: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Admin: User Management Routes ---

@app.route('/api/users', methods=['GET'])
def get_users():
    """(Admin) Fetches all student users."""
    if (db_error := check_db()): return db_error

    try:
        users_ref = db.collection(USERS_COLLECTION).where('role', '==', 'student').stream()
        users_list = [user.to_dict() for user in users_ref]
        
        # Serialize timestamps if necessary (though not shown in original for this route)
        for user in users_list:
             if 'created_at' in user and hasattr(user['created_at'], 'isoformat'):
                 user['created_at'] = user['created_at'].isoformat()

        return jsonify({"success": True, "users": users_list}), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/status', methods=['POST'])
def update_user_status():
    """(Admin) Updates a user's account status (block/unblock)."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or not all(k in data for k in ('userId', 'status')):
        return jsonify({"success": False, "message": "Missing userId or status."}), 400

    user_id = data['userId']
    new_status = data['status']

    if new_status not in ['active', 'blocked']:
        return jsonify({"success": False, "message": "Invalid status."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        user_ref.update({'account_status': new_status})
        action_text = "blocked" if new_status == "blocked" else "activated"
        return jsonify({"success": True, "message": f"User account {action_text}."}), 200

    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """(Admin) Deletes a user."""
    if (db_error := check_db()): return db_error

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        # TODO: In a real app, you'd also delete associated issue records
        # or handle them (e.g., auto-return books).
        user_ref.delete()

        return jsonify({"success": True, "message": "User deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# --- Book Management Routes (Admin & General) ---

@app.route('/api/books', methods=['GET'])
def get_books():
    """Fetches all books. If userId is provided, shows user-specific status."""
    if (db_error := check_db()): return db_error

    user_id = request.args.get('userId')

    try:
        books_ref = db.collection(BOOKS_COLLECTION).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        books_list = []
        
        for book in books_ref:
            book_data = book.to_dict()
            book_id = book_data.get('book_id')

            if 'created_at' in book_data and hasattr(book_data['created_at'], 'isoformat'):
                 book_data['created_at'] = book_data['created_at'].isoformat()

            # Default status
            book_data['display_status'] = 'available' if book_data.get('copies_available', 0) > 0 else 'not_available'

            if user_id and book_id:
                # Check user's record for this book
                issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('book_id', '==', book_id).where('return_status', 'in', ['pending_issue', 'issued']).limit(1).get()
                
                if issue_ref:
                    issue_status = issue_ref[0].to_dict().get('return_status')
                    if issue_status == 'pending_issue':
                        book_data['display_status'] = 'pending_issue'
                    elif issue_status == 'issued':
                        book_data['display_status'] = 'issued'

            books_list.append(book_data)

        return jsonify({"success": True, "books": books_list}), 200

    except Exception as e:
        print(f"Error fetching books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books', methods=['POST'])
def add_book():
    """(Admin) Adds a new book, handling optional image upload."""
    if (db_error := check_db()): return db_error

    try:
        if 'title' not in request.form or 'author' not in request.form:
            return jsonify({"success": False, "message": "Missing required fields (title, author)."}), 400

        book_id = str(uuid.uuid4())
        total_copies = int(request.form.get('copies', 1))
        
        book_data = {
            'book_id': book_id,
            'title': request.form['title'],
            'author': request.form['author'],
            'category': request.form.get('category', 'Uncategorized'),
            'total_copies': total_copies,
            'copies_available': total_copies,
            'image_url': None,
            'created_at': firestore.SERVER_TIMESTAMP
        }

        if 'image' in request.files:
            image_file = request.files['image']
            if image_file.filename != '':
                filename = f"book_{book_id}_{secure_filename(image_file.filename)}"
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(image_path)
                book_data['image_url'] = f"/uploads/{filename}" # Relative URL

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
    """(Admin) Deletes a book."""
    if (db_error := check_db()): return db_error

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404
        
        # TODO: Also delete associated issue records or handle them.
        # TODO: Delete the associated image file from /uploads.
        book_ref.delete()

        return jsonify({"success": True, "message": "Book deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books/<string:book_id>', methods=['PUT'])
def update_book_details(book_id):
    """(Admin) Updates book's text details (title, author, category)."""
    if (db_error := check_db()): return db_error

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided."}), 400

        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        update_data = {}
        if 'title' in data: update_data['title'] = data['title']
        if 'author' in data: update_data['author'] = data['author']
        if 'category' in data: update_data['category'] = data['category']

        if update_data:
            book_ref.update(update_data)
            return jsonify({"success": True, "message": "Book details updated."}), 200
        else:
            return jsonify({"success": False, "message": "No valid fields to update."}), 400
            
    except Exception as e:
        print(f"Error updating book details: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/update-image', methods=['POST'])
def update_book_image():
    """(Admin) Updates the image for a specific book."""
    if (db_error := check_db()): return db_error

    try:
        if 'image' not in request.files or 'bookId' not in request.form:
            return jsonify({"success": False, "message": "Missing image file or bookId."}), 400

        image_file = request.files['image']
        book_id = request.form['bookId']

        if image_file.filename == '':
            return jsonify({"success": False, "message": "No selected file."}), 400

        # TODO: Delete the old image file.
        filename = f"book_{book_id}_{secure_filename(image_file.filename)}"
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(image_path)
        image_url = f"/uploads/{filename}"

        db.collection(BOOKS_COLLECTION).document(book_id).update({'image_url': image_url})

        return jsonify({
            "success": True,
            "message": "Image updated successfully!",
            "image_url": image_url
        }), 200

    except Exception as e:
        print(f"Error updating book image: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/books/update-copies', methods=['POST'])
def update_book_copies():
    """(Admin) Updates the total copies for a book, adjusting available copies."""
    if (db_error := check_db()): return db_error

    try:
        data = request.get_json()
        if 'bookId' not in data or 'copies' not in data:
            return jsonify({"success": False, "message": "Missing bookId or copies."}), 400

        book_id = data['bookId']
        new_total_copies = int(data['copies'])

        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        book_data = book_doc.to_dict()
        current_total = book_data.get('total_copies', 0)
        current_available = book_data.get('copies_available', 0)
        issued_copies = current_total - current_available

        if new_total_copies < issued_copies:
            return jsonify({"success": False, "message": f"Cannot set copies lower than currently issued books ({issued_copies})."}), 400

        new_available_copies = new_total_copies - issued_copies

        book_ref.update({
            'total_copies': new_total_copies,
            'copies_available': new_available_copies
        })
        return jsonify({"success": True, "message": "Book copies updated."}), 200
        
    except Exception as e:
        print(f"Error updating book copies: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Issue & Return Routes (Student) ---

@app.route('/api/issue-book', methods=['POST'])
def issue_book_request():
    """(Student) Creates a request to issue a book."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if not data or not all(k in data for k in ('userId', 'bookId')):
        return jsonify({"success": False, "message": "User ID or Book ID is missing."}), 400

    user_id = data['userId']
    book_id = data['bookId']

    try:
        # Check if already requested or issued
        existing_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('book_id', '==', book_id).where('return_status', 'in', ['pending_issue', 'issued']).limit(1).get()
        if existing_ref:
            return jsonify({"success": False, "message": "You have already requested or issued this book."}), 409
        
        # Check if book is available
        book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()
        if not book_doc.exists or book_doc.to_dict().get('copies_available', 0) == 0:
            return jsonify({"success": False, "message": "Book is not available for issue."}), 400

        issue_id = str(uuid.uuid4())
        issue_data = {
            'issue_id': issue_id,
            'user_id': user_id,
            'book_id': book_id,
            'request_date': firestore.SERVER_TIMESTAMP,
            'issue_date': None,
            'return_date': None,
            'return_request_date': None,
            'return_status': 'pending_issue' # Statuses: pending_issue, issued, pending_return, returned
        }
        db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id).set(issue_data)
        return jsonify({"success": True, "message": "Book issue request sent."}), 201

    except Exception as e:
        print(f"Error creating issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/my-orders', methods=['GET'])
def get_my_orders():
    """(Student) Fetches all pending and issued books for the user."""
    if (db_error := check_db()): return db_error

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "User ID is required."}), 400

    try:
        orders_ref = db.collection(ISSUE_RECORDS_COLLECTION).where('user_id', '==', user_id).where('return_status', 'in', ['issued', 'pending_issue']).stream()
        
        orders_list = []
        for order in orders_ref:
            order_data = order.to_dict()
            book_doc = db.collection(BOOKS_COLLECTION).document(order_data['book_id']).get()
            
            if book_doc.exists:
                book_data = book_doc.to_dict()
                order_data['title'] = book_data.get('title', 'N/A')
                order_data['author'] = book_data.get('author', 'N/A')
                order_data['image_url'] = book_data.get('image_url')
            
            # Serialize timestamps
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
    """(Student) Cancels a 'pending_issue' request."""
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

        if issue_doc.to_dict().get('return_status') != 'pending_issue':
            return jsonify({"success": False, "message": "Only pending requests can be cancelled."}), 400

        issue_ref.delete()
        return jsonify({"success": True, "message": "Request cancelled."}), 200

    except Exception as e:
        print(f"Error cancelling request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-book', methods=['POST'])
def return_book_request():
    """(Student) Creates a request to return an 'issued' book."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if 'issueId' not in data:
        return jsonify({"success": False, "message": "Issue ID is missing."}), 400

    issue_id = data['issueId']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)
        issue_doc = issue_ref.get()

        if not issue_doc.exists:
            return jsonify({"success": False, "message": "Issue record not found."}), 404
        if issue_doc.to_dict().get('return_status') != 'issued':
            return jsonify({"success": False, "message": "Only issued books can be returned."}), 400

        issue_ref.update({'return_status': 'pending_return', 'return_request_date': firestore.SERVER_TIMESTAMP})
        return jsonify({"success": True, "message": "Return request sent."}), 201

    except Exception as e:
        print(f"Error creating return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/returned-books', methods=['GET'])
def get_returned_books():
    """(Student) Fetches all 'returned' books for the user."""
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
                book_data = book_doc.to_dict()
                record_data['title'] = book_data.get('title', 'N/A')
                record_data['author'] = book_data.get('author', 'N/A')
                record_data['image_url'] = book_data.get('image_url')

            if 'issue_date' in record_data and record_data['issue_date']:
                record_data['issue_date'] = record_data['issue_date'].isoformat()
            if 'return_date' in record_data and record_data['return_date']:
                record_data['return_date'] = record_data['return_date'].isoformat()
                
            returned_list.append(record_data)

        return jsonify({"success": True, "returned_books": returned_list}), 200
    except Exception as e:
        print(f"Error fetching returned books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Issue & Return Routes (Admin) ---

def fetch_and_join_requests(status_field, status_value):
    """Helper to fetch issue/return requests and join user/book data."""
    requests_ref = db.collection(ISSUE_RECORDS_COLLECTION).where(status_field, '==', status_value).stream()
    requests_list = []
    
    for req in requests_ref:
        req_data = req.to_dict()
        user_doc = db.collection(USERS_COLLECTION).document(req_data['user_id']).get()
        book_doc = db.collection(BOOKS_COLLECTION).document(req_data['book_id']).get()

        if user_doc.exists:
            req_data['username'] = user_doc.to_dict().get('username', 'N/A')
        if book_doc.exists:
            req_data['title'] = book_doc.to_dict().get('title', 'N/A')
            req_data['author'] = book_doc.to_dict().get('author', 'N/A')
        
        # Serialize timestamps
        for date_field in ['request_date', 'issue_date', 'return_request_date']:
            if date_field in req_data and hasattr(req_data[date_field], 'isoformat'):
                req_data[date_field] = req_data[date_field].isoformat()
                
        requests_list.append(req_data)
    return requests_list

@app.route('/api/issue-requests', methods=['GET'])
def get_issue_requests():
    """(Admin) Fetches all pending book issue requests."""
    if (db_error := check_db()): return db_error
    try:
        requests_list = fetch_and_join_requests('return_status', 'pending_issue')
        return jsonify({"success": True, "requests": requests_list}), 200
    except Exception as e:
        print(f"Error fetching issue requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-requests', methods=['GET'])
def get_return_requests():
    """(Admin) Fetches all pending book return requests."""
    if (db_error := check_db()): return db_error
    try:
        requests_list = fetch_and_join_requests('return_status', 'pending_return')
        return jsonify({"success": True, "requests": requests_list}), 200
    except Exception as e:
        print(f"Error fetching return requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-request', methods=['POST'])
def handle_issue_request():
    """(Admin) Accepts or rejects a 'pending_issue' request."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if 'issueId' not in data or 'action' not in data:
        return jsonify({"success": False, "message": "Missing issueId or action."}), 400

    issue_id = data['issueId']
    action = data['action']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)

        if action == 'accept':
            book_id = data.get('bookId')
            if not book_id:
                return jsonify({"success": False, "message": "Missing bookId for accept."}), 400
                
            book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

            @firestore.transactional
            def update_in_transaction(transaction, book_ref, issue_ref):
                book_snapshot = book_ref.get(transaction=transaction)
                if book_snapshot.to_dict().get('copies_available', 0) > 0:
                    transaction.update(book_ref, {'copies_available': firestore.Increment(-1)})
                    transaction.update(issue_ref, {'return_status': 'issued', 'issue_date': firestore.SERVER_TIMESTAMP})
                    return True
                return False

            transaction = db.transaction()
            if update_in_transaction(transaction, book_ref, issue_ref):
                return jsonify({"success": True, "message": "Request accepted and book issued."}), 200
            else:
                return jsonify({"success": False, "message": "Book is out of stock."}), 400

        elif action == 'reject':
            issue_ref.delete()
            return jsonify({"success": True, "message": "Request rejected."}), 200
        else:
            return jsonify({"success": False, "message": "Invalid action."}), 400

    except Exception as e:
        print(f"Error handling issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-return', methods=['POST'])
def handle_return_request():
    """(Admin) Accepts or rejects a 'pending_return' request."""
    if (db_error := check_db()): return db_error

    data = request.get_json()
    if 'issueId' not in data or 'action' not in data:
        return jsonify({"success": False, "message": "Missing issueId or action."}), 400

    issue_id = data['issueId']
    action = data['action']

    try:
        issue_ref = db.collection(ISSUE_RECORDS_COLLECTION).document(issue_id)

        if action == 'accept':
            book_id = data.get('bookId')
            if not book_id:
                 return jsonify({"success": False, "message": "Missing bookId for accept."}), 400
                 
            book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

            @firestore.transactional
            def update_in_transaction(transaction, book_ref, issue_ref):
                # We increment copies even if the book doc doesn't exist,
                # though it should.
                transaction.update(book_ref, {'copies_available': firestore.Increment(1)})
                transaction.update(issue_ref, {'return_status': 'returned', 'return_date': firestore.SERVER_TIMESTAMP})
                return True

            transaction = db.transaction()
            if update_in_transaction(transaction, book_ref, issue_ref):
                return jsonify({"success": True, "message": "Return accepted."}), 200
            else:
                return jsonify({"success": False, "message": "Error processing return."}), 400

        elif action == 'reject':
            # Reset status to 'issued'
            issue_ref.update({'return_status': 'issued', 'return_request_date': firestore.DELETE_FIELD})
            return jsonify({"success": True, "message": "Return request rejected."}), 200
        else:
            return jsonify({"success": False, "message": "Invalid action."}), 400

    except Exception as e:
        print(f"Error handling return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# --- Static File Serving ---

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serves files from the UPLOAD_FOLDER."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/', methods=['GET'])
def home():
    """Redirects the root URL to login.html (assuming it's in 'public')."""
    return redirect('/login.html')

@app.route('/<path:path>')
def serve_public_files(path):
    """Serves static files from the 'public' directory."""
    return send_from_directory('public', path)

# --- Run Application ---

# We remove the if __name__ == '__main__': block.
# Vercel will import the 'app' object and run it.
# The startup print statements are moved to the global scope
# to run during the serverless function's cold start.
if not db:
    print("---")
    print("CRITICAL: Firebase DB not initialized. Server is running but API calls will fail.")
    print("Please check your FIREBASE_SA_FILE path in the .env file.")
    print("---")
else:
    print("Flask app object created. Ready for Vercel.")
