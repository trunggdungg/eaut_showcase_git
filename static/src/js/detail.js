/** UIKick - Campaign detail page interactions */
(function () {
    "use strict";

    function initTabs() {
        var tabs = document.querySelectorAll(".uikick-tab");
        var contents = document.querySelectorAll(".uikick-tab-content");
        if (!tabs.length || !contents.length) return;

        tabs.forEach(function (tab) {
            tab.addEventListener("click", function (ev) {
                ev.preventDefault();
                var target = tab.getAttribute("data-tab");

                tabs.forEach(function (t) { t.classList.remove("active"); });
                tab.classList.add("active");

                contents.forEach(function (content) {
                    content.classList.toggle("active", content.getAttribute("data-tab") === target);
                });
            });
        });
    }

    function initHeroVideo() {
        var hero = document.getElementById("uikick-hero-video");
        if (!hero) return;
        var video = hero.querySelector(".uikick-hero-video-el");
        var playOverlay = hero.querySelector(".uikick-hero-play-overlay");
        if (!video || !playOverlay) return;

        // Overlay chỉ dùng để bắt đầu phát lần đầu (che thumbnail). Sau khi đã
        // phát, overlay biến mất vĩnh viễn (class has-played) để không che
        // thanh điều khiển gốc của video (tua, âm lượng, play/pause...).
        playOverlay.addEventListener("click", function () {
            video.play().then(function () {
                hero.classList.add("is-playing", "has-played");
            }).catch(function () {
                /* autoplay blocked, ignore */
            });
        });

        video.addEventListener("play", function () { hero.classList.add("is-playing"); });
        video.addEventListener("pause", function () { hero.classList.remove("is-playing"); });
    }

    function initRemindMe() {
        var buttons = document.querySelectorAll(".uikick-remind-btn");
        if (!buttons.length) return;
        // var reminded = false;
        //
        // function render() {
        //     buttons.forEach(function (btn) {
        //         btn.classList.toggle("is-reminded", reminded);
        //         var label = btn.querySelector(".uikick-remind-label");
        //         if (label) label.textContent = reminded ? "Đã quan tâm!" : "Để lại thông tin";
        //     });
        // }

        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                // reminded = !reminded;
                // render();
                   var campaignTab = document.querySelector('.uikick-tab[data-tab="Campaign"]');
                if (campaignTab) campaignTab.click();

                var form = document.querySelector(".uikick-lead-form");
                if (!form) return;
                form.scrollIntoView({ behavior: "smooth", block: "start" });
                var firstField = form.querySelector("input, textarea");
                if (firstField) firstField.focus({ preventScroll: true });
            });
        });
    }
    function initDescriptionToc() {
        // Tự tách "Mô tả giới thiệu" (project.description) theo từng tiêu đề H2
        // thành các phần riêng, đồng thời sinh mục lục bên trái; click vào mục
        // nào thì chỉ hiện nội dung phần đó — không cần khai báo tay như trước.
        var content = document.getElementById("uikick-description-content");
        var tocNav = document.getElementById("uikick-toc-nav");
        if (!content || !tocNav) return;

        var children = Array.prototype.slice.call(content.children);
        var firstH2Index = children.findIndex(function (el) { return el.tagName === "H2"; });
        if (firstH2Index === -1) return; // Không dùng H2 nào -> hiển thị nguyên nội dung, không tách mục lục

        var sections = [];
        var current = null;
        children.slice(firstH2Index).forEach(function (el) {
            if (el.tagName === "H2") {
                current = { heading: el, nodes: [] };
                sections.push(current);
            } else if (current) {
                current.nodes.push(el);
            }
        });

        function activate(index) {
            content.querySelectorAll(".uikick-desc-section").forEach(function (section, i) {
                section.classList.toggle("active", i === index);
            });
            tocNav.querySelectorAll(".uikick-toc-item").forEach(function (link, i) {
                link.classList.toggle("active", i === index);
            });
        }

        sections.forEach(function (section, index) {
            var wrapper = document.createElement("div");
            wrapper.className = "uikick-desc-section";
            wrapper.appendChild(section.heading);
            section.nodes.forEach(function (node) { wrapper.appendChild(node); });
            content.appendChild(wrapper);

            var link = document.createElement("a");
            link.href = "#";
            link.className = "uikick-toc-item";
            link.textContent = section.heading.textContent.trim();
            link.addEventListener("click", function (ev) {
                ev.preventDefault();
                var campaignTab = document.querySelector('.uikick-tab[data-tab="Campaign"]');
                if (campaignTab && !campaignTab.classList.contains("active")) campaignTab.click();
                activate(index);
            });
            tocNav.appendChild(link);
        });

        tocNav.classList.add("has-items");
        activate(0);
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
        if (!document.querySelector(".uikick-detail")) return; // chỉ chạy trên trang detail
        initTabs();
        initHeroVideo();
        initDescriptionToc();
        initRemindMe();
    });
})();
