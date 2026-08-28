# Tài liệu hướng dẫn sử dụng — Hệ thống Chọn Giảng viên hướng dẫn (EAUT Showcase)

Tài liệu này hướng dẫn sử dụng chức năng **Chọn giảng viên hướng dẫn (GVHD)** đồ án trong module *EAUT Showcase*, dành cho 3 nhóm người dùng:

1. **Admin** — quản trị viên hệ thống (nhân sự phòng đào tạo/khoa, tài khoản backend Odoo).
2. **Giảng viên** — người hướng dẫn đồ án, sử dụng qua Cổng thông tin (Portal).
3. **Sinh viên** — người chọn giảng viên hướng dẫn, sử dụng qua Cổng thông tin (Portal) và trang web công khai.

> Ghi chú thuật ngữ: "GVHD" = Giảng viên hướng dẫn. "Kỳ đồ án" (Term) là một đợt đăng ký chọn GVHD (ví dụ: "Đồ án tốt nghiệp — HK2 2025-2026"). "Nguyện vọng" là một lựa chọn giảng viên mà sinh viên đưa vào danh sách ưu tiên của mình.

---

## 0. Tổng quan luồng nghiệp vụ

```
Admin tạo "Kỳ đồ án" → Mở đăng ký
        │
        ├─► Admin/Giảng viên thiết lập "sức chứa" (số SV tối đa) của từng giảng viên trong kỳ
        │
        ▼
Sinh viên hoàn thiện hồ sơ (MSSV/Lớp/Ngành) → chọn tối đa N giảng viên,
xếp theo thứ tự ưu tiên (nguyện vọng 1, 2, 3...) → Nộp nguyện vọng
        │
        ▼
Hệ thống tự động gửi nguyện vọng #1 cho giảng viên tương ứng (kèm hạn phản hồi)
        │
        ├─ Giảng viên DUYỆT ──────────► Sinh viên có GVHD (hoàn tất)
        │
        └─ Giảng viên TỪ CHỐI / hết hạn không phản hồi
                 │
                 ▼
        Hệ thống tự động chuyển sang nguyện vọng kế tiếp
                 │
                 └─ Hết cả danh sách nguyện vọng mà không ai duyệt
                          │
                          ▼
                 Sinh viên ở trạng thái "Chưa có GVHD"
                 → Admin gán tay (kéo-thả) hoặc cho sinh viên "chọn lại từ đầu"
        │
        ▼
Admin "Chốt danh sách" → "Đóng kỳ" khi hoàn tất
```

Mọi thay đổi trạng thái quan trọng đều được **email tự động** thông báo cho người liên quan (sinh viên hoặc giảng viên).

---

# PHẦN 1 — HƯỚNG DẪN CHO ADMIN (Quản trị hệ thống)

Admin là người dùng nội bộ Odoo thuộc nhóm quyền **Cài đặt/Hệ thống (Settings)**, truy cập qua giao diện backend (không phải Cổng thông tin/Portal).

## 1.1. Truy cập module

Sau khi đăng nhập backend Odoo, chọn ứng dụng **"Eaut Showcase"** trên thanh menu. Menu gồm:

```
Eaut Showcase
├── Tác giả                    → Danh sách giảng viên/tác giả
├── Danh mục                   → Danh mục/lĩnh vực dùng chung
├── Cấu hình dự án             → (Dự án, Người quan tâm, Bình luận, Trạng thái — thuộc website showcase, không thuộc phần chọn GVHD)
└── Cấu hình đồ án
    ├── Kỳ đồ án                        → Quản lý các đợt đăng ký chọn GVHD
    ├── Đăng ký chọn GVHD               → Xem toàn bộ hồ sơ đăng ký của sinh viên
    ├── Phân bổ sinh viên cho giảng viên → Bảng Kanban gán/chuyển sinh viên
    └── Phân bổ giảng viên theo kỳ       → Bảng Kanban thêm giảng viên vào kỳ
```

## 1.2. Bước 1 — Tạo tài khoản Portal cho giảng viên

Trước khi giảng viên có thể tham gia hệ thống, họ cần một tài khoản Cổng thông tin (Portal).

