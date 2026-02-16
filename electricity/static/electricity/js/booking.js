document.addEventListener("DOMContentLoaded", () => {
    const toggleActive = (selector) => {
        document.querySelectorAll(selector).forEach((label) => {
            const input = label.querySelector("input");
            if (!input) return;
            const update = () => {
                if (input.type === "radio") {
                    document.querySelectorAll(selector).forEach((item) => item.classList.remove("is-active"));
                }
                if (input.checked) {
                    label.classList.add("is-active");
                } else {
                    label.classList.remove("is-active");
                }
            };
            input.addEventListener("change", update);
            update();
        });
    };

    toggleActive(".option-card");
    toggleActive(".service-card");
    toggleActive(".time-card");
    toggleActive(".toggle-option");
    toggleActive(".day-pill");
    toggleActive(".urgent-option");

    document.querySelectorAll(".upload-card input").forEach((input) => {
        input.addEventListener("change", () => {
            const label = input.closest(".upload-card");
            if (!label) return;
            label.classList.toggle("is-active", input.files.length > 0);
        });
    });

    const otherField = document.querySelector("[data-other-field]");
    if (otherField) {
        const propertyInputs = document.querySelectorAll("input[name='property_type']");
        const updateOtherVisibility = () => {
            let isOther = false;
            propertyInputs.forEach((input) => {
                if (input.checked && input.value === "other") {
                    isOther = true;
                }
            });
            otherField.classList.toggle("is-visible", isOther);
        };
        propertyInputs.forEach((input) => input.addEventListener("change", updateOtherVisibility));
        updateOtherVisibility();
    }

    const privateBlock = document.querySelector("[data-private]");
    const businessBlock = document.querySelector("[data-business]");
    if (privateBlock || businessBlock) {
        const contactInputs = document.querySelectorAll("input[name='contact_type']");
        const updateContactVisibility = () => {
            let type = "private";
            contactInputs.forEach((input) => {
                if (input.checked) type = input.value;
            });
            if (privateBlock) privateBlock.classList.toggle("is-visible", type === "private");
            if (businessBlock) businessBlock.classList.toggle("is-visible", type === "business");
        };
        contactInputs.forEach((input) => input.addEventListener("change", updateContactVisibility));
        updateContactVisibility();
    }
});
