// Add change event to all inputs, selects
document.querySelectorAll('#config-forms-container input').forEach((element) => {
    // TODO is this working?
    element.addEventListener('change', () => {
        element.classList.add('changed');
        // Find the associated hidden input, for checkbox changes
        const hiddenInput = element.nextElementSibling;
        if (hiddenInput && hiddenInput.type === 'hidden') {
            hiddenInput.classList.add('changed');
        }
    })
});

// Handle form submission
// TODO can we simplify this with document.querySelectorAll('#config-forms-container')?
document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', (e) => {
        // Disable all inputs that don't have the 'changed' class
        // TODO can we simplify this with e.target.querySelectorAll('input:...')
        document.querySelectorAll('#config-forms-container input:not(.changed)').forEach((element) => {
            // TODO is this check even necessary? if yes, why?
            if (element.id != "plugin-name") {
                element.disabled = true;
            }
        });
    });
});
