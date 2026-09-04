import json
from app.services.tailoring_merge import merge_tailoring_changes
from app.core.llm.prompts.resume_tailor import TailoredResumeData, ExperienceEntry
from app.models.enums import ChangeType

class MockChange:
    def __init__(self, cid, ttype, tref, orig, prop):
        self.change_id = cid
        self.change_type = ttype
        self.target_reference = tref
        self.original_text = orig
        self.proposed_text = prop

base = TailoredResumeData(
    name="John Doe",
    skills=["Python", "Java"],
    experience=[ExperienceEntry(title="Dev", company="Google", description="Did things.")]
)

changes = [
    MockChange("1", ChangeType.MODIFY, "skills[0]", "Python", "Python/Django"),
    MockChange("2", ChangeType.ADD, "skills[2]", None, "AWS"),
    MockChange("3", ChangeType.REMOVE, "experience[0]", None, None)
]

new_doc = merge_tailoring_changes(base, changes)
print(new_doc.model_dump_json(indent=2))
