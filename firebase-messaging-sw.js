importScripts(
    "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"
);

importScripts(
    "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js"
);

firebase.initializeApp({
    apiKey: "AIzaSyD3SZ1Y5yIjPm4udN_sUJNRKEEnPJyGwQ",
    authDomain: "my-doctor-1eb38.firebaseapp.com",
    projectId: "my-doctor-1eb38",
    storageBucket: "my-doctor-1eb38.firebasestorage.app",
    messagingSenderId: "510392843241",
    appId: "1:510392843241:web:fc70e07682089793a02978"
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
    const notificationTitle =
        payload.notification?.title || "MY DOCTOR";

    const notificationOptions = {
        body:
            payload.notification?.body ||
            "لديك إشعار جديد",
        icon: "/static/accounts/logo.png"
    };

    self.registration.showNotification(
        notificationTitle,
        notificationOptions
    );
});