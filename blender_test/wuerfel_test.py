# Blender-Testszene: rotierender Wuerfel, Kamera, Licht -> MP4
import bpy, math, os, sys, time

ENGINE = os.environ.get("ENGINE", "CYCLES")   # oder "BLENDER_EEVEE" (hier ~2x langsamer)
OUT = os.environ.get("OUT", os.path.expanduser("~/forschung/blender_test/wuerfel.mp4"))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Wuerfel mit Material
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
cube = bpy.context.active_object
mat = bpy.data.materials.new("Rot")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.1, 0.1, 1)
cube.data.materials.append(mat)

# Boden
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -1))

# Kamera
bpy.ops.object.camera_add(location=(6, -6, 4))
cam = bpy.context.active_object
c = cam.constraints.new("TRACK_TO"); c.target = cube
scene.camera = cam

# Licht
bpy.ops.object.light_add(type="SUN", location=(4, -2, 6))
bpy.context.active_object.data.energy = 4
world = bpy.data.worlds.new("Welt"); scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[1].default_value = 0.5

# Animation: 360 Grad ueber 75 Frames (3 s bei 25 fps), linear
scene.frame_start, scene.frame_end = 1, 75
scene.render.fps = 25
cube.rotation_euler = (0, 0, 0); cube.keyframe_insert("rotation_euler", frame=1)
cube.rotation_euler = (0, 0, math.radians(360)); cube.keyframe_insert("rotation_euler", frame=76)
try:
    for fc in cube.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
except AttributeError:
    # Blender 5.x: Layered Actions
    for layer in cube.animation_data.action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for fc in bag.fcurves:
                    for kp in fc.keyframe_points: kp.interpolation = "LINEAR"

# Render-Einstellungen
r = scene.render
r.engine = ENGINE
r.resolution_x, r.resolution_y, r.resolution_percentage = 640, 360, 100
if ENGINE == "CYCLES":
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
else:
    try: scene.eevee.taa_render_samples = 16
    except Exception: pass

# Ausgabe direkt als MP4 (H.264) ueber FFmpeg in Blender
if hasattr(r.image_settings, "media_type"):  # ab Blender 5.0
    r.image_settings.media_type = "VIDEO"
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "MEDIUM"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
r.filepath = OUT

t = time.time()
bpy.ops.render.render(animation=True)
print(f"RENDERZEIT: {time.time()-t:.1f} s  Engine={ENGINE}  Datei={OUT}")
