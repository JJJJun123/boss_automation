#!/usr/bin/env python3
"""
简历上传校验测试

按 IMPLEMENTATION_PLAN.md 阶段 0.7 + design.md F1：
- 支持 PDF / DOCX / DOC
- 拒绝 TXT 及其它格式
- 单文件 ≤ 5MB
- 校验 = 扩展名 + magic bytes 双重（避免 evil.exe 改名 .pdf）
"""

import io
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.upload_validator import (
    validate_resume_file,
    UploadValidationError,
    MAX_UPLOAD_BYTES,
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MAX_DOCX_COMPRESSION_RATIO,
)


def _build_minimal_docx() -> bytes:
    """构造一个最小合法 docx（ZIP 容器 + Word 必备 XML 文件）

    真 docx 必须含：
    - [Content_Types].xml（在根目录）
    - word/document.xml（正文）
    其它（_rels/.rels 等）可选但常见。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<?xml version='1.0'?><Types/>")
        zf.writestr("_rels/.rels", "<?xml version='1.0'?><Relationships/>")
        zf.writestr(
            "word/document.xml",
            "<?xml version='1.0'?><document><body><p>简历正文</p></body></document>",
        )
    return buf.getvalue()


def _build_arbitrary_zip(names_and_data) -> bytes:
    """构造任意 ZIP（没有 docx 必备结构）"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in names_and_data:
            zf.writestr(name, data)
    return buf.getvalue()


def _build_compression_bomb(compress_ratio: int = 200) -> bytes:
    """构造一个真实的压缩比攻击 zip：单文件高重复内容 → 压缩比超阈值

    生成 1MB 全 'A' 高度可压缩内容，但塞进 docx 必备结构外面。
    返回的 zip 解压后会触发"单文件压缩比 > MAX_DOCX_COMPRESSION_RATIO"。
    """
    buf = io.BytesIO()
    payload_size = compress_ratio * 1024 * 10  # 高重复 → 压缩极高
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("[Content_Types].xml", "<?xml version='1.0'?><Types/>")
        zf.writestr("word/document.xml", "<doc/>")
        zf.writestr("bomb.txt", b"A" * payload_size)
    return buf.getvalue()


def _make_file(content: bytes, filename: str):
    """构造一个最小 file-like 对象（mimic werkzeug FileStorage）"""
    class FakeFile:
        def __init__(self, content, filename):
            self._buf = io.BytesIO(content)
            self.filename = filename

        def read(self, size=-1):
            return self._buf.read(size)

        def seek(self, pos, whence=0):
            return self._buf.seek(pos, whence)

        def tell(self):
            return self._buf.tell()
    return FakeFile(content, filename)


# 真实 magic bytes 前缀
_PDF_PREFIX = b"%PDF-1.5\n"
_DOCX_PREFIX = b"PK\x03\x04"  # ZIP 文件头（DOCX = ZIP）
_DOC_PREFIX = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE2 文件头


# ─── 合法格式 ─────────────────────────────────────────────

def test_pdf_passes():
    f = _make_file(_PDF_PREFIX + b"fake pdf body", "resume.pdf")
    validate_resume_file(f)  # 不抛异常


def test_real_minimal_docx_passes():
    """真实结构最小 docx（含 [Content_Types].xml + word/document.xml）应通过"""
    f = _make_file(_build_minimal_docx(), "resume.docx")
    validate_resume_file(f)


def test_fake_zip_magic_without_docx_structure_rejected():
    """旧版仅靠 magic bytes 通过的"假 docx"，新版必须拒绝（Codex P1-5）"""
    f = _make_file(_DOCX_PREFIX + b"fake docx body", "resume.docx")
    with pytest.raises(UploadValidationError, match="不像有效|不是合法|zip"):
        validate_resume_file(f)


def test_doc_passes():
    f = _make_file(_DOC_PREFIX + b"fake doc body", "resume.doc")
    validate_resume_file(f)


# ─── 拒绝格式 ─────────────────────────────────────────────

def test_txt_rejected():
    """design.md 明确不支持 TXT"""
    f = _make_file(b"hello world", "resume.txt")
    with pytest.raises(UploadValidationError, match="格式"):
        validate_resume_file(f)


