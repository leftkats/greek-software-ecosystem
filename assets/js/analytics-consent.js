(function () {
    var STORAGE_KEY = "agtj_analytics_consent";

    function consentUpdate(granted) {
        if (typeof gtag !== "function") return;
        var v = granted ? "granted" : "denied";
        gtag("consent", "update", {
            analytics_storage: v,
            ad_storage: v,
            ad_user_data: v,
            ad_personalization: v,
        });
    }

    function bannerEl() {
        return document.getElementById("agtj-consent-banner");
    }

    function hideBanner() {
        var el = bannerEl();
        if (el) el.setAttribute("hidden", "");
    }

    function showBanner() {
        var el = bannerEl();
        if (!el) return;
        el.removeAttribute("hidden");
        var focusBtn = el.querySelector("#agtj-consent-accept");
        if (focusBtn && typeof focusBtn.focus === "function") {
            focusBtn.focus();
        }
    }

    function accept() {
        localStorage.setItem(STORAGE_KEY, "accepted");
        consentUpdate(true);
        hideBanner();
    }

    function reject() {
        localStorage.setItem(STORAGE_KEY, "rejected");
        consentUpdate(false);
        hideBanner();
    }

    function init() {
        var stored = localStorage.getItem(STORAGE_KEY);
        if (stored === "accepted") {
            consentUpdate(true);
            hideBanner();
        } else if (stored === "rejected") {
            consentUpdate(false);
            hideBanner();
        } else {
            showBanner();
        }

        document.getElementById("agtj-consent-accept")?.addEventListener("click", accept);
        document.getElementById("agtj-consent-reject")?.addEventListener("click", reject);
        document.getElementById("agtj-cookie-choices-btn")?.addEventListener("click", function (e) {
            e.preventDefault();
            showBanner();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
