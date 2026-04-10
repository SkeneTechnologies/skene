<p align="center">
  <a href="../../README.md">English</a> |
  <a href="README.zh.md">简体中文</a> |
  <a href="README.zht.md">繁體中文</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.da.md">Dansk</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.bs.md">Bosanski</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.no.md">Norsk</a> |
  <a href="README.br.md">Português (Brasil)</a> |
  <a href="README.th.md">ไทย</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.uk.md">Українська</a> |
  <a href="README.bn.md">বাংলা</a> |
  <a href="README.gr.md">Ελληνικά</a> |
  <a href="README.vi.md">Tiếng Việt</a> |
  <a href="README.fi.md">Suomi</a> |
  <a href="README.sv.md">Svenska</a>
</p>

<p align="center">
  <img width="4000" height="800" alt="Skene_git" src="https://github.com/user-attachments/assets/2be11c04-6b98-4e26-8905-bf3250c4addb" />
  <a href="https://www.skene.ai"><img width="120" height="42" alt="website" src="https://github.com/user-attachments/assets/8ae8c68f-eeb5-411f-832f-6b6818bd2c34"></a>
  <a href="https://www.skene.ai/resources/docs/skene"><img width="120" height="42" alt="docs" src="https://github.com/user-attachments/assets/f847af52-0f6f-4570-9a48-1b7c8f4f0d7a"></a>
  <a href="https://www.skene.ai/resources/blog"><img width="100" height="42" alt="blog" src="https://github.com/user-attachments/assets/8c62e3b8-39a8-43f6-bb0b-f00b118aff82"></a>
  <a href="https://www.reddit.com/r/plgbuilders/"><img width="153" height="42" alt="reddit" src="https://github.com/user-attachments/assets/b420ea50-26e3-40fe-ab34-ac179f748357"></a>
</p>


Skene là bộ công cụ phân tích mã nguồn dành cho tăng trưởng dẫn dắt bởi sản phẩm. Nó quét mã nguồn của bạn, phát hiện cơ hội tăng trưởng và tạo ra các kế hoạch triển khai cụ thể.

## Bắt đầu nhanh

Cài đặt và mở giao diện terminal tương tác:

```bash
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash
skene
```

Trình hướng dẫn sẽ dẫn bạn qua các bước chọn nhà cung cấp, xác thực và phân tích — không cần cấu hình trước.

<p align="center">
  <img src="https://github.com/user-attachments/assets/49dcd0c4-2bad-4fd3-b29e-89ba2b85c669" width="100%" height="auto"/>
<p>

## Chức năng

- **Phát hiện tech stack** -- nhận diện framework, cơ sở dữ liệu, xác thực và triển khai
- **Khám phá tính năng tăng trưởng** -- tìm các luồng đăng ký, chia sẻ, mời và thanh toán hiện có
- **Sổ đăng ký tính năng** -- theo dõi tính năng qua các lần phân tích và liên kết chúng với growth loop
- **Phân tích thất thoát doanh thu** -- phát hiện cơ hội kiếm tiền bị bỏ lỡ và các bậc giá yếu
- **Tạo kế hoạch tăng trưởng** -- tạo các growth loop được ưu tiên kèm lộ trình triển khai
- **Lời nhắc triển khai** -- xây dựng các prompt sẵn sàng dùng cho Cursor, Claude hoặc các công cụ AI khác
- **Triển khai telemetry** -- tạo migration Supabase và đẩy lên upstream
- **Xác thực vòng lặp** -- kiểm tra xem các yêu cầu của growth loop đã được triển khai hay chưa
- **Trò chuyện tương tác** -- đặt câu hỏi về mã nguồn của bạn ngay trong terminal

Hỗ trợ OpenAI, Gemini, Claude, LM Studio, Ollama và bất kỳ endpoint nào tương thích OpenAI. Có sẵn kiểm tra cục bộ miễn phí, không cần khóa API.

<img width="1662" height="393" alt="ide_git" src="https://github.com/user-attachments/assets/0b9de3f8-9083-4dc8-b68e-105abc7ea0b4" />

## Cài đặt

### Giao diện Terminal (khuyến nghị)

TUI là trình hướng dẫn tương tác giúp bạn đi qua toàn bộ quy trình làm việc. Không cần điều kiện tiên quyết — trình cài đặt xử lý mọi thứ.

```bash
# Cài đặt TUI
curl -fsSL https://raw.githubusercontent.com/SkeneTechnologies/skene/main/tui/install.sh | bash

# Khởi chạy
skene
```

### Python CLI

Nếu bạn thích dòng lệnh, bạn có thể chạy Skene trực tiếp với `uvx` (không cần cài đặt) hoặc cài đặt toàn cục:

```bash
# Cài đặt uv (nếu bạn chưa có)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Chạy trực tiếp (không cần cài đặt)
uvx skene

# Hoặc cài đặt toàn cục
pip install skene
```

Để biết chi tiết về cách sử dụng CLI, xem [tài liệu](https://www.skene.ai/resources/docs/skene).

## Cấu trúc Monorepo

| Thư mục | Mô tả | Ngôn ngữ | Phân phối |
|-----------|-------------|----------|-------------|
| `src/skene/` | CLI + công cụ phân tích | Python | [PyPI](https://pypi.org/project/skene/) |
| `tui/` | Trình hướng dẫn terminal tương tác | Go | [GitHub Releases](https://github.com/SkeneTechnologies/skene/releases) |
| `cursor-plugin/` | Plugin Cursor IDE | — | — |

TUI (`tui/`) là ứng dụng Bubble Tea cung cấp trải nghiệm hướng dẫn tương tác và điều phối Python CLI thông qua `uvx`. Mỗi gói có quy trình CI/CD độc lập.

## Đóng góp

Chào đón mọi đóng góp. Vui lòng [mở một issue](https://github.com/SkeneTechnologies/skene/issues) hoặc gửi [pull request](https://github.com/SkeneTechnologies/skene/pulls).

## Giấy phép

[MIT](https://opensource.org/licenses/MIT)

<img width="4000" height="800" alt="Skene_end_git" src="https://github.com/user-attachments/assets/04119cd1-ee00-4902-9075-5fc3e1e5ec48" />
