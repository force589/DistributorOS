from fastapi import APIRouter

from distributoros.modules.customers.router import router as customers_router
from distributoros.modules.identity.router import router as auth_router
from distributoros.modules.insights.router import router as insights_router
from distributoros.modules.inventory.router import router as inventory_router
from distributoros.modules.invoices.router import router as invoices_router
from distributoros.modules.ledger.router import router as ledger_router
from distributoros.modules.payments.router import router as payments_router
from distributoros.modules.products.router import router as products_router
from distributoros.modules.sales.router import router as sales_router
from distributoros.modules.tenancy.router import router as business_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(customers_router)
api_router.include_router(products_router)
api_router.include_router(inventory_router)
api_router.include_router(sales_router)
api_router.include_router(ledger_router)
api_router.include_router(payments_router)
api_router.include_router(invoices_router)
api_router.include_router(insights_router)
api_router.include_router(business_router)
