(() => {
    const returningWithinFlow = () => {
        try {
            if (!document.referrer) return false;
            const current = new URL(window.location.href);
            const previous = new URL(document.referrer);
            const currentStep = current.pathname.match(/^(.*\/)step-(\d+)\/?$/);
            const previousStep = previous.pathname.match(/^(.*\/)step-(\d+)\/?$/);
            return current.origin === previous.origin && currentStep && previousStep
                && currentStep[1] === previousStep[1]
                && Number(previousStep[2]) > Number(currentStep[2]);
        } catch {
            return false;
        }
    };
    const initialise = () => document.querySelectorAll("[data-customer-popup]").forEach((root) => {
        if (root.dataset.popupInitialised) return;
        const dialog = root.querySelector("[data-contact-dialog]");
        if (!dialog || typeof dialog.showModal !== "function") return;
        root.dataset.popupInitialised = "true";
        const fieldset = root.querySelector("[data-contact-fieldset]");
        const summary = root.querySelector("[data-contact-summary]");
        const changeButton = summary.querySelector("[data-change-contact]");
        const choiceName = fieldset.dataset.choiceName;
        const selected = () => fieldset.querySelector(`input[name="${choiceName}"]:checked`);
        let returnFocus = null;
        let restoringFocus = false;
        const updateSummary = () => {
            const input = selected();
            if (!input) return;
            summary.querySelector("[data-contact-label]").textContent = input.closest("label").querySelector(".customer-type-title").textContent;
            summary.hidden = false;
            const start = root.querySelector("[data-customer-start]");
            if (start) start.hidden = true;
            if (choiceName === "customer_type") {
                document.querySelectorAll("[data-customer-private][data-customer-business]").forEach((label) => {
                    label.textContent = input.value === "business" ? label.dataset.customerBusiness : label.dataset.customerPrivate;
                });
            }
        };
        const openDialog = () => {
            if (dialog.open) return;
            returnFocus = document.activeElement;
            if (!dialog.open) dialog.showModal();
            (selected() || fieldset.querySelector("input")).focus();
        };
        const choose = () => {
            if (!selected() || !dialog.open) return;
            updateSummary();
            dialog.close();
            root.dispatchEvent(new CustomEvent("customer-type-selected", {bubbles: true, detail: {value: selected().value}}));
            const form = root.closest("form");
            if (root.hasAttribute("data-submit-on-private") && selected().value === "private") {
                // This only chooses the residential booking route; coverage
                // fields for the professional agreement are not submitted yet.
                form.noValidate = true;
                form.requestSubmit();
            } else if (root.hasAttribute("data-submit-on-choice")) form.requestSubmit();
        };
        changeButton.addEventListener("click", openDialog);
        root.addEventListener("customer-type-open", openDialog);
        const start = root.querySelector("[data-customer-start]");
        if (start) {
            start.hidden = Boolean(selected());
            start.addEventListener("click", openDialog);
        }
        if (root.hasAttribute("data-popup-on-focus")) {
            root.closest("form")?.addEventListener("focusin", () => {
                if (!selected() && !restoringFocus) openDialog();
            });
        }
        fieldset.addEventListener("change", (event) => {
            if (event.target.name === choiceName) choose();
        });
        fieldset.addEventListener("click", (event) => {
            // A label's initial click precedes its radio's default action.
            // Wait for the radio click so changing an existing choice uses
            // the newly selected value rather than the previous one.
            if (event.target.matches('input[type="radio"]') && event.target.checked) choose();
        });
        fieldset.addEventListener("invalid", openDialog, true);
        dialog.addEventListener("cancel", (event) => {
            if (!selected() && !root.hasAttribute("data-popup-manual")) event.preventDefault();
        });
        dialog.querySelector("[data-popup-dismiss]")?.addEventListener("click", () => dialog.close());
        dialog.addEventListener("close", () => {
            updateSummary();
            if (selected() && !root.hasAttribute("data-submit-on-choice")) changeButton.focus();
            else {
                restoringFocus = true;
                returnFocus?.focus();
                restoringFocus = false;
            }
        });
        root.closest("form")?.addEventListener("reset", () => {
            summary.hidden = true;
            if (start) start.hidden = false;
        });
        if (selected()) updateSummary();
        // Ask on a new booking entry, but keep the existing choice when
        // returning from a later step or after the entry popup just submitted.
        const justConfirmed = selected() && (root.hasAttribute("data-popup-confirmed") || returningWithinFlow());
        if (!root.hasAttribute("data-popup-manual") && !justConfirmed) openDialog();
    });
    // Each popup renders its fields inside the closed dialog and loads this
    // script immediately afterwards. Initialise now, without waiting for
    // unrelated scripts and assets to finish loading.
    initialise();
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initialise);
})();
