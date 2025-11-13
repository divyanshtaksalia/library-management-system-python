document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault(); 

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const messageElement = document.getElementById('message');

    
    messageElement.style.display = 'none';
    messageElement.className = 'message';
    messageElement.textContent = '';

    try {

        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (data.success) {
            messageElement.classList.add('success');
            messageElement.textContent = data.message;

            localStorage.setItem('userRole', data.user.role);
            localStorage.setItem('userId', data.user.id);
            localStorage.setItem('username', data.user.username);
            if (data.user.profile_picture_url) {
                localStorage.setItem('profilePictureUrl', data.user.profile_picture_url);
            }


            if (data.user.role === 'admin') {
                window.location.href = 'admin.html';
            } else {
                window.location.href = 'dashboard.html';
            }
        } else {
            messageElement.classList.add('error');
            messageElement.textContent = data.message;
        }

    } catch (error) {
        console.error('Login failed:', error);
        messageElement.classList.add('error');
        messageElement.textContent = 'Network error: Unable to connect to the server.';
    }
});