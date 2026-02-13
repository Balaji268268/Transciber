// Clerk Authentication Helper Functions

const CLERK_PUBLISHABLE_KEY = "pk_test_dXNlZnVsLWNoZWV0YWgtMzguY2xlcmsuYWNjb3VudHMuZGV2JA";

// Check if user is authenticated
async function isAuthenticated() {
    if (!window.Clerk) {
        console.error("Clerk not loaded");
        return false;
    }

    await window.Clerk.load();
    return window.Clerk.user !== null;
}

// Redirect to login if not authenticated
async function requireAuth() {
    const authed = await isAuthenticated();
    if (!authed) {
        window.location.href = '/';
    }
}

// Sign out user
async function signOut() {
    if (window.Clerk) {
        await window.Clerk.signOut();
        window.location.href = '/';
    }
}

// Get session token for backend requests
async function getSessionToken() {
    if (!window.Clerk || !window.Clerk.session) {
        return null;
    }
    return await window.Clerk.session.getToken();
}

// Get user info
function getCurrentUser() {
    if (!window.Clerk || !window.Clerk.user) {
        return null;
    }
    return window.Clerk.user;
}
