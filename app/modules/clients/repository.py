from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.model import Client
from app.modules.clients.schema import ClientCreate, ClientUpdate


class ClientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, client_id: int) -> Optional[Client]:
        result = await self.db.execute(
            select(Client).where(Client.id == client_id, Client.is_active == True)
        )
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Client]:
        result = await self.db.execute(
            select(Client).where(Client.is_active == True).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, client_in: ClientCreate) -> Client:
        client = Client(**client_in.model_dump())
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def update(self, client: Client, client_in: ClientUpdate) -> Client:
        update_data = client_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(client, field, value)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def soft_delete(self, client: Client) -> Client:
        client.is_active = False
        await self.db.commit()
        await self.db.refresh(client)
        return client
