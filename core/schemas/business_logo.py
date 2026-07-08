from ninja import Schema


class BusinessLogoOutSchema(Schema):

    id: int

    logo: str | None