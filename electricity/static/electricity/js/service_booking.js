(() => {
  const uploads = document.querySelector('input[type="file"][name="uploads"]');
  if (!uploads) return;
  uploads.addEventListener("change", () => {
    // placeholder for future enhancements
  });
})();

(() => {
  const billingRadios = document.querySelectorAll('input[name="billing_type"]');
  if (!billingRadios.length) return;

  const updateBillingVisibility = () => {
    const selected = document.querySelector('input[name="billing_type"]:checked');
    const value = selected ? selected.value : null;
    document.querySelectorAll('[data-billing]').forEach((el) => {
      el.classList.toggle('is-visible', value && el.dataset.billing === value);
    });
  };

  billingRadios.forEach((radio) => {
    radio.addEventListener('change', updateBillingVisibility);
  });

  updateBillingVisibility();
})();