1. Vào **Eaut Showcase → Tác giả**, tạo mới hoặc mở hồ sơ giảng viên (nhập Tên, Email liên hệ, Vai trò, Lĩnh vực...).
2. Nếu trường **"Tài khoản Portal"** đang trống, form sẽ hiện nút **"Tạo tài khoản người dùng"**. Bấm nút này để hệ thống tự tạo/gán tài khoản Portal theo email đã nhập và gửi email mời đăng nhập cho giảng viên.
3. Sau khi tạo, trường "Tài khoản Portal" sẽ hiển thị tài khoản Odoo liên kết với hồ sơ giảng viên này.

> Lưu ý: Nếu sau này giảng viên tự đổi **Tên** hoặc **Email** trong hồ sơ Portal của họ, hệ thống sẽ tự đồng bộ hai chiều với tài khoản Odoo (kể cả tên đăng nhập). Nếu email trùng với một tài khoản đăng nhập khác đang tồn tại, hệ thống sẽ báo lỗi và không cho lưu.

## 1.3. Bước 2 — Tạo "Kỳ đồ án" và mở đăng ký

1. Vào **Cấu hình đồ án → Kỳ đồ án**, bấm **Mới**.
2. Nhập:
   - **Tên kỳ** (ví dụ: "Đồ án tốt nghiệp — HK2 2025-2026").
   - **Ngày mở đăng ký / Ngày đóng đăng ký** (chỉ mang tính thông tin tham khảo — việc mở/đóng thực tế do Admin bấm nút trạng thái, không tự động theo ngày).
   - **Hạn phản hồi của giảng viên (giờ)**: số giờ tối đa để một giảng viên phản hồi (duyệt/từ chối) một yêu cầu trước khi hệ thống tự động chuyển sang nguyện vọng kế tiếp. Mặc định 24 giờ.
   - **Số nguyện vọng tối đa/sinh viên**: số giảng viên tối đa mà mỗi sinh viên được phép đưa vào danh sách ưu tiên. Mặc định 5.
3. (Tuỳ chọn) Tab **"Sinh viên đủ điều kiện"**: nếu chỉ muốn một danh sách sinh viên cụ thể được tham gia kỳ này (ví dụ mỗi khoa chạy một kỳ riêng), thêm danh sách sinh viên vào đây. Để trống nghĩa là **mọi** sinh viên Portal đều thấy và đăng ký được kỳ này.
4. Bấm nút **"Mở đăng ký"** trên thanh trạng thái (draft → open) để sinh viên bắt đầu thấy và thao tác được.

Thanh trạng thái của Kỳ đồ án: **Nháp → Đang mở → Chốt danh sách → Đã đóng**.

## 1.4. Bước 3 — Thêm giảng viên vào kỳ (thiết lập sức chứa)

Có 2 cách:

**Cách A — Admin chủ động thêm (nhanh, cho toàn bộ danh sách):**
Vào **Cấu hình đồ án → Phân bổ giảng viên theo kỳ**, đây là bảng Kanban các cột theo từng Kỳ đồ án. Kéo thả thẻ giảng viên vào cột kỳ tương ứng — hệ thống tự tạo bản ghi "sức chứa" với số lượng mặc định là 1 sinh viên (có thể sửa lại sau).

**Cách B — Giảng viên tự đăng ký (cần Admin duyệt):**
Giảng viên có thể tự bấm "Đăng ký nhận hướng dẫn" trên Portal của họ (xem Phần 2). Yêu cầu này sẽ **không có hiệu lực ngay** — Admin cần vào duyệt.

Để duyệt/từ chối các yêu cầu tự đăng ký của giảng viên: mở **Kỳ đồ án** cần xử lý → tab **"Giảng viên nhận hướng dẫn"**. Mỗi dòng giảng viên có yêu cầu đang chờ sẽ hiện badge trạng thái:
- **Chờ duyệt tham gia** — giảng viên muốn tham gia/tham gia lại kỳ này.
- **Chờ duyệt rút** — giảng viên muốn rút khỏi kỳ.
- **Chờ duyệt đổi số lượng** — giảng viên muốn tăng/giảm số sinh viên tối đa nhận hướng dẫn.

