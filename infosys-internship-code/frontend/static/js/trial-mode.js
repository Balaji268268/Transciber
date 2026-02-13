// Free Trial Mode Handler
// This file manages the free trial upload limit functionality

class TrialModeManager {
    constructor() {
        this.MAX_TRIALS = 2;
        this.isLoggedIn = false;
        this.trialCount = 0;
    }

    async initialize() {
        // Check if user is logged in via Clerk
        try {
            const clerkPubKey = "pk_test_Y29vcC1naWxsLTQ0LmNsZXJrLmFjY291bnRzLmRldiQ";
            await Clerk.load({ publishableKey: clerkPubKey });

            if (Clerk.user) {
                this.isLoggedIn = true;
                this.showLoggedInUI();
            } else {
                this.isLoggedIn = false;
                this.loadTrialCount();
                this.showTrialUI();
            }
        } catch (error) {
            console.error('Clerk initialization error:', error);
            // Default to trial mode on error
            this.isLoggedIn = false;
            this.loadTrialCount();
            this.showTrialUI();
        }
    }

    loadTrialCount() {
        this.trialCount = parseInt(localStorage.getItem('trial_uploads') || '0');
    }

    saveTrialCount() {
        localStorage.setItem('trial_uploads', this.trialCount.toString());
    }

    getRemainingTrials() {
        return Math.max(0, this.MAX_TRIALS - this.trialCount);
    }

    canUpload() {
        if (this.isLoggedIn) return true;
        return this.trialCount < this.MAX_TRIALS;
    }

    incrementTrial() {
        if (!this.isLoggedIn) {
            this.trialCount++;
            this.saveTrialCount();
            this.updateTrialDisplay();
        }
    }

    showLoggedInUI() {
        // Hide trial counter if exists
        const trialCounter = document.getElementById('trial-counter');
        if (trialCounter) trialCounter.classList.add('hidden');

        // Show user profile if exists
        const userProfile = document.getElementById('user-profile');
        if (userProfile) userProfile.classList.remove('hidden');
    }

    showTrialUI() {
        const remaining = this.getRemainingTrials();

        // Update trial counter if exists
        const trialCounter = document.getElementById('trial-counter');
        if (trialCounter) {
            trialCounter.classList.remove('hidden');
            this.updateTrialDisplay();
        }

        // Hide user profile
        const userProfile = document.getElementById('user-profile');
        if (userProfile) userProfile.classList.add('hidden');

        // Show limit banner if no trials left
        if (remaining === 0) {
            this.showLimitBanner();
            this.disableUpload();
        }
    }

    updateTrialDisplay() {
        const remaining = this.getRemainingTrials();
        const remainingEl = document.getElementById('trial-remaining');
        if (remainingEl) {
            remainingEl.textContent = `${remaining}/${this.MAX_TRIALS}`;
            if (remaining === 0) {
                remainingEl.classList.add('text-red-400');
                remainingEl.classList.remove('text-[#00f2ff]');
            }
        }
    }

    showLimitBanner() {
        const banner = document.getElementById('trial-limit-banner');
        if (banner) banner.classList.remove('hidden');
    }

    disableUpload() {
        const fileInput = document.getElementById('fileInput');
        const uploadBtn = document.getElementById('uploadBtn');
        if (fileInput) fileInput.disabled = true;
        if (uploadBtn) {
            uploadBtn.disabled = true;
            uploadBtn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }

    getUploadMode() {
        return this.isLoggedIn ? 'authenticated' : 'trial';
    }
}

// Export singleton instance
window.trialManager = new TrialModeManager();
