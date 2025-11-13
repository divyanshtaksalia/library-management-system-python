const usersContainer = document.getElementById('usersList');

async function loadUsers() {
    try {
        const response = await fetch('/api/users');
        const data = await response.json();

        if (data.success) {
            renderUsers(data.users);
        } else {
            usersContainer.innerHTML = `<p class="error">${data.message}</p>`;
        }
    } catch (error) {
        usersContainer.innerHTML = '<p class="error">Network error: Unable to load users.</p>';
    }
}

function renderUsers(users) {
    usersContainer.innerHTML = '';

    if (users.length === 0) {
        usersContainer.innerHTML = '<p>No users found.</p>';
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
                    <tr>
                        <td>${user.user_id}</td>
                        <td>${user.username}</td>
                        <td>${user.email}</td>
                        <td class="status-${user.account_status}">
                            ${user.account_status === 'blocked' ? 'Blocked' : 'Active'}
                        </td>
                        <td>
                            <button data-id="${user.user_id}" 
                                data-status="${user.account_status === 'active' ? 'blocked' : 'active'}"
                                class="btn-toggle-status">
                                ${user.account_status === 'active' ? 'Block' : 'Unblock'}
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        <style>
            table { width: 100%; border-collapse: collapse; margin-top: 15px; }
            th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
            th { background-color: #f2f2f2; }
            .status-blocked { color: red; font-weight: bold; }
            .status-active { color: green; }
            .btn-toggle-status { padding: 5px 10px; cursor: pointer; }
        </style>
    `;

    usersContainer.innerHTML = tableHtml;
    setupStatusToggleListeners();
}

function setupStatusToggleListeners() {
    usersContainer.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-toggle-status')) {
            const userId = e.target.dataset.id;
            const newStatus = e.target.dataset.status;

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
                alert('Network error while updating status.');
            }
        }
    });
}