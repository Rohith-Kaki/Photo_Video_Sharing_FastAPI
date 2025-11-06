from dotenv import load_dotenv
from imagekitio import ImageKit
import os

load_dotenv()

imagekit = ImageKit(
    private_key=os.getenv('IMAGE_KIT_PRIVATE'), 
    public_key= os.getenv("IMAGE_KIT_PUBLIC"),
    url_endpoint= os.getenv("IMAGE_URL")
)