import pytest
from app.services.tailoring_merge import merge_tailoring_changes, MergeConflictError, InvalidTargetError
from app.core.llm.prompts.resume_tailor import TailoredResumeData, ExperienceEntry
from app.models.enums import ChangeType

class MockChange:
    def __init__(self, cid, ttype, tref, orig, prop):
        self.change_id = cid
        self.change_type = ttype
        self.target_reference = tref
        self.original_text = orig
        self.proposed_text = prop

@pytest.fixture
def base_doc():
    return TailoredResumeData(
        name="Alice",
        skills=["Python", "C++"],
        experience=[
            ExperienceEntry(title="Dev", company="Corp", description="Line 1\nLine 2")
        ]
    )

def test_add_item(base_doc):
    changes = [MockChange("1", ChangeType.ADD, "skills[2]", None, "Go")]
    merged = merge_tailoring_changes(base_doc, changes)
    assert "Go" in merged.skills

def test_modify_item(base_doc):
    changes = [MockChange("1", ChangeType.MODIFY, "skills[0]", "Python", "Python 3")]
    merged = merge_tailoring_changes(base_doc, changes)
    assert merged.skills[0] == "Python 3"

def test_remove_item(base_doc):
    changes = [MockChange("1", ChangeType.REMOVE, "skills[1]", "C++", None)]
    merged = merge_tailoring_changes(base_doc, changes)
    assert "C++" not in merged.skills

def test_conflict_duplicate_modify(base_doc):
    changes = [
        MockChange("1", ChangeType.MODIFY, "skills[0]", "Python", "Python 3"),
        MockChange("2", ChangeType.MODIFY, "skills[0]", "Python", "Py")
    ]
    with pytest.raises(MergeConflictError):
        merge_tailoring_changes(base_doc, changes)

def test_conflict_modify_after_remove(base_doc):
    changes = [
        MockChange("1", ChangeType.REMOVE, "skills[0]", "Python", None),
        MockChange("2", ChangeType.MODIFY, "skills[0]", "Python", "Py")
    ]
    with pytest.raises(MergeConflictError):
        merge_tailoring_changes(base_doc, changes)

def test_invalid_target(base_doc):
    changes = [MockChange("1", ChangeType.MODIFY, "skills[99]", "X", "Y")]
    with pytest.raises(InvalidTargetError):
        merge_tailoring_changes(base_doc, changes)

def test_invalid_path(base_doc):
    changes = [MockChange("1", ChangeType.MODIFY, "nonexistent[0]", "X", "Y")]
    with pytest.raises(InvalidTargetError):
        merge_tailoring_changes(base_doc, changes)

def test_object_property_modify(base_doc):
    changes = [MockChange("1", ChangeType.MODIFY, "experience[0].title", "Dev", "Senior Dev")]
    merged = merge_tailoring_changes(base_doc, changes)
    assert merged.experience[0].title == "Senior Dev"
