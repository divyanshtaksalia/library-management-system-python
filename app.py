from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS 
import firebase_admin
from firebase_admin import credentials, initialize_app, firestore
from dotenv import load_dotenv
import os
import uuid # To generate unique user IDs
import json # JSON string को process करने के लिए ज़रूरी है
from flask import Flask, jsonify, request, send_from_directory, redirect

# Firestore Collection Names
USERS_COLLECTION = 'users'
BOOKS_COLLECTION = 'books'
ISSUE_REQUESTS_COLLECTION = 'issue_requests'
RETURN_REQUESTS_COLLECTION = 'return_requests'
RETURNED_BOOKS_COLLECTION = 'returned_books' # New collection for history

# 1. Load environment variables from the .env file
load_dotenv()


def initialize_firebase():
    """Firebase Admin SDK को initialize करता है और db object लौटाता है।
       यह पहले FIREBASE_SA_JSON environment variable (JSON string) को चेक करता है, 
       नहीं तो FIREBASE_SA_FILE environment variable (File path) को चेक करता है।"""
    try:
        # 1. Check for JSON Content directly (Cloud environment के लिए preferred)
        sa_json_string = os.getenv("FIREBASE_SA_JSON")
        
        if sa_json_string:
            print("Initializing Firebase using JSON content from FIREBASE_SA_JSON environment variable.")
            # JSON string को डिक्शनरी में लोड करें
            sa_dict = json.loads(sa_json_string)
            cred = credentials.Certificate(sa_dict)
        
        # 2. Check for File Path (Local environment के लिए)
        else:
            sa_file = os.getenv("FIREBASE_SA_FILE")
            
            if not sa_file or not os.path.exists(sa_file):
                print(f"ERROR: No Firebase credential found. Checked FIREBASE_SA_JSON environment variable and FIREBASE_SA_FILE path: {sa_file}")
                return None, None
            
            print(f"Initializing Firebase using file path from FIREBASE_SA_FILE: {sa_file}")
            cred = credentials.Certificate(sa_file)

        
        # Firebase App को initialize करें
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
# सुनिश्चित करें कि uploads फोल्डर मौजूद है
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# CORS configuration to allow requests from the frontend
CORS(app, resources={r"/api/*": {"origins": "*"}})

# =================================================================================
#                         AUTHENTICATION ROUTES (Auth.py)
# =================================================================================

# Helper function to check if the user is an admin
def is_admin(user_id):
    """Checks if a user is an admin by querying Firestore."""
    if not db: return False
    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        user_doc = user_ref.get()
        if user_doc.exists and user_doc.to_dict().get('role') == 'admin':
            return True
    except Exception as e:
        print(f"Error checking admin status for user {user_id}: {e}")
    return False


