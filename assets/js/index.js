(function initAgtjConfigFromDom() {
    const el = document.getElementById("agtj-config");
    let itemsPerPage = 20;
    if (el?.textContent?.trim()) {
        try {
            const c = JSON.parse(el.textContent);
            const n = c?.itemsPerPage;
            if (typeof n === "number" && Number.isFinite(n) && n > 0) {
                itemsPerPage = n;
            }
        } catch (_) {
            /* keep default */
        }
    }
    window.AGTJ_CONFIG = { itemsPerPage };
})();

let currentPage = 1;
const itemsPerPage = Number(window.AGTJ_CONFIG?.itemsPerPage) || 20;
let activeSectors = [];
let activeLocations = [];
let activePolicies = [];
let activeIndustries = [];
let filterWorkableHiringOnly = false;
let activeSort = "open_desc";
const ALLOWED_SORTS = new Set(["open_desc", "open_asc"]);

function normalizeSector(sector) {
    return (sector ?? "").toString().trim().toLowerCase();
}

function normalizeLocation(location) {
    return (location ?? "").toString().trim().toLowerCase();
}

function normalizeIndustry(industry) {
    return (industry ?? "").toString().trim().toLowerCase();
}

function setActiveSectors(next) {
    const deduped = Array.from(new Set((next ?? []).map(normalizeSector).filter(Boolean)));
    activeSectors = deduped;
    document.body.classList.toggle("has-sector-filters", activeSectors.length > 0);
    updateSectorFilterUI();
}

