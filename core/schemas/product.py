from ninja import Schema


class ProductCreateSchema(Schema):

    business_id: int
    name: str
    description: str | None = None
    price: float


class ProductUpdateSchema(Schema):

    name: str | None = None
    description: str | None = None
    price: float | None = None
    is_active: bool | None = None


class ProductOutSchema(Schema):

    id: int
    business_id: int
    name: str
    description: str | None = None
    image: str | None = None
    price: float
    is_active: bool


class ProductListSchema(Schema):

    id: int
    name: str
    price: float
    image: str | None = None