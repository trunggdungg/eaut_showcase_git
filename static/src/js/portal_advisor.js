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

    /** Modal xác nhận tự dựng (thay cho window.confirm() mặc định của trình
     * duyệt, hiện dạng "localhost:8069 cho biết" xấu và không style được) —
     * chỉ dùng HTML/CSS/JS thuần, không phụ thuộc API nào của Odoo. */
    function initConfirmForms() {
        var overlay = document.getElementById("uikick-confirm-overlay");
        if (!overlay) {
            return;
        }
        var messageEl = document.getElementById("uikick-confirm-message");
        var okBtn = document.getElementById("uikick-confirm-ok");
        var cancelBtn = document.getElementById("uikick-confirm-cancel");
        var pendingForm = null;

        function close() {
            overlay.style.display = "none";
            pendingForm = null;
        }

        document.querySelectorAll(".uikick-confirm-form").forEach(function (form) {
            form.addEventListener("submit", function (ev) {
                if (form.dataset.confirmed === "1") {
                    return;
                }
                ev.preventDefault();
                pendingForm = form;
                messageEl.textContent = form.dataset.confirmMessage || "Bạn có chắc chắn?";
                overlay.style.display = "flex";
            });
        });

        okBtn.addEventListener("click", function () {
            var form = pendingForm;
            close();
            if (form) {
                form.dataset.confirmed = "1";
                form.submit();
            }
        });
        cancelBtn.addEventListener("click", close);
        overlay.addEventListener("click", function (ev) {
            if (ev.target === overlay) {
                close();
            }
        });
    }

    /** Toolbar định dạng gọn nhẹ kiểu Word (Đậm/Nghiêng/Danh sách/Link...)
     * cho các ô Html trên Portal (Giới thiệu, Đề tài gợi ý) — dùng
     * document.execCommand trên 1 div contenteditable, không phụ thuộc
     * trình soạn thảo web_editor của Odoo (tránh rủi ro khác bản Odoo, và
     * không cần thêm asset bundle nào). Textarea cùng tên field vẫn được
     * giữ (ẩn) để form submit HTML ra đúng như cũ, controller không cần
     * đổi gì. */
    function initRichEditors() {
        document.querySelectorAll(".uikick-rich-editor[contenteditable]").forEach(function (editor) {
            var hidden = document.getElementById(editor.id.replace(/_editor$/, ""));
            if (!hidden) {
                return;
            }
            var toolbar = document.querySelector('.uikick-richtoolbar[data-target="' + editor.id + '"]');

             // Nội dung HTML ban đầu được đưa qua attribute data-content (QWeb
            // t-att-* tự escape đúng chuẩn HTML attribute) thay vì để QWeb
            // chèn thẳng HTML vào giữa thẻ — tránh phụ thuộc t-out/t-raw,
            // vốn không hiển thị đúng trên bản Odoo đang dùng.
            if (editor.dataset.content) {
                editor.innerHTML = editor.dataset.content;
            }

            function syncHidden() {
                hidden.value = editor.innerHTML;
            }

            if (toolbar) {
                toolbar.querySelectorAll("button[data-cmd]").forEach(function (btn) {
                    btn.addEventListener("click", function () {
                        var cmd = btn.dataset.cmd;
                        editor.focus();
                        if (cmd === "createLink") {
                            var url = window.prompt("Nhập URL:");
                            if (!url) {
                                return;
                            }
                            document.execCommand(cmd, false, url);
                        } else {
                            document.execCommand(cmd, false, null);
                        }
                        syncHidden();
                    });
                });
            }
            editor.addEventListener("input", syncHidden);
            editor.closest("form").addEventListener("submit", syncHidden);
            syncHidden();
        });
    }

    /** Bootstrap tab tự reset về tab "active" hardcode trong HTML mỗi khi
     * trang load lại (F5/redirect sau khi submit form) — không nhớ tab
     * người dùng đang đứng. Đọc query string ?tab=<id> (id không có tiền tố
     * "tab-") rồi giả lập click đúng nút đó, tận dụng luôn event listener
     * Bootstrap đã gắn sẵn (không cần đụng tới API bootstrap.Tab trực
     * tiếp — không chắc chắn nó có lộ ra window hay không). */
    function restoreActiveTab() {
        var params = new URLSearchParams(window.location.search);
        var tab = params.get("tab");
        if (!tab) {
            return;
        }
        var btn = document.querySelector('[data-bs-toggle="tab"][data-bs-target="#tab-' + tab + '"]');
        if (btn) {
            btn.click();
        }
    }


    /** Popup tóm tắt kết quả nộp nguyện vọng — chỉ render khi vừa nộp xong
     * (?submitted=1), tự hiện sẵn qua CSS (server chỉ render div này khi
     * cần), JS ở đây chỉ lo đóng lại (nút "Đóng" hoặc bấm ra ngoài). */
    function initOutcomeOverlay() {
        var overlay = document.getElementById("uikick-outcome-overlay");
        var closeBtn = document.getElementById("uikick-outcome-overlay-close");
        if (!overlay || !closeBtn) {
            return;
        }
        function close() {
            overlay.style.display = "none";
        }
        closeBtn.addEventListener("click", close);
        overlay.addEventListener("click", function (ev) {
            if (ev.target === overlay) {
                close();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        initConfirmForms();
        initRichEditors();
        initOutcomeOverlay();
        restoreActiveTab();
        if (!document.querySelector(".uikick-countdown[data-deadline]")) {
            return;
        }
        tick();
        setInterval(tick, 30000);
    });
})();