import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.prompts.extraction_prompts import ExtractionPrompts
from analyzer.prompts.job_analysis_prompts import RESUME_MATCH_PROMPT


def test_resume_match_prompt_has_required_placeholders():
    for field in [
        "{resume_text}",
        "{job_title}",
        "{company}",
        "{salary}",
        "{description}",
        "{requirements}",
    ]:
        assert field in RESUME_MATCH_PROMPT, f"Missing placeholder: {field}"


def test_resume_match_prompt_requests_json_output():
    for key in ["score", "match_highlights", "gaps", "summary"]:
        assert key in RESUME_MATCH_PROMPT, f"Missing JSON output key: {key}"


def test_screening_prompt_no_resume_reference():
    job_data = {
        "title": "数据分析师",
        "company": "测试公司",
        "job_description": "负责数据分析工作，要求熟悉Python和SQL",
    }
    prompt = ExtractionPrompts.get_job_relevance_screening_prompt(job_data, "数据分析")
    assert "简历" not in prompt, "Screening prompt must NOT reference resume"

