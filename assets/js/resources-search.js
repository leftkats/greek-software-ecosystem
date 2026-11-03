/**
 * Filter resources.html table rows using precomputed data-search (same pattern as open-source-search.js).
 */
(function () {
    const input = document.getElementById("res-filter-input");
    const tbody = document.getElementById("res-tbody");
    if (!input || !tbody) {
        return;
    }

    const rows = Array.from(tbody.querySelectorAll("tr.agtj-res-row"));
    const total = rows.length;
    const countEl = document.getElementById("res-filter-hint");
    const DEBOUNCE_MS = 160;

    let debounceTimer = null;

    function applyFilter() {
        const q = input.value.trim().toLowerCase();
        let visible = 0;
        for (let i = 0; i < rows.length; i++) {
            const tr = rows[i];
            const hay = tr.dataset.search || "";
            const show = !q || hay.includes(q);
            tr.hidden = !show;
            if (show) {
                visible += 1;
            }
        }
        if (countEl) {
            if (q) {
                countEl.textContent =
                    "Showing " + visible + " of " + total + " · press Esc to clear";
            } else {
                countEl.textContent =
                    total +
                    " links · order follows _data/queries.yaml & open_greek_data.yaml";
            }
        }
    }

    function scheduleFilter() {
        if (debounceTimer !== null) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(function () {
            debounceTimer = null;
            requestAnimationFrame(applyFilter);
        }, DEBOUNCE_MS);
    }

    input.addEventListener("input", scheduleFilter);
    input.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            if (debounceTimer !== null) {
                clearTimeout(debounceTimer);
                debounceTimer = null;
            }
            input.value = "";
            requestAnimationFrame(applyFilter);
            input.blur();
        }
    });
})();
