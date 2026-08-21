import httpx, asyncio
from app.core.security import create_access_token

async def run():
    token = create_access_token('f9305c63796d4430bcdb178025ea6d64')
    res = await httpx.AsyncClient(timeout=60.0).post('http://localhost:8000/api/v1/workflow/discover', headers={'Authorization': f'Bearer {token}'}, json={'url': 'https://jobs.workable.com/en/view/ww7scbfrJsQ5jU9qjNLada/document-controller-in-riyadh-at-hanmiglobal-saudi'})
    print('STATUS:', res.status_code)
    data = res.json()
    print('JOBS:', len(data.get('jobs', [])))
asyncio.run(run())