Với mỗi dòng đang chờ, bấm **"Duyệt yêu cầu"** để áp dụng thay đổi, hoặc **"Từ chối yêu cầu"** để huỷ bỏ (giữ nguyên trạng thái cũ).

> Hệ thống sẽ tự tạo một **hoạt động nhắc việc (activity)** trên bản ghi Kỳ đồ án cho các tài khoản thuộc nhóm quyền Hệ thống, với nội dung "Có N yêu cầu từ giảng viên đang chờ duyệt" — Admin nên theo dõi hoạt động này để không bỏ sót yêu cầu.

Ngoài ra Admin cũng có thể **sửa trực tiếp** số "Số sinh viên tối đa" hoặc bấm **"Rút khỏi kỳ"** ngay trong bảng — các thao tác Admin làm trực tiếp có hiệu lực ngay, không cần bước duyệt.

## 1.5. Theo dõi & xử lý trong lúc kỳ đang mở

**Xem toàn bộ hồ sơ đăng ký:** vào **Đăng ký chọn GVHD** để xem danh sách tất cả sinh viên cùng trạng thái: *Chưa nộp* / *Đang xét* / *Đã có GVHD* / *Chưa có GVHD*.

**Gán/chuyển sinh viên bằng kéo-thả:** vào **Phân bổ sinh viên cho giảng viên** — bảng Kanban nhóm theo giảng viên đang phụ trách, mặc định chỉ hiển thị các sinh viên **"Chưa gán"**. Admin có thể:
- Kéo một thẻ sinh viên sang cột của giảng viên khác để **gán trực tiếp** (hệ thống tự kiểm tra sĩ số còn trống của giảng viên đích trước khi cho gán).
- Bấm **"Bỏ gán"** trên thẻ để đưa sinh viên về lại trạng thái chưa gán (không phải Admin thao tác bằng cách xoá).

**Cho sinh viên chọn lại từ đầu:** khi một sinh viên đã nộp nguyện vọng nhưng bị **tất cả** giảng viên trong danh sách từ chối/hết hạn (trạng thái "Chưa có GVHD"), mở hồ sơ đăng ký của sinh viên đó, bấm nút **"Cho SV chọn lại"** (chỉ hiện khi sinh viên thực sự cần chọn lại). Hệ thống sẽ xoá toàn bộ nguyện vọng cũ, đưa hồ sơ về trạng thái "Chưa nộp" và gửi email báo sinh viên quay lại Portal để chọn lại từ đầu.

> Nếu một giảng viên **rút khỏi kỳ** (dù do Admin duyệt hay Admin thao tác trực tiếp) trong khi đang có sinh viên chờ/đã được giảng viên đó duyệt, hệ thống sẽ **tự động** đưa các sinh viên bị ảnh hưởng về trạng thái "Chưa nộp" và gửi email yêu cầu họ chọn lại giảng viên khác — Admin không cần thao tác thủ công cho từng sinh viên.

## 1.6. Chốt danh sách và Đóng kỳ

- **Chốt danh sách** (open → locked): dừng việc sinh viên nộp mới và giảng viên rút khỏi kỳ, nhưng trang giới thiệu giảng viên vẫn hiển thị công khai. Dùng khi muốn "khoá" số liệu để rà soát trước khi đóng hẳn.
- **Đóng kỳ** (locked → closed): ẩn danh sách giảng viên của kỳ này khỏi trang web công khai. Nếu vẫn còn sinh viên **"Chưa có GVHD"**, hệ thống sẽ hiện **hộp thoại cảnh báo**: *"Kỳ này vẫn còn N sinh viên chưa được gán giảng viên hướng dẫn. Bạn có chắc muốn đóng kỳ không?"* — Admin có thể vào "Phân bổ sinh viên cho giảng viên" để gán tay trước, hoặc xác nhận đóng kỳ luôn.
- **Chuyển về nháp** (closed → draft): dùng nếu cần mở lại một kỳ đã đóng để chỉnh sửa.

## 1.7. Quản lý dữ liệu dùng chung