def test_no_extension_rejected():
    f = _make_file(_PDF_PREFIX + b"body", "resume")
    with pytest.raises(UploadValidationError):
        validate_resume_file(f)


def test_empty_filename_rejected():
    f = _make_file(_PDF_PREFIX + b"body", "")
    with pytest.raises(UploadValidationError):
        validate_resume_file(f)


# ─── magic bytes 双重校验 ─────────────────────────────────

def test_exe_renamed_to_pdf_rejected():
    """攻击者把 evil.exe 改名 resume.pdf 上传——magic bytes 拒绝"""
    f = _make_file(b"MZ\x90\x00fake exe", "resume.pdf")
    with pytest.raises(UploadValidationError, match="不像有效"):
        validate_resume_file(f)


def test_random_bytes_renamed_to_docx_rejected():
    f = _make_file(b"random garbage", "resume.docx")
    with pytest.raises(UploadValidationError, match="不像有效"):
        validate_resume_file(f)


def test_arbitrary_zip_renamed_to_docx_rejected():
    """任意 ZIP 改名 .docx（无 Word 结构）必须拒绝"""
    payload = _build_arbitrary_zip([("hello.txt", "hi"), ("foo/bar.txt", "x")])
    f = _make_file(payload, "resume.docx")
    with pytest.raises(UploadValidationError, match="不像有效|Word|content_types|document"):
        validate_resume_file(f)


def test_zip_with_only_content_types_but_no_document_rejected():
    """有 [Content_Types].xml 但缺 word/document.xml 也不算 docx"""
    payload = _build_arbitrary_zip([("[Content_Types].xml", "<Types/>")])
    f = _make_file(payload, "resume.docx")
    with pytest.raises(UploadValidationError):
        validate_resume_file(f)


def test_txt_renamed_to_pdf_rejected():
    """普通文本改名 .pdf 也被识别为非真 PDF"""
    f = _make_file(b"this is plain text content", "resume.pdf")
    with pytest.raises(UploadValidationError):
        validate_resume_file(f)


# ─── 大小限制 ─────────────────────────────────────────────

def test_oversized_rejected():
    """> 5MB 拒绝"""
    big_body = _PDF_PREFIX + b"x" * (MAX_UPLOAD_BYTES + 1)
    f = _make_file(big_body, "resume.pdf")
    with pytest.raises(UploadValidationError, match="过大"):
        validate_resume_file(f)


def test_exactly_max_bytes_passes():
    """正好 5MB 通过（边界条件）"""
    body = _PDF_PREFIX + b"x" * (MAX_UPLOAD_BYTES - len(_PDF_PREFIX))
    f = _make_file(body, "resume.pdf")
    validate_resume_file(f)


def test_empty_file_rejected():
    f = _make_file(b"", "resume.pdf")
    with pytest.raises(UploadValidationError, match="空"):
        validate_resume_file(f)


# ─── Zip Bomb 防护（Codex P1-5） ──────────────────────────

def test_zip_bomb_total_size_rejected():
    """zip 内部总解压大小 > 上限 → 拒绝（防 zip bomb）"""
    buf = io.BytesIO()
    # 单文件元数据声明的解压大小要 > MAX_DOCX_UNCOMPRESSED_BYTES
    bomb_size = MAX_DOCX_UNCOMPRESSED_BYTES + 1
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
        zf.writestr("bomb.bin", b"A" * bomb_size)
    f = _make_file(buf.getvalue(), "resume.docx")
    # 这种 1MB-1GB 量级 zip 攻击但同时 file_size 字段够大 → 必须挡住
    with pytest.raises(UploadValidationError, match="解压|过大|zip"):
        validate_resume_file(f)


def test_zip_bomb_extreme_compression_ratio_rejected():
    """单文件压缩比 > 阈值 → 拒绝（高度重复内容是经典 zip bomb 特征）"""
    payload = _build_compression_bomb(compress_ratio=MAX_DOCX_COMPRESSION_RATIO + 200)
    f = _make_file(payload, "resume.docx")
    with pytest.raises(UploadValidationError, match="压缩比|zip"):
        validate_resume_file(f)


def test_legit_docx_with_acceptable_compression_passes():
    """正常 docx 压缩比 < 阈值 → 通过（确保防护不误伤）"""
    f = _make_file(_build_minimal_docx(), "resume.docx")
    validate_resume_file(f)  # 不抛


