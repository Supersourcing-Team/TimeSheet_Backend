
from typing import Callable, List
from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_active_user
from app.models.user import User


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if not current_user.role or current_user.role.name not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required role: {', '.join(self.allowed_roles)}",
            )
        return current_user


def require_roles(*roles: str) -> Callable:
    return RoleChecker(allowed_roles=list(roles))


require_admin = require_roles("Admin")
require_project_manager = require_roles("Admin", "Project_Manager")
require_account_manager = require_roles("Admin", "Account_Manager")
