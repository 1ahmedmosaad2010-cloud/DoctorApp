// Firebase Cloud Messaging Service Worker
// File: accounts/firebase-messaging-sw.js

importScripts(
    "https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"
);

importScripts(
    "https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js"
);


// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyD3SZ1Y5yIjPm4udN_sUJNRkEENpPJyGwQ",
    authDomain: "my-doctor-1eb38.firebaseapp.com",
    projectId: "my-doctor-1eb38",
    storageBucket: "my-doctor-1eb38.firebasestorage.app",
    messagingSenderId: "510392843241",
    appId: "1:510392843241:web:fc70e07682089793a02978",
    measurementId: "G-EW3G0PL121"
};


// Initialize Firebase
firebase.initializeApp(firebaseConfig);

const messaging = firebase.messaging();

console.log(
    "Firebase Messaging Service Worker initialized successfully."
);


// Receive background notifications
messaging.onBackgroundMessage(function (payload) {

    console.log(
        "[firebase-messaging-sw.js] Background message received:",
        payload
    );

    const notificationTitle =
        payload.notification?.title || "MY DOCTOR";

    const notificationOptions = {

        body:
            payload.notification?.body ||
            "لديك إشعار جديد من MY DOCTOR",

        icon: "/static/images/icon-192.png",

        badge: "/static/images/icon-192.png",

        data: payload.data || {},

        tag: "my-doctor-notification",

        requireInteraction: false
    };


    return self.registration.showNotification(
        notificationTitle,
        notificationOptions
    );

});


// Handle notification click
self.addEventListener(
    "notificationclick",
    function (event) {

        event.notification.close();


        const targetUrl =
            event.notification?.data?.url ||
            "/accounts/dashboard/";


        event.waitUntil(

            clients.matchAll({

                type: "window",

                includeUncontrolled: true

            }).then(function (clientList) {


                for (const client of clientList) {

                    if ("focus" in client) {

                        if ("navigate" in client) {

                            client.navigate(targetUrl);

                        }

                        return client.focus();

                    }

                }


                if (clients.openWindow) {

                    return clients.openWindow(targetUrl);

                }

            })

        );

    }
);


// Service Worker installation
self.addEventListener(
    "install",
    function (event) {

        self.skipWaiting();

    }
);


// Service Worker activation
self.addEventListener(
    "activate",
    function (event) {

        event.waitUntil(
            self.clients.claim()
        );

    }
);


console.log(
    "MY DOCTOR Firebase Service Worker loaded successfully."
);