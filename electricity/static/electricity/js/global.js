document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select").forEach(function (el) {
        if (!el.classList.contains("ts-initialized") && !el.classList.contains("no-tom-select")) {
            const isSearchable = el.classList.contains("searchable-select");
            new TomSelect(el, {
                dropdownParent: "body",
                allowEmptyOption: true,
                create: false,
                searchField: isSearchable ? ["text"] : [],
                controlInput: isSearchable
                    ? '<input type="search" autocomplete="off" placeholder="Search customer...">'
                    : null
            });

            el.classList.add("ts-initialized");
        }
    });
});
