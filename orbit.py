from AirSimClient import *
import sys
import math
import time
import argparse
from PIL import Image

class Position:
    def __init__(self, pos):
        self.x = pos.x_val
        self.y = pos.y_val
        self.z = pos.z_val

# Make the drone fly in a circle.
class OrbitNavigator:
    def __init__(self, takeoff = True, radius = 2, altitude = 10, speed = 2, iterations = 1, center = [1,0], snapshots = None, photo_prefix = "photo_"):
        self.radius = radius
        self.altitude = altitude
        self.speed = speed
        self.iterations = iterations
        self.snapshots = snapshots
        self.snapshot_delta = None
        self.next_snapshot = None
        self.z = None
        self.snapshot_index = 0
        self.takeoff = takeoff # whether to do the take off and landing.
        self.photo_prefix = photo_prefix

        if self.snapshots > 0:
            self.snapshot_delta = 360 / self.snapshots

        if self.iterations <= 0:
            self.iterations = 1

        if len(center) != 2:
            raise Exception("Expecting '[x,y]' for the center direction vector")
        
        # center is just a direction vector, so normalize it to compute the actual cx,cy locations.
        cx = float(center[0])
        cy = float(center[1])
        length = math.sqrt(cx*cx)+(cy*cy)
        cx /= length
        cy /= length
        cx *= self.radius
        cy *= self.radius

        self.client = MultirotorClient()
        self.client.confirmConnection()
        self.client.enableApiControl(True)

        self.home = self.getPosition()
        # check that our home position is stable
        start = time.time()
        count = 0
        while count < 100:
            pos = self.home
            if abs(pos.z - self.home.z) > 1:                                
                count = 0
                self.home = pos
                if time.time() - start > 10:
                    print("Drone position is drifting, we are waiting for it to settle down...")
                    start = time
            else:
                count += 1

        self.center = self.getPosition()
        self.center.x += cx
        self.center.y += cy


    def getPosition(self):
        pos = self.client.getPosition()
        return Position(pos)

    def start(self):
        print("arming the drone...")
        self.client.armDisarm(True)
        
        # AirSim uses NED coordinates so negative axis is up.
        start = self.getPosition()
        landed = self.client.getLandedState()
        if self.takeoff and landed == LandedState.Landed: 
            print("taking off...")
            self.client.takeoff()
            start = self.getPosition()
            z = -self.altitude + self.home.z
        else:
            print("already flying so we will orbit at current altitude {}".format(start.z))                
            z = start.z # use current altitude then

        print("climbing to position: {},{},{}".format(start.x, start.y, z))
        self.client.moveToPosition(start.x, start.y, z, self.speed)
        self.z = z
        
        print("ramping up to speed...")
        count = 0
        self.start_angle = None
        self.next_snapshot = None
        
        # ramp up time
        ramptime = self.radius / 10
        self.start_time = time.time()        

        while count < self.iterations:

            # ramp up to full speed in smooth increments so we don't start too aggresively.
            now = time.time()
            speed = self.speed
            diff = now - self.start_time
            if diff < ramptime:
                speed = self.speed * diff / ramptime
            elif ramptime > 0:
                print("reached full speed...")
                ramptime = 0
                
            lookahead_angle = speed / self.radius            

            # compute current angle
            pos = self.getPosition()
            dx = pos.x - self.center.x
            dy = pos.y - self.center.y
            actual_radius = math.sqrt((dx*dx) + (dy*dy))
            angle_to_center = math.atan2(dy, dx)

            camera_heading = (angle_to_center - math.pi) * 180 / math.pi 

            # compute lookahead
            lookahead_x = self.center.x + self.radius * math.cos(angle_to_center + lookahead_angle)
            lookahead_y = self.center.y + self.radius * math.sin(angle_to_center + lookahead_angle)

            vx = lookahead_x - pos.x
            vy = lookahead_y - pos.y

            if self.track_orbits(angle_to_center * 180 / math.pi):
                count += 1
                print("completed {} orbits".format(count))
            
            self.camera_heading = camera_heading
            self.client.moveByVelocityZ(vx, vy, z, 1, DrivetrainType.MaxDegreeOfFreedom, YawMode(False, camera_heading))


        self.client.moveToPosition(start.x, start.y, z, 2)

        if self.takeoff:            
            # if we did the takeoff then also do the landing.
            if z < self.home.z:
                print("descending")
                self.client.moveToPosition(start.x, start.y, self.home.z - 5, 2)

            print("landing...")
            self.client.land()

            print("disarming.")
            self.client.armDisarm(False)


    def track_orbits(self, angle):
        # tracking # of completed orbits is surprisingly tricky to get right in order to handle random wobbles
        # about the starting point.  So we watch for complete 1/2 orbits to avoid that problem.
        if angle < 0:
            angle += 360

        if self.start_angle is None:
            self.start_angle = angle
            if self.snapshot_delta:
                self.next_snapshot = angle + self.snapshot_delta
            self.previous_angle = angle
            self.shifted = False
            self.previous_sign = None
            self.previous_diff = None            
            self.quarter = False
            return False

        # now we just have to watch for a smooth crossing from negative diff to positive diff
        if self.previous_angle is None:
            self.previous_angle = angle
            return False            

        # ignore the click over from 360 back to 0
        if self.previous_angle > 350 and angle < 10:
            if self.snapshot_delta and self.next_snapshot >= 360:
                self.next_snapshot -= 360
            return False

        diff = self.previous_angle - angle
        crossing = False
        self.previous_angle = angle

        if self.snapshot_delta and angle > self.next_snapshot:            
            print("Taking snapshot at angle {}".format(angle))
            self.take_snapshot()
            self.next_snapshot += self.snapshot_delta

        diff = abs(angle - self.start_angle)
        if diff > 45:
            self.quarter = True

        if self.quarter and self.previous_diff is not None and diff != self.previous_diff:
            # watch direction this diff is moving if it switches from shrinking to growing
            # then we passed the starting point.
            direction = self.sign(self.previous_diff - diff)
            if self.previous_sign is None:
                self.previous_sign = direction
            elif self.previous_sign > 0 and direction < 0:
                if diff < 45:
                    crossing = True
                    self.quarter = False
                    
            self.previous_sign = direction
        self.previous_diff = diff

        return crossing

    def take_snapshot(self):
        image_dir = "./images/"
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
        
        # first hold our current position so drone doesn't try and keep flying while we take the picture.
        pos = self.getPosition()
        self.client.moveToPosition(pos.x, pos.y, self.z, 0.5, 10, DrivetrainType.MaxDegreeOfFreedom, YawMode(False, self.camera_heading))
        responses = self.client.simGetImages([ImageRequest(0, AirSimImageType.Scene)]) #scene vision image in png format
        response = responses[0]
        filename = self.photo_prefix + str(self.snapshot_index) + "_" + str(int(time.time())) 
        self.snapshot_index += 1
        AirSimClientBase.write_file(os.path.normpath(image_dir + filename + '.png'), response.image_data_uint8)        
        print("Saved snapshot: {}".format(filename))
        self.start_time = time.time()  # cause smooth ramp up to happen again after photo is taken.

    def sign(self, s):
        if s < 0: 
            return -1
        return 1

