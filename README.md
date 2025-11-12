# Library Management System

A comprehensive web-based library management system built with Python Flask backend and modern HTML/CSS/JavaScript frontend. The system supports both student and admin roles with features for book management, issue/return requests, user management, and profile customization.

## Features

### For Students
- **User Registration & Authentication**: Secure login and registration system
- **Book Browsing**: View all available books with search and category filtering
- **Book Issue Requests**: Request to borrow books from the library
- **Issued Books Management**: View currently issued books and request returns
- **Return History**: Track all previously returned books with dates
- **Profile Management**: Upload and manage profile pictures
- **Responsive Design**: Works seamlessly on desktop and mobile devices

### For Admins
- **Book Management**: Add, edit, delete, and manage book inventory
- **User Management**: View, block/unblock, and delete student accounts
- **Request Management**: Approve or reject book issue and return requests
- **Dashboard Overview**: Comprehensive admin panel for system management
- **Image Upload**: Upload book cover images
- **Real-time Updates**: Live updates on book availability and user status

### System Features
- **Firebase Integration**: Cloud-based data storage with Firestore
- **Responsive UI**: Mobile-first design with adaptive layouts
- **Secure Authentication**: Role-based access control
- **Real-time Notifications**: Instant feedback on actions
- **Image Management**: Profile and book cover image uploads
- **Search & Filter**: Advanced book search capabilities

## Tech Stack

### Backend
- **Python Flask**: Web framework for API development
- **Firebase Admin SDK**: Cloud database and authentication
- **Firestore**: NoSQL cloud database
- **Flask-CORS**: Cross-origin resource sharing

### Frontend
- **HTML5**: Semantic markup
- **CSS3**: Modern styling with responsive design
- **JavaScript (ES6+)**: Interactive functionality
- **Font Awesome**: Icons and UI elements

### Development Tools
- **Git**: Version control
- **VS Code**: Development environment
- **Firebase Console**: Database management

## Installation

### Prerequisites
- Python 3.8 or higher
- Node.js (optional, for development)
- Firebase project with Firestore enabled
- Git

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/library-management-system.git
   cd library-management-system
   ```

2. **Set up Python virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Firebase**
   - Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
   - Enable Firestore Database
   - Generate a service account key (JSON file)
   - Place the JSON file in the project root and rename it to `my-new-firebase-key.json`

5. **Configure environment variables**
   Create a `.env` file in the project root:
   ```env
   FIREBASE_SA_FILE=my-new-firebase-key.json
   SERVER_PORT=5001
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

7. **Access the application**
   - Open your browser and go to `http://127.0.0.1:5001`
   - Register as a student or use admin credentials

## Usage

### Student Workflow
1. **Register/Login**: Create an account or log in with existing credentials
2. **Browse Books**: View available books, use search and filters
3. **Request Books**: Click "Issue Now" on available books
4. **Manage Requests**: View pending requests in "Issue Requests" section
5. **Return Books**: Request returns for issued books
6. **View History**: Check returned books in "Return Books" section

### Admin Workflow
1. **Login**: Use admin credentials to access admin panel
2. **Manage Books**: Add new books, update inventory, upload images
3. **Handle Requests**: Approve/reject issue and return requests
4. **User Management**: View student accounts, block/unblock users
5. **System Overview**: Monitor all library activities

## Project Structure

```
library-management-system/
├── app.py                      # Flask application main file
├── requirements.txt            # Python dependencies
├── my-new-firebase-key.json    # Firebase service account key
├── .env                        # Environment variables
├── README.md                   # Project documentation
├── TODO.md                     # Development tasks
├── public/                     # Frontend files
│   ├── index.html             # Landing page
│   ├── login.html             # Login page
│   ├── register.html          # Registration page
│   ├── dashboard.html         # Student dashboard
│   ├── admin.html             # Admin dashboard
│   ├── style.css              # Main stylesheet
│   ├── auth.css               # Authentication styles
│   ├── auth.js                # Authentication logic
│   ├── login.js               # Login page logic
│   ├── register.js            # Registration logic
│   ├── dashboard.js           # Student dashboard logic
│   ├── books.js               # Book management logic
│   └── users.js               # User management logic
└── uploads/                   # Uploaded images directory
```

## API Endpoints

### Authentication
- `POST /api/register` - User registration
- `POST /api/login` - User login

### Books
- `GET /api/books` - Get all books (with user-specific status)
- `POST /api/books` - Add new book
- `DELETE /api/books/<book_id>` - Delete book
- `PUT /api/books/<book_id>` - Update book details

### User Management
- `GET /api/users` - Get all users (admin only)
- `POST /api/users/status` - Update user status
- `DELETE /api/users/<user_id>` - Delete user

### Book Transactions
- `POST /api/issue-book` - Request to issue a book
- `POST /api/handle-request` - Admin approve/reject issue request
- `GET /api/my-orders` - Get user's issued/pending books
- `POST /api/return-book` - Request to return a book
- `GET /api/return-requests` - Get return requests (admin)
- `POST /api/handle-return` - Admin approve/reject return request
- `GET /api/returned-books` - Get user's return history

### Utilities
- `POST /api/user/update-profile-picture` - Update profile picture
- `POST /api/books/update-image` - Update book image
- `POST /api/books/update-copies` - Update book copies

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use meaningful commit messages
- Test all new features thoroughly
- Update documentation as needed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, email [your-email@example.com] or create an issue in the GitHub repository.

## Acknowledgments

- Font Awesome for icons
- Google Fonts for typography
- Firebase for backend services
- Flask community for the excellent framework

---

**Note**: This is a development project. For production deployment, additional security measures and optimizations would be required.
