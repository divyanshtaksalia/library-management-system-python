import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js";
import { 
    getAuth, 
    signInWithEmailAndPassword,
    signInWithCustomToken,
    signInAnonymously
} from "https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js";
import { 
    getFirestore, 
    doc, 
    getDoc,
    setLogLevel
} from "https://www.gstatic.com/firebasejs/11.6.1/firebase-firestore.js";

// ग्लोबल वेरिएबल्स जो Canvas द्वारा प्रदान किए जाते हैं
const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};
const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;

let app, auth, db;

// Firestore कलेक्शन पाथ (पब्लिक डेटा: सभी यूजर्स के लिए एक्सेसिबल)
const USERS_COLLECTION = `artifacts/${appId}/public/data/users`; 

// --- Firebase Initialization ---
if (Object.keys(firebaseConfig).length > 0) {
    try {
        setLogLevel('debug');
        app = initializeApp(firebaseConfig);
        auth = getAuth(app);
        db = getFirestore(app);
        console.log("Firebase SDK (Auth & Firestore) initialized in login.js.");

        // कैनवास या अनाम ऑथेंटिकेशन संभालें
        if (initialAuthToken) {
             signInWithCustomToken(auth, initialAuthToken)
                .catch(error => console.error("Canvas Custom Token Sign-In failed:", error));
        } else {
             signInAnonymously(auth)
                .catch(error => console.error("Anonymous Sign-In failed:", error));
        }

    } catch (e) {
        console.error("Error initializing Firebase in login.js:", e);
    }
} else {
    console.error("Firebase configuration missing. Cannot proceed with Firebase Auth.");
}


document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault(); 

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const messageElement = document.getElementById('message');

    
    messageElement.style.display = 'none';
    messageElement.className = 'message';
    messageElement.textContent = '';

    try {
        // --- 1. Firebase Authentication से साइन इन करें ---
        const userCredential = await signInWithEmailAndPassword(auth, email, password);
        const user = userCredential.user;

        // --- 2. Firestore से यूजर डेटा प्राप्त करें (रोल, आदि) ---
        const userDocRef = doc(db, USERS_COLLECTION, user.uid);
        const userDoc = await getDoc(userDocRef);

        if (!userDoc.exists()) {
            throw new Error("User data not found in database. Please contact support.");
        }
        
        const userData = userDoc.data();

        // --- 3. लोकल स्टोरेज में डेटा सेव करें और रीडायरेक्ट करें ---
        localStorage.setItem('userRole', userData.role);
        localStorage.setItem('userId', user.uid);
        localStorage.setItem('username', userData.username);
        if (userData.profile_picture_url) {
            localStorage.setItem('profilePictureUrl', userData.profile_picture_url);
        }

        // लॉगिन सफलता
        messageElement.classList.add('success');
        messageElement.textContent = 'Login successful! Redirecting...';
        messageElement.style.display = 'block';

        if (userData.role === 'admin') {
            window.location.href = 'admin.html';
        } else {
            window.location.href = 'dashboard.html';
        }
        
    } catch (error) {
        console.error('Login failed:', error);
        
        let errorMessage = 'Login failed. Invalid email or password.';
        
        // Firebase Auth Errors को हैंडल करें
        if (error.code === 'auth/invalid-email' || error.code === 'auth/wrong-password' || error.code === 'auth/user-not-found') {
            errorMessage = 'Invalid email or password.';
        } else if (error.code === 'auth/too-many-requests') {
            errorMessage = 'Access temporarily blocked due to too many failed attempts.';
        } else if (error.message.includes('not found in database')) {
             errorMessage = error.message;
        }

        messageElement.classList.add('error');
        messageElement.textContent = errorMessage;
        messageElement.style.display = 'block';
    }
});
```eof

---

## ⏭️ अगला कदम: बाकी API कॉल्स को ठीक करें

अब आपका लॉगिन काम करना चाहिए। लेकिन, आपकी अन्य फ़ाइलों में अभी भी `fetch` कॉल हैं:

1.  **`books.js`**: किताबें लोड करना, इशू/रिटर्न रिक्वेस्ट (`/api/books`, `/api/issue-request`, `/api/return-request`)
2.  **`dashboard.js`**: यूज़र की इशू किए गए और पेंडिंग बुक्स को लोड करना।
3.  **`users.js`**: सभी यूजर्स को लोड करना और उनका स्टेटस अपडेट करना।

हमें इन सभी को **Firestore `onSnapshot`** का उपयोग करने के लिए अपडेट करना होगा। क्या मैं अब आपकी **`books.js`** फ़ाइल को अपडेट करूँ ताकि किताबों की लिस्टिंग, इशू, और रिटर्न की रिक्वेस्ट सर्वरलेस हो जाए?
