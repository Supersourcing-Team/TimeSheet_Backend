from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status
from app.modules.clients.repository import ClientRepository
from app.modules.clients.schema import ClientCreate, ClientUpdate, ClientResponse


class ClientService:
    def __init__(self, db: AsyncSession):
        self.repository = ClientRepository(db)

    async def get_client_by_id(self, client_id: int) -> ClientResponse:
        client = await self.repository.get_by_id(client_id)
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
        return ClientResponse.model_validate(client)

    async def get_all_clients(self, skip: int = 0, limit: int = 100) -> List[ClientResponse]:
        clients = await self.repository.get_all(skip=skip, limit=limit)
        return [ClientResponse.model_validate(c) for c in clients]

    async def create_client(self, client_in: ClientCreate) -> ClientResponse:
        client = await self.repository.create(client_in)
        return ClientResponse.model_validate(client)

    async def update_client(self, client_id: int, client_in: ClientUpdate) -> ClientResponse:
        client = await self.repository.get_by_id(client_id)
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
        
        updated_client = await self.repository.update(client, client_in)
        return ClientResponse.model_validate(updated_client)

    async def delete_client(self, client_id: int) -> None:
        client = await self.repository.get_by_id(client_id)
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
        
        await self.repository.soft_delete(client)
