# cấu trúc của một commit chuẩn

```
<type>(scope): <short summary>
<body>
<footer>
```

# type (bắt buộc) – loại commit

| type         | ý nghĩa                                              |
| ------------ | ---------------------------------------------------- |
| **feat**     | thêm tính năng mới                                   |
| **fix**      | sửa lỗi                                              |
| **refactor** | cải tổ code (không thêm tính năng, không sửa bug)    |
| **docs**     | update tài liệu                                      |
| **style**    | thay đổi không ảnh hưởng logic (format, indent, ; …) |
| **test**     | thêm/sửa test                                        |
| **chore**    | việc linh tinh (config, build, CI)                   |
| **perf**     | tối ưu performance                                   |
| **revert**   | hoàn tác commit trước                                |

# ví dụ: scope (không bắt buộc) – khu vực thay đổi

```
feat(auth): add login with Google
fix(ui): overflow on sidebar
```

# ví dụ: Short summary (bắt buộc)

Viết ngắn gọn (≤ 70 ký tự)
Không viết hoa chữ cái đầu
Không dấu chấm cuối

```
feat(video): support autoplay on homepage
```

# Commit nhiều dòng

```
feat(auth): add refresh token flow

- add new /refresh endpoint
- update axios interceptor
- improve token validation
```
