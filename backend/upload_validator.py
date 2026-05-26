#!/usr/bin/env python3
"""
简历上传校验

按 IMPLEMENTATION_PLAN.md 阶段 0.7 + design.md F1：
- 支持 PDF / DOCX / DOC
- 拒绝 TXT、可执行文件等
- 单文件 ≤ 5MB
- 双重校验：扩展名白名单 + magic bytes 头部识别

magic bytes 比 MIME 头更可靠（攻击者控制不了文件内容字节）。
"""

from typing import Any


MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB

# 扩展名白名单（小写比较）
_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# 文件类型 magic bytes 前缀
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # DOCX 本质是 ZIP
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # 老 .doc 用 OLE2

# 各扩展名对应可接受的 magic bytes 列表
_EXT_TO_MAGIC = {
    ".pdf": [_PDF_MAGIC],
    ".docx": [_ZIP_MAGIC],
    ".doc": [_OLE2_MAGIC],
}


class UploadValidationError(ValueError):
    """上传校验失败"""


def validate_resume_file(file_obj: Any) -> None:
    """校验上传的简历文件。不通过抛 UploadValidationError。

    参数：
        file_obj - file-like 对象（werkzeug FileStorage 或测试用的 BytesIO 包装）
                   需有 .filename、.read()、.seek()、.tell()

    校验通过后文件指针回到 0，调用方可以继续 .read() 拿内容。
    """
    filename = (getattr(file_obj, "filename", "") or "").strip()
    if not filename:
        raise UploadValidationError("文件名为空")

    # 扩展名白名单
    ext = _get_ext(filename)
    if not ext:
        raise UploadValidationError(f"文件没有扩展名: {filename}")
    if ext not in _ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            f"格式不支持: {ext}。仅接受 PDF / DOCX / DOC"
        )

    # 读首 8 字节做 magic 校验
    file_obj.seek(0)
    head = file_obj.read(16)
    if not head:
        raise UploadValidationError("文件为空")

    expected_magics = _EXT_TO_MAGIC[ext]
    if not any(head.startswith(m) for m in expected_magics):
        raise UploadValidationError(
            f"文件内容不像有效的 {ext} 文件（magic bytes 不匹配）"
        )

    # 大小限制：seek 到末尾算 size
    file_obj.seek(0, 2)  # 2 = SEEK_END
    size = file_obj.tell()
    file_obj.seek(0)  # 重置指针供后续读取

    if size == 0:
        raise UploadValidationError("文件为空")
    if size > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            f"文件过大: {size / 1024 / 1024:.1f}MB > "
            f"{MAX_UPLOAD_BYTES / 1024 / 1024:.0f}MB 上限"
        )


def _get_ext(filename: str) -> str:
    """提取小写扩展名，含点。'resume.PDF' → '.pdf'。无扩展名返回 ''"""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()
