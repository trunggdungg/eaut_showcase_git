/** UIKick - Home page interactions (thay cho useState/hover logic của React ProjectCard) */
(function () {
    "use strict";

    function initCardVideos() {
        document.querySelectorAll(".uikick-card").forEach(function (card) {
            var video = card.querySelector(".uikick-card-video");
            if (!video) return;

            card.addEventListener("mouseenter", function () {
                video.currentTime = 0;
                video.play().then(function () {
                    card.classList.add("is-playing");
                }).catch(function () {
                    /* autoplay blocked, ignore */
                });
            });

            card.addEventListener("mouseleave", function () {
                card.classList.remove("is-playing");
                video.pause();
                video.currentTime = 0;
            });
        });
    }

    function initFilterForm() {
        var form = document.getElementById("uikick-filter-form");
        if (!form) return;
        // Status/goal checkboxes & radios no longer auto-submit on every click —
        // the user picks as many options as they want, then presses "Apply
        // filters" (the form's own submit button) to reload with them all.
        var sortSelect = document.getElementById("uikick-sort-select");
        if (sortSelect) {
            sortSelect.addEventListener("change", function () { form.submit(); });
        }
    }

    function initMobileFilterToggle() {
        // Capture phase + delegation: this Odoo build has several other
        // document-level click listeners registered with useCapture:true that
        // can stop propagation before a normal (bubble-phase) listener ever
        // sees the click, so bind ours in the capture phase too.
        document.addEventListener("click", function (ev) {
            var toggle = ev.target.closest("#uikick-filter-toggle");
            if (!toggle) return;
            var sidebar = document.getElementById("uikick-filter-form");
            if (!sidebar) return;
            var isOpen = sidebar.classList.toggle("is-open");
            toggle.classList.toggle("is-open", isOpen);
        }, true);
    }

    function onReady(fn) {
        // This bundle can load lazily, after DOMContentLoaded has already
        // fired — listening for that event at that point would never call
        // fn again. Run immediately if the DOM is already parsed.
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", fn);
        } else {
            fn();
        }
    }

    onReady(function () {
        if (!document.querySelector(".uikick-grid")) return; // chỉ chạy trên trang home
        initCardVideos();
        initFilterForm();
        initMobileFilterToggle();
    });
})();
