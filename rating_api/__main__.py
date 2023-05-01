import uvicorn

from rating_api.routes.base import app


if __name__ == '__main__':
    uvicorn.run(app)