- **Danh mục** (`Eaut Showcase → Danh mục`): các lĩnh vực dùng để gắn thẻ cho cả giảng viên (Lĩnh vực) và dự án showcase. Danh sách chỉnh sửa trực tiếp (tên, màu, thứ tự).
- **Trạng thái**: chỉ dùng cho phần dự án showcase (không ảnh hưởng đến luồng chọn GVHD).

## 1.8. Bảng trạng thái tham khảo (dành cho Admin)

**Hồ sơ đăng ký của sinh viên** (`eaut_showcase.advisor.registration`):

| Trạng thái | Ý nghĩa |
|---|---|
| Chưa nộp (draft) | Sinh viên chưa nộp hoặc đang xây dựng hàng chờ nguyện vọng |
| Đang xét (in_progress) | Đã nộp, đang chờ giảng viên phản hồi nguyện vọng hiện tại |
| Đã có GVHD (approved) | Một giảng viên đã duyệt |
| Chưa có GVHD (unassigned) | Đã hết tất cả nguyện vọng mà không ai duyệt — cần Admin xử lý |

**Từng nguyện vọng (dòng)** (`eaut_showcase.advisor.registration.line`):

| Trạng thái | Ý nghĩa |
|---|---|
| Trong hàng chờ (cart) | Sinh viên đang thêm, chưa nộp |
| Chờ kích hoạt (waiting) | Đã nộp nhưng đứng sau nguyện vọng khác đang được xử lý |
| Đang chờ giảng viên duyệt (pending) | Đã gửi cho giảng viên, còn hạn phản hồi |
| Đã duyệt (approved) | Giảng viên đồng ý nhận hướng dẫn |
| Bị từ chối (rejected) | Giảng viên từ chối |
| Hết hạn phản hồi (expired) | Giảng viên không phản hồi trong hạn |
| Đã huỷ (cancelled) | Bị huỷ do một nguyện vọng khác đã được duyệt, hoặc do Admin bỏ gán/giảng viên rút khỏi kỳ |

## 1.9. Tác vụ tự động chạy nền (không cần Admin can thiệp)

Hệ thống có 2 tác vụ tự động chạy **mỗi giờ**:
1. Tự động chuyển các yêu cầu **quá hạn phản hồi** của giảng viên sang trạng thái "Hết hạn" và chuyển tiếp cho nguyện vọng kế tiếp của sinh viên.
2. Tự động gửi email **nhắc giảng viên** khi một yêu cầu đang chờ họ còn dưới 6 giờ là hết hạn.

Do chạy theo giờ, có thể có độ trễ tối đa ~1 giờ trước khi một yêu cầu quá hạn được đánh dấu chính thức trong backend (tuy nhiên khi giảng viên tự mở trang duyệt yêu cầu trên Portal, hệ thống sẽ kiểm tra và cập nhật hạn ngay lập tức, nên giảng viên sẽ không bao giờ thấy nút Duyệt/Từ chối cho một yêu cầu thực chất đã hết hạn).

---

# PHẦN 2 — HƯỚNG DẪN CHO GIẢNG VIÊN

Giảng viên sử dụng hệ thống qua **Cổng thông tin (Portal)** bằng tài khoản do Admin cấp (xem mục 1.2). Không cần quyền truy cập backend.

## 2.1. Đăng nhập

1. Truy cập trang đăng nhập Portal bằng đường link/email mời mà Admin đã gửi, đặt mật khẩu lần đầu.
2. Sau khi đăng nhập, vào **"Tài khoản của tôi"** (`/my/home`) — sẽ thấy thẻ **"Quản lý sinh viên hướng dẫn"**, bấm vào để vào trang quản lý yêu cầu (`/my/advisor-requests`).

## 2.2. Hoàn thiện hồ sơ giảng viên

Bấm liên kết **"Hồ sơ của tôi"** ở góc trang quản lý yêu cầu để vào form chỉnh sửa hồ sơ công khai của mình:

