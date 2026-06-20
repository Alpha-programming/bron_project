from ninja import Router
from core.security import JWTAuth
from core.models import User
from core.schemas.branch import (
    BranchCreateSchema,
    BranchUpdateSchema,
    BranchOutSchema,
    BranchListSchema,
)
from core.services.branch import (
    create_branch,
    get_branches,
    get_branch,
    get_business_branches,
    update_branch,
    delete_branch,
)

router = Router(tags=["Branches"])


@router.post("/create", auth=JWTAuth(), response=BranchOutSchema)
def create_branch_view(request, payload: BranchCreateSchema):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)
    return create_branch(user, payload)


@router.get("/", response=list[BranchListSchema])
def branch_list(request):
    return get_branches()


@router.get("/{branch_id}", response=BranchOutSchema)
def branch_detail(request, branch_id: int):
    return get_branch(branch_id)


@router.get("/business/{business_id}", response=list[BranchListSchema])
def business_branches(request, business_id: int):
    return get_business_branches(business_id)


@router.put("/{branch_id}", auth=JWTAuth(), response=BranchOutSchema)
def update_branch_view(request, branch_id: int, payload: BranchUpdateSchema):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    branch = get_branch(branch_id)
    return update_branch(user, branch, payload)


@router.delete("/{branch_id}", auth=JWTAuth())
def delete_branch_view(request, branch_id: int):
    # FIX: Safely extract authenticated user identity from request context
    user = request.auth
    if not user or hasattr(user, '_wrapped'):
        user = User.objects.get(id=request.user.id)

    branch = get_branch(branch_id)
    return delete_branch(user, branch)