const booksContainer = document.getElementById('booksList');
const addBookForm = document.getElementById('addBookForm');
const returnRequestsList = document.getElementById('returnRequestsList');
const issueRequestsList = document.getElementById('issueRequestsList');
const usersList = document.getElementById('usersList');

function showBookSkeleton() {
    if (!booksContainer) return;
    const skeletonHTML = Array(5).fill(`
        <div class="book-item-skeleton">
            <div class="skeleton skeleton-image"></div>
            <div class="skeleton-info">
                <div class="skeleton skeleton-line"></div>
                <div class="skeleton skeleton-line short"></div>
            </div>
        </div>`).join('');
    booksContainer.innerHTML = skeletonHTML;
}

// Helper function for button loading state
function setButtonLoading(button, isLoading, originalText) {
    if (isLoading) {
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${originalText.replace('Add', 'Adding...').replace('Update', 'Updating...')}`;
    } else {
        button.disabled = false;
        button.innerHTML = originalText;
    }
}

async function loadUsers() {
    if (!usersList) return;
    try {
        const response = await fetch('/api/users');
        const data = await response.json();
        if (data.success) {
            renderUsers(data.users);
        } else {
            usersList.innerHTML = `<p class="error">Error in loading users: ${data.message}</p>`;
        }
    } catch (error) {
        usersList.innerHTML = '<p class="error">Network error while loading users.</p>';
    }
}

function renderUsers(users) {
    if (users.length === 0) {
        usersList.innerHTML = '<p>No student users found.</p>';
        return;
    }

    const tableHtml = `
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Status</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${users.map(user => `
                    <tr class="user-row" data-user-id="${user.user_id}">
                        <td>${user.user_id}</td>
                        <td>${user.username}</td>
                        <td>${user.email}</td>
                        <td style="color: ${user.account_status === 'blocked' ? 'red' : 'green'}; font-weight: bold;">
                            ${user.account_status === 'blocked' ? 'Blocked' : 'Active'}
                        </td>
                        <td class="user-actions">
                            ${user.account_status === 'active' ? 
                                `<button 
                                    data-user-id="${user.user_id}" 
                                    data-status="blocked" 
                                    class="btn-status btn-block">Block</button>` 
                                : 
                                `<button 
                                    data-user-id="${user.user_id}" 
                                    data-status="active" 
                                    class="btn-status btn-activate">Activate</button>`
                            }
                            <button 
                                data-user-id="${user.user_id}" 
                                class="btn-status btn-delete-user">
                                Delete
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
    usersList.innerHTML = tableHtml;
}

async function showUserDetails(userId) {
    const modal = document.getElementById('userDetailsModal');
    const modalContent = document.getElementById('userDetailsContent');
    modalContent.innerHTML = '<p>Loading user details...</p>';
    modal.style.display = 'block';

    try {
        const response = await fetch(`/api/user-details/${userId}`);
        const data = await response.json();

        if (data.success) {
            const { user, issuedBooks } = data.details;
            let booksHtml = '<h4>Issued Books</h4>';

            if (issuedBooks.length > 0) {
                booksHtml += issuedBooks.map(book => `
                    <div class="order-card">
                        <p><strong>Title:</strong> ${book.title}</p>
                        <p><strong>Author:</strong> ${book.author}</p>
                        <p><strong>Issue Date:</strong> ${new Date(book.issue_date).toLocaleDateString()}</p>
                        <p><strong>Status:</strong> ${book.return_status}</p>
                    </div>
                `).join('');
            } else {
                booksHtml += '<p>This user has no issued books.</p>';
            }

            modalContent.innerHTML = `
                <h2>${user.username}</h2>
                <p><strong>User ID:</strong> ${user.user_id}</p>
                <p><strong>Email:</strong> ${user.email}</p>
                <p><strong>Account Created:</strong> ${new Date(user.created_at).toLocaleString()}</p>
                <hr>
                ${booksHtml}
            `;
        } else {
            modalContent.innerHTML = `<p class="error">Error: ${data.message}</p>`;
        }
    } catch (error) {
        modalContent.innerHTML = '<p class="error">Network error while fetching user details.</p>';
    }
}


function setupUserStatusListeners() {
    if (!usersList) return;

    // Modal close logic
    const modal = document.getElementById('userDetailsModal');
    const closeButton = document.querySelector('.close-button');
    if(closeButton) {
        closeButton.onclick = () => modal.style.display = 'none';
    }
    window.onclick = (event) => {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }

    usersList.addEventListener('click', async (e) => {
        const targetRow = e.target.closest('.user-row');

        // Handle delete user button first, as it's more specific
        if (e.target.classList.contains('btn-delete-user')) {
            const userId = e.target.dataset.userId;
            
            if (!confirm('Are you sure you want to permanently delete this user? This action cannot be undone.')) {
                return;
            }

            try {
                
                const response = await fetch(`/api/users/${userId}`, {
                    method: 'DELETE'
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    loadUsers();
                }
            } catch (error) {
                alert('Network error while deleting user.');
            }
        } 
        // Handle status change button
        else if (e.target.classList.contains('btn-status')) {
            const userId = e.target.dataset.userId;
            const newStatus = e.target.dataset.status;
            const actionText = newStatus === 'blocked' ? 'Block' : 'Activate';

            try {
                
                const response = await fetch('/api/users/status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: userId, status: newStatus })
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    loadUsers();
                }
            } catch (error) {
                alert('Network error while updating user status.');
            }
        }
        else if (targetRow) {
            // If the click is on the row itself (but not a button), show details
            // NOTE: This will fail until you create the /api/user-details/:id endpoint in app.py
            // showUserDetails(targetRow.dataset.userId); 
            console.log("User row clicked, showUserDetails is commented out until endpoint is built.");
        }
    });
}

async function loadBooks(showAdminTools = false) {
    showBookSkeleton();
    const userId = localStorage.getItem('userId');
    
    
    const url = new URL('/api/books', window.location.origin);
    if (userId) url.searchParams.append('userId', userId);

    try {
        const response = await fetch(url);
        const data = await response.json();
        if (data.success) {
            renderBooks(data.books, showAdminTools);
        } else {
            booksContainer.innerHTML = `<p class="error">${data.message}</p>`;
        }
    } catch (error) {
        booksContainer.innerHTML = '<p class="error">Network error while loading books.</p>';
    }
}

function renderBooks(books, showAdminTools) {
    if (!booksContainer) return; // Early return if container doesn't exist
    
    booksContainer.innerHTML = '';
    if (books.length === 0) {
        booksContainer.innerHTML = '<p class="empty-state">No books found in the library.</p>';
        return;
    }

    // Add search section
    const searchHtml = `
        <div class="search-section">
            <input type="text" id="searchBooks" placeholder="Search books by title, author, or category...">
            <button onclick="filterBooks()">Search</button>
        </div>
    `;

    const listHtml = books.map(book => `
        <div class="book-item ${book.display_status}">
            <div class="book-image">
                ${book.image_url ?
                    `<img src="${book.image_url}" alt="${book.title} cover">` :
                    `<div class="no-image"><i class="fas fa-book"></i></div>`
                }
            </div>
            <div class="book-info">
                <div class="book-title">${book.title}</div>
                <div class="book-author">By ${book.author}</div>
                <div class="book-details">
                    <span class="book-category">📚 ${book.category}</span>
                    ${showAdminTools ? `
                        <span class="book-copies">• 📚 ${book.copies_available || 0}/${book.total_copies || 1} copies available</span>
                    ` : ` 
                        <span class="book-status">• ${book.display_status === 'available' ? '🟢 Available' : (book.display_status === 'pending_issue' ? '🟡 Request Sent' : '🔴 Issued')}</span>
                    `}
                </div>
            </div>
            <div class="book-actions">
                ${showAdminTools ? ` 
                    <button onclick="toggleActions('${book.book_id}')" class="btn-more">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                    <div id="actions-${book.book_id}" class="actions-dropdown">
                        <button onclick="updateBookImage('${book.book_id}')" class="action-btn">
                            <i class="fas fa-image"></i> Update Image
                        </button>
                        <button onclick="editBook('${book.book_id}')" class="action-btn">
                            <i class="fas fa-edit"></i> Edit Details
                        </button>
                        <button onclick="updateCopies('${book.book_id}')" class="action-btn">
                            <i class="fas fa-copy"></i> Update Copies
                        </button>
                        <button onclick="deleteBook('${book.book_id}')" class="action-btn text-danger">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                ` : `
                    <button data-id="${book.book_id}" class="btn-order" ${book.display_status !== 'available' ? 'disabled' : ''} data-status="${book.display_status}">
                        ${book.display_status === 'available' ? '📖 Issue Now' : (book.display_status === 'pending_issue' ? 'Request Sent' : 'Currently Issued')}
                    </button>
                    ${book.book_pdf_url && book.book_pdf_url !== 'null' ? 
                            `<button class="open-pdf-btn" href="${book.book_pdf_url}">Read</button>` 
                            : 
                            `<button class="open-pdf-btn" disabled style="opacity: 0.5; cursor: not-allowed;">No PDF</button>`
                    }
                `} 
            </div>
        </div>
    `).join('');

    booksContainer.innerHTML = searchHtml + listHtml;

    window.filterBooks = function() {
        const searchTerm = document.getElementById('searchBooks').value.toLowerCase();
        const bookItems = document.querySelectorAll('.book-item');
        
        bookItems.forEach(item => {
            const title = item.querySelector('.book-title').textContent.toLowerCase();
            const author = item.querySelector('.book-author').textContent.toLowerCase();
            const category = item.querySelector('.book-category').textContent.toLowerCase();
            
            if (title.includes(searchTerm) || 
                author.includes(searchTerm) || 
                category.includes(searchTerm)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    };
}

function setupDeleteListeners() {
    if (!booksContainer) return;
    booksContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-delete')) {
            const bookId = e.target.dataset.id;
            if (!confirm(`Are you sure you want to delete book ID: ${bookId}?`)) {
                return;
            }

            try {
                
                const response = await fetch(`/api/books/${bookId}`, { method: 'DELETE' });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    loadBooks(true);
                }
            } catch (error) {
                alert('Network error while deleting book.');
            }
        }
    });
}

function setupReadListeners() {
    if (!booksContainer) return;

    booksContainer.addEventListener('click', (e) => {
        // Check if the clicked element is the Read button
        if (e.target.classList.contains('open-pdf-btn')) {
            // Get the URL from the href attribute
            const pdfUrl = e.target.getAttribute('href');

            // Check if the URL is valid (not null, not empty, not undefined)
            if (pdfUrl && pdfUrl !== 'null' && pdfUrl !== 'undefined') {
                // Open the PDF in a new tab
                window.open(pdfUrl, '_blank');
            } else {
                alert('Sorry, no PDF is available for this book.');
            }
        }
    });
}

function setupIssueListeners() {
    if (!booksContainer) return;
    booksContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-order')) {
            const bookId = e.target.dataset.id;
            const button = e.target;
            const userId = localStorage.getItem('userId');

            if (!userId) {
                alert('Please log in first!');
                return;
            }

            if (!confirm('Are you sure you want to request this book?')) {
                return;
            }

            try {
                
                const response = await fetch('/api/issue-book', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: userId, bookId: bookId })
                });

                const data = await response.json();
                alert(data.message);

                if (data.success) {
                    button.textContent = 'Request Sent';
                    button.disabled = true;
                    // Optionally reload books to reflect any status changes if the backend changes book status on request
                    if (typeof loadMyOrders === 'function') {
                        loadMyOrders();
                    }
                }
            } catch (error) {
                alert('Network error while issuing book.');
            }
        }
    });
}

function showReturnRequestSkeleton() {
    if (!returnRequestsList) return;
    const skeletonHTML = Array(3).fill(`
        <div class="card-skeleton">
            <div class="skeleton skeleton-line"></div>
            <div class="skeleton skeleton-line medium"></div>
        </div>`).join('');
    returnRequestsList.innerHTML = skeletonHTML;
}

async function loadReturnRequests() {
    if (!returnRequestsList) return;
    try {
        
        const response = await fetch('/api/return-requests');
        const data = await response.json();
        if (data.success) {
            renderReturnRequests(data.requests);
        } else {
            returnRequestsList.innerHTML = `<p class="error">${data.message}</p>`;
        }
    } catch (error) {
        returnRequestsList.innerHTML = '<p class="error">Network error while loading return requests.</p>';
    }
}

window.loadReturnRequests = loadReturnRequests;

function renderReturnRequests(requests) {
    if (requests.length === 0) {
        returnRequestsList.innerHTML = '<p>No pending return requests.</p>';
        return;
    }

    const tableHtml = `
        <table>
            <thead>
                <tr>
                    <th>Book ID</th>
                    <th>Title</th>
                    <th>Author</th>
                    <th>User</th>
                    <th>Issue Date</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${requests.map(request => `
                    <tr class="request-row">
                        <td>${request.book_id}</td>
                        <td>${request.title}</td>
                        <td>${request.author}</td>
                        <td>${request.username}</td>
                        <td>${new Date(request.issue_date).toLocaleDateString()}</td>
                        <td class="request-actions">
                            <button 
                                data-issue-id="${request.issue_id}" 
                                data-book-id="${request.book_id}" 
                                data-action="accept" 
                                class="btn-handle btn-accept">
                                Accept
                            </button>
                            <button 
                                data-issue-id="${request.issue_id}" 
                                data-book-id="${request.book_id}" 
                                data-action="reject" 
                                class="btn-handle btn-reject">
                                Reject
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    returnRequestsList.innerHTML = tableHtml;
}

async function loadIssueRequests() {
    if (!issueRequestsList) return;
    try {
        const response = await fetch('/api/issue-requests');
        const data = await response.json();
        if (data.success) {
            renderIssueRequests(data.requests);
        } else {
            issueRequestsList.innerHTML = `<p class="error">${data.message}</p>`;
        }
    } catch (error) {
        issueRequestsList.innerHTML = '<p class="error">Network error while loading issue requests.</p>';
    }
}

function renderIssueRequests(requests) {
    if (!issueRequestsList) return;
    if (requests.length === 0) {
        issueRequestsList.innerHTML = '<p>No pending issue requests.</p>';
        return;
    }

    const tableHtml = `
        <table>
            <thead>
                <tr>
                    <th>Book ID</th>
                    <th>Title</th>
                    <th>Author</th>
                    <th>User</th>
                    <th>Request Date</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${requests.map(request => `
                    <tr class="request-row">
                        <td>${request.book_id}</td>
                        <td>${request.title}</td>
                        <td>${request.author}</td>
                        <td>${request.username}</td>
                        <td>${new Date(request.request_date).toLocaleDateString()}</td>
                        <td class="request-actions">
                            <button 
                                data-issue-id="${request.issue_id}" 
                                data-book-id="${request.book_id}" 
                                data-action="accept" 
                                class="btn-handle-issue btn-accept">
                                Accept
                            </button>
                            <button 
                                data-issue-id="${request.issue_id}" 
                                data-book-id="${request.book_id}" 
                                data-action="reject" 
                                class="btn-handle-issue btn-reject">
                                Reject
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    issueRequestsList.innerHTML = tableHtml;
}

function setupIssueRequestListeners() {
    if (!issueRequestsList) return;
    issueRequestsList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-handle-issue')) {
            const issueId = e.target.dataset.issueId;
            const bookId = e.target.dataset.bookId; // Get bookId from the button
            const action = e.target.dataset.action;

            try {
                const response = await fetch('/api/handle-request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ issueId, bookId, action }) // Add bookId to the request body
                });
                const data = await response.json();
                alert(data.message);
                if (data.success) {
                    loadIssueRequests();
                    loadBooks(true);
                    loadUsers();
                }
            } catch (error) {
                alert('Network error while handling issue request.');
            }
        }
    });
}

function setupReturnRequestListeners() {
    if (!returnRequestsList) return;
    returnRequestsList.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-handle')) {
            const issueId = e.target.dataset.issueId;
            const bookId = e.target.dataset.bookId;
            const action = e.target.dataset.action;
            const actionText = action === 'accept' ? 'Accept' : 'Reject';

            if (!confirm(`Are you sure you want to ${actionText} this request?`)) {
                return;
            }

            try {
                const response = await fetch('/api/handle-return', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ issueId, bookId, action })
                });

                const data = await response.json();
                alert(data.message);

                if (data.success) {
                    loadReturnRequests();
                    if (action === 'accept') {
                        loadBooks(true);
                    }
                }
            } catch (error) {
                alert('Network error while handling return request.');
            }
        }
    });
}

// Image preview functionality
if (document.getElementById('bookImage')) {
    document.getElementById('bookImage').addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const preview = document.getElementById('imagePreview');
                preview.querySelector('img').src = e.target.result;
                preview.querySelector('img').style.display = 'block';
                preview.querySelector('.placeholder-icon').style.display = 'none';
            }
            reader.readAsDataURL(file);
        }
    });
}

// Toggle actions dropdown
window.toggleActions = function(bookId) {
    const dropdown = document.getElementById(`actions-${bookId}`);
    const allDropdowns = document.querySelectorAll('.actions-dropdown');
    allDropdowns.forEach(d => {
        if (d.id !== `actions-${bookId}`) {
            d.classList.remove('show');
        }
    });
    dropdown.classList.toggle('show');
};

// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.book-actions')) {
        document.querySelectorAll('.actions-dropdown').forEach(d => {
            d.classList.remove('show');
        });
    }
});

// Book action functions
window.updateBookImage = async function(bookId) {
    // 1. Prompt the user for the new Image URL
    const newImageUrl = prompt("Enter the new Image URL:");

    if (newImageUrl === null || newImageUrl.trim() === "") {
        return;
    }

    try {
    
        const response = await fetch(`/api/books/${bookId}`, {
            method: 'PUT',
            headers: { 
                'Content-Type': 'application/json' 
            },
            body: JSON.stringify({ 
                image_url: newImageUrl 
            })
        });

        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            loadBooks(true); 
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error while updating book image.');
    }
};

window.editBook = async function(bookId) {
    const bookItem = document.querySelector(`.book-item [onclick="toggleActions('${bookId}')"]`).closest('.book-item');
    const currentTitle = bookItem.querySelector('.book-title').textContent;
    const currentAuthor = bookItem.querySelector('.book-author').textContent.replace('By ', '');
    const currentCategory = bookItem.querySelector('.book-category').textContent.replace('📚 ', '');
    const currentPdf = bookItem.querySelector('.open-pdf-btn') ? bookItem.querySelector('.open-pdf-btn').getAttribute('href') : '';

    const newTitle = prompt('Enter new title:', currentTitle);
    const newAuthor = prompt('Enter new author:', currentAuthor);
    const newCategory = prompt('Enter new category:', currentCategory);
    const newPdfUrl = prompt('Enter PDF URL:', currentPdf === 'null' ? '' : currentPdf);

    if (newTitle === null || newAuthor === null || newCategory === null) {
        return; // User cancelled
    }

    try {
        const response = await fetch(`/api/books/${bookId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: newTitle,
                author: newAuthor,
                category: newCategory,
                book_pdf_url: newPdfUrl
            })
        });
        const data = await response.json();
        alert(data.message);
        if (data.success) {
            loadBooks(true); // Refresh the book list
        }
    } catch (error) {
        alert('Error updating book details.');
    }
};

window.updateCopies = async function(bookId) {
    const bookItem = document.querySelector(`.book-item [onclick="toggleActions('${bookId}')"]`).closest('.book-item');
    const copiesText = bookItem.querySelector('.book-copies').textContent;
    const currentCopies = copiesText.split('/')[1].trim().split(' ')[0];

    const newCopies = prompt('Enter the new total number of copies:', currentCopies);

    if (newCopies === null || isNaN(newCopies) || parseInt(newCopies) < 0) {
        if (newCopies !== null) alert('Please enter a valid number.');
        return;
    }

    try {
        const response = await fetch('/api/books/update-copies', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bookId: bookId, copies: parseInt(newCopies) })
        });
        const data = await response.json();
        alert(data.message);
        if (data.success) loadBooks(true);
    } catch (error) {
        alert('Error updating book copies.');
    }
};