def _patch_central_dir_file_size(data: bytes, target_name: bytes, new_size: int) -> bytes:
    """攻击工具：把 zip 中央目录里指定文件的 uncompressed size 字段改成 new_size

    Codex 用同样手法演示了我们旧版只查 file_size 元数据被绕过。
    """
    import struct
    arr = bytearray(data)
    sig = b"PK\x01\x02"  # 中央目录文件头签名
    pos = 0
    while True:
        i = arr.find(sig, pos)
        if i < 0:
            break
        name_len = struct.unpack_from("<H", arr, i + 28)[0]
        name = bytes(arr[i + 46:i + 46 + name_len])
        if name == target_name:
            struct.pack_into("<I", arr, i + 24, new_size)  # offset 24 = uncompressed size
            return bytes(arr)
        pos = i + 46 + name_len
    return bytes(arr)


def test_zip_bomb_with_lying_file_size_metadata_rejected():
    """攻击场景：中央目录 file_size 声明 1 字节，实际解压 2MB

    Codex review 找到的 P0：旧版只看 info.file_size 元数据，被这种攻击绕过。
    修复：流式解压数实际字节，元数据撒谎检测。
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
        zf.writestr("bomb.bin", b"A" * (2 * 1024 * 1024))  # 真实 2MB
    # 攻击者把 bomb.bin 的 file_size 字段改成 1 字节
    patched = _patch_central_dir_file_size(buf.getvalue(), b"bomb.bin", 1)
    f = _make_file(patched, "resume.docx")
    with pytest.raises(UploadValidationError, match="zip|元数据|解压"):
        validate_resume_file(f)


def test_zip_slip_path_traversal_rejected():
    """docx 内部文件名含 .. 拒绝（zip slip 攻击）"""
    payload = _build_arbitrary_zip([
        ("[Content_Types].xml", "<Types/>"),
        ("word/document.xml", "<doc/>"),
        ("../../etc/passwd", "evil"),
    ])
    f = _make_file(payload, "resume.docx")
    with pytest.raises(UploadValidationError, match="路径穿越"):
        validate_resume_file(f)


def test_encrypted_docx_entry_rejected():
    """加密 entry 拒绝（docx 不应含加密内容）

    通过修改中央目录的 General Purpose Bit Flag 把 bit 0 置 1（加密标志）。
    zipfile 库默认不会写加密 entry，需手动 patch。
    """
    import struct
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<doc/>")
        zf.writestr("dummy.bin", b"\x00" * 16)
    arr = bytearray(buf.getvalue())
    # Central Directory Entry header: PK\x01\x02, offset 8 = general purpose bit flag (2B)
    sig = b"PK\x01\x02"
    pos = 0
    while True:
        i = arr.find(sig, pos)
        if i < 0:
            break
        name_len = struct.unpack_from("<H", arr, i + 28)[0]
        name = bytes(arr[i + 46:i + 46 + name_len])
        if name == b"dummy.bin":
            # offset 8 = GPBF flag bits；置 bit 0 = 加密
            struct.pack_into("<H", arr, i + 8, 0x1)
            break
        pos = i + 46 + name_len
    f = _make_file(bytes(arr), "resume.docx")
    with pytest.raises(UploadValidationError, match="加密"):
        validate_resume_file(f)


def test_zip_slip_absolute_path_rejected():
    """docx 内部文件名是绝对路径拒绝"""
    payload = _build_arbitrary_zip([
        ("[Content_Types].xml", "<Types/>"),
        ("word/document.xml", "<doc/>"),
        ("/etc/passwd", "evil"),
    ])
    f = _make_file(payload, "resume.docx")
    with pytest.raises(UploadValidationError, match="路径穿越"):
        validate_resume_file(f)


# ─── 文件指针重置 ─────────────────────────────────────────

def test_validator_resets_file_pointer():
    """validate 完后文件指针应回到 0，调用方能正常 .read() 拿内容"""
    body = _PDF_PREFIX + b"body"
    f = _make_file(body, "resume.pdf")
    validate_resume_file(f)
    assert f.tell() == 0
    assert f.read() == body
