from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_users():
    return {"message": "Get all users endpoint"}

@router.get("/{user_id}")
def get_user(user_id: int):
    return {"message": f"Get user with ID: {user_id}"}

@router.post("/")
def create_user():
    return {"message": "Create user endpoint"}

@router.put("/{user_id}")
def update_user(user_id: int):
    return {"message": f"Update user with ID: {user_id}"}

@router.delete("/{user_id}")
def delete_user(user_id: int):
    return {"message": f"Delete user with ID: {user_id}"}