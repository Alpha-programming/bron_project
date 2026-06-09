from ninja import Schema


class BranchCreateSchema(Schema):

    business_id: int

    name: str
    address: str
    phone: str

    latitude: float | None = None
    longitude: float | None = None


class BranchUpdateSchema(Schema):

    name: str | None = None
    address: str | None = None
    phone: str | None = None

    latitude: float | None = None
    longitude: float | None = None


class BranchListSchema(Schema):

    id: int

    name: str
    address: str
    phone: str


class BranchOutSchema(Schema):

    id: int

    business_id: int

    name: str
    address: str
    phone: str

    latitude: float | None = None
    longitude: float | None = None