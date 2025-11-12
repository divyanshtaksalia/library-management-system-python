// Dropdown toggle functionality
function toggleDropdown(dropdownId) {
    const dropdown = document.getElementById(dropdownId);
    const allDropdowns = document.querySelectorAll('.dropdown-menu');

    // Close all dropdowns first
    allDropdowns.forEach(menu => {
        if (menu.id !== dropdownId) {
            menu.classList.remove('show');
        }
    });

    // Toggle the clicked dropdown
    dropdown.classList.toggle('show');
}

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.nav-item')) {
        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            menu.classList.remove('show');
        });
    }
});

// Section switching function
function switchSection(sectionId) {
    // Hide all sections
    const sections = document.querySelectorAll('.admin-section');
    sections.forEach(section => {
        section.style.display = 'none';
    });

    // Show the selected section
    const targetSection = document.getElementById(sectionId);
    if (targetSection) {
        targetSection.style.display = 'block';
    }

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });

    // Close all dropdowns
    document.querySelectorAll('.dropdown-menu').forEach(menu => {
        menu.classList.remove('show');
    });
}

// Placeholder functions for new dropdown actions
function focusSearch() {
    const searchInput = document.querySelector('#booksListSection input[type="text"]');
    if (searchInput) {
        searchInput.focus();
        switchSection('booksListSection');
    }
}

function showCategories() {
    alert('Categories feature coming soon!');
    switchSection('booksListSection');
}

async function showReturnBooks() {
    const userId = localStorage.getItem('userId');
    if (!userId) {
        alert('Please log in first!');
        return;
    }

    try {
        const response = await fetch(`http://127.0.0.1:5001/api/returned-books?userId=${userId}`);
        const data = await response.json();

        if (data.success) {
            renderReturnedBooks(data.returned_books);
            switchSection('returnedBooksSection');
        } else {
            alert('Error loading returned books: ' + data.message);
        }
    } catch (error) {
        alert('Network error while loading returned books.');
    }
}

function renderReturnedBooks(books) {
    const returnedBooksList = document.getElementById('returnedBooksList');
    if (!returnedBooksList) return;

    if (books.length === 0) {
        returnedBooksList.innerHTML = '<p>You have no returned books.</p>';
        return;
    }

    const tableHtml = `
        <table>
            <thead>
                <tr>
                    <th>Book Image</th>
                    <th>Title</th>
                    <th>Author</th>
                    <th>Issue Date</th>
                    <th>Return Date</th>
                </tr>
            </thead>
            <tbody>
                ${books.map(book => `
                    <tr>
                        <td>
                            ${book.image_url ? `<img src="${book.image_url}" alt="${book.title}" style="width: 50px; height: 70px; object-fit: cover;">` : '<div style="width: 50px; height: 70px; background: #f0f0f0; display: flex; align-items: center; justify-content: center;"><i class="fas fa-book"></i></div>'}
                        </td>
                        <td>${book.title}</td>
                        <td>${book.author}</td>
                        <td>${book.issue_date ? new Date(book.issue_date).toLocaleString() : 'N/A'}</td>
                        <td>${book.return_date ? new Date(book.return_date).toLocaleString() : 'N/A'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    returnedBooksList.innerHTML = tableHtml;
}

async function showCancelRequests() {
    const userId = localStorage.getItem('userId');
    if (!userId) {
        alert('Please log in first!');
        return;
    }

    try {
        const response = await fetch(`http://127.0.0.1:5001/api/my-orders?userId=${userId}`);
        const data = await response.json();

        if (data.success) {
            const pendingRequests = data.orders.filter(order => order.return_status === 'pending_issue');
            if (pendingRequests.length === 0) {
                alert('You have no pending requests to cancel.');
                return;
            }

            // Show cancel options for pending requests
            renderCancelRequests(pendingRequests);
            switchSection('issueRequestsSection');
        } else {
            alert('Error loading requests: ' + data.message);
        }
    } catch (error) {
        alert('Network error while loading requests.');
    }
}

function renderCancelRequests(requests) {
    const pendingList = document.getElementById('myPendingRequestsList');

    if (requests.length === 0) {
        pendingList.innerHTML = '<p>You have no pending book requests.</p>';
    } else {
        pendingList.innerHTML = requests.map(request => `
            <div class="book-item">
                <div class="book-info">
                    <div class="book-title">${request.title}</div>
                    <div class="book-author">By ${request.author}</div>
                    <div class="book-details">
                        <span class="book-status">Requested on: ${new Date(request.request_date).toLocaleDateString()}</span>
                    </div>
                </div>
                <div class="book-actions">
                    <button onclick="cancelRequest('${request.issue_id}')" class="btn-cancel">Cancel Request</button>
                </div>
            </div>
        `).join('');
    }
}

async function cancelRequest(issueId) {
    if (!confirm('Are you sure you want to cancel this request?')) {
        return;
    }

    try {
        const response = await fetch('http://127.0.0.1:5001/api/cancel-request', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issueId: issueId })
        });

        const data = await response.json();
        alert(data.message);

        if (data.success) {
            // Reload the requests section
            showCancelRequests();
            // Also reload books to update status
            loadBooks(false);
        }
    } catch (error) {
        alert('Network error while cancelling request.');
    }
}

