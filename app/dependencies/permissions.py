
from typing import Callable, List
from fastapi import Depends, HTTPException, status

from app.dependencies.auth import get_current_active_user
from app.modules.users.model import User


class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        roles = []
        for r in allowed_roles:
            if isinstance(r, (list, tuple)):
                roles.extend(r)
            else:
                roles.append(r)
        self.allowed_roles = roles

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        user_role = current_user.role.name if current_user.role else ""
        if user_role.lower() == "admin" or user_role in self.allowed_roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted. Required role: {', '.join(self.allowed_roles)}",
        )


def require_roles(*roles: str) -> Callable:
    return RoleChecker(allowed_roles=list(roles))


require_admin = require_roles("Admin")
require_project_manager = require_roles("Admin", "Project_Manager")
require_account_manager = require_roles("Admin", "Account_Manager")
