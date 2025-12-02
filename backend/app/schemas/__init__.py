from pydantic import BaseModel, EmailStr, Field


class LoginSchema(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AddUserSchema(BaseModel):
    username: str = Field(..., min_length=1)
    email: EmailStr
    role: str = Field(default="user")


class ChangePasswordSchema(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)


class UpdateUserRoleSchema(BaseModel):
    username: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)


class DeleteUserSchema(BaseModel):
    username: str = Field(..., min_length=1)


class AddIpSourceSchema(BaseModel):
    source_name: str = Field(..., min_length=1)
    ip_address: str = Field(..., min_length=1)


class DeleteIpSourceSchema(BaseModel):
    ip_address: str = Field(..., min_length=1)