function updateSectorFilterUI() {
    document.querySelectorAll(".sector-filter").forEach((btn) => {
        const sector = normalizeSector(btn.dataset.sector);
        const isActive = activeSectors.includes(sector);
        btn.classList.toggle("active-filter", isActive);
        btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
}

function toggleSectorFilter(sector) {
    const normalized = normalizeSector(sector);
    if (!normalized) return;
    if (activeSectors.includes(normalized)) {
        setActiveSectors(activeSectors.filter((s) => s !== normalized));
    } else {
        setActiveSectors([...activeSectors, normalized]);
    }
    currentPage = 1;
    updatePagination();
}

function updateIndustryFilterSummary() {
    const el = document.getElementById("industryFilterSummary");
    if (!el) return;
    if (activeIndustries.length === 0) {
        el.textContent = "All industries";
        return;
    }
    const labelFor = (norm) => {
        const cb = Array.from(document.querySelectorAll(".industry-filter-cb")).find(
            (c) => normalizeIndustry(c.value) === norm,
        );
        return cb ? cb.value : null;
    };
    const labels = activeIndustries.map(labelFor).filter(Boolean);
    if (labels.length === 0) {
        el.textContent = "All industries";
        return;
    }
    if (labels.length === 1) {
        el.textContent = labels[0];
        return;
    }
    el.textContent = `${labels[0]} +${labels.length - 1} more`;
}

function updateLocationFilterSummary() {
    const el = document.getElementById("locationFilterSummary");
    if (!el) return;
    if (activeLocations.length === 0) {
        el.textContent = "All locations";
        return;
    }
    const labelFor = (norm) => {
        const cb = Array.from(document.querySelectorAll(".location-filter-cb")).find(
            (c) => normalizeLocation(c.value) === norm,
        );
        return cb ? cb.value : null;
    };
    const labels = activeLocations.map(labelFor).filter(Boolean);
    if (labels.length === 0) {
        el.textContent = "All locations";
        return;
    }
    if (labels.length === 1) {
        el.textContent = labels[0];
        return;
    }
    el.textContent = `${labels[0]} +${labels.length - 1} more`;
}

function syncIndustryFilterWidgetsFromState() {
    const want = new Set(activeIndustries);
    document.querySelectorAll(".industry-filter-cb").forEach((cb) => {
        cb.checked = want.has(normalizeIndustry(cb.value));
    });
    updateIndustryFilterSummary();
}

function syncLocationFilterWidgetsFromState() {
    const want = new Set(activeLocations);
    document.querySelectorAll(".location-filter-cb").forEach((cb) => {
        cb.checked = want.has(normalizeLocation(cb.value));
    });
    updateLocationFilterSummary();
}

function closeAllFilterPanels() {
    document.getElementById("industryFilterPanel")?.classList.add("hidden");
    document.getElementById("locationFilterPanel")?.classList.add("hidden");
    document.getElementById("industryFilterToggle")?.setAttribute("aria-expanded", "false");
    document.getElementById("locationFilterToggle")?.setAttribute("aria-expanded", "false");
    document.getElementById("industryFilterChevron")?.classList.remove("rotate-180");
    document.getElementById("locationFilterChevron")?.classList.remove("rotate-180");
}

function toggleIndustryFilterPanel(ev) {
    ev?.stopPropagation();
    const panel = document.getElementById("industryFilterPanel");
    const btn = document.getElementById("industryFilterToggle");
    const chev = document.getElementById("industryFilterChevron");
    if (!panel || !btn) return;
    const wasOpen = !panel.classList.contains("hidden");
    closeAllFilterPanels();
    if (!wasOpen) {
        panel.classList.remove("hidden");
        btn.setAttribute("aria-expanded", "true");
        chev?.classList.add("rotate-180");
    }
}

function toggleLocationFilterPanel(ev) {
    ev?.stopPropagation();
    const panel = document.getElementById("locationFilterPanel");
    const btn = document.getElementById("locationFilterToggle");
    const chev = document.getElementById("locationFilterChevron");
    if (!panel || !btn) return;
    const wasOpen = !panel.classList.contains("hidden");
    closeAllFilterPanels();
    if (!wasOpen) {
        panel.classList.remove("hidden");
        btn.setAttribute("aria-expanded", "true");
        chev?.classList.add("rotate-180");
    }
}

function setActiveIndustries(next) {
    const raw = Array.from(new Set((next ?? []).map(normalizeIndustry).filter(Boolean)));
    const boxes = document.querySelectorAll(".industry-filter-cb");
    if (boxes.length) {
        const allowed = new Set(Array.from(boxes).map((cb) => normalizeIndustry(cb.value)));
        activeIndustries = raw.filter((x) => allowed.has(x));
    } else {
        activeIndustries = raw;
    }
    syncIndustryFilterWidgetsFromState();
}

function setActiveLocations(next) {
    const raw = Array.from(new Set((next ?? []).map(normalizeLocation).filter(Boolean)));
    const boxes = document.querySelectorAll(".location-filter-cb");
    let deduped = raw;
    if (boxes.length) {
        const allowed = new Set(Array.from(boxes).map((cb) => normalizeLocation(cb.value)));
        deduped = raw.filter((x) => allowed.has(x));
    }
    activeLocations = deduped;
    document.body.classList.toggle("has-location-filters", activeLocations.length > 0);
    updateCompanyLocationTagUI();
    syncLocationFilterWidgetsFromState();
}

function updateCompanyLocationTagUI() {
    document.querySelectorAll(".company-location-tag").forEach((btn) => {
        const loc = normalizeLocation(btn.dataset.location);
        const isActive = activeLocations.includes(loc);
        btn.classList.toggle("active-filter", isActive);
        btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
}

function toggleLocationFilter(location) {
    const normalized = normalizeLocation(location);
    if (!normalized) return;
    if (activeLocations.includes(normalized)) {
        setActiveLocations(activeLocations.filter((l) => l !== normalized));
    } else {
        setActiveLocations([...activeLocations, normalized]);
    }
    currentPage = 1;
    updatePagination();
}

function normalizePolicy(policy) {
    const raw = (policy ?? "").toString().trim().toLowerCase();
    if (!raw) return "";
    if (raw === "n/a" || raw === "na" || raw === "none") return "n/a";
    if (raw === "remote") return "remote";
    if (raw === "hybrid") return "hybrid";
    if (raw === "on-site" || raw === "onsite" || raw === "on site") return "on-site";
    return raw;
}

function setActivePolicies(next) {
    const deduped = Array.from(new Set((next ?? []).map(normalizePolicy).filter(Boolean)));
    activePolicies = deduped;
    document.body.classList.toggle("has-policy-filters", activePolicies.length > 0);
    updatePolicyFilterUI();
}

function updatePolicyFilterUI() {
    document.querySelectorAll(".policy-filter").forEach((btn) => {
        const policy = normalizePolicy(btn.dataset.policy);
        const isActive = activePolicies.includes(policy);
        btn.classList.toggle("active-filter", isActive);
        btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
}

function togglePolicyFilter(policy) {
    const normalized = normalizePolicy(policy);
    if (!normalized) return;

    if (activePolicies.includes(normalized)) {
        setActivePolicies(activePolicies.filter((p) => p !== normalized));
    } else {
        setActivePolicies([...activePolicies, normalized]);
    }

    currentPage = 1;
    updatePagination();
    syncUrlFromState();
}

function initPolicyFilters() {
    document.querySelectorAll(".company-row").forEach((row) => {
        const policy = normalizePolicy(row.dataset.policy);
        if (policy !== "remote" && policy !== "hybrid" && policy !== "on-site") return;

        const badge = row.querySelector(".policy-badge-slot");
        if (!badge) return;

        const iconName = policy === "remote" ? "home_work" : policy === "hybrid" ? "swap_horiz" : "apartment";

        const label = policy === "on-site" ? "On-site" : policy.charAt(0).toUpperCase() + policy.slice(1);

        badge.innerHTML = `
                    <button type="button"
                        class="policy-filter inline-flex items-center gap-1 px-1 rounded-full"
                        data-policy="${policy}"
                        aria-pressed="false"
                        title="Filter by ${label}"
                    >
                        <span class="material-symbols-outlined text-[14px] leading-none">${iconName}</span>
                        <span class="uppercase">${label}</span>
                    </button>
                `;

        const btn = badge.querySelector("button.policy-filter");
        if (btn)
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                togglePolicyFilter(btn.dataset.policy);
            });
    });

    setActivePolicies(activePolicies);
}

function workableOpeningsSortKey(row) {
    if (!row.dataset.workableSlug) return -1;
    const raw = row.dataset.workableOpenings;
    if (raw === undefined || raw === "") return -1;
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : -1;
}

function compareByName(a, b) {
    return (a.dataset.name || "").localeCompare(b.dataset.name || "", undefined, { sensitivity: "base" });
}

function sortRows(rows) {
    rows.sort((a, b) => {
        const ka = workableOpeningsSortKey(a);
        const kb = workableOpeningsSortKey(b);

        if (activeSort === "open_asc") {
            const aMissing = ka < 0;
            const bMissing = kb < 0;
            if (aMissing && bMissing) return compareByName(a, b);
            if (aMissing) return 1;
            if (bMissing) return -1;
            if (ka !== kb) return ka - kb;
            return compareByName(a, b);
        }

        const aMissing = ka < 0;
        const bMissing = kb < 0;
        if (aMissing && bMissing) return compareByName(a, b);
        if (aMissing) return 1;
        if (bMissing) return -1;
        if (kb !== ka) return kb - ka;
        return compareByName(a, b);
    });
    return rows;
}

function updateOpenRolesSortButtonUI() {
    const btn = document.getElementById("sortOpenRolesBtn");
    if (!btn) return;
    const isOpenRolesSort = activeSort === "open_desc" || activeSort === "open_asc";
    btn.setAttribute("aria-pressed", isOpenRolesSort ? "true" : "false");
    if (activeSort === "open_asc") {
        btn.textContent = "Sort Open Roles: Low-High";
    } else {
        btn.textContent = "Sort Open Roles: High-Low";
    }
}

function updateStatHeaderTriggersUI() {
    document.querySelectorAll(".stat-header-policy[data-policy]").forEach((btn) => {
        const pol = normalizePolicy(btn.dataset.policy);
        const on = activePolicies.includes(pol);
        btn.classList.toggle("stat-header-active", on);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
    });
    const wBtn = document.getElementById("statWorkableHiringBtn");
    if (wBtn) {
        if (wBtn.disabled) {
            wBtn.classList.remove("stat-header-active");
            wBtn.setAttribute("aria-pressed", "false");
        } else {
            wBtn.classList.toggle("stat-header-active", filterWorkableHiringOnly);
            wBtn.setAttribute("aria-pressed", filterWorkableHiringOnly ? "true" : "false");
        }
    }
}

function updatePagination() {
    const query = document.getElementById("searchInput").value.toLowerCase();
    const allRows = Array.from(document.querySelectorAll(".company-row"));
    const companyListEl = document.getElementById("companyList");

    const filtered = allRows.filter((row) => {
        const matchesText = (
            (row.dataset.name || "") +
            " " +
            (row.dataset.sectors || "") +
            " " +
            (row.dataset.industries || "") +
            " " +
            (row.dataset.policy || "") +
            " " +
            (row.dataset.locations || "")
        )
            .toLowerCase()
            .includes(query);
        const sectorsList = (row.dataset.sectorsList || "")
            .split("||")
            .map(normalizeSector)
            .filter(Boolean);
        const matchesSector = activeSectors.length === 0 || sectorsList.some((s) => activeSectors.includes(s));
        const industriesList = (row.dataset.industriesList || "")
            .split("||")
            .map((s) => s.trim())
            .filter(Boolean);
        const matchesIndustry =
            activeIndustries.length === 0 ||
            industriesList.some((ind) => activeIndustries.includes(normalizeIndustry(ind)));
        const locationsList = (row.dataset.locationsList || "")
            .split("||")
            .map(normalizeLocation)
            .filter(Boolean);
        const matchesLocation =
            activeLocations.length === 0 || locationsList.some((l) => activeLocations.includes(l));
        const rowPolicy = normalizePolicy(row.dataset.policy);
        const matchesPolicy = activePolicies.length === 0 || activePolicies.includes(rowPolicy);
        const matchesWorkableHiring = !filterWorkableHiringOnly || workableOpeningsSortKey(row) > 0;
        return (
            matchesText &&
            matchesSector &&
            matchesIndustry &&
            matchesLocation &&
            matchesPolicy &&
            matchesWorkableHiring
        );
    });

    sortRows(filtered);

    const filteredSet = new Set(filtered);
    const nonFiltered = allRows.filter((row) => !filteredSet.has(row));
    if (companyListEl) {
        const fragment = document.createDocumentFragment();
        filtered.forEach((row) => fragment.appendChild(row));
        nonFiltered.forEach((row) => fragment.appendChild(row));
        companyListEl.appendChild(fragment);
    }

    const totalPages = Math.ceil(filtered.length / itemsPerPage) || 1;
    allRows.forEach((row) => row.classList.add("hidden-row"));

    filtered
        .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
        .forEach((row) => row.classList.remove("hidden-row"));

    document.getElementById("pageIndicator").innerText = currentPage.toString().padStart(2, "0");
    document.getElementById("prevBtn").disabled = currentPage === 1;
    document.getElementById("nextBtn").disabled = currentPage === totalPages;
    document.getElementById("paginationControls").style.display = totalPages > 1 ? "flex" : "none";
    updateOpenRolesSortButtonUI();
    updateStatHeaderTriggersUI();
}

function changePage(step) {
    currentPage += step;
    updatePagination();
    window.scrollTo(0, 0);
}

function syncUrlFromState() {
    const params = new URLSearchParams(window.location.search);
    const q = document.getElementById("searchInput").value.trim();
    if (q) params.set("q", q);
    else params.delete("q");
    if (activePolicies.length) params.set("pol", activePolicies.join(","));
    else params.delete("pol");
    if (activeSectors.length) params.set("sec", activeSectors.join(","));
    else params.delete("sec");
    if (activeIndustries.length) params.set("ind", activeIndustries.join(","));
    else params.delete("ind");
    if (activeLocations.length) params.set("loc", activeLocations.join(","));
    else params.delete("loc");
    if (filterWorkableHiringOnly) params.set("hire", "1");
    else params.delete("hire");
    if (activeSort && ALLOWED_SORTS.has(activeSort)) params.set("sort", activeSort);
    else params.delete("sort");
    const next = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, "", next);
}

function applyStateFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const q = params.get("q") || "";
    document.getElementById("searchInput").value = q;

    const pol = (params.get("pol") || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    const sec = (params.get("sec") || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    const loc = (params.get("loc") || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    const sort = (params.get("sort") || "").trim();
    const indParts = (params.get("ind") || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

    filterWorkableHiringOnly = params.get("hire") === "1";
    if (ALLOWED_SORTS.has(sort)) {
        activeSort = sort;
    }

    setActivePolicies(pol);
    setActiveSectors(sec);
    setActiveIndustries(indParts);
    setActiveLocations(loc);
}

document.querySelectorAll(".sector-filter").forEach((btn) => {
    btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleSectorFilter(btn.dataset.sector);
        syncUrlFromState();
    });
});

document.getElementById("companyList")?.addEventListener("click", (e) => {
    const tag = e.target.closest(".company-location-tag");
    if (!tag || !tag.dataset.location) return;
    e.preventDefault();
    e.stopPropagation();
    toggleLocationFilter(tag.dataset.location);
    syncUrlFromState();
});

document.getElementById("searchInput").addEventListener("input", () => {
    currentPage = 1;
    updatePagination();
    syncUrlFromState();
});

document.getElementById("industryFilterToggle")?.addEventListener("click", toggleIndustryFilterPanel);
document.getElementById("locationFilterToggle")?.addEventListener("click", toggleLocationFilterPanel);

document.getElementById("industryFilterPanel")?.addEventListener("change", (e) => {
    const t = e.target;
    if (!(t instanceof HTMLInputElement) || !t.classList.contains("industry-filter-cb")) return;
    const picked = Array.from(document.querySelectorAll(".industry-filter-cb:checked"))
        .map((cb) => cb.value)
        .filter(Boolean);
    setActiveIndustries(picked);
    currentPage = 1;
    updatePagination();
    syncUrlFromState();
});

document.getElementById("locationFilterPanel")?.addEventListener("change", (e) => {
    const t = e.target;
    if (!(t instanceof HTMLInputElement) || !t.classList.contains("location-filter-cb")) return;
    const picked = Array.from(document.querySelectorAll(".location-filter-cb:checked"))
        .map((cb) => cb.value)
        .filter(Boolean);
    setActiveLocations(picked);
    currentPage = 1;
    updatePagination();
    syncUrlFromState();
});

document.addEventListener("click", (e) => {
    if (e.target.closest("#industryFilterWrap") || e.target.closest("#locationFilterWrap")) return;
    closeAllFilterPanels();
});

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllFilterPanels();
});

document.getElementById("clearDropdownFiltersBtn")?.addEventListener("click", (e) => {
    e.preventDefault();
    closeAllFilterPanels();
    setActiveIndustries([]);
    setActiveLocations([]);
    currentPage = 1;
    updatePagination();
    syncUrlFromState();
});

document.getElementById("sortOpenRolesBtn").addEventListener("click", () => {
    if (activeSort === "open_desc") {
        activeSort = "open_asc";
    } else {
        activeSort = "open_desc";
    }
    currentPage = 1;
    updatePagination();
    syncUrlFromState();
});

document.querySelectorAll(".stat-header-policy[data-policy]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
        e.preventDefault();
        togglePolicyFilter(btn.dataset.policy);
    });
});

