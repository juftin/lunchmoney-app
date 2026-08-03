/** Provide contained dashboard panel and category controls without a data store. */

/** Activate the selected left-rail overview panel. */
function initializePanelSwitcher() {
    const buttons = document.querySelectorAll("[data-panel-target]");
    const panels = document.querySelectorAll(".rail-panel");

    for (const button of buttons) {
        button.addEventListener("click", () => {
            const targetId = button.dataset.panelTarget;
            for (const currentButton of buttons) {
                const isActive = currentButton === button;
                currentButton.classList.toggle("is-active", isActive);
                currentButton.setAttribute("aria-selected", String(isActive));
            }
            for (const panel of panels) {
                panel.hidden = panel.id !== targetId;
            }
        });
    }
}

/** Filter the category explorer between income and expense rows. */
function initializeCategoryFilter() {
    const buttons = document.querySelectorAll("[data-category-filter]");
    const rows = document.querySelectorAll("[data-category-kind]");

    for (const button of buttons) {
        button.addEventListener("click", () => {
            const kind = button.dataset.categoryFilter;
            for (const currentButton of buttons) {
                currentButton.classList.toggle(
                    "is-active",
                    currentButton === button,
                );
            }
            for (const row of rows) {
                row.classList.toggle(
                    "is-hidden",
                    row.dataset.categoryKind !== kind,
                );
            }
        });
    }
}

initializePanelSwitcher();
initializeCategoryFilter();