@app.route('/api/register', methods=['POST'])
def register_user():
    """Registers a new user (student) into the Firestore database."""
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
        
        # Check by email (assuming email is unique)
        query = users_ref.where('email', '==', email).limit(1).get()
        if len(query) > 0:
            return jsonify({"success": False, "message": "User with this email already exists."}), 409

        # Register the user
        user_id = str(uuid.uuid4())
        
        new_user = {
            'user_id': user_id,
            'username': username,
            'email': email,
            'password': password,  # NOTE: In a real app, hash the password!
            'role': 'student',
            'account_status': 'active',
            'profile_picture_url': '',
            'created_at': firestore.SERVER_TIMESTAMP
        }

        db.collection(USERS_COLLECTION).document(user_id).set(new_user)
        
        return jsonify({"success": True, "message": "Registration successful. Please log in."}), 201

    except Exception as e:
        print(f"Error during registration: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/login', methods=['POST'])
def login_user():
    """Logs in a user by checking credentials against Firestore."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"success": False, "message": "Missing email or password."}), 400

    try:
        users_ref = db.collection(USERS_COLLECTION)
        
        # Find user by email and password (NOTE: Password should be hashed in production!)
        # Since Firestore has limitations on complex queries without indexes, 
        # we'll fetch by email and check password client-side (bad practice in production, 
        # but simpler for this example). 
        # Since we are using an unhashed password in this example, we can query both.

        query = users_ref.where('email', '==', email).where('password', '==', password).limit(1).get()

        if len(query) == 0:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401

        user_doc = query[0]
        user_data = user_doc.to_dict()
        user_id = user_doc.id

        if user_data.get('account_status') == 'blocked':
             return jsonify({"success": False, "message": "Your account has been blocked by the administrator."}), 403

        # Prepare user data for frontend
        user_info = {
            'id': user_id,
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'role': user_data.get('role'),
            'profile_picture_url': user_data.get('profile_picture_url', '')
        }

        return jsonify({"success": True, "message": "Login successful.", "user": user_info}), 200

    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# =================================================================================
#                              ADMIN ROUTES (Users.js)
# =================================================================================

@app.route('/api/users', methods=['GET'])
def get_all_users():
    """Retrieves all non-admin user accounts."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    # NOTE: A real application should verify admin status before allowing this route.

    try:
        users_ref = db.collection(USERS_COLLECTION)
        # Fetch all non-admin users
        query = users_ref.where('role', '!=', 'admin').get()
        
        users_list = []
        for doc in query:
            user_data = doc.to_dict()
            users_list.append({
                'user_id': doc.id,
                'username': user_data.get('username'),
                'email': user_data.get('email'),
                'account_status': user_data.get('account_status', 'active'),
            })

        return jsonify({"success": True, "users": users_list}), 200

    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/users/status', methods=['POST'])
def update_user_status():
    """Updates the status (active/blocked) of a user account."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    # NOTE: A real application should verify admin status before allowing this route.
    
    data = request.get_json()
    user_id = data.get('userId')
    status = data.get('status') # Should be 'active' or 'blocked'

    if not all([user_id, status]) or status not in ['active', 'blocked']:
        return jsonify({"success": False, "message": "Invalid user ID or status."}), 400

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        
        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404
        
        # Prevent self-blocking or blocking the only admin
        if is_admin(user_id):
            return jsonify({"success": False, "message": "Cannot change the status of an admin account."}), 403

        user_ref.update({'account_status': status})
        
        message = f"User account successfully {'blocked' if status == 'blocked' else 'activated'}."
        return jsonify({"success": True, "message": message}), 200

    except Exception as e:
        print(f"Error updating user status: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Deletes a user and their related data from Firestore collection by their ID."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        user_ref = db.collection(USERS_COLLECTION).document(user_id)

        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        # In a real system, you would also delete:
        # 1. All book issue requests related to this user
        # 2. All book return requests related to this user
        # 3. All entries in the 'issued_books' and 'returned_books' collections
        
        # For simplicity, we only delete the user document here.
        user_ref.delete()

        return jsonify({"success": True, "message": "User deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting user: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def home():
    """Redirects the root URL to the login.html page."""
    # This sends a 302 Redirect to the browser
    return redirect('/public/login.html')

    return jsonify({
        "message": "Python backend is running! Firebase initialized successfully.",
        "status": "ok"
    })

# Route to serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# =================================================================================
#                              BOOK MANAGEMENT (Books.js)
# =================================================================================

@app.route('/api/books', methods=['POST'])
def add_book():
    """Adds a new book or updates an existing one (Admin only)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    # NOTE: Admin check should be implemented here

    try:
        # Use request.form for non-file data and request.files for file data
        title = request.form.get('title')
        author = request.form.get('author')
        category = request.form.get('category')
        copies = int(request.form.get('copies', 0))
        description = request.form.get('description')
        book_id = request.form.get('bookId') # For editing existing books
        image_file = request.files.get('image')

        if not all([title, author, category, description]) or copies <= 0:
            return jsonify({"success": False, "message": "Missing required book details or copies is invalid."}), 400

        book_data = {
            'title': title,
            'author': author,
            'category': category,
            'copies': copies,
            'available_copies': copies, # Initially all are available
            'description': description,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Handle Image Upload
        image_url = ''
        if image_file:
            # Create a unique filename for the image
            extension = image_file.filename.split('.')[-1] if '.' in image_file.filename else 'jpg'
            if book_id:
                 # Use existing book ID for filename
                image_filename = f'book_{book_id}.{extension}'
            else:
                 # Generate a temporary ID for new books until doc is created
                temp_id = str(uuid.uuid4())
                image_filename = f'book_{temp_id}.{extension}'
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            image_file.save(filepath)
            image_url = f'/uploads/{image_filename}'
            book_data['image_url'] = image_url

        
        # Add new book
        if not book_id:
            book_data['created_at'] = firestore.SERVER_TIMESTAMP
            doc_ref = db.collection(BOOKS_COLLECTION).add(book_data)
            # If an image was uploaded, we need to rename the file to use the new Firestore ID
            if image_file:
                # Get the newly created ID
                new_book_id = doc_ref[1].id
                # Rename the file using the new ID
                old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], f'book_{temp_id}.{extension}')
                new_image_filename = f'book_{new_book_id}.{extension}'
                new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_image_filename)
                
                os.rename(old_filepath, new_filepath)
                
                # Update the Firestore document with the correct final image URL
                book_data['image_url'] = f'/uploads/{new_image_filename}'
                db.collection(BOOKS_COLLECTION).document(new_book_id).update({'image_url': book_data['image_url']})

            return jsonify({"success": True, "message": "New book added successfully!"}), 201
            
        # Update existing book
        else:
            book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
            if not book_ref.get().exists:
                return jsonify({"success": False, "message": "Book not found for update."}), 404

            # If a new image was uploaded during an update, the URL is already updated in book_data
            if 'image_url' in book_data:
                # If an image was uploaded in an update, we assume the filename used the correct book_id already
                 pass 

            book_ref.update(book_data)
            return jsonify({"success": True, "message": "Book updated successfully!"}), 200

    except Exception as e:
        print(f"Error adding/updating book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books', methods=['GET'])
def get_books():
    """Retrieves a list of all books."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    try:
        books_ref = db.collection(BOOKS_COLLECTION)
        books = books_ref.get()
        
        books_list = []
        for doc in books:
            book_data = doc.to_dict()
            books_list.append({
                'id': doc.id,
                'title': book_data.get('title'),
                'author': book_data.get('author'),
                'category': book_data.get('category'),
                'copies': book_data.get('copies'),
                'available_copies': book_data.get('available_copies'),
                'description': book_data.get('description'),
                'image_url': book_data.get('image_url', ''),
            })

        return jsonify({"success": True, "books": books_list}), 200

    except Exception as e:
        print(f"Error fetching books: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/books/<book_id>', methods=['DELETE'])
def delete_book(book_id):
    """Deletes a book (Admin only)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    # NOTE: Admin check should be implemented here

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)

        if not book_ref.get().exists:
            return jsonify({"success": False, "message": "Book not found."}), 404

        # In a real system, you should check for outstanding issue/return requests
        # and issued copies before deleting.

        book_ref.delete()
        return jsonify({"success": True, "message": "Book deleted successfully."}), 200

    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# =================================================================================