const statWorkableHiringBtn = document.getElementById("statWorkableHiringBtn");
if (statWorkableHiringBtn) {
    statWorkableHiringBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (statWorkableHiringBtn.disabled) return;
        filterWorkableHiringOnly = !filterWorkableHiringOnly;
        currentPage = 1;
        updatePagination();
        syncUrlFromState();
    });
}

function initWorkableJobCounts() {
    const wBtn = document.getElementById("statWorkableHiringBtn");
    const rows = Array.from(document.querySelectorAll(".company-row[data-workable-slug]"));
    if (!rows.length) {
        if (wBtn) {
            wBtn.disabled = true;
            filterWorkableHiringOnly = false;
        }
        return;
    }

    const snapEl = document.getElementById("workable-job-snapshot");
    let snapshot = null;
    if (snapEl && snapEl.textContent.trim()) {
        try {
            snapshot = JSON.parse(snapEl.textContent);
        } catch (_) {
            snapshot = null;
        }
    }

    const accounts = snapshot && typeof snapshot.accounts === "object" && snapshot.accounts !== null ? snapshot.accounts : {};
    const generatedAt = snapshot && snapshot.generated_at ? String(snapshot.generated_at) : "";

    function formatSnapshotTime(iso) {
        if (!iso) return null;
        try {
            const d = new Date(iso);
            if (Number.isNaN(d.getTime())) return iso;
            const dateStr = d.toLocaleDateString("en-GB", {
                day: "numeric",
                month: "short",
                year: "numeric",
                timeZone: "UTC",
            });
            const timeStr = d.toLocaleTimeString("en-GB", {
                hour: "2-digit",
                minute: "2-digit",
                hour12: false,
                timeZone: "UTC",
            });
            return `${dateStr}, ${timeStr} UTC`;
        } catch (_) {
            return iso;
        }
    }

    const totalEl = document.getElementById("workableLiveTotal");
    const sublineEl = document.getElementById("workableLiveSubline");
    const explainerEl = document.getElementById("workableLiveExplainer");
    const WORKABLE_EXPLAINER_DEFAULT =
        "Open role counts are fetched from Workable's public API at build time and are embedded into this HTML.";

    let aggregateOpen = 0;
    let numericRows = 0;

    rows.forEach((row) => {
        const slug = (row.dataset.workableSlug || "").trim();
        const badge = row.querySelector(".workable-job-badge");
        const careerLink = row.querySelector("a.company-career-link");
        const careerLabel = careerLink && careerLink.querySelector(".career-btn-label");
        if (!slug) return;

        if (!Object.prototype.hasOwnProperty.call(accounts, slug)) {
            if (badge) badge.remove();
            return;
        }

        const n = accounts[slug];
        if (typeof n !== "number" || !Number.isFinite(n) || n <= 0) {
            if (badge) badge.remove();
            return;
        }

        row.dataset.workableOpenings = String(n);
        numericRows += 1;
        aggregateOpen += n;

        row.classList.add("company-row-has-openings");
        if (badge) badge.remove();

        if (careerLink && careerLabel) {
            const roleLabel = n === 1 ? "1 open role" : `${n} open roles`;
            careerLabel.textContent = roleLabel;
            careerLabel.classList.add("text-emerald-700", "dark:text-emerald-300");
            careerLink.classList.add("company-career-link-has-roles");
            careerLink.setAttribute("title", `View ${n === 1 ? "this role" : "these roles"} on Workable (Greece)`);
            careerLink.setAttribute("aria-label", `${roleLabel} - open Workable careers page`);
        }
    });

    if (totalEl) {
        if (numericRows === 0) {
            totalEl.textContent = "-";
            totalEl.classList.remove("text-emerald-700", "dark:text-emerald-400");
        } else {
            totalEl.textContent = String(aggregateOpen);
            if (aggregateOpen > 0) {
                totalEl.classList.add("text-emerald-700", "dark:text-emerald-400");
            } else {
                totalEl.classList.remove("text-emerald-700", "dark:text-emerald-400");
            }
        }
    }

    if (wBtn) {
        wBtn.disabled = numericRows === 0;
        if (wBtn.disabled) {
            filterWorkableHiringOnly = false;
        }
    }

    if (sublineEl && explainerEl) {
        if (!generatedAt && numericRows === 0) {
            explainerEl.innerHTML =
                'No snapshot found. Run <code class="font-mono text-[11px]">just fetch</code> then <code class="font-mono text-[11px]">just index</code> (or the equivalent <code class="font-mono text-[11px]">uv run python -m greek_software_ecosystem.…</code>), or wait for CI.';
            sublineEl.textContent = "";
        } else if (generatedAt && numericRows === 0) {
            explainerEl.textContent =
                "Snapshot exists but no usable Workable counts were stored for this build. Re-run the fetch step in CI or locally.";
            sublineEl.textContent = "";
        } else {
            explainerEl.textContent = WORKABLE_EXPLAINER_DEFAULT;
            const when = formatSnapshotTime(generatedAt);
            sublineEl.textContent = when ? ` Data snapshot: ${when}` : "";
        }
    }
}

document.getElementById("prevBtn")?.addEventListener("click", () => {
    changePage(-1);
});

document.getElementById("nextBtn")?.addEventListener("click", () => {
    changePage(1);
});

applyStateFromUrl();
initWorkableJobCounts();
syncUrlFromState();
initPolicyFilters();
updatePagination();
