// Notification System for TranscribeFlow
// Replaces browser alerts with styled in-website notifications

class NotificationManager {
    constructor() {
        this.container = null;
        this.init();
    }

    init() {
        // Create notification container if it doesn't exist
        if (!document.getElementById('notification-container')) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'fixed top-20 right-6 z-[100] space-y-3 max-w-md';
            document.body.appendChild(this.container);
        } else {
            this.container = document.getElementById('notification-container');
        }
    }

    show(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `notification-toast glass-panel p-4 rounded-xl border flex items-start gap-3 shadow-lg transform translate-x-full transition-transform duration-300`;

        // Set colors based on type
        let icon, borderColor, iconColor;
        switch (type) {
            case 'success':
                icon = 'check_circle';
                borderColor = 'border-[#00ffc3]/50';
                iconColor = 'text-[#00ffc3]';
                break;
            case 'error':
                icon = 'error';
                borderColor = 'border-red-400/50';
                iconColor = 'text-red-400';
                break;
            case 'warning':
                icon = 'warning';
                borderColor = 'border-yellow-400/50';
                iconColor = 'text-yellow-400';
                break;
            case 'info':
            default:
                icon = 'info';
                borderColor = 'border-[#00f2ff]/50';
                iconColor = 'text-[#00f2ff]';
                break;
        }

        notification.classList.add(borderColor);

        notification.innerHTML = `
            <span class="material-symbols-outlined ${iconColor} text-2xl">${icon}</span>
            <div class="flex-1">
                <p class="text-white text-sm font-medium">${message}</p>
            </div>
            <button class="notification-close text-slate-400 hover:text-white transition-colors">
                <span class="material-symbols-outlined text-sm">close</span>
            </button>
        `;

        // Add to container
        this.container.appendChild(notification);

        // Animate in
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
            notification.classList.add('translate-x-0');
        }, 10);

        // Close button handler
        const closeBtn = notification.querySelector('.notification-close');
        closeBtn.addEventListener('click', () => {
            this.remove(notification);
        });

        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.remove(notification);
            }, duration);
        }

        return notification;
    }

    remove(notification) {
        notification.classList.remove('translate-x-0');
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }

    success(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }

    error(message, duration = 4000) {
        return this.show(message, 'error', duration);
    }

    warning(message, duration = 3500) {
        return this.show(message, 'warning', duration);
    }

    info(message, duration = 3000) {
        return this.show(message, 'info', duration);
    }

    confirm(message, onConfirm, onCancel) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 z-[200] flex items-center justify-center bg-black/70 backdrop-blur-sm';
        modal.innerHTML = `
            <div class="glass-panel p-8 rounded-3xl border border-white/20 max-w-md mx-4 transform scale-95 transition-transform duration-200">
                <div class="flex items-start gap-4 mb-6">
                    <span class="material-symbols-outlined text-yellow-400 text-3xl">help</span>
                    <div>
                        <h3 class="text-xl font-black text-white mb-2">Confirm Action</h3>
                        <p class="text-slate-300 text-sm">${message}</p>
                    </div>
                </div>
                <div class="flex gap-3 justify-end">
                    <button class="confirm-cancel px-6 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-bold uppercase text-xs tracking-widest hover:bg-white/10 transition-colors">
                        Cancel
                    </button>
                    <button class="confirm-ok px-6 py-3 rounded-xl bg-gradient-to-r from-[#00f2ff] to-[#00ffc3] text-black font-bold uppercase text-xs tracking-widest hover:scale-105 transition-transform">
                        Confirm
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Animate in
        setTimeout(() => {
            modal.querySelector('.glass-panel').classList.remove('scale-95');
            modal.querySelector('.glass-panel').classList.add('scale-100');
        }, 10);

        const close = () => {
            modal.querySelector('.glass-panel').classList.remove('scale-100');
            modal.querySelector('.glass-panel').classList.add('scale-95');
            setTimeout(() => {
                if (modal.parentNode) {
                    modal.parentNode.removeChild(modal);
                }
            }, 200);
        };

        modal.querySelector('.confirm-ok').addEventListener('click', () => {
            close();
            if (onConfirm) onConfirm();
        });

        modal.querySelector('.confirm-cancel').addEventListener('click', () => {
            close();
            if (onCancel) onCancel();
        });

        // Click outside to cancel
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                close();
                if (onCancel) onCancel();
            }
        });
    }
}

// Create global instance
window.notify = new NotificationManager();
