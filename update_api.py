import re
with open('backend/app/api/v1/tailoring.py', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = '''
@router.post("/{session_id}/revise")
async def api_revise_change(
    session_id: str,
    req: CVTailoringReviseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    llm_router = await build_llm_router_for_user(db, user.id)
    try:
        new_change = await revise_change(db, user.id, session_id, req.change_id, req.instruction, llm_router)
        return new_change
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
'''

text = re.sub(r'@router.post\(\"\/\{session_id\}\/revise\"\).*?raise HTTPException\(status_code=501, detail=\"Not implemented yet\"\)', replacement.strip(), text, flags=re.DOTALL)

with open('backend/app/api/v1/tailoring.py', 'w', encoding='utf-8') as f:
    f.write(text)