window.deleteBook = async function(bookId) {
    if (confirm('Are you sure you want to delete this book?')) {
        try {
            const response = await fetch(`/api/books/${bookId}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            if (data.success) {
                loadBooks(true);
            }
            alert(data.message);
        } catch (error) {
            alert('Error deleting book');
        }
    }
};

if (addBookForm) {
    addBookForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // 1. Get the Image Link
        const imageLink = document.getElementById('newImageLink').value; 
        
        // 2. GET THE PDF LINK (This was missing)
        const pdfLink = document.getElementById('bookpdflink').value;

        const bookData = {
            title: document.getElementById('newTitle').value,
            author: document.getElementById('newAuthor').value,
            category: document.getElementById('newCategory').value,
            copies: document.getElementById('newCopies').value,
            image_url: imageLink,
            book_pdf_url: document.getElementById('newPdfUrl') ? document.getElementById('newPdfUrl').value : "" 
        };

        try {
            const response = await fetch('/api/books', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify(bookData)
            });

            const data = await response.json();
            if (data.success) {
                alert('Book added successfully!');
                
                // Reset form
                addBookForm.reset();
                
                // Hide previews
                const previewImg = document.getElementById('urlPreviewImg');
                if (previewImg) previewImg.style.display = 'none';

                if (typeof loadBooks === 'function') {
                    loadBooks(true);
                }
            } else {
                alert(data.message);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('An error occurred while adding the book.');
        }
    });
}

if (returnRequestsList) {
    loadReturnRequests();
    setupReturnRequestListeners();
}

if (issueRequestsList) {
    loadIssueRequests();
    setupIssueRequestListeners();
}

if (usersList) {
    loadUsers();
    setupUserStatusListeners();
}

window.loadBooks = loadBooks;

setupDeleteListeners();
setupIssueListeners();
setupReadListeners();
