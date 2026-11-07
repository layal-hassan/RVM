(() => {
  const dialog = document.querySelector('.careers-confirmation');
  if (!dialog) return;

  dialog.querySelectorAll('[data-confirmation-close]').forEach(button => {
    button.addEventListener('click', () => dialog.close());
  });
  dialog.addEventListener('close', () => {
    document.documentElement.classList.remove('careers-confirmation-open');
    document.querySelector('.careers-form button[type="submit"]')?.focus({ preventScroll: true });
  });

  dialog.showModal();
  document.documentElement.classList.add('careers-confirmation-open');
})();