async function returnBook(issueId) {
    if (!confirm('Are you sure you want to return this book?')) {
        return;
    }

    try {
        const response = await fetch('http://127.0.0.1:5001/api/return-book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ issueId: issueId })
        });

        const data = await response.json();
        alert(data.message);

        if (data.success) {
            // Reload the orders section
            loadMyOrders();
            // Also reload books to update status
            loadBooks(false);
        }
    } catch (error) {
        alert('Network error while returning book.');
    }
}

async function loadMyOrders() {
    const ordersList = document.getElementById('myOrdersList');
    const pendingList = document.getElementById('myPendingRequestsList');
    const userId = localStorage.getItem('userId');

    if (!ordersList || !pendingList || !userId) return;

    try {
        const response = await fetch(`http://127.0.0.1:5001/api/my-orders?userId=${userId}`);
        const data = await response.json();

        if (data.success) {
            renderMyOrders(data.orders);
        } else {
            ordersList.innerHTML = `<p class="error">${data.message}</p>`;
            pendingList.innerHTML = '';
        }
    } catch (error) {
        ordersList.innerHTML = '<p class="error">Network error while fetching your orders.</p>';
        pendingList.innerHTML = '';
    }
}

function renderMyOrders(orders) {
    const ordersList = document.getElementById('myOrdersList');
    const pendingList = document.getElementById('myPendingRequestsList');

    const issuedBooks = orders.filter(order => order.return_status === 'issued');
    const pendingBooks = orders.filter(order => order.return_status === 'pending_issue');

    // Always render issued books in myOrdersList with return button
    if (issuedBooks.length === 0) {
        ordersList.innerHTML = '<p>You have no issued books.</p>';
    } else {
        ordersList.innerHTML = issuedBooks.map(book => `
            <div class="book-item">
                <div class="book-image">
                    ${book.image_url ? `<img src="${book.image_url}" alt="${book.title}">` : `<div class="no-image"><i class="fas fa-book"></i></div>`}
                </div>
                <div class="book-info">
                    <div class="book-title">${book.title}</div>
                    <div class="book-author">By ${book.author}</div>
                    <div class="book-details">
                        <span class="book-status">Issued on: ${new Date(book.issue_date).toLocaleDateString()}</span>
                    </div>
                </div>
                <div class="book-actions">
                    <button onclick="returnBook('${book.issue_id}')" class="btn-return">Return Book</button>
                </div>
            </div>
        `).join('');
    }

    // Always render pending books in myIssueRequestsList
    if (pendingBooks.length === 0) {
        pendingList.innerHTML = '<p>You have no pending book requests.</p>';
    } else {
        pendingList.innerHTML = pendingBooks.map(book => `
            <div class="book-item">
                <div class="book-info">
                    <div class="book-title">${book.title}</div>
                    <div class="book-author">By ${book.author}</div>
                    <div class="book-details">
                        <span class="book-status">Requested on: ${new Date(book.request_date).toLocaleDateString()}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }
}
