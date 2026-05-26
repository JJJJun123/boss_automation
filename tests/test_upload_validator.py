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

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.upload_validator import (
    validate_resume_file,
    UploadValidationError,
    MAX_UPLOAD_BYTES,
)


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


def test_docx_passes():
    f = _make_file(_DOCX_PREFIX + b"fake docx body", "resume.docx")
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


# ─── 文件指针重置 ─────────────────────────────────────────

def test_validator_resets_file_pointer():
    """validate 完后文件指针应回到 0，调用方能正常 .read() 拿内容"""
    body = _PDF_PREFIX + b"body"
    f = _make_file(body, "resume.pdf")
    validate_resume_file(f)
    assert f.tell() == 0
    assert f.read() == body
