from AirSimClient import *
import orbit
import time
from PIL import Image
import os

client = MultirotorClient()
client.confirmConnection()
client.enableApiControl(True)
client.armDisarm(True)

landed = client.getLandedState()

if landed == LandedState.Landed:
    print("taking off...")
    pos = client.getPosition()
    z = pos.z_val - 1
    client.takeoff()
else:
    print("already flying...")
    client.hover()
    pos = client.getPosition()
    z = pos.z_val

image_dir = "./images/"

def OrbitAnimal(cx, cy, radius, speed, altitude, camera_angle, animal):
    """
    @param cx: The x position of our orbit starting location
    @param cy: The x position of our orbit starting location
    @param radius: The radius of the orbit circle
    @param speed: The speed the drone should more, it's hard to take photos when flying fast
    @param altitude: The alitidude we want to fly at, dont fly too high!
    @param camera_angle: The angle of the camera
    @param animal: The name of the animal, used to prefix the photos
    """
    x = cx - radius
    y = cy

    # set camera angle
    client.setCameraOrientation(0, AirSimClientBase.toQuaternion(camera_angle * math.pi / 180, 0, 0)); #radians

    # move the drone to the requested location
    print("moving to position...")
    client.moveToPosition(x, y, z, 1, 60, drivetrain = DrivetrainType.MaxDegreeOfFreedom, yaw_mode = YawMode(False, 0))
    pos = client.getPosition()

    dx = x - pos.x_val
    dy = y - pos.y_val
    yaw = client.getPitchRollYaw()[2]

    # keep the drone on target, it's windy out there!
    print("correcting position and yaw...")   
    while abs(dx) > 1 or abs(dy) > 1 or abs(yaw) > 0.1:
        client.moveToPosition(x, y, z, 0.25, 60, drivetrain = DrivetrainType.MaxDegreeOfFreedom, yaw_mode = YawMode(False, 0))
        pos = client.getPosition()
        dx = x - pos.x_val
        dy = y - pos.y_val   
        yaw = client.getPitchRollYaw()[2]

    print("location is off by {},{}".format(dx, dy))

    o = client.getPitchRollYaw()
    print("yaw is {}".format(o[2]))

    # let's orbit around the animal and take some photos
    nav = orbit.OrbitNavigator(takeoff = False, radius = radius, altitude = altitude, speed = speed, iterations = 1, center = [cx - pos.x_val, cy - pos.y_val], snapshots = 30, photo_prefix = animal)
    nav.start()

def CropImages():
    """
    @param image_path: The path to the image to edit
    @param saved_location:yy Path to save the cropped image
    """
    width=800
    height=800

    os.chdir(image_dir)

    directory = os.fsencode("./")
    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        if filename.endswith(".png"):
            img = Image.open(filename)
            print("Image Size ({},{})".format(img.size[0], img.size[1]))
            middle = ((img.size[0] / 2), (img.size[1] / 2))
            img_x_offset = middle[0] - (width / 2)
            img_y_offset = middle[1] - (height / 2)
            print("Image Offset ({},{})".format(img_x_offset, img_y_offset))
            print("New Size ({},{})".format(img_x_offset + width, img_y_offset + height))
            
            box = (img_x_offset, img_y_offset, img_x_offset + width, img_y_offset + height)

            cropped_image = img.crop(box)
            cropped_image.save(filename, "PNG")

            continue

if __name__ == '__main__':
    #animals = [(19.8, -11, "AlpacaPink"), (5.42, -3.7, "AlpacaTeal"), (-12.18, -13.56, "AlpacaRainbow"), (19.6, 9.6, "BlackSheep"), (-1.9, -0.9, "Bunny"), (3.5, 9.4, "Chick"), (-13.2, -0.25, "Chipmunk"), (-6.55, 12.25, "Hippo")]
    animals = [(19.8, -11, "AlpacaPink")]

    # let's find the animals and take some photos
    for pos in animals:
        print(pos[2])
        OrbitAnimal(pos[0], pos[1], 2, 0.4, 1, -20, pos[2])
        OrbitAnimal(pos[0], pos[1], 1, 0.4, 1, -15, pos[2])
        OrbitAnimal(pos[0], pos[1], 2, 0.4, 1, -40, pos[2])

    # crop 800 x 800 from the center of the image
    CropImages()

    print("Image capture complete...")        

    # that's enough fun for now. let's quit cleanly
    client.armDisarm(False)
    client.reset()
    client.enableApiControl(False)