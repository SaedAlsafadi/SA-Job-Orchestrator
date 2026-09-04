import copy
from typing import Any
from app.core.llm.prompts.resume_tailor import TailoredResumeData
from app.models.enums import ChangeType

class MergeConflictError(ValueError):
    pass

class InvalidTargetError(ValueError):
    pass

def resolve_target(data: dict[str, Any], path: str) -> tuple[Any, str | int]:
    """
    Resolves a JSONPath-like string to its parent object and the key/index.
    Example: 'experience[0].description' -> (experience[0] dict, 'description')
    """
    import re
    parts = re.split(r'\.|\[', path)
    current = data
    parent = None
    last_key = None
    
    for i, part in enumerate(parts):
        if not part:
            continue
        part = part.rstrip(']')
        
        # If this is the last part, we just return the parent and this key
        is_last = (i == len(parts) - 1)
        
        if isinstance(current, list):
            if not part.isdigit():
                raise InvalidTargetError(f"Expected list index, got '{part}' in path '{path}'")
            idx = int(part)
            if idx < 0 or idx >= len(current):
                if not (is_last and idx == len(current)): # allow appending at end
                    raise InvalidTargetError(f"Index {idx} out of bounds in path '{path}'")
            if is_last:
                return current, idx
            current = current[idx]
        elif isinstance(current, dict):
            if part not in current and not is_last:
                raise InvalidTargetError(f"Key '{part}' not found in path '{path}'")
            if is_last:
                return current, part
            current = current[part]
        else:
            raise InvalidTargetError(f"Cannot traverse into primitive type at '{part}' in path '{path}'")
            
    return current, last_key

def apply_change(data_dict: dict[str, Any], target: str, change_type: str, new_value: Any, expected_original: Any = None):
    parent, key = resolve_target(data_dict, target)
    
    if change_type == "add":
        if isinstance(parent, list):
            if isinstance(key, int):
                parent.insert(key, new_value)
            else:
                parent.append(new_value)
        elif isinstance(parent, dict):
            parent[key] = new_value
    
    elif change_type == "modify":
        if isinstance(parent, list):
            if not isinstance(key, int) or key >= len(parent):
                raise InvalidTargetError(f"Cannot modify nonexistent list item at {target}")
            # Strict validation could check expected_original here
            parent[key] = new_value
        elif isinstance(parent, dict):
            if key not in parent:
                raise InvalidTargetError(f"Cannot modify nonexistent dict key at {target}")
            parent[key] = new_value
            
    elif change_type == "remove":
        if isinstance(parent, list):
            if not isinstance(key, int) or key >= len(parent):
                raise InvalidTargetError(f"Cannot remove nonexistent list item at {target}")
            parent.pop(key)
        elif isinstance(parent, dict):
            if key not in parent:
                raise InvalidTargetError(f"Cannot remove nonexistent dict key at {target}")
            del parent[key]

def merge_tailoring_changes(base_document: TailoredResumeData, accepted_changes: list) -> TailoredResumeData:
    """
    Deterministically merges accepted changes into a TailoredResumeData object.
    """
    # Convert to dict for easier traversal
    doc_dict = base_document.model_dump()
    
    modified_paths = set()
    
    # Sort changes by some deterministic key, e.g. change_id to ensure order stability if needed
    # But semantically they should be independent
    sorted_changes = sorted(accepted_changes, key=lambda c: c.change_id)
    
    for change in sorted_changes:
        # Avoid conflicting modifications
        if change.target_reference in modified_paths and change.change_type in (ChangeType.MODIFY, ChangeType.REMOVE):
            raise MergeConflictError(f"Conflict at target: {change.target_reference}")
            
        apply_change(
            data_dict=doc_dict,
            target=change.target_reference,
            change_type=change.change_type.value if hasattr(change.change_type, 'value') else change.change_type,
            new_value=change.proposed_text,
            expected_original=change.original_text
        )
        
        modified_paths.add(change.target_reference)
        
    return TailoredResumeData.model_validate(doc_dict)
