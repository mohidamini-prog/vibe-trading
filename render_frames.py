import bpy
import math

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.render.resolution_x = 720
scene.render.resolution_y = 1280
scene.render.fps = 24
scene.frame_end = 48 # 2 seconds

bpy.ops.object.camera_add(location=(0, -4, 2.0), rotation=(math.radians(70), 0, 0))
scene.camera = bpy.context.active_object

bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, -0.1))
floor = bpy.context.active_object
floor.scale = (3, 4, 0.1)

bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 2, 0.8))
counter = bpy.context.active_object
counter.scale = (2.5, 1, 0.8)

bpy.ops.object.light_add(type='POINT', location=(0, 0, 3.5))
light = bpy.context.active_object
light.data.energy = 1500
light.data.color = (1.0, 0.9, 0.7)

scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = '/root/forschung/frame_'

bpy.ops.render.render(animation=True)
print("Frames rendered.")
