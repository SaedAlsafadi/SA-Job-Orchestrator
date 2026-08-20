import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        res = await client.post('https://apply.workable.com/api/v3/accounts/workable/jobs', json={"query":"","location":[],"department":[],"worktype":[],"remote":[]})
        results = res.json().get('results', [])
        if results:
            print(results[0]['url'] + "/apply")
        else:
            print("No jobs found for workable")

asyncio.run(main())
