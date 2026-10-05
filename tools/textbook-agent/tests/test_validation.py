from pathlib import Path
from textbook_agent.validation import validate_lesson, check_math
from textbook_agent.site import validate_site
from textbook_agent.models import LessonEvidence,SourceItem

def test_invalid_formula_and_missing_assets_block_application(book,tmp_path):
    e=LessonEvidence(lesson=book.lessons[0],medium='ta',pages=[],items=[],fingerprint='x')
    result=validate_lesson('---\ntitle: Motion\nweight: 1\n---\n![diagram](missing.png)\n\\(x',book.lessons[0],e,[],tmp_path)
    assert not result.passing and any('image' in x for x in result.errors) and any('math' in x for x in result.errors)

def test_katex_rejects_balanced_invalid_latex():
    assert check_math(r'\(\notarealcommand{x}\)')
    assert check_math(r'\(p = mv\)')==[]

def test_script_and_html_images_are_checked(book,tmp_path):
    e=LessonEvidence(lesson=book.lessons[0],medium='ta',pages=[],items=[],fingerprint='x')
    r=validate_lesson('---\ntitle: Motion\nweight: 1\n---\n<script>alert(1)</script>\n<img src="../escape.png">',book.lessons[0],e,[],tmp_path)
    assert not r.passing and len(r.errors)>=2

def test_generic_destination_and_missing_hugo_dependencies(book,tmp_path):
    assert validate_site(book,{},tmp_path/'site').passing
    book.output.mkdir(); (book.output/'config.toml').write_text("baseURL='/'\ntheme='missing-theme'\n")
    assert not validate_site(book,{},tmp_path/'site2').passing