- **Ảnh đại diện**
- **Tên hiển thị** — *lưu ý: đổi tên ở đây sẽ cập nhật luôn tên tài khoản Odoo của bạn.*
- **Email liên hệ** — *lưu ý: đây cũng là email dùng để đăng nhập; đổi ở đây sẽ đổi luôn tên đăng nhập, lần sau phải đăng nhập bằng email mới.*
- **Vai trò**, **Website / mạng xã hội**
- **Lĩnh vực** (chọn các danh mục phù hợp để sinh viên dễ tìm)
- **Giới thiệu** — mô tả bản thân (có trình soạn thảo định dạng: đậm/nghiêng/gạch chân/danh sách/liên kết)
- **Đề tài gợi ý** — gợi ý các hướng đề tài mà bạn sẵn sàng hướng dẫn, hiển thị công khai trên trang cá nhân để sinh viên tham khảo trước khi chọn.

Bấm **"Lưu hồ sơ"** để hoàn tất.

## 2.3. Đăng ký nhận hướng dẫn trong một kỳ đồ án (tab "Quản lý số lượng nhận hướng dẫn")

Tại trang `/my/advisor-requests`, chọn tab **"Quản lý số lượng nhận hướng dẫn"**. Với mỗi kỳ đồ án đang mở:

- **Nếu chưa tham gia:** nhập số sinh viên tối đa muốn nhận, bấm **"Đăng ký nhận hướng dẫn"**.
- **Nếu muốn đổi số lượng:** nhập số mới, bấm **"Gửi yêu cầu đổi"**.
- **Nếu muốn ngừng nhận sinh viên trong kỳ:** bấm **"Rút khỏi kỳ"**.
- **Nếu muốn huỷ một yêu cầu vừa gửi (chưa được Admin xử lý):** bấm **"Huỷ yêu cầu"**.

> **Quan trọng:** Mọi thao tác trên đều chỉ là **gửi yêu cầu** — cần **Admin duyệt** trong backend thì mới thật sự có hiệu lực (số lượng cũ vẫn giữ nguyên cho đến khi được duyệt). Khi đang chờ duyệt yêu cầu rút, bạn **vẫn tiếp tục nhận sinh viên bình thường** cho đến khi yêu cầu được Admin duyệt.

## 2.4. Duyệt / từ chối yêu cầu từ sinh viên

Khi có sinh viên chọn bạn làm nguyện vọng và đến lượt nguyện vọng đó được kích hoạt, bạn sẽ nhận được **email "Yêu cầu mới"**, đồng thời yêu cầu xuất hiện ở tab **"Đang chờ"** trên trang `/my/advisor-requests`, kèm đồng hồ đếm ngược hạn phản hồi.

Bạn có hai cách xử lý:

- **Duyệt nhanh ngay trong bảng danh sách:** bấm nút **"Duyệt"** ở dòng tương ứng.
- **Xem chi tiết trước khi quyết định:** bấm **"Chi tiết"** để mở trang riêng, xem đầy đủ thông tin sinh viên (họ tên, ảnh, MSSV/Lớp/Ngành, email, số điện thoại), **đề tài dự kiến** và **lời giới thiệu bản thân** sinh viên viết cho bạn. Tại đây có 2 lựa chọn:
  - Bấm **"Duyệt"** để đồng ý nhận hướng dẫn sinh viên này.
  - Bấm **"Từ chối"**, có thể ghi thêm **lý do từ chối** (không bắt buộc, sinh viên sẽ nhìn thấy lý do này).

Kết quả:
- Nếu **Duyệt**: sinh viên chính thức thuộc về bạn, mọi nguyện vọng khác của sinh viên đó (đến giảng viên khác) sẽ tự động bị huỷ. Sinh viên nhận email chúc mừng.
- Nếu **Từ chối** hoặc để **hết hạn không phản hồi**: hệ thống tự động chuyển yêu cầu sang nguyện vọng kế tiếp của sinh viên (nếu còn), sinh viên nhận email thông báo đang được chuyển sang giảng viên khác.

> Lưu ý: nếu bạn để yêu cầu quá hạn phản hồi (mặc định 24 giờ, hoặc theo cấu hình của kỳ), hệ thống sẽ tự động đánh dấu "Hết hạn phản hồi" và bạn sẽ không còn thấy nút Duyệt/Từ chối cho yêu cầu đó nữa. Nếu còn dưới 6 giờ là hết hạn, bạn sẽ nhận thêm một email nhắc nhở.

## 2.5. Theo dõi sinh viên đang hướng dẫn và lịch sử