#                              USER UTILITIES
# =================================================================================

@app.route('/api/user/update-profile-picture', methods=['POST'])
def update_profile_picture():
    """Handles the upload and update of a user's profile picture."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    try:
        user_id = request.form.get('userId')
        image_file = request.files.get('image')

        if not user_id or not image_file:
            return jsonify({"success": False, "message": "Missing user ID or image file."}), 400

        user_ref = db.collection(USERS_COLLECTION).document(user_id)
        if not user_ref.get().exists:
            return jsonify({"success": False, "message": "User not found."}), 404

        # Create a unique filename for the image
        extension = image_file.filename.split('.')[-1] if '.' in image_file.filename else 'jpg'
        image_filename = f'profile_{user_id}.{extension}'
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        
        # Save the file
        image_file.save(filepath)
        
        # Construct the URL
        image_url = f'/uploads/{image_filename}'

        # Update the user document in Firestore
        user_ref.update({'profile_picture_url': image_url})

        return jsonify({"success": True, "message": "Profile picture updated.", "image_url": image_url}), 200

    except Exception as e:
        print(f"Error updating profile picture: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


# =================================================================================
#                              ISSUE REQUESTS (Dashboard.js / Admin)
# =================================================================================

@app.route('/api/request-issue', methods=['POST'])
def request_issue():
    """A student requests to issue a book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
    
    data = request.get_json()
    user_id = data.get('userId')
    book_id = data.get('bookId')

    if not all([user_id, book_id]):
        return jsonify({"success": False, "message": "Missing User ID or Book ID."}), 400

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            return jsonify({"success": False, "message": "Book not found."}), 404
        
        book_data = book_doc.to_dict()

        if book_data.get('available_copies', 0) <= 0:
            return jsonify({"success": False, "message": "No available copies of this book."}), 400

        # Check for existing pending request by this user for this book
        pending_query = db.collection(ISSUE_REQUESTS_COLLECTION) \
            .where('user_id', '==', user_id) \
            .where('book_id', '==', book_id) \
            .limit(1).get()

        if len(pending_query) > 0:
            return jsonify({"success": False, "message": "You already have a pending request for this book."}), 400
            
        # Check if the book is already issued to the user
        issued_query = db.collection(USERS_COLLECTION).document(user_id).collection('issued_books') \
            .where('book_id', '==', book_id) \
            .limit(1).get()
            
        if len(issued_query) > 0:
            return jsonify({"success": False, "message": "You have already issued this book."}), 400

        # Create the issue request
        request_data = {
            'user_id': user_id,
            'book_id': book_id,
            'book_title': book_data.get('title'),
            'request_date': firestore.SERVER_TIMESTAMP,
            'status': 'pending'
        }
        
        db.collection(ISSUE_REQUESTS_COLLECTION).add(request_data)
        
        return jsonify({"success": True, "message": "Book issue request sent to admin."}), 200

    except Exception as e:
        print(f"Error requesting book issue: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/issue-requests', methods=['GET'])
def get_issue_requests():
    """Retrieves all pending book issue requests (Admin only)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    # NOTE: Admin check should be implemented here
    
    try:
        # Fetch only pending requests
        requests_query = db.collection(ISSUE_REQUESTS_COLLECTION) \
            .where('status', '==', 'pending') \
            .get()
            
        requests_list = []
        for doc in requests_query:
            req_data = doc.to_dict()
            # Get user and book details (optional but good for context)
            user_doc = db.collection(USERS_COLLECTION).document(req_data['user_id']).get()
            book_doc = db.collection(BOOKS_COLLECTION).document(req_data['book_id']).get()

            requests_list.append({
                'request_id': doc.id,
                'user_id': req_data['user_id'],
                'username': user_doc.to_dict().get('username', 'N/A'),
                'book_id': req_data['book_id'],
                'book_title': book_doc.to_dict().get('title', 'N/A'),
                'request_date': req_data['request_date'].strftime('%Y-%m-%d %H:%M:%S') if req_data['request_date'] else 'N/A',
                'status': req_data['status']
            })

        return jsonify({"success": True, "requests": requests_list}), 200

    except Exception as e:
        print(f"Error fetching issue requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-issue-request', methods=['POST'])
def handle_issue_request():
    """Admin approves or rejects a book issue request."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
        
    # NOTE: Admin check should be implemented here

    data = request.get_json()
    request_id = data.get('requestId')
    action = data.get('action') # 'approve' or 'reject'

    if not all([request_id, action]) or action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Invalid request ID or action."}), 400

    try:
        request_ref = db.collection(ISSUE_REQUESTS_COLLECTION).document(request_id)
        request_doc = request_ref.get()

        if not request_doc.exists or request_doc.to_dict().get('status') != 'pending':
            return jsonify({"success": False, "message": "Pending request not found or already handled."}), 404

        request_data = request_doc.to_dict()
        book_id = request_data['book_id']
        user_id = request_data['user_id']
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()
        book_data = book_doc.to_dict()

        if action == 'approve':
            if book_data.get('available_copies', 0) <= 0:
                 return jsonify({"success": False, "message": "Cannot approve: Book is out of stock."}), 400

            # 1. Update book availability
            new_available_copies = book_data['available_copies'] - 1
            book_ref.update({'available_copies': new_available_copies})

            # 2. Mark request as approved
            request_ref.update({'status': 'approved'})

            # 3. Add to user's issued books sub-collection
            issued_book_data = {
                'issue_id': str(uuid.uuid4()),
                'book_id': book_id,
                'book_title': book_data['title'],
                'book_author': book_data['author'],
                'image_url': book_data.get('image_url', ''),
                'issue_date': firestore.SERVER_TIMESTAMP,
                'due_date': firestore.SERVER_TIMESTAMP # NOTE: Add real due date logic
            }
            db.collection(USERS_COLLECTION).document(user_id).collection('issued_books').add(issued_book_data)

            return jsonify({"success": True, "message": "Issue request approved. Book issued successfully."}), 200

        elif action == 'reject':
            # Mark request as rejected
            request_ref.update({'status': 'rejected'})
            return jsonify({"success": True, "message": "Issue request rejected."}), 200

    except Exception as e:
        print(f"Error handling issue request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

# =================================================================================
#                              MY ORDERS / RETURN REQUESTS
# =================================================================================

@app.route('/api/my-orders', methods=['GET'])
def get_my_orders():
    """Retrieves a student's currently issued and pending book requests."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "Missing User ID."}), 400

    try:
        # 1. Get Issued Books (from the user's sub-collection)
        issued_query = db.collection(USERS_COLLECTION).document(user_id).collection('issued_books').get()
        issued_books = []
        for doc in issued_query:
            data = doc.to_dict()
            issued_books.append({
                'issue_id': doc.id, # The ID of the document in the sub-collection
                'book_id': data.get('book_id'),
                'title': data.get('book_title'),
                'author': data.get('book_author'),
                'image_url': data.get('image_url', ''),
                'issue_date': data.get('issue_date').isoformat() if data.get('issue_date') else 'N/A',
                'due_date': data.get('due_date').isoformat() if data.get('due_date') else 'N/A',
            })
        
        # 2. Get Pending Requests (from the main issue_requests collection)
        pending_query = db.collection(ISSUE_REQUESTS_COLLECTION) \
            .where('user_id', '==', user_id) \
            .where('status', '==', 'pending') \
            .get()
            
        pending_books = []
        for doc in pending_query:
            data = doc.to_dict()
            pending_books.append({
                'request_id': doc.id,
                'book_id': data.get('book_id'),
                'title': data.get('book_title'),
                'request_date': data.get('request_date').isoformat() if data.get('request_date') else 'N/A',
            })

        return jsonify({"success": True, "issued": issued_books, "pending": pending_books}), 200

    except Exception as e:
        print(f"Error fetching user orders: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/return-book', methods=['POST'])
def request_return():
    """A student requests to return a book."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
        
    data = request.get_json()
    user_id = data.get('userId')
    issue_id = data.get('issueId') # The ID of the issued book document in the sub-collection

    if not all([user_id, issue_id]):
        return jsonify({"success": False, "message": "Missing User ID or Issue ID."}), 400

    try:
        # 1. Check if the book is actually issued and get details
        issued_book_ref = db.collection(USERS_COLLECTION).document(user_id).collection('issued_books').document(issue_id)
        issued_book_doc = issued_book_ref.get()

        if not issued_book_doc.exists:
            return jsonify({"success": False, "message": "Issued book record not found."}), 404
        
        issued_book_data = issued_book_doc.to_dict()
        book_id = issued_book_data['book_id']

        # 2. Check for existing pending return request for this issue
        pending_return_query = db.collection(RETURN_REQUESTS_COLLECTION) \
            .where('issue_doc_id', '==', issue_id) \
            .where('status', '==', 'pending') \
            .limit(1).get()

        if len(pending_return_query) > 0:
            return jsonify({"success": False, "message": "A return request for this book is already pending admin approval."}), 400

        # 3. Create the return request
        request_data = {
            'user_id': user_id,
            'issue_doc_id': issue_id, # Reference to the document in the user's issued_books sub-collection
            'book_id': book_id,
            'book_title': issued_book_data.get('book_title'),
            'request_date': firestore.SERVER_TIMESTAMP,
            'status': 'pending'
        }
        
        db.collection(RETURN_REQUESTS_COLLECTION).add(request_data)
        
        return jsonify({"success": True, "message": "Book return request sent to admin."}), 200

    except Exception as e:
        print(f"Error requesting book return: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/return-requests', methods=['GET'])
def get_return_requests():
    """Retrieves all pending book return requests (Admin only)."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    # NOTE: Admin check should be implemented here
    
    try:
        # Fetch only pending requests
        requests_query = db.collection(RETURN_REQUESTS_COLLECTION) \
            .where('status', '==', 'pending') \
            .get()
            
        requests_list = []
        for doc in requests_query:
            req_data = doc.to_dict()
            # Get user and book details (optional but good for context)
            user_doc = db.collection(USERS_COLLECTION).document(req_data['user_id']).get()
            
            requests_list.append({
                'request_id': doc.id,
                'user_id': req_data['user_id'],
                'username': user_doc.to_dict().get('username', 'N/A'),
                'book_id': req_data['book_id'],
                'book_title': req_data['book_title'],
                'request_date': req_data['request_date'].strftime('%Y-%m-%d %H:%M:%S') if req_data['request_date'] else 'N/A',
                'status': req_data['status']
            })

        return jsonify({"success": True, "requests": requests_list}), 200

    except Exception as e:
        print(f"Error fetching return requests: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/handle-return', methods=['POST'])
def handle_return_request():
    """Admin approves or rejects a book return request."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500
        
    # NOTE: Admin check should be implemented here

    data = request.get_json()
    request_id = data.get('requestId')
    action = data.get('action') # 'approve' or 'reject'

    if not all([request_id, action]) or action not in ['approve', 'reject']:
        return jsonify({"success": False, "message": "Invalid request ID or action."}), 400

    try:
        request_ref = db.collection(RETURN_REQUESTS_COLLECTION).document(request_id)
        request_doc = request_ref.get()

        if not request_doc.exists or request_doc.to_dict().get('status') != 'pending':
            return jsonify({"success": False, "message": "Pending request not found or already handled."}), 404

        request_data = request_doc.to_dict()
        book_id = request_data['book_id']
        user_id = request_data['user_id']
        issue_doc_id = request_data['issue_doc_id']
        
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        
        if action == 'approve':
            # 1. Update book availability
            book_doc = book_ref.get()
            if not book_doc.exists:
                return jsonify({"success": False, "message": "Book not found in inventory."}), 404

            book_data = book_doc.to_dict()
            new_available_copies = book_data.get('available_copies', 0) + 1
            book_ref.update({'available_copies': new_available_copies})

            # 2. Mark return request as approved
            request_ref.update({'status': 'approved'})

            # 3. Get the original issued book record and delete it
            issued_book_ref = db.collection(USERS_COLLECTION).document(user_id).collection('issued_books').document(issue_doc_id)
            issued_book_doc = issued_book_ref.get()
            
            if issued_book_doc.exists:
                issued_data = issued_book_doc.to_dict()
                issued_book_ref.delete()
            else:
                # If the record is missing, log an error but continue the return process
                print(f"WARNING: Issued book record {issue_doc_id} not found during return approval.")
                issued_data = {'book_author': 'Unknown', 'issue_date': firestore.SERVER_TIMESTAMP}
            
            # 4. Add to returned books history
            returned_book_data = {
                'user_id': user_id,
                'book_id': book_id,
                'book_title': request_data.get('book_title'),
                'book_author': issued_data.get('book_author', 'Unknown'),
                'issue_date': issued_data.get('issue_date'),
                'return_date': firestore.SERVER_TIMESTAMP,
            }
            db.collection(USERS_COLLECTION).document(user_id).collection('returned_books').add(returned_book_data)

            return jsonify({"success": True, "message": "Return request approved. Book returned successfully."}), 200

        elif action == 'reject':
            # Mark request as rejected
            request_ref.update({'status': 'rejected'})
            return jsonify({"success": True, "message": "Return request rejected."}), 200

    except Exception as e:
        print(f"Error handling return request: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/returned-books', methods=['GET'])
def get_returned_books_history():
    """Retrieves a student's history of returned books."""
    if not db:
        return jsonify({"success": False, "message": "Backend not initialized."}), 500

    user_id = request.args.get('userId')
    if not user_id:
        return jsonify({"success": False, "message": "Missing User ID."}), 400

    try:
        # Get history from the user's returned_books sub-collection
        history_query = db.collection(USERS_COLLECTION).document(user_id).collection('returned_books').get()
        returned_history = []
        for doc in history_query:
            data = doc.to_dict()
            returned_history.append({
                'id': doc.id, 
                'title': data.get('book_title'),
                'author': data.get('book_author'),
                'issue_date': data.get('issue_date').isoformat() if data.get('issue_date') else 'N/A',
                'return_date': data.get('return_date').isoformat() if data.get('return_date') else 'N/A',
            })

        return jsonify({"success": True, "history": returned_history}), 200

    except Exception as e:
        print(f"Error fetching return history: {e}")
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
