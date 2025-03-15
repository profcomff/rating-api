from pydantic import BaseModel, ConfigDict


class Base(BaseModel):
    def __repr__(self) -> str:
        attrs = []
        return "{}({})".format(self.__class__.__name__, ', '.join(attrs))

    model_config = ConfigDict(from_attributes=True)


class StatusResponseModel(Base):
    status: str
    message: str
    ru: str