- Tab **"Đang hướng dẫn"**: danh sách sinh viên bạn đã duyệt (tên, MSSV/Lớp/Ngành, ngày duyệt).
- Tab **"Lịch sử"**: các yêu cầu đã kết thúc không thành (bị từ chối bởi chính bạn, hết hạn, hoặc bị huỷ) — có thể lọc theo từng kỳ đồ án.

---

# PHẦN 3 — HƯỚNG DẪN CHO SINH VIÊN

Sinh viên sử dụng hệ thống qua **Cổng thông tin (Portal)** và trang web công khai (không cần cài đặt gì thêm).

## 3.1. Đăng nhập và hoàn thiện hồ sơ

1. Đăng nhập Portal bằng tài khoản sinh viên được cấp.
2. Vào **"Tài khoản của tôi"** → bấm thẻ **"Chọn giảng viên hướng dẫn đồ án"** để vào trang `/my/advisor`.
3. Nếu là lần đầu sử dụng, hệ thống sẽ yêu cầu hoàn thiện hồ sơ trước khi cho chọn giảng viên: nhập **MSSV**, **Lớp**, **Ngành học**, sau đó bấm **"Lưu hồ sơ"**.

> Nếu trang báo *"Hiện không có kỳ đồ án nào đang mở đăng ký"*, nghĩa là Nhà trường/Khoa chưa mở đợt đăng ký chọn GVHD, hoặc bạn không thuộc danh sách sinh viên đủ điều kiện của kỳ hiện có — hãy liên hệ Admin/khoa để được xác nhận.

## 3.2. Tìm hiểu và chọn giảng viên

Trước khi chọn, bạn nên tham khảo trang giới thiệu giảng viên trên trang web công khai (mục **Khám phá → Giảng viên hướng dẫn đồ án**, hoặc `/showcase?section=advisors`):

- Có thể lọc theo **Kỳ đồ án**, **Danh mục/Lĩnh vực**, và **Trạng thái nhận SV** (*Còn nhận* / *Đã đầy*).
- Sắp xếp theo *Liên quan*, *Còn nhiều chỗ nhất*, hoặc *Mới thêm gần đây*.
- Bấm vào một giảng viên để xem trang chi tiết: giới thiệu bản thân, **đề tài gợi ý**, các **đề tài đã từng hướng dẫn** trước đây, số chỗ còn trống, email/website liên hệ.
- Nếu giảng viên còn chỗ trống và bạn thuộc kỳ đang mở, sẽ thấy nút **"Chọn làm giảng viên hướng dẫn"** — bấm vào sẽ đưa bạn tới trang `/my/advisor` để thêm giảng viên đó vào hàng chờ nguyện vọng.

## 3.3. Xây dựng hàng chờ nguyện vọng

Tại trang `/my/advisor`, khi hồ sơ đăng ký còn ở trạng thái **chưa nộp**, bạn sẽ thấy khu vực **"Hàng chờ nguyện vọng"** (tối đa theo số lượng do Admin cấu hình, ví dụ 5):

1. Ở phần **"Thêm giảng viên vào hàng chờ"**: chọn 1 giảng viên từ danh sách (hiển thị kèm số chỗ còn trống), điền **Đề tài dự kiến** (nếu có), viết vài dòng **giới thiệu bản thân với thầy/cô** đó, rồi bấm **"Thêm vào hàng chờ"**.
2. Lặp lại để thêm nhiều giảng viên khác (theo thứ tự bạn ưu tiên nhất trước).
3. Trong bảng hàng chờ, dùng nút **↑ / ↓** để **sắp xếp lại thứ tự ưu tiên**, hoặc **"Xoá"** để bỏ một giảng viên khỏi danh sách.
4. Không thể chọn trùng một giảng viên hai lần, và không thể thêm giảng viên đã hết chỗ hoặc đã rút khỏi kỳ.

## 3.4. Nộp nguyện vọng

Khi đã sắp xếp xong thứ tự ưu tiên, bấm **"Nộp nguyện vọng"** và xác nhận trong hộp thoại.

> **Rất quan trọng:** Sau khi nộp, bạn **không thể sửa hoặc nộp lại** hàng chờ nữa. Hãy kiểm tra kỹ thứ tự ưu tiên trước khi bấm nộp.

