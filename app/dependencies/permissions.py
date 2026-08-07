from fastapi import Depends, HTTPException, status
from typing import List, Callable

from app.models.user import User
from app.dependencies.auth import get_current_active_user

def require_roles(allowed_roles: List[str]) -> Callable:
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )
        return current_user
    return role_checker

require_admin = require_roles(["Admin"])
require_project_manager = require_roles(["Project_Manager", "Admin"]) # Assuming Admin can do what PM can
require_account_manager = require_roles(["Account_Manager", "Admin"]) # Assuming Admin can do what AM can
