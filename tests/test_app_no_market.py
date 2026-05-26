import os


def test_no_market_analysis_calls_in_app():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "backend",
        "app.py",
    )
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()

    assert "generate_market_analysis" not in source, "Must remove generate_market_analysis call"
    assert "get_market_analysis" not in source, "Must remove get_market_analysis call"

