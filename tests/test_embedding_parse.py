import json

from backend.db_mysql import _parse_embedding_column


def test_parse_list():
    assert _parse_embedding_column([0.1, 0.2]) == [0.1, 0.2]


def test_parse_json_bytes():
    raw = json.dumps([0.5, 1.0, -0.25]).encode("utf-8")
    assert _parse_embedding_column(raw) == [0.5, 1.0, -0.25]


def test_parse_json_str():
    assert _parse_embedding_column("[1,2,3]") == [1.0, 2.0, 3.0]


def test_parse_none():
    assert _parse_embedding_column(None) == []


def test_parse_tuple():
    assert _parse_embedding_column((0.1, 0.2, 0.3)) == [0.1, 0.2, 0.3]
