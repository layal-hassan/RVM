(() => {
    const storageKey = "electricity_previous_page";
    const current = new URL(window.location.href);
    // Keep navigation inside this site and avoid returning to the same form
    // after a validation error, reload, or successful POST.
    const previousURL = (value) => {
        if (!value) return null;
        try {
            const url = new URL(value, current.origin);
            if (url.origin !== current.origin || url.pathname === current.pathname) return null;
            return url.pathname + url.search + url.hash;
        } catch {
            return null;
        }
    };
    let saved = {};
    try {
        saved = JSON.parse(sessionStorage.getItem(storageKey) || "{}") || {};
    } catch {
        // Referrer navigation still works when tab storage is unavailable.
    }
    const previous = previousURL(document.referrer)
        || previousURL(saved.current)
        || previousURL(saved.previous);
    const remember = () => {
        try {
            sessionStorage.setItem(storageKey, JSON.stringify({
                current: current.pathname + current.search + current.hash,
                previous,
            }));
        } catch {
            // Leave the ordinary fallback links usable without storage.
        }
    };
    const updateLinks = () => {
        if (!previous) return;
        document.querySelectorAll("a[data-site-back]").forEach((link) => {
            link.setAttribute("href", previous);
        });
    };
    remember();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", updateLinks);
    } else {
        updateLinks();
    }
    window.addEventListener("pageshow", () => {
        remember();
        updateLinks();
    });
})();
