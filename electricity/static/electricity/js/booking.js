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

    const uploadSummary = document.querySelector("[data-upload-summary]");
    if (uploadSummary) {
        const uploadList = uploadSummary.querySelector("[data-upload-list]");
        const uploadEmpty = uploadSummary.querySelector("[data-upload-empty]");
        const emptyText = uploadSummary.dataset.emptyText || "";

        const formatSize = (size) => {
            if (!size) return "";
            if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
            return `${Math.max(1, Math.round(size / 1024))} KB`;
        };

        const renderSelectedUploads = () => {
            if (!uploadList) return;
            const existingItems = Array.from(uploadList.querySelectorAll("[data-existing-upload]"));
            uploadList.querySelectorAll("[data-temp-upload]").forEach((node) => node.remove());

            document.querySelectorAll("[data-upload-card] input").forEach((input) => {
                const card = input.closest("[data-upload-card]");
                if (!card || !input.files || !input.files.length) return;

                Array.from(input.files).forEach((file) => {
                    const row = document.createElement("div");
                    row.className = "upload-summary-item is-pending";
                    row.setAttribute("data-temp-upload", "true");
                    row.innerHTML = `
                        <span class="upload-summary-kind">${card.dataset.uploadLabel || ""}</span>
                        <span class="upload-summary-name">${file.name}</span>
                        <span class="upload-summary-size">${formatSize(file.size)}</span>
                    `;
                    uploadList.appendChild(row);
                });
            });

            const hasItems =
                existingItems.length > 0 || uploadList.querySelectorAll("[data-temp-upload]").length > 0;
            uploadSummary.classList.toggle("has-files", hasItems);
            if (uploadEmpty) {
                uploadEmpty.hidden = hasItems;
                if (!hasItems) uploadEmpty.textContent = emptyText;
            }
        };

        document.querySelectorAll("[data-upload-card] input").forEach((input) => {
            const card = input.closest("[data-upload-card]");
            const updateState = () => {
                if (!card) return;
                const hasFile = input.files && input.files.length > 0;
                card.classList.toggle("is-active", hasFile);
            };
            input.addEventListener("change", () => {
                updateState();
                renderSelectedUploads();
            });
            updateState();
        });

        renderSelectedUploads();
    }

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

    const privateBlocks = document.querySelectorAll("[data-private]");
    const businessBlocks = document.querySelectorAll("[data-business]");
    if (privateBlocks.length || businessBlocks.length) {
        const contactInputs = document.querySelectorAll(
            "input[name='contact_type'], input[name='customer_type']"
        );
        const updateContactVisibility = () => {
            let type = "private";
            contactInputs.forEach((input) => {
                if (input.checked) type = input.value;
            });
            privateBlocks.forEach((block) => {
                block.classList.toggle("is-visible", type === "private");
                block.style.display = type === "private" ? "" : "none";
            });
            businessBlocks.forEach((block) => {
                block.classList.toggle("is-visible", type === "business");
                block.style.display = type === "business" ? "" : "none";
            });
            document.querySelectorAll("[data-contact-field]").forEach((field) => {
                const group = field.getAttribute("data-contact-field");
                field.disabled = group !== type;
            });
        };
        contactInputs.forEach((input) => input.addEventListener("change", updateContactVisibility));
        updateContactVisibility();
    }
});
