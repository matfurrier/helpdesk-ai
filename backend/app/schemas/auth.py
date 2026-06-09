from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    credential: str  # email or AD login
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(strict=True)

    user_id: str
    login: str
    name: str
    email: str
    role: str
