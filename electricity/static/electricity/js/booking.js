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
            label.addEventListener("click", (event) => {
                if (event.target.closest("input")) return;
                if (input.disabled) return;
                if (input.type === "radio" || input.type === "checkbox") {
                    input.checked = input.type === "radio" ? true : !input.checked;
                    input.dispatchEvent(new Event("change", { bubbles: true }));
                }
            });
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
        const uploadRemovals = uploadSummary.querySelector("[data-upload-removals]");
        const emptyText = uploadSummary.dataset.emptyText || "";

        const formatSize = (size) => {
            if (!size) return "";
            if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
            return `${Math.max(1, Math.round(size / 1024))} KB`;
        };

        const syncUploadSummaryState = () => {
            if (!uploadList) return;
            const hasItems = uploadList.querySelectorAll(".upload-summary-item").length > 0;
            uploadSummary.classList.toggle("has-files", hasItems);
            if (uploadEmpty) {
                uploadEmpty.hidden = hasItems;
                if (!hasItems) uploadEmpty.textContent = emptyText;
            }
        };

        const addRemovalInput = (value) => {
            if (!uploadRemovals || !value) return;
            if (uploadRemovals.querySelector(`[data-upload-removal="${value}"]`)) return;
            const hidden = document.createElement("input");
            hidden.type = "hidden";
            hidden.name = "remove_temp_uploads";
            hidden.value = value;
            hidden.setAttribute("data-upload-removal", value);
            uploadRemovals.appendChild(hidden);
        };

        const renderSelectedUploads = () => {
            if (!uploadList) return;
            uploadList.querySelectorAll("[data-temp-upload]").forEach((node) => node.remove());

            document.querySelectorAll("[data-upload-card] input").forEach((input) => {
                const card = input.closest("[data-upload-card]");
                if (!card || !input.files || !input.files.length) return;

                Array.from(input.files).forEach((file, index) => {
                    const row = document.createElement("div");
                    row.className = "upload-summary-item is-pending";
                    row.setAttribute("data-temp-upload", "true");
                    row.setAttribute("data-upload-field", input.name);
                    row.setAttribute("data-upload-index", String(index));
                    row.innerHTML = `
                        <span class="upload-summary-kind">${card.dataset.uploadLabel || ""}</span>
                        <span class="upload-summary-name">${file.name}</span>
                        <span class="upload-summary-size">${formatSize(file.size)}</span>
                        <button
                            type="button"
                            class="upload-summary-remove"
                            data-remove-pending
                            aria-label="Remove ${file.name}"
                        >x</button>
                    `;
                    uploadList.appendChild(row);
                });
            });

            syncUploadSummaryState();
        };

        const removePendingFile = (fieldName, removedIndex) => {
            const input = document.querySelector(`[data-upload-card] input[name="${fieldName}"]`);
            if (!input || !input.files) return;
            const files = Array.from(input.files);
            const transfer = new DataTransfer();
            files.forEach((file, index) => {
                if (index !== removedIndex) {
                    transfer.items.add(file);
                }
            });
            input.files = transfer.files;
            input.dispatchEvent(new Event("change", { bubbles: true }));
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

        if (uploadList) {
            uploadList.addEventListener("click", (event) => {
                const target = event.target.closest(".upload-summary-remove");
                if (!target) return;

                const existingValue = target.getAttribute("data-remove-existing");
                if (existingValue) {
                    addRemovalInput(existingValue);
                    target.closest(".upload-summary-item")?.remove();
                    syncUploadSummaryState();
                    return;
                }

                if (target.hasAttribute("data-remove-pending")) {
                    const row = target.closest("[data-temp-upload]");
                    if (!row) return;
                    const fieldName = row.getAttribute("data-upload-field") || "";
                    const fileIndex = Number(row.getAttribute("data-upload-index"));
                    if (!fieldName || Number.isNaN(fileIndex)) return;
                    removePendingFile(fieldName, fileIndex);
                }
            });
        }

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
        document.querySelectorAll("[data-contact-option]").forEach((option) => {
            option.addEventListener("click", (event) => {
                event.preventDefault();
                const value = option.getAttribute("data-contact-option");
                const input = document.querySelector(`input[name='contact_type'][value='${value}']`);
                if (!input) return;
                input.checked = true;
                input.dispatchEvent(new Event("change", { bubbles: true }));
            });
        });
        const updateContactVisibility = () => {
            let type = "private";
            contactInputs.forEach((input) => {
                if (input.checked) type = input.value;
            });
            document.querySelectorAll("[data-contact-option]").forEach((option) => {
                option.classList.toggle("is-active", option.getAttribute("data-contact-option") === type);
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
