"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


REMOVE_IMAGE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
DROP_LINE_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
def fix(ds, issues, cfg):
    fixes = []
    # 1.xoá ảnh hỏng, trùng, leaked
    processed_removals = set()
    for iss in issues:
        if iss.severity == ERROR and iss.code in REMOVE_IMAGE_CODES:
            stem = iss.image
            if stem in processed_removals:
                continue
            processed_removals.add(stem)
            if ds.images_dir.exists():
                for p in ds.images_dir.iterdir():
                    if p.stem == stem:
                        p.unlink(missing_ok=True)
            lbl = ds.label_path(stem)
            if lbl.exists():
                lbl.unlink(missing_ok=True)
            fixes.append({
                "image": stem,
                "line": "",
                "action": "remove_image",
                "before": stem,
                "after": "(đã xoá)",
            })
    # 2. Sửa tên lớp trong data.yaml
    for iss in issues:
        if iss.severity == ERROR and iss.code == "BAD_CLASS_NAME":
            if ds.yaml_path.exists():
                data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
                before = str(data.get("names", ""))
                data["names"] = list(cfg["classes"])
                ds.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
                fixes.append({
                    "image": "data.yaml",
                    "line": "",
                    "action": "rename_classes",
                    "before": before,
                    "after": str(cfg["classes"]),
                })
            break
    # 3. ảnh thiếu file nhãn -> đẩy cho người gán
    for iss in issues:
        if iss.severity == ERROR and iss.code == "MISSING_LABEL_FILE":
            fixes.append({
                "image": iss.image,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            })
    # 4. gom lỗi cấp dòng theo ảnh
    line_issues = defaultdict(lambda: defaultdict(list))
    for iss in issues:
        if iss.severity != ERROR or iss.image in processed_removals:
            continue
        if iss.line is not None and isinstance(iss.line, int):
            line_issues[iss.image][iss.line].append(iss.code)
    for stem, lines_map in line_issues.items():
        lbl_p = ds.label_path(stem)
        if not lbl_p.exists():
            continue
        orig_lines = lbl_p.read_text(encoding="utf-8", errors="replace").splitlines()
        new_lines = []
        for idx, orig_text in enumerate(orig_lines, 1):
            if idx not in lines_map:
                new_lines.append(orig_text)
            else:
                codes = lines_map[idx]
                if any(c in DROP_LINE_CODES for c in codes):
                    fixes.append({
                        "image": stem,
                        "line": idx,
                        "action": "drop_line",
                        "before": orig_text,
                        "after": "",
                    })
                elif "BOX_OUT_OF_IMAGE" in codes:
                    try:
                        c, cx, cy, w, h = parse_yolo_line(orig_text)
                        x1 = cx - w / 2.0
                        x2 = cx + w / 2.0
                        y1 = cy - h / 2.0
                        y2 = cy + h / 2.0
                        nx1 = max(0.0, min(1.0, x1))
                        nx2 = max(0.0, min(1.0, x2))
                        ny1 = max(0.0, min(1.0, y1))
                        ny2 = max(0.0, min(1.0, y2))
                        nw = nx2 - nx1
                        nh = ny2 - ny1
                        if nw <= 0 or nh <= 0:
                            fixes.append({
                                "image": stem,
                                "line": idx,
                                "action": "drop_line",
                                "before": orig_text,
                                "after": "",
                            })
                        else:
                            ncx = (nx1 + nx2) / 2.0
                            ncy = (ny1 + ny2) / 2.0
                            new_line_str = f"{int(c)} {ncx:.6g} {ncy:.6g} {nw:.6g} {nh:.6g}"
                            new_lines.append(new_line_str)
                            fixes.append({
                                "image": stem,
                                "line": idx,
                                "action": "clip_box",
                                "before": orig_text,
                                "after": new_line_str,
                            })
                    except Exception:
                        fixes.append({
                            "image": stem,
                            "line": idx,
                            "action": "drop_line",
                            "before": orig_text,
                            "after": "",
                        })
        lbl_p.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    return fixes
