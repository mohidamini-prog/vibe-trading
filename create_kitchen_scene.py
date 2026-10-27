import bpy
import math

# Clear existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Set up render settings for quality
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 32
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.fps = 24

# Create Camera
bpy.ops.object.camera_add(location=(0, -4, 2.5), rotation=(math.radians(65), 0, 0))
camera = bpy.context.active_object
scene.camera = camera

# Create Kitchen Floor (using primitive_cube_add)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -0.1))
floor = bpy.context.active_object
floor.scale = (3, 4, 0.1)

# Create Kitchen Counter
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 2, 0.9))
counter = bpy.context.active_object
counter.scale = (2.5, 1, 0.9)

# Create Warm Lighting
bpy.ops.object.light_add(type='POINT', location=(0, 0, 4))
light = bpy.context.active_object
light.data.energy = 1500
light.data.color = (1.0, 0.85, 0.6)

print("Kitchen 3D scene successfully generated.")
