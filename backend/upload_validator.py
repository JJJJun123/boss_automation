#!/usr/bin/env python3
"""
简历上传校验

按 IMPLEMENTATION_PLAN.md 阶段 0.7 + design.md F1 + Codex review P1-5：
- 支持 PDF / DOCX / DOC
- 拒绝 TXT、可执行文件等
- 单文件 ≤ 5MB
- 多层校验：
  1. 扩展名白名单
  2. magic bytes 头部识别
  3. DOCX 深度校验：打开 ZIP 检查 [Content_Types].xml + word/document.xml
  4. ZIP bomb 防护：解压总大小上限 + 单文件压缩比阈值
"""

import io
import zipfile
from typing import Any


MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB 上传上限

# DOCX 深度校验阈值
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024  # 解压后总大小上限 20MB
MAX_DOCX_COMPRESSION_RATIO = 100                # 单文件压缩比阈值（典型 docx 5-10:1）

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

# DOCX 必备的内部文件（OOXML 标准要求）
_DOCX_REQUIRED_ENTRIES = ("[Content_Types].xml", "word/document.xml")


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

    # 读首 16 字节做 magic 校验
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

    # DOCX 深度校验：打开 ZIP 看内部结构 + 防 zip bomb
    if ext == ".docx":
        # 把整个文件读进 BytesIO（避免 zipfile 反复 seek 真实文件破坏指针）
        file_obj.seek(0)
        payload = file_obj.read()
        file_obj.seek(0)
        _validate_docx_zip_contents(payload)


def _is_unsafe_zip_path(name: str) -> bool:
    """zip slip 防御：拒绝 .. / 绝对路径 / Windows 盘符 / 反斜杠

    OOXML 规范的 docx 内部文件名都是相对路径 + 正斜杠。
    含 `..` 或绝对路径的几乎肯定是攻击。
    """
    if not name:
        return True
    if name.startswith("/") or name.startswith("\\"):
        return True
    if ".." in name.replace("\\", "/").split("/"):
        return True
    # Windows 盘符（如 C:\...）
    if len(name) >= 2 and name[1] == ":":
        return True
    return False


def _validate_docx_zip_contents(payload: bytes) -> None:
    """深度校验 DOCX：必备 XML + ZIP bomb 防护 + zip slip 防御

    Codex review 反馈强化（按多轮审查）：
    1. 用 zipfile 打开校验是不是合法 ZIP
    2. 必备的 [Content_Types].xml + word/document.xml 都得有
    3. **流式解压**每个 entry 边读边数字节，超 MAX_DOCX_UNCOMPRESSED_BYTES 立刻 abort
       —— 不信任 file_size 元数据（攻击者可声明 1 字节实则 2MB）
    4. 单文件压缩比阈值兜底防御
    5. zip slip 防御：拒绝含 `..` / 绝对路径的文件名
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as e:
        raise UploadValidationError(f"docx 不是合法 zip 容器: {e}")

    try:
        names = set(zf.namelist())
        # 必备条目（Word OOXML 标准）
        missing = [name for name in _DOCX_REQUIRED_ENTRIES if name not in names]
        if missing:
            raise UploadValidationError(
                f"docx 缺必备文件 {missing}，不像有效 Word 文档"
            )

        total_uncompressed = 0

        for info in zf.infolist():
            # zip slip 防御
            if _is_unsafe_zip_path(info.filename):
                raise UploadValidationError(
                    f"docx 内部文件名 {info.filename!r} 含路径穿越字符，拒绝"
                )

            # 加密 entry 拒绝（docx 不应含加密 entry；passworded zip 也无法解析）
            if info.flag_bits & 0x1:
                raise UploadValidationError(
                    f"docx 内部 {info.filename!r} 是加密 entry，拒绝"
                )

            # 元数据声明的压缩比兜底（攻击者声明 file_size=0 时 compress_size 仍能暴露异常）
            if info.compress_size > 0:
                declared_ratio = info.file_size / info.compress_size
                if declared_ratio > MAX_DOCX_COMPRESSION_RATIO:
                    raise UploadValidationError(
                        f"docx 内部 {info.filename!r} 元数据压缩比 {declared_ratio:.0f}x "
                        f"超过阈值，疑似 zip bomb"
                    )

            # **关键**：流式解压数实际字节，不信 file_size 元数据
            # （Codex 攻击：file_size 字段可被攻击者改成 1，但实际解压是 MB 级）
            remaining_budget = MAX_DOCX_UNCOMPRESSED_BYTES - total_uncompressed
            actual_size = _measure_entry_uncompressed(zf, info, remaining_budget + 1)
            total_uncompressed += actual_size
            if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise UploadValidationError(
                    f"docx 实际解压总大小超过 {MAX_DOCX_UNCOMPRESSED_BYTES / 1024 / 1024:.0f}MB，"
                    "疑似 zip bomb 攻击"
                )

            # 实际解压字节 vs 元数据声明对比：差太多也是攻击信号
            if info.file_size > 0 and actual_size > info.file_size * 2:
                # 元数据撒谎：声明小但实际大
                raise UploadValidationError(
                    f"docx 内部 {info.filename!r} 元数据声明 {info.file_size}B "
                    f"但实际解压 {actual_size}B，元数据不一致，疑似 zip bomb"
                )
    finally:
        zf.close()


def _measure_entry_uncompressed(zf: zipfile.ZipFile, info: zipfile.ZipInfo,
                                 hard_limit_bytes: int) -> int:
    """流式解压一个 entry，返回实际字节数；超 hard_limit 立即抛错

    关键设计：边读边数字节，**任何时刻** 总数 > hard_limit 就 abort —— 永远
    不会把炸弹一次性解出来。对纯 stored（无压缩）entry 也保持流式读。
    """
    total = 0
    chunk_size = 64 * 1024
    try:
        with zf.open(info, mode="r") as src:
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > hard_limit_bytes:
                    raise UploadValidationError(
                        f"docx 内部 {info.filename!r} 解压超 {hard_limit_bytes}B 立即 abort，"
                        "疑似 zip bomb 攻击"
                    )
    except zipfile.BadZipFile as e:
        raise UploadValidationError(f"docx 内部 {info.filename!r} 解压失败: {e}")
    return total


def _get_ext(filename: str) -> str:
    """提取小写扩展名，含点。'resume.PDF' → '.pdf'。无扩展名返回 ''"""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()
