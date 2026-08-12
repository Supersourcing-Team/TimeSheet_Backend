from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses import created_response, success_response
from app.core.database import get_db
from app.dependencies.permissions import require_roles
from app.modules.clients.schema import ClientCreate, ClientUpdate, ClientResponse
from app.modules.clients.service import ClientService


router = APIRouter()
pm_only = require_roles("Project_Manager")


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED, dependencies=[Depends(pm_only)])
async def create_client(client_in: ClientCreate, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client = await service.create_client(client_in)
    return created_response(data=client.model_dump(mode="json"), message="Client created successfully")


@router.get("", response_model=dict, dependencies=[Depends(pm_only)])
async def get_clients(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    clients = await service.get_all_clients(skip=skip, limit=limit)
    return success_response(data=[c.model_dump(mode="json") for c in clients], message="Clients retrieved successfully")


@router.get("/{client_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client = await service.get_client_by_id(client_id)
    return success_response(data=client.model_dump(mode="json"), message="Client retrieved successfully")


@router.put("/{client_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def update_client(client_id: int, client_in: ClientUpdate, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client = await service.update_client(client_id, client_in)
    return success_response(data=client.model_dump(mode="json"), message="Client updated successfully")



@router.delete("/{client_id}", response_model=dict, dependencies=[Depends(pm_only)])
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    await service.delete_client(client_id)
    return success_response(message="Client deleted successfully")
