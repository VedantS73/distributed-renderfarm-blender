import bpy

fps = bpy.context.scene.render.fps
current_renderer = bpy.context.scene.render.engine

frame_start = bpy.context.scene.frame_start
frame_end = bpy.context.scene.frame_end

lines = []
lines.append("fps:" + str(fps) + "\n")
lines.append("renderer:" + str(current_renderer) + "\n")
lines.append("frame_start:" + str(frame_start) + "\n")
lines.append("frame_end:" + str(frame_end))

with(open("blend_file_data.txt", "w") as file):
    
    file.writelines(lines)

file.close()
bpy.ops.wm.quit_blender()