/** Portal giảng viên - đếm ngược "Hạn phản hồi" cho dễ nhìn hơn ngày/giờ thô. */
(function () {
    "use strict";

    function formatRemaining(ms) {
        if (ms <= 0) {
            return "Đã hết hạn";
        }
         // Gộp hết vào giờ (kể cả khi hơn 1 ngày) + phút, không hiện giây —
        // đỡ rối mắt hơn so với đếm ngược đủ ngày/giờ/phút/giây.
        var totalMinutes = Math.floor(ms / 60000);
        var hours = Math.floor(totalMinutes / 60);
        var minutes = totalMinutes % 60;
        return "Còn " + hours + " giờ " + minutes + " phút";
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
         setInterval(tick, 30000);
    });
})();