def str2bool(v):
    return v.lower() in [ "true", "1", "yes"]

if __name__ == "__main__":
    args = sys.argv
    args.pop(0)
    arg_parser = argparse.ArgumentParser("Orbit.py makes drone fly in a circle with camera pointed at the given center vector")
    arg_parser.add_argument("--radius", type=float, help="radius of the orbit", default=10)
    arg_parser.add_argument("--altitude", type=float, help="altitude of orbit (in positive meters)", default=20)
    arg_parser.add_argument("--speed", type=float, help="speed of orbit (in meters/second)", default=3)
    arg_parser.add_argument("--center", help="x,y direction vector pointing to center of orbit from current starting position (default 1,0)", default="1,0")
    arg_parser.add_argument("--iterations", type=float, help="number of 360 degree orbits (default 3)", default=3)
    arg_parser.add_argument("--snapshots", type=int, help="number of FPV snapshots to take during orbit (default 0)", default=30)    
    arg_parser.add_argument("--takeoff", help="Whether to perform takeoff or not", default="True")
    arg_parser.add_argument("--photo_prefix", help="Snapshot filename prefix", default="photo_")
    args = arg_parser.parse_args(args)    
    nav = OrbitNavigator(str2bool(args.takeoff), args.radius, args.altitude, args.speed, args.iterations, args.center.split(','), args.snapshots, args.photo_prefix)
    nav.start()
