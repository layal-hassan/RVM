document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select").forEach(function (el) {
        if (!el.classList.contains("ts-initialized")) {
            new TomSelect(el, {
                dropdownParent: "body",
                allowEmptyOption: true,
                create: false,
                searchField: [],
                controlInput: null
            });

            el.classList.add("ts-initialized");
        }
    });
});
