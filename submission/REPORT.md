# Báo cáo Day 09 — Giang Nguyễn Xuân Bách, 2A202603105


## 1. Kết luận trước
Pipeline kết luận: Hold

Số ảnh vào: 224 ảnh thô ban đầu.
Intake: Loại bỏ 21 ảnh hỏng, nhỏ, trùng và rò rỉ (3 BAD_SIZE, 2 CORRUPT_IMAGE, 8 DUP_IMAGE_EXACT, 3 DUP_IMAGE_NEAR, 5 LEAK_TEST), nhận 203/224 ảnh vào pipeline.
Số ảnh ra: 203 ảnh tại submission/export/clean_v1
Lý do : Pipeline đã sửa tự động an toàn toàn bộ lỗi bắt buộc (0 ERROR). Sau khi mô phỏng người duyệt 80 ảnh, vẫn còn 38 ảnh mang cảnh báo ngữ nghĩa chưa được xử lý. Tỉ lệ cảnh báo là 18.72% (38/203), vượt ngưỡng Hold 10.00%. Theo QC, lô dữ liệu phải Hold để người duyệt

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
| --- | ---: | --- | --- |
| BAD_SIZE | 3 ảnh | Máy (intake) | cạnh ngắn < 250px |
| CORRUPT_IMAGE | 2 ảnh | Máy (intake) | file hỏng không đọc được, máy tự loại bỏ |
| DUP_IMAGE_EXACT | 8 ảnh | Máy (intake) | Trùng từng byte (MD5), máy tự xoá ảnh trùng để tránh học lặp |
| DUP_IMAGE_NEAR | 3 ảnh | Máy (intake) | Trùng gần đúng qua pHash (khoảng cách <= 8), máy tự loại bỏ |
| LEAK_TEST | 5 ảnh | Máy (intake) | Trùng với kho test/val, máy tự xoá để tránh rò rỉ dữ liệu đánh giá |
| BAD_CLASS_NAME | 2 lỗi | Máy (autofix) | Tên lớp sai quy chuẩn trong data.yaml ('Person', 'Bus') |
| BAD_CLASS_ID | 6 dòng | Máy (autofix) | ID lớp ngoài dải 0..3 (ID -1, 4, 7, 93) |
| BAD_FORMAT | 3 dòng | Máy (autofix) | dòng nhãn lỗi NaN hoặc thiếu cột toạ đ |
| BOX_ZERO | 4 dòng | Máy (autofix) | box có w <= 0 hoặc h <= 0 |
| BOX_OUT_OF_IMAGE | 8 dòng | Máy (autofix) | Box tràn mép ảnh > 0.002, máy cắt toạ độ về [0, 1]  |
| DUP_BOX | 7 dòng | Máy (autofix) | Cùng lớp và IoU > 0.9 với box trước trong ảnh|
| MISSING_LABEL_FILE | 6 ảnh | Người (hàng đợi) | Ảnh không có file nhãn|
| POSSIBLE_WRONG_CLASS | 18 ảnh | Người (hàng đợi) | Model lớn nghi ngờ nhầm lớp (IoU >= 0.5 khác lớp) |
| POSSIBLE_MISSING | 53 ảnh | Người (hàng đợi) | Model lớn phát hiện vật mà nhãn thiếu |
| POSSIBLE_LOOSE_BOX | 28 ảnh | Người (hàng đợi) | Đúng vật nhưng IoU < 0.5 (box vẽ lỏng/lệch) |
| POSSIBLE_FALSE_POS | 29 ảnh | Người (hàng đợi) | Nhãn không khớp vật nào model thấy|
| EMPTY_LABEL | 12 ảnh | Người (hàng đợi) | File nhãn rỗng |
| BOX_TINY / BOX_HUGE | 9 dòng | Người (hàng đợi) | Box quá nhỏ (<12px) hoặc quá lớn (>95%)|
| CLASS_RARE | 4 lớp | Cảnh báo hệ thống | Lớp hiếm có ít box |




