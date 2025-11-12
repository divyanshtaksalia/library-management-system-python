document.getElementById('registerForm').addEventListener('submit', async (e) => {
    e.preventDefault(); 

    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const messageElement = document.getElementById('message');

    
    messageElement.style.display = 'none';
    messageElement.className = 'message';
    messageElement.textContent = '';

    try {
        const response = await fetch('http://127.0.0.1:5001/api/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();

        if (data.success) {
           
            messageElement.classList.add('success');
            messageElement.textContent = data.message;
            
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
            
        } else {
            
            messageElement.classList.add('error');
            messageElement.textContent = data.message;
        }

    } catch (error) {
        console.error('Registration failed:', error);
        messageElement.classList.add('error');
        messageElement.textContent = 'Network error: Unable to connect to the server.';
    }
});