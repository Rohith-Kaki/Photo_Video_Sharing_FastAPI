from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import UserCreate, UserRead, UserUpdate
from app.db import Post, create_db_and_tables, get_async_session, User
from contextlib import asynccontextmanager
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from app.images import imagekit
from imagekitio.models.UploadFileRequestOptions import UploadFileRequestOptions
import os
import uuid
import tempfile
import shutil
from app.users import fastapi_users, auth_backend, current_active_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["Users"])


@app.post('/upload')
async def upload_file(
    file: UploadFile = File(...), caption: str = Form(""),user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session) #dependency injection.
    ):
    temp_file = None
    try:
        #we are splitting filename and get the type of file (.jgp, .pdf) and creating a temporary file with the saeme extension
        with tempfile.NamedTemporaryFile(delete=False, suffix= os.path.splitext(file.filename)[1]) as temp_file:
            #and copy the content into the temp file 
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
            
        # now you need to save the copied file into imagekit
        upload_result = imagekit.upload_file(
            file = open(temp_file_path, "rb"), 
            file_name= file.filename,
            options= UploadFileRequestOptions(
                use_unique_file_name = True, 
                tags=['backend-upload']
            )
        )
        
        if upload_result.response_metadata.http_status_code == 200:
            post = Post(
                user_id = user.id,
                caption = caption, 
                url = upload_result.url,
                file_type = "video" if file.content_type.startswith("video/") else "image",
                file_name = upload_result.name 
            )
            session.add(post)
            await session.commit() #id and created_at are generated automatically
            await session.refresh(post) #u get the added data id and created_at as a part of the post.
            return post
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        file.file.close()

@app.get('/feed')
async def get_feed(
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    result = await session.execute(Select(Post).order_by(Post.created_at.desc()))
    #since you can only return json like data convert it from list..
    posts = [row[0] for row in result.all()] 

    result = await session.execute(Select(User))
    users = [row[0] for row in result.all()]
    user_dict = {u.id:u.email for u in users}


    posts_data = []
    for post in posts:
        posts_data.append(
            {
                "id": str(post.id),
                "user_id": str(post.user_id),
                "caption": post.caption, 
                "url":post.url, 
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat(),
                "is_owner": post.user_id == user.id,
                "email": user_dict.get(post.user_id, "Unknown")
            }
        )
    return {"posts": posts_data}

@app.delete('/posts/{post_id}')
async def delete_post(
    post_id: str, session:AsyncSession = Depends(get_async_session), user: User = Depends(current_active_user)
    ):
    try:
        post_uuid = uuid.UUID(post_id) #the post_id from url is string converting it back to uuid object to compare and delete.
        result = await session.execute(Select(Post).where(Post.id == post_uuid))
        post = result.scalars().first() #this will directly give the result and we can skip looping throught the objects.

        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if post.user_id != user.id:
            raise HTTPException(status_code=403, detail="You didn't have access to delete this post.")

        await session.delete(post)
        await session.commit()
        return {"success": True, "message": "Post Deleted Successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))