Sau khi nộp, hệ thống sẽ:
1. Tự động gửi **nguyện vọng số 1** cho giảng viên tương ứng để họ xét duyệt.
2. Các nguyện vọng còn lại (2, 3, ...) sẽ **tự động lần lượt được kích hoạt** — chỉ khi nguyện vọng phía trước bị từ chối hoặc hết hạn phản hồi — cho đến khi có một giảng viên duyệt, hoặc hết danh sách.

Trang `/my/advisor` từ lúc này sẽ chuyển sang chế độ chỉ xem, hiển thị bảng trạng thái từng nguyện vọng:

| Trạng thái hiển thị | Ý nghĩa |
|---|---|
| Chờ kích hoạt | Chưa tới lượt (đứng sau nguyện vọng khác) |
| Đang chờ duyệt | Đã gửi tới giảng viên, đang chờ phản hồi |
| Đã duyệt | Giảng viên đã đồng ý nhận hướng dẫn bạn |
| Bị từ chối | Giảng viên từ chối (có thể kèm lý do) |
| Hết hạn phản hồi | Giảng viên không phản hồi trong thời hạn |
| Đã huỷ | Không còn cần xét (do một nguyện vọng khác đã được duyệt) |

## 3.5. Theo dõi kết quả

Bạn sẽ nhận **email thông báo** ở mỗi bước quan trọng, đồng thời có thể quay lại `/my/advisor` bất cứ lúc nào để xem trạng thái mới nhất:

- **Có giảng viên duyệt:** trang hiển thị "Bạn đã có giảng viên hướng dẫn: <tên giảng viên>." — hoàn tất, không cần làm gì thêm.
- **Đang xử lý:** trang hiển thị nguyện vọng nào đang được xét, các nguyện vọng còn lại sẽ tự động được thử tiếp nếu cần — bạn chỉ cần chờ, không cần thao tác gì.
- **Không giảng viên nào duyệt (hết nguyện vọng):** trang hiển thị "Chưa có GVHD" và thông báo Nhà trường sẽ liên hệ để phân giảng viên hướng dẫn cho bạn. Trong trường hợp này Admin có thể chủ động gán một giảng viên cho bạn, hoặc **cho phép bạn chọn lại từ đầu** — nếu được cho chọn lại, bạn sẽ nhận email thông báo và có thể quay lại `/my/advisor` để xây dựng một hàng chờ nguyện vọng mới hoàn toàn.
- **Giảng viên bạn đang chờ/đã được duyệt bất ngờ rút khỏi kỳ:** hệ thống sẽ tự động đưa hồ sơ của bạn về trạng thái ban đầu và gửi email yêu cầu bạn chọn lại giảng viên khác.

---

## Phụ lục — Câu hỏi thường gặp

**Sinh viên có sửa được nguyện vọng sau khi nộp không?**
Không. Hàng chờ chỉ chỉnh sửa được trước khi nhấn "Nộp nguyện vọng". Sau khi nộp, chỉ có Admin mới có thể cho phép chọn lại (xoá toàn bộ và làm lại từ đầu), áp dụng khi cả danh sách đã bị từ chối/hết hạn.

**Một tài khoản vừa là giảng viên vừa là sinh viên được không?**
Không. Nếu một tài khoản đã được gắn với hồ sơ giảng viên, hệ thống sẽ chặn tài khoản đó sử dụng chức năng chọn GVHD dành cho sinh viên.

**Giảng viên tự thêm/bớt số lượng sinh viên nhận hướng dẫn có hiệu lực ngay không?**
Không, luôn cần Admin duyệt trong backend (trừ khi chính Admin là người sửa trực tiếp).

**Vì sao một yêu cầu tôi định duyệt lại không còn nút Duyệt/Từ chối?**
Yêu cầu đó đã quá hạn phản hồi và tự động chuyển sang nguyện vọng kế tiếp của sinh viên.

**Đóng một kỳ đồ án còn sinh viên chưa có GVHD thì sao?**
Hệ thống sẽ cảnh báo trước khi cho đóng. Admin nên xử lý (gán tay hoặc cho chọn lại) trước khi đóng kỳ hẳn.