- Vì sao 05_review_queue.csv xếp ảnh đầu hàng như vậy: Hàng đợi sắp xếp theo độ ưu tiên theo trọng số, cao nhất được dành cho ảnh NEEDS_LABEL: trọng số 10 và ảnhFIXED_DROP_LINE: 2, POSSIBLE_WRONG_CLASS: 3, POSSIBLE_MISSING: 2.
- Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa: đã xử lý 6 ảnh thiếu file nhãn và duyệt 74 ảnh có cảnh báo ngữ nghĩa nặng nhất

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
| --- | --- | --- | --- | --- |
| `duplicates.phash_dist` | 2 | 8 | DUP_IMAGE_NEAR: 1.00 / 0.50 / 0.67 → 1.00 / 0.67 / 0.80 | Tăng từ 2 lên 8 giúp bắt thêm các ảnh gần trùng biến dạng nhẹ (Recall tăng), tại giá trị 8 recall là cao nhất mà vẫn giữ pre = 1 |
| `second_opinion.conf` | 0.25 | 0.5 | POSSIBLE_MISSING: 0.50 / 1.00 / 0.67 → 0.57 / 1.00 / 0.73; WRONG_CLASS: 0.56 / 0.83 / 0.67 | giữ Recall 100% cho lỗi thiếu nhãn và 83% cho gán nhầm lớp, Precision của MISSING tăng từ 0.50 lên 0.57|

Một chỗ calibration có thể đánh lừa bạn: Trên tập calib (chỉ có 39 ảnh), ngưỡng duplicates.phash_dist = 16 cho F1 cao nhất là 0.91 (Precision=1.00, Recall=0.83). Tuy nhiên, đây là do tập calib quá nhỏ: khoảng cách Hamming 16 quá lỏng đối với dữ liệu thực tế. Bằng chứng trên tập raw (224 ảnh): khi đặt ngưỡng 16, số ảnh bị loại tăng từ 16 lên 26 ảnh, 6 ảnh bị coi là leaked và 4 ảnh trùng lặp gần đúng. Các ảnh chụp bối cảnh đường phố khác nhau có độ sáng tương tự (như img_0011 và img_0008) bị coi là trùng lặp và bị xoá nhầm

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
(a) Chứng minh gate chặn đúng: Khi chạy thử nghiệm với kịch bản không có người duyệt (python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb), 6 ảnh thiếu file nhãn (MISSING_LABEL_FILE) không được ai gán bổ sung. Gate đã phát hiện còn 6 lỗi bắt buộc (ERROR), đưa ra kết luận REWORK, trả về mã thoát $LASTEXITCODE = 20, và không xuất thư mục dataset work/exp_nb
(b) Hai điểm mù của pipeline có bằng chứng:
Box lỏng nhẹ hoặc viền thừa: Mô hình checker chỉ cảnh báo POSSIBLE_LOOSE_BOX khi IoU < 0.5. Với các box vẽ thừa lề hoặc hơi lệch có IoU nằm trong khoảng 0.5 – 0.7, pipeline bỏ qua
Vật thể cực nhỏ hoặc bị che khuất mà cả nhãn lẫn model lớn đều bỏ qua: Cấu hình second_opinion bỏ qua các dự đoán có diện tích < 600 px² (min_area_px). Nếu người gán nhãn bỏ sót một vật thể nhỏ ở xa và model lớn cũng không nhận ra, pipeline sẽ không phát hiện lỗi này.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa chạy
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).


## 6. Quyết định và ghi chú AI
- Quyết định cuối: Tạm giữ lô dữ liệu (Hold). Để chuyển trạng thái thành Release, dự án cần:
Bổ sung ngân sách duyệt người từ 80 ảnh lên ít nhất 125 ảnh để người duyệt hết 45 ảnh còn lại trong hàng đợi.
(b) Ghi chú AI:
Prompt đây là 4 file pipeline, hãy dựa vào guide bên trong viết 4 module pipeline kiểm nhãn theo TDD, bắt buộc phải theo các quy tắc, và format sẵn của file

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
