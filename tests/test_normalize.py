"""Unit tests for backend/services/normalize.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from backend.services.normalize import (
    parse_menu_from_filename,
    is_valid_filename,
    extract_upload_stored_name,
    build_storage_filename,
    style_table_rows_have_content,
    style_table_from_saved_analysis_style,
    normalize_case,
    normalize_record,
    now_iso,
)


class TestNowIso:
    def test_format(self):
        ts = now_iso()
        assert len(ts) == 19
        assert ts[4] == "-" and ts[10] == " " and ts[13] == ":"


class TestParseMenuFromFilename:
    def test_single_part(self):
        sys_name, menu = parse_menu_from_filename("首页.png")
        assert sys_name == "默认系统"
        assert len(menu) == 1
        assert menu[0] == {"level": 1, "name": "首页"}

    def test_multi_parts(self):
        _, menu = parse_menu_from_filename("系统管理_用户管理_新增.png")
        assert len(menu) == 3
        assert menu[0]["name"] == "系统管理"
        assert menu[2]["name"] == "新增"

    def test_empty_parts_skipped(self):
        _, menu = parse_menu_from_filename("A__B.png")
        assert all(m["name"] != "" for m in menu)


class TestIsValidFilename:
    @pytest.mark.parametrize("name", ["hello.png", "file_name.jpg", "中文名.txt"])
    def test_valid(self, name):
        assert is_valid_filename(name) is True

    @pytest.mark.parametrize("name", ["", " bad", "a/b", "a\\b", "..", "a:b", 'a"b'])
    def test_invalid(self, name):
        assert is_valid_filename(name) is False


class TestExtractUploadStoredName:
    def test_normal(self):
        assert extract_upload_stored_name("/uploads/abc.png") == "abc.png"

    def test_encoded(self):
        assert extract_upload_stored_name("/uploads/%E4%B8%AD%E6%96%87.png") == "中文.png"

    def test_empty(self):
        assert extract_upload_stored_name("") == ""
        assert extract_upload_stored_name(None) == ""

    def test_no_prefix(self):
        assert extract_upload_stored_name("abc.png") == ""


class TestBuildStorageFilename:
    def test_preserves_extension(self):
        name = build_storage_filename("photo.PNG")
        assert name.endswith(".png")
        assert len(name) > 10

    def test_no_extension(self):
        name = build_storage_filename("noext")
        assert "." not in name


class TestStyleTableRowsHaveContent:
    def test_empty(self):
        assert style_table_rows_have_content([]) is False

    def test_blank_rows(self):
        rows = [{"element": "", "requirement": ""}]
        assert style_table_rows_have_content(rows) is False

    def test_has_element(self):
        rows = [{"element": "用户名", "requirement": ""}]
        assert style_table_rows_have_content(rows) is True

    def test_attribute_only_non_default_counts(self):
        rows = [{"element": "", "attribute": "按钮", "requirement": ""}]
        assert style_table_rows_have_content(rows) is True

    def test_attribute_default_text_only_still_empty(self):
        rows = [{"element": "", "attribute": "文本", "requirement": ""}]
        assert style_table_rows_have_content(rows) is False


class TestStyleTableFromSaved:
    def test_empty(self):
        assert style_table_from_saved_analysis_style("") == []

    def test_multiline(self):
        text = "用户名\n密码\n登录按钮"
        rows = style_table_from_saved_analysis_style(text)
        assert len(rows) == 3
        assert rows[0]["element"] == "用户名"
        assert rows[0]["attribute"] == "文本"

    def test_ocr_prefix_stripped(self):
        text = "OCR识别原文（来自截图，摘要）：\n字段A"
        rows = style_table_from_saved_analysis_style(text)
        assert len(rows) == 1
        assert rows[0]["element"] == "字段A"

    def test_ocr_failure(self):
        rows = style_table_from_saved_analysis_style("OCR识别失败：识别异常")
        assert len(rows) == 1
        assert "识别异常" in rows[0]["element"]


class TestNormalizeCase:
    def test_defaults(self):
        c = normalize_case({})
        assert c["id"] == 0
        assert c["status"] == "draft"
        assert c["steps"] == []
        assert c["step_expected"] == []
        assert c["system_id"] is None
        assert c["priority"] == "P2"
        assert c["created_at"]

    def test_preserves_existing(self):
        c = normalize_case({"id": 5, "title": "测试", "status": "pass"})
        assert c["id"] == 5
        assert c["title"] == "测试"
        assert c["status"] == "pass"

    def test_priority_normalized(self):
        assert normalize_case({"priority": "p0"})["priority"] == "P0"
        assert normalize_case({"priority": "bad"})["priority"] == "P2"


class TestNormalizeRecord:
    def test_minimal(self):
        r = normalize_record({"file_name": "首页.png"})
        assert r["system_name"] == "默认系统"
        assert len(r["menu_structure"]) == 1
        assert r["analysis"] == ""
        assert r["system_id"] is None
        assert isinstance(r["manual"], dict)

    def test_timestamps_added(self):
        r = normalize_record({})
        assert r["created_at"]
        assert r["updated_at"]

    def test_file_url_fallback(self):
        r = normalize_record({"file_name": "test.png"})
        assert r["file_url"] == "/uploads/test.png"

    def test_file_url_preserved(self):
        r = normalize_record({"file_name": "test.png", "file_url": "/uploads/abc123.png"})
        assert r["file_url"] == "/uploads/abc123.png"

    def test_style_table_backfill(self):
        r = normalize_record({
            "analysis_style": "用户名\n密码",
            "analysis_style_table": [],
        })
        assert len(r["analysis_style_table"]) == 2
