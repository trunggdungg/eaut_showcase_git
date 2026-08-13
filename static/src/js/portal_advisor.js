/** Portal giảng viên - đếm ngược "Hạn phản hồi" cho dễ nhìn hơn ngày/giờ thô. */
(function () {
    "use strict";

    function formatRemaining(ms) {
        if (ms <= 0) {
            return "Đã hết hạn";
        }
        var totalSeconds = Math.floor(ms / 1000);
        var days = Math.floor(totalSeconds / 86400);
        var hours = Math.floor((totalSeconds % 86400) / 3600);
        var minutes = Math.floor((totalSeconds % 3600) / 60);
        var seconds = totalSeconds % 60;
        var parts = [];
        if (days > 0) {
            parts.push(days + " ngày");
        }
        parts.push(hours + " giờ", minutes + " phút", seconds + " giây");
        return "Còn " + parts.join(" ");
    }

    function tick() {
        document.querySelectorAll(".uikick-countdown[data-deadline]").forEach(function (el) {
            var deadline = new Date(el.dataset.deadline).getTime();
            var remaining = deadline - Date.now();
            el.textContent = formatRemaining(remaining);
            el.classList.toggle("text-danger", remaining <= 0);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        if (!document.querySelector(".uikick-countdown[data-deadline]")) {
            return;
        }
        tick();
        setInterval(tick, 1000);
    });
})();
