import logging

import uvicorn

from local_llm.app import create_app
from local_llm.settings import MANAGER_HOST, MANAGER_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = create_app()

if __name__ == "__main__":
    uvicorn.run("local_llm.main:app", host=MANAGER_HOST, port=MANAGER_PORT, reload=False)
