"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    issues = []
    fmt_cfg = cfg.get("label_format", {})
    overflow_tol = fmt_cfg.get("overflow_tol", 0.002)
    min_box_px = fmt_cfg.get("min_box_px", 12)
    max_box_frac = fmt_cfg.get("max_box_frac", 0.95)
    dup_box_iou = fmt_cfg.get("dup_box_iou", 0.9)
    num_classes = len(ds.classes)
    # duyệt file
    for label_path in ds.label_files():
        stem = label_path.stem
        lines_info = ds.read_label_lines(stem)
        if lines_info is None:
            continue
        img_size = ds.image_size(stem)
        img_w, img_h = img_size if img_size else (None, None)
        # kiểm tra DUP_BOX: (line_no, cls_id, box_tuple)
        valid_prev_boxes = []
        for line_no, text in lines_info:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(
                    Issue("label_format", ERROR, "BAD_FORMAT", stem, f"Định dạng dòng nhãn lỗi: {e}", line=line_no)
                )
                continue
            if cls_id < 0 or cls_id >= num_classes:
                issues.append(
                    Issue("label_format", ERROR, "BAD_CLASS_ID", stem, f"ID lớp {cls_id} không hợp lệ", line=line_no)
                )
                continue
            if w <= 0 or h <= 0:
                issues.append(
                    Issue("label_format", ERROR, "BOX_ZERO", stem, f"Kích thước box <= 0: w={w}, h={h}", line=line_no)
                )
                continue
            # toạ độ các mép
            x1 = cx - w / 2.0
            y1 = cy - h / 2.0
            x2 = cx + w / 2.0
            y2 = cy + h / 2.0
            # mức tràn ngoài [0, 1]
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)
            if overflow > overflow_tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"Box tràn mép ảnh {overflow:.4f} > {overflow_tol}",
                        line=line_no,
                        extra={"overflow": overflow},
                    )
                )
            # kiểm tra trùng box (DUP_BOX)
            box = (cx, cy, w, h)
            is_dup = False
            for prev_line_no, prev_cls, prev_box in valid_prev_boxes:
                if prev_cls == cls_id:
                    iou = iou_xywh(box, prev_box)
                    if iou > dup_box_iou:
                        issues.append(
                            Issue(
                                "label_format",
                                ERROR,
                                "DUP_BOX",
                                stem,
                                f"Trùng box với dòng {prev_line_no} (IoU={iou:.3f} > {dup_box_iou})",
                                line=line_no,
                            )
                        )
                        is_dup = True
                        break
            valid_prev_boxes.append((line_no, cls_id, box))
            # cảnh báo BOX_TINY
            if img_w is not None and img_h is not None:
                box_w_px = w * img_w
                box_h_px = h * img_h
                short_side_px = min(box_w_px, box_h_px)
                if short_side_px < min_box_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"Box nhỏ: cạnh ngắn {short_side_px:.1f}px < {min_box_px}px",
                            line=line_no,
                        )
                    )
            # cảnh báo BOX_HUGE
            box_area_frac = w * h
            if box_area_frac > max_box_frac:
                issues.append(
                    Issue(
                        "label_format",
                        WARN,
                        "BOX_HUGE",
                        stem,
                        f"Box chiếm diện tích {box_area_frac:.2%} > {max_box_frac:.2%}",
                        line=line_no,
                    )
                )
    return issues
