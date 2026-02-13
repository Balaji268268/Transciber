// Append custom dropdown function to upload.js
function initializeCustomDropdown() {
    const dropdownBtn = document.getElementById('language-dropdown-btn');
    const dropdownMenu = document.getElementById('language-dropdown-menu');
    const languageSearch = document.getElementById('language-search');
    const languageOptions = document.querySelectorAll('.language-option');
    const selectedFlag = document.getElementById('selected-flag');
    const selectedLanguage = document.getElementById('selected-language');
    const hiddenInput = document.getElementById('target-language');

    if (!dropdownBtn) return;

    // Toggle dropdown
    dropdownBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownMenu.classList.toggle('hidden');
        if (!dropdownMenu.classList.contains('hidden')) {
            languageSearch.focus();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!dropdownBtn.contains(e.target) && !dropdownMenu.contains(e.target)) {
            dropdownMenu.classList.add('hidden');
        }
    });

    // Search functionality
    languageSearch.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        languageOptions.forEach(option => {
            const languageName = option.getAttribute('data-name').toLowerCase();
            if (languageName.includes(searchTerm)) {
                option.style.display = 'flex';
            } else {
                option.style.display = 'none';
            }
        });
    });

    // Language selection
    languageOptions.forEach(option => {
        option.addEventListener('click', () => {
            const value = option.getAttribute('data-value');
            const flag = option.getAttribute('data-flag');
            const name = option.getAttribute('data-name');

            // Update UI
            selectedFlag.textContent = flag;
            selectedLanguage.textContent = name;
            hiddenInput.value = value;

            // Update selected state
            languageOptions.forEach(opt => opt.classList.remove('selected'));
            option.classList.add('selected');

            // Close dropdown
            dropdownMenu.classList.add('hidden');
            languageSearch.value = '';
            languageOptions.forEach(opt => opt.style.display = 'flex');
        });
    });
}
