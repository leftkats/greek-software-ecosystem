/**
 * Workspaces page: text + location filters, table/map toggle, Leaflet map.
 */
(function () {
    const input = document.getElementById("ws-filter-input");
    const locationSelect = document.getElementById("ws-location-filter");
    const tbody = document.getElementById("ws-tbody");
    const countEl = document.getElementById("ws-filter-hint");
    const tablePanel = document.getElementById("ws-table-panel");
    const mapPanel = document.getElementById("ws-map-panel");
    const btnTable = document.getElementById("ws-view-table");
    const btnMap = document.getElementById("ws-view-map");
    const mapEl = document.getElementById("ws-map");
    const mapEmpty = document.getElementById("ws-map-empty");
    const mapDataEl = document.getElementById("ws-map-data");
    const locationBoundsEl = document.getElementById("ws-location-bounds");
    const mapCountEl = document.getElementById("ws-map-count-hint");

    if (!input || !tbody) {
        return;
    }

    const rows = Array.from(tbody.querySelectorAll("tr.agtj-ws-row"));
    const total = rows.length;
    const DEBOUNCE_MS = 160;
    const GREECE_CENTER = [39.074, 21.824];
    const GREECE_ZOOM = 6;

    let debounceTimer = null;
    let mapInstance = null;
    let tileLayer = null;
    let markerLayer = null;
    let activeView = "table";
    let allMarkers = [];
    let cityBounds = {};

    if (mapDataEl && mapDataEl.textContent) {
        try {
            allMarkers = JSON.parse(mapDataEl.textContent);
        } catch (e) {
            allMarkers = [];
        }
    }
    if (locationBoundsEl && locationBoundsEl.textContent) {
        try {
            cityBounds = JSON.parse(locationBoundsEl.textContent);
        } catch (e) {
            cityBounds = {};
        }
    }

    function getFilterQuery() {
        return input.value.trim().toLowerCase();
    }

    function getLocationKey() {
        if (!locationSelect) {
            return "";
        }
        return (locationSelect.value || "").trim().toLowerCase();
    }

    function matchesLocationFilter(locationFilterStr, locationKey) {
        if (!locationKey) {
            return true;
        }
        const hay = (locationFilterStr || "").toLowerCase();
        if (!hay) {
            return false;
        }
        const tokens = hay.split(/\s+/);
        if (tokens.indexOf(locationKey) >= 0) {
            return true;
        }
        return hay.indexOf(locationKey) >= 0;
    }

    function rowMatchesFilters(tr) {
        const q = getFilterQuery();
        if (q && !(tr.dataset.search || "").includes(q)) {
            return false;
        }
        return matchesLocationFilter(tr.dataset.locationFilter || "", getLocationKey());
    }

    function markerMatchesFilters(marker) {
        const q = getFilterQuery();
        if (q && !(marker.search_text || "").includes(q)) {
            return false;
        }
        return matchesLocationFilter(marker.location_filter || "", getLocationKey());
    }

    function countVisibleTableRows() {
        let visible = 0;
        for (let i = 0; i < rows.length; i++) {
            if (rowMatchesFilters(rows[i])) {
                visible += 1;
            }
        }
        return visible;
    }

    function countVisibleMapMarkers() {
        let visible = 0;
        for (let i = 0; i < allMarkers.length; i++) {
            if (markerMatchesFilters(allMarkers[i])) {
                visible += 1;
            }
        }
        return visible;
    }

    function updateCountHint() {
        const q = getFilterQuery();
        const locKey = getLocationKey();
        const tableVisible = countVisibleTableRows();
        const mapVisible = countVisibleMapMarkers();
        const hasFilter = q || locKey;

        if (countEl) {
            if (hasFilter) {
                countEl.textContent =
                    "Showing " +
                    tableVisible +
                    " of " +
                    total +
                    " · press Esc to clear search";
            } else {
                countEl.textContent =
                    total + " places · edit _data/cafe_resources.yaml to add more";
            }
        }
        if (mapCountEl) {
            if (allMarkers.length === 0 && locKey && cityBounds[locKey]) {
                mapCountEl.textContent =
                    "Focused on " +
                    (locationSelect &&
                        locationSelect.options[locationSelect.selectedIndex].text.split(" (")[0]) +
                    " — add lat/lng to show pins";
            } else if (allMarkers.length === 0) {
                mapCountEl.textContent =
                    "No mapped places yet — add lat/lng (or a Maps link with coordinates)";
            } else if (hasFilter) {
                mapCountEl.textContent =
                    "Showing " + mapVisible + " of " + allMarkers.length + " on map";
            } else {
                mapCountEl.textContent = mapVisible + " places on map";
            }
        }
    }

    function focusMapOnLocation(locKey, markerBounds) {
        if (!mapInstance) {
            return;
        }
        if (markerBounds.length === 1) {
            mapInstance.setView(markerBounds[0], 14);
            return;
        }
        if (markerBounds.length > 1) {
            mapInstance.fitBounds(markerBounds, { padding: [48, 48], maxZoom: 14 });
            return;
        }
        if (locKey && cityBounds[locKey] && cityBounds[locKey].center) {
            mapInstance.setView(cityBounds[locKey].center, cityBounds[locKey].zoom || 12);
            return;
        }
        mapInstance.setView(GREECE_CENTER, GREECE_ZOOM);
    }

    function applyFilters() {
        const locKey = getLocationKey();
        for (let i = 0; i < rows.length; i++) {
            rows[i].hidden = !rowMatchesFilters(rows[i]);
        }
        updateCountHint();
        if (activeView === "map") {
            rebuildMapMarkers();
        } else if (locKey) {
            setView("map");
        }
    }

    function scheduleFilter() {
        if (debounceTimer !== null) {
            clearTimeout(debounceTimer);
        }
        debounceTimer = setTimeout(function () {
            debounceTimer = null;
            requestAnimationFrame(applyFilters);
        }, DEBOUNCE_MS);
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function popupHtml(marker) {
        const parts = [
            '<div class="ws-map-popup">',
            '<p class="ws-map-popup-type">' + escapeHtml(marker.type) + "</p>",
            '<p class="ws-map-popup-title"><a href="' +
                escapeHtml(marker.url) +
                '" target="_blank" rel="noopener noreferrer">' +
                escapeHtml(marker.title) +
                "</a></p>",
        ];
        if (marker.location) {
            parts.push(
                '<p class="ws-map-popup-loc">' + escapeHtml(marker.location) + "</p>"
            );
        }
        if (marker.google_maps_url) {
            parts.push(
                '<p class="ws-map-popup-maps"><a href="' +
                    escapeHtml(marker.google_maps_url) +
                    '" target="_blank" rel="noopener noreferrer">Open in Google Maps</a></p>'
            );
        }
        parts.push("</div>");
        return parts.join("");
    }

    function markerIcon(kind) {
        const kindKey = kind === "cafe" || kind === "remote_hub" || kind === "directory" ? kind : "default";
        return L.divIcon({
            className: "ws-map-marker-icon",
            html:
                '<span class="ws-map-marker-pin ws-map-marker-pin--' +
                kindKey +
                '" aria-hidden="true"><span class="ws-map-marker-pin__core"></span></span>',
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -17],
        });
    }

    function isDarkTheme() {
        return document.documentElement.classList.contains("dark");
    }

    function applyTileLayer() {
        if (!mapInstance || typeof L === "undefined") {
            return;
        }
        if (tileLayer) {
            mapInstance.removeLayer(tileLayer);
        }
        if (isDarkTheme()) {
            tileLayer = L.tileLayer(
                "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
                {
                    attribution:
                        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                    subdomains: "abcd",
                    maxZoom: 19,
                }
            );
        } else {
            tileLayer = L.tileLayer(
                "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
                {
                    attribution:
                        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
                    subdomains: "abcd",
                    maxZoom: 19,
                }
            );
        }
        tileLayer.addTo(mapInstance);
    }

    function rebuildMapMarkers() {
        if (!mapInstance || !markerLayer) {
            return;
        }
        markerLayer.clearLayers();
        const locKey = getLocationKey();
        const bounds = [];
        for (let i = 0; i < allMarkers.length; i++) {
            const marker = allMarkers[i];
            if (!markerMatchesFilters(marker)) {
                continue;
            }
            const leafletMarker = L.marker([marker.lat, marker.lng], {
                icon: markerIcon(marker.type_kind),
            }).bindPopup(popupHtml(marker), { maxWidth: 280 });
            markerLayer.addLayer(leafletMarker);
            bounds.push([marker.lat, marker.lng]);
        }
        focusMapOnLocation(locKey, bounds);
        if (mapEmpty) {
            mapEmpty.hidden = bounds.length > 0 || !!(locKey && cityBounds[locKey]);
        }
        updateCountHint();
    }

    function showMapLoadError(message) {
        if (!mapEmpty) {
            return;
        }
        mapEmpty.hidden = false;
        const card = mapEmpty.querySelector("div");
        if (card) {
            card.innerHTML =
                '<p class="font-semibold text-slate-800 dark:text-slate-100">Map could not load</p>' +
                '<p class="mt-1 text-xs leading-relaxed">' +
                escapeHtml(message || "Leaflet failed to load. Refresh the page or check your network.") +
                "</p>";
        }
    }

    function initMap() {
        if (mapInstance || !mapEl) {
            return;
        }
        if (typeof L === "undefined") {
            showMapLoadError(
                "The map library did not load. If you are previewing locally, run just generate and ensure assets/vendor/leaflet/ is present."
            );
            return;
        }
        mapInstance = L.map(mapEl, {
            scrollWheelZoom: true,
            zoomControl: true,
        });
        applyTileLayer();
        markerLayer = L.layerGroup().addTo(mapInstance);
        mapInstance.setView(GREECE_CENTER, GREECE_ZOOM);
        rebuildMapMarkers();
    }

    function setView(mode) {
        activeView = mode === "map" ? "map" : "table";
        const isMap = activeView === "map";
        if (tablePanel) {
            tablePanel.hidden = isMap;
        }
        if (mapPanel) {
            mapPanel.hidden = !isMap;
        }
        if (btnTable) {
            btnTable.setAttribute("aria-selected", isMap ? "false" : "true");
            btnTable.classList.toggle("ws-view-active", !isMap);
        }
        if (btnMap) {
            btnMap.setAttribute("aria-selected", isMap ? "true" : "false");
            btnMap.classList.toggle("ws-view-active", isMap);
        }
        if (isMap) {
            initMap();
            window.requestAnimationFrame(function () {
                window.requestAnimationFrame(function () {
                    if (mapInstance) {
                        mapInstance.invalidateSize();
                        rebuildMapMarkers();
                    }
                });
            });
        }
    }

    if (btnTable) {
        btnTable.addEventListener("click", function () {
            setView("table");
        });
    }
    if (btnMap) {
        btnMap.addEventListener("click", function () {
            setView("map");
        });
    }

    input.addEventListener("input", scheduleFilter);
    input.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            if (debounceTimer !== null) {
                clearTimeout(debounceTimer);
                debounceTimer = null;
            }
            input.value = "";
            requestAnimationFrame(applyFilters);
            input.blur();
        }
    });

    if (locationSelect) {
        locationSelect.addEventListener("change", function () {
            applyFilters();
        });
    }

    const themeObserver = new MutationObserver(function () {
        if (mapInstance) {
            applyTileLayer();
        }
    });
    themeObserver.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"],
    });

    updateCountHint();
})();
