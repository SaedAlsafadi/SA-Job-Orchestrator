import asyncio
import io
from pathlib import Path

from starlette.datastructures import UploadFile

from app.db.session import async_session_factory
from app.services.resume import upload_resume


async def main() -> None:
    async with async_session_factory() as session:
        file_path = Path("test_candidate_cv.pdf")
        with open(file_path, "rb") as f:
            content = f.read()

        file = UploadFile(filename="test_candidate_cv.pdf", file=io.BytesIO(content))
        response = await upload_resume(session, file, "test-user-id")
        print(response)


if __name__ == "__main__":
    asyncio.run(main())
