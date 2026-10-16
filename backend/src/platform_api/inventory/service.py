from platform_api.config import get_settings
from platform_api.inventory.repository import (
    InMemoryInventoryRepository,
    InventoryRepository,
    SqlAlchemyInventoryRepository,
)

inventory_repository: InventoryRepository = (
    InMemoryInventoryRepository() if get_settings().demo_mode else SqlAlchemyInventoryRepository()
)
