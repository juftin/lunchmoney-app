/** Client-side interactivity for the Lunch Money dashboard.
 *
 *  Uses Alpine.js for tab switching, keyboard shortcuts, category search,
 *  toast notifications, and Frappe Charts lifecycle.  HTMX handles period
 *  navigation and live polling; Alpine plugs into htmx:afterSettle to
 *  re-initialise charts after DOM swaps.
 */

(function () {
    "use strict";

    // ----------------------------------------------------------------
    //  Forward API key to every HTMX request
    // ----------------------------------------------------------------
    document.addEventListener("htmx:configRequest", (evt) => {
        const key = localStorage.getItem("lm_api_key");
        if (key) {
            evt.detail.headers["X-API-Key"] = key;
        }
    });



    document.addEventListener("alpine:init", () => {
        Alpine.store("toasts", {
            toasts: [],

            addToast(message, type) {
                const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
                this.toasts.push({ id, message, type, ttl: 5000 });
                setTimeout(() => this.dismissToast(id), 5000);
            },

            dismissToast(id) {
                this.toasts = this.toasts.filter((t) => t.id !== id);
            },
        });

        Alpine.data("dashboard", () => ({
            activeTab: localStorage.getItem("lm_active_tab") || "accounts",
            searchQuery: "",
            allExpanded: false,
            showApiKeyDialog: false,
            apiKeyInput: "",
            isSyncing: false,
            _categoryFilterObserver: null,

            triggerRefresh(evt) {
                if (this.isSyncing) {
                    if (evt) evt.preventDefault();
                    return;
                }
                this.isSyncing = true;
                setTimeout(() => {
                    this.isSyncing = false;
                }, 2000);
            },

        /** ----- lifecycle ----- */

        init() {
            const savedTab = localStorage.getItem("lm_active_tab");
            if (savedTab && ["accounts", "summary", "activity", "sync"].includes(savedTab)) {
                this.activeTab = savedTab;
            }

            this.initChart();
            this._formatLocalTimes();
            this._updateRelativeTimes();

            setInterval(() => {
                this._updateRelativeTimes();
            }, 15000);

            document.body.addEventListener("htmx:afterSettle", () => {
                this.isSyncing = false;
                this.initChart();
                this._formatLocalTimes();
                this._updateRelativeTimes();
                this._setupCategoryFilter();
                this._applySearchFilter();
            });

            document.body.addEventListener("htmx:responseError", (evt) => {
                this.isSyncing = false;
                const xhr = evt.detail.xhr;
                if (xhr && xhr.status === 401) {
                    this.showApiKeyDialog = true;
                    return;
                }
                const targetId = evt.detail.target?.id || "dashboard-content";
                Alpine.store("toasts").addToast(
                    `Could not load ${targetId.replace("dashboard-", "").replace("-", " ")}`,
                    "error",
                );
            });

            this._setupCategoryFilter();
        },

        _formatLocalTimes() {
            document.querySelectorAll("time.js-local-time").forEach((el) => {
                const iso = el.getAttribute("datetime");
                if (!iso) return;
                const date = new Date(iso);
                if (isNaN(date.getTime())) return;
                const formatted = new Intl.DateTimeFormat(navigator.language || "en-US", {
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                }).format(date);
                el.textContent = formatted;
            });
        },

        _updateRelativeTimes() {
            document.querySelectorAll("time.js-time-ago").forEach((el) => {
                const iso = el.getAttribute("datetime");
                if (!iso) return;
                const date = new Date(iso);
                if (isNaN(date.getTime())) return;

                const now = new Date();
                const diffSeconds = Math.max(0, Math.floor((now - date) / 1000));
                let phrase = "just now";
                if (diffSeconds >= 60) {
                    const minutes = Math.floor(diffSeconds / 60);
                    if (minutes < 60) {
                        phrase = `${minutes} minute${minutes !== 1 ? "s" : ""} ago`;
                    } else {
                        const hours = Math.floor(minutes / 60);
                        if (hours < 24) {
                            phrase = `${hours} hour${hours !== 1 ? "s" : ""} ago`;
                        } else {
                            const days = Math.floor(hours / 24);
                            if (days < 30) {
                                phrase = `${days} day${days !== 1 ? "s" : ""} ago`;
                            } else {
                                const months = Math.floor(days / 30);
                                if (months < 12) {
                                    phrase = `${months} month${months !== 1 ? "s" : ""} ago`;
                                } else {
                                    const years = Math.floor(days / 365);
                                    phrase = `${years} year${years !== 1 ? "s" : ""} ago`;
                                }
                            }
                        }
                    }
                }
                const prefix = el.dataset.prefix;
                el.textContent = prefix ? `${prefix} ${phrase}` : phrase;
            });
        },

        /** ----- tabs ----- */

        setTab(tab) {
            this.activeTab = tab;
            try {
                localStorage.setItem("lm_active_tab", tab);
            } catch {
                // Ignore storage errors
            }
        },

        /** ----- keyboard shortcuts ----- */

        onKeydown(event) {
            const tag = document.activeElement?.tagName?.toLowerCase();
            const isEditing = document.activeElement?.isContentEditable;
            if (tag === "input" || tag === "textarea" || tag === "select" || isEditing) {
                return;
            }

            switch (event.key) {
                case "1":
                    this.setTab("accounts");
                    break;
                case "2":
                    this.setTab("summary");
                    break;
                case "3":
                    this.setTab("activity");
                    break;
                case "4":
                    this.setTab("sync");
                    break;
                case "j":
                case "ArrowLeft":
                    this._clickPeriodButton("Previous month");
                    break;
                case "k":
                case "ArrowRight":
                    this._clickPeriodButton("Next month");
                    break;
                case "/":
                    event.preventDefault();
                    this._focusSearch();
                    break;
                case "Escape":
                    this.searchQuery = "";
                    this.showApiKeyDialog = false;
                    this._focusSearch();
                    break;
                default:
                    return;
            }
            event.preventDefault();
        },

        _clickPeriodButton(label) {
            const btn = document.querySelector(
                `.period-control__button[aria-label="${label}"]`,
            );
            if (btn && !btn.classList.contains("is-disabled")) {
                btn.click();
            }
        },

        _focusSearch() {
            const input = document.querySelector(".category-search");
            if (input) {
                input.focus();
                input.select();
            }
        },

        /** ----- collapse / expand all ----- */

        toggleAllDetails() {
            this.allExpanded = !this.allExpanded;
            const container = document.querySelector("[data-category-explorer]");
            if (!container) return;
            container.querySelectorAll("details.category-item--group").forEach((el) => {
                el.open = this.allExpanded;
            });
        },

        /** ----- category search filter ----- */

        _setupCategoryFilter() {
            if (this._categoryFilterObserver) {
                this._categoryFilterObserver.disconnect();
            }
            this._categoryFilterObserver = new MutationObserver(() => {
                this._applySearchFilter();
            });
            const container = document.querySelector("[data-category-explorer]");
            if (container) {
                this._categoryFilterObserver.observe(container, {
                    childList: true,
                    subtree: true,
                });
            }
        },

        _applySearchFilter() {
            const container = document.querySelector("[data-category-explorer]");
            if (!container) return;

            const query = this.searchQuery.toLowerCase().trim();
            const items = container.querySelectorAll(".category-item, .category-child");
            const sections = container.querySelectorAll(".category-section");

            items.forEach((item) => {
                const label = item.querySelector(".category-name__label, .category-child__name");
                if (!label) return;
                const text = label.textContent?.toLowerCase() || "";
                item.style.display = !query || text.includes(query) ? "" : "none";
            });

            sections.forEach((section) => {
                const visibleItems = Array.from(
                    section.querySelectorAll(".category-item, .category-child"),
                ).filter((item) => item.style.display !== "none");
                section.style.display = !query || visibleItems.length > 0 ? "" : "none";
            });
        },

        /** ----- Frappe Charts ----- */

        initChart() {
            if (typeof frappe === "undefined") return;
            const scriptEl = document.getElementById("chart-data");
            if (!scriptEl) return;

            let chartData;
            try {
                chartData = JSON.parse(scriptEl.textContent || "null");
            } catch {
                return;
            }
            if (!chartData) return;

            const container = document.getElementById("category-donut");
            if (!container) return;
            container.innerHTML = "";

            const colors = [
                "#32cf82", "#efb20e", "#ff5c6c", "#5f7ce8", "#a36ddd", "#1fb6a5",
                "#2ecc71", "#f1c40f", "#e74c3c", "#3498db", "#9b59b6", "#1abc9c",
            ];

            new frappe.Chart(container, {
                data: chartData,
                type: "percentage",
                height: 260,
                colors: colors,
                tooltipOptions: { formatTooltipY: (d) => d.toFixed(2) },
            });
        },

        /** ----- API key ----- */

        submitApiKey() {
            const key = this.apiKeyInput.trim();
            if (!key) return;
            localStorage.setItem("lm_api_key", key);
            this.showApiKeyDialog = false;
            this.apiKeyInput = "";
            htmx.ajax("GET", "/", { target: "#dashboard-content", swap: "innerHTML" });
            Alpine.store("toasts").addToast("Connected — refreshing data", "success");
        },
    }));
});
})();
