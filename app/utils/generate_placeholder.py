from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def generate_placeholder_image():
    # Create directory if it doesn't exist
    static_dir = Path(__file__).parent.parent / "static" / "images"
    static_dir.mkdir(parents=True, exist_ok=True)

    # Create a new image with a gradient background
    width = 1000
    height = 600
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)

    # Draw some mock dashboard elements
    # Background
    draw.rectangle([0, 0, width, height], fill='#f8f9fa')
    
    # Header
    draw.rectangle([50, 50, width-50, 150], fill='#ffffff', outline='#e1e4e8')
    
    # Sidebar
    draw.rectangle([50, 170, 250, height-50], fill='#ffffff', outline='#e1e4e8')
    
    # Main content area
    draw.rectangle([270, 170, width-50, height-50], fill='#ffffff', outline='#e1e4e8')
    
    # Add some mock charts/graphs
    # Chart 1
    draw.rectangle([290, 190, 590, 370], fill='#e1e4e8')
    # Chart 2
    draw.rectangle([610, 190, 910, 370], fill='#e1e4e8')
    # Chart 3
    draw.rectangle([290, 390, 910, 530], fill='#e1e4e8')

    # Save the image
    image_path = static_dir / "log-analyzer.png"
    image.save(image_path)
    return image_path

if __name__ == "__main__":
    generate_placeholder_image() 