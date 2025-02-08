from pathlib import Path
from app.utils.generate_placeholder import generate_placeholder_image

def setup_static_directory():
    # Create static directory structure
    app_dir = Path(__file__).parent.parent
    static_dir = app_dir / "static"
    images_dir = static_dir / "images"
    
    # Create directories if they don't exist
    static_dir.mkdir(exist_ok=True)
    images_dir.mkdir(exist_ok=True)
    
    # Generate placeholder image
    image_path = generate_placeholder_image()
    print(f"Created placeholder image at: {image_path}")
    return static_dir

if __name__ == "__main__":
    setup_static_directory() 