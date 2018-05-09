from PIL import Image
import os
 
def crop(image_path, saved_location):
    """
    @param image_path: The path to the image to edit
    @param saved_location:yy Path to save the cropped image
    """
    width=800
    height=800

    img = Image.open(image_path)
    print("Image Size ({},{})".format(img.size[0], img.size[1]))
    middle = ((img.size[0] / 2), (img.size[1] / 2))
    img_x_offset = middle[0] - (width / 2)
    img_y_offset = middle[1] - (height / 2)
    print("Image Offset ({},{})".format(img_x_offset, img_y_offset))
    print("New Size ({},{})".format(img_x_offset + width, img_y_offset + height))
    
    box = (img_x_offset, img_y_offset, img_x_offset + width, img_y_offset + height)

    cropped_image = img.crop(box)
    cropped_image.save(saved_location, "PNG")
  
if __name__ == '__main__':
    directory = os.fsencode("./")
    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        if filename.endswith(".png"):
            crop(filename,filename)
            continue
