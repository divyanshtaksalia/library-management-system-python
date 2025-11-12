function checkAuth(requiredRole) {
    const userRole = localStorage.getItem('userRole');
    
    if (!userRole) {
        window.location.href = 'login.html';
        return false;
    }
    
    if (requiredRole && userRole !== requiredRole) {
        alert("You do not have permission to access this page.");
        window.location.href = 'dashboard.html'; 
        return false;
    }
    return true; 
}

function logout() {
    localStorage.removeItem('userRole');
    localStorage.removeItem('userId');
    localStorage.removeItem('username');
    localStorage.removeItem('profilePictureUrl');
    window.location.href = 'login.html';
}

function setupProfilePictureUpload() {
    const uploadBtn = document.getElementById('uploadProfilePicBtn');
    if (!uploadBtn) return;

    uploadBtn.addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async (e) => {
            const file = e.target.files[0];
            if (file) {
                const userId = localStorage.getItem('userId');
                if (!userId) {
                    alert('Could not find user ID. Please log in again.');
                    return;
                }

                const formData = new FormData();
                formData.append('image', file);
                formData.append('userId', userId);

                try {
                    const response = await fetch('http://127.0.0.1:5001/api/user/update-profile-picture', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    alert(data.message);
                } catch (error) {
                    alert('Network error while uploading profile picture.');
                }
            }
        };
        input.click();
    });
}

window.checkAuth = checkAuth;
window.logout = logout;