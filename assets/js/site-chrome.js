/* Theme toggle: persist across full page loads (localStorage + sessionStorage + cookie). */
(function () {
    if (window.__agtjThemeChrome) return;
    window.__agtjThemeChrome = true;

    var STORAGE_KEY = "agtj-color-scheme";

    function cookiePath() {
        var meta = document.querySelector('meta[name="agtj-theme-cookie-path"]');
        var p = meta && meta.getAttribute("content");
        return p && p.charAt(0) === "/" ? p : "/";
    }

    function persist(isDark) {
        var val = isDark ? "dark" : "light";
        try {
            localStorage.setItem(STORAGE_KEY, val);
        } catch (e) { }
        try {
            sessionStorage.setItem(STORAGE_KEY, val);
        } catch (e) { }
        try {
            var path = cookiePath();
            var bits =
                "agtj-color-scheme=" +
                encodeURIComponent(val) +
                ";path=" +
                path +
                ";max-age=31536000;SameSite=Lax";
            if (typeof location !== "undefined" && location.protocol === "https:") {
                bits += ";Secure";
            }
            document.cookie = bits;
        } catch (e) { }
    }

    function applyDark(on) {
        var root = document.documentElement;
        if (on) {
            root.classList.add("dark");
            root.classList.remove("light");
        } else {
            root.classList.remove("dark");
            root.classList.add("light");
        }
        persist(on);
    }

    var btn = document.getElementById("themeToggleBtn");
    if (!btn) return;

    btn.setAttribute(
        "aria-pressed",
        document.documentElement.classList.contains("dark") ? "true" : "false"
    );
    btn.addEventListener("click", function () {
        var nextDark = !document.documentElement.classList.contains("dark");
        applyDark(nextDark);
        btn.setAttribute("aria-pressed", nextDark ? "true" : "false");
    });
})();
