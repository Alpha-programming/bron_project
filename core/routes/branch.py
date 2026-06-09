from ninja import Router

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

from core.utils.auth import (
    get_current_user
)

router = Router(tags=["Branches"])

@router.post(
    "/create",
    response=BranchOutSchema
)
def create_branch_view(
    request,
    payload: BranchCreateSchema
):

    user = get_current_user(
        request
    )

    return create_branch(
        user,
        payload
    )

@router.get(
    "/",
    response=list[BranchListSchema]
)
def branch_list(request):

    return get_branches()

@router.get(
    "/{branch_id}",
    response=BranchOutSchema
)
def branch_detail(
    request,
    branch_id: int
):

    return get_branch(
        branch_id
    )

@router.get(
    "/business/{business_id}",
    response=list[BranchListSchema]
)
def business_branches(
    request,
    business_id: int
):

    return get_business_branches(
        business_id
    )

@router.put(
    "/{branch_id}",
    response=BranchOutSchema
)
def update_branch_view(
    request,
    branch_id: int,
    payload: BranchUpdateSchema
):

    user = get_current_user(
        request
    )

    branch = get_branch(
        branch_id
    )

    return update_branch(
        user,
        branch,
        payload
    )

@router.delete(
    "/{branch_id}"
)
def delete_branch_view(
    request,
    branch_id: int
):

    user = get_current_user(
        request
    )

    branch = get_branch(
        branch_id
    )

    return delete_branch(
        user,
        branch
    )