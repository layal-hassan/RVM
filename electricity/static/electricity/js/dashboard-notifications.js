(function () {
        const revealRecord = () => {
            if (!/^#record-\d+$/.test(window.location.hash)) return;
            const row = document.getElementById(window.location.hash.slice(1));
            if (row) row.scrollIntoView({ block: "center" });
        };
        revealRecord();
        window.addEventListener("load", revealRecord, { once: true });
        window.addEventListener("hashchange", revealRecord);
        const readStorage = (key) => { try { return localStorage.getItem(key); } catch { return null; } };
        const writeStorage = (key, value) => { try { localStorage.setItem(key, value); } catch {} };
        const enableBtn = document.getElementById("enable-notifications");
        const badge = document.getElementById("dash-unread-badge");
        const unreadText = document.getElementById("dash-unread-text");
        const unreadView = document.getElementById("dash-unread-view");
        const bellBtn = document.getElementById("dash-bell-btn");
        const panel = document.getElementById("dash-notify-panel");
        const storageKey = "adminNotificationsLastId";
        const desktopKey = "adminDashboardDesktopAlerts";
        const desktopStatus = document.getElementById("dash-desktop-status");
        const desktopToggle = document.getElementById("dash-desktop-toggle");
        const editableSections = document.querySelectorAll("[data-editable]");

        function updateBanner(count) {
            if (!badge || !unreadText) return;
            badge.textContent = count;
            unreadText.textContent = count;
            if (unreadView) unreadView.textContent = count;
            badge.classList.toggle("is-active", count > 0);
        }

        function requestPermission() {
            if (!("Notification" in window)) return;
            Notification.requestPermission().then(() => {});
        }

        if (enableBtn) {
            enableBtn.addEventListener("click", requestPermission);
        }

        function updateDesktopStatus(value) {
            if (!desktopStatus) return;
            desktopStatus.textContent = value ? "Enabled" : "Disabled";
        }

        if (desktopToggle) {
            const stored = readStorage(desktopKey) === "true";
            desktopToggle.checked = stored;
            updateDesktopStatus(stored);
        }

        editableSections.forEach((section) => {
            const toggleBtn = section.querySelector(".dash-edit-toggle");
            const cancelBtn = section.querySelector("[data-edit-cancel]");
            const saveBtn = section.querySelector("[data-edit-save]");

            if (toggleBtn) {
                toggleBtn.addEventListener("click", () => {
                    section.classList.add("is-editing");
                });
            }

            if (cancelBtn) {
                cancelBtn.addEventListener("click", () => {
                    section.classList.remove("is-editing");
                    if (desktopToggle) {
                        const stored = readStorage(desktopKey) === "true";
                        desktopToggle.checked = stored;
                        updateDesktopStatus(stored);
                    }
                });
            }

            if (saveBtn) {
                saveBtn.addEventListener("click", () => {
                    if (desktopToggle) {
                        writeStorage(desktopKey, desktopToggle.checked ? "true" : "false");
                        updateDesktopStatus(desktopToggle.checked);
                    }
                    section.classList.remove("is-editing");
                });
            }
        });

        if (bellBtn && panel) {
            bellBtn.addEventListener("click", () => {
                const isOpen = panel.classList.toggle("is-open");
                bellBtn.setAttribute("aria-expanded", isOpen ? "true" : "false");
            });

            document.addEventListener("click", (event) => {
                if (!panel.classList.contains("is-open")) return;
                const target = event.target;
                if (bellBtn.contains(target) || panel.contains(target)) return;
                panel.classList.remove("is-open");
                bellBtn.setAttribute("aria-expanded", "false");
            });
        }

        if (panel) {
            panel.addEventListener("click", (event) => {
                const item = event.target.closest("a.dash-notify-item");
                if (!item || !item.classList.contains("is-unread")) return;
                const csrfInput = panel.querySelector('input[name="csrfmiddlewaretoken"]');
                fetch(panel.dataset.markReadUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    keepalive: true,
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "X-CSRFToken": csrfInput ? csrfInput.value : "",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: new URLSearchParams({ notification_id: item.dataset.id }),
                }).then(async (response) => {
                    if (!response.ok) return;
                    const data = await response.json();
                    item.classList.replace("is-unread", "is-read");
                    updateBanner(data.unread_count || 0);
                }).catch(() => {});
            });
        }

        function renderNotifications(items) {
            const list = panel.querySelector(".dash-notify-list");
            const signature = JSON.stringify(items);
            if (list.dataset.signature === signature) return;
            list.dataset.signature = signature;
            const scrollTop = list.scrollTop;
            const focusedId = list.contains(document.activeElement) ? document.activeElement.dataset.id : null;
            const links = items.map((item) => {
                const link = document.createElement("a");
                link.className = "dash-notify-item " + (item.is_read ? "is-read" : "is-unread");
                link.href = item.url;
                link.dataset.id = item.id;
                const time = document.createElement("div");
                time.className = "dash-notify-time";
                time.textContent = new Date(item.created_at).toLocaleString();
                const message = document.createElement("div");
                message.className = "dash-notify-msg";
                message.textContent = item.message;
                link.append(time, message);
                return link;
            });
            list.replaceChildren(...links);
            if (!links.length) {
                const empty = document.createElement("div");
                empty.className = "dash-notify-empty";
                empty.textContent = "No notifications yet.";
                list.append(empty);
            }
            if (focusedId) links.find(link => link.dataset.id === focusedId)?.focus({ preventScroll: true });
            list.scrollTop = scrollTop;
        }

        async function poll() {
            try {
                const res = await fetch(panel.dataset.feedUrl, { credentials: "same-origin" });
                if (!res.ok) return;
                const data = await res.json();
                updateBanner(data.unread_count || 0);
                renderNotifications(data.items || []);

                const lastId = Number(readStorage(storageKey) || 0);
                const newest = data.items && data.items.length ? data.items[0] : null;
                if (newest && newest.id > lastId) {
                    writeStorage(storageKey, String(newest.id));
                    if ("Notification" in window && Notification.permission === "granted") {
                        new Notification("Admin Alert", { body: newest.message });
                    }
                }
            } catch (e) {}
        }

        if (panel) {
            poll();
            setInterval(poll, 10000);
        }
    })();
