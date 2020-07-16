# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import os
from bpy.types import (
    Operator,
    AddonPreferences,
    EnumProperty,
)

bl_info = {
    "name": "Animatic Video Sequencer",
    "author": "Edward S. White",
    "description": "Imports an image sequence as an animatic",
    "blender": (2, 80, 0),
    "version": (0, 8, 8),
    "location": "Sequencer > Add > Images as Animatic",
    "doc_url": "https://github.com/edwardswhite/AnimaticVideoSequencer/wiki",
    "tracker_url": "https://github.com/edwardswhite/AnimaticVideoSequencer/issues",
    "category": "Sequencer"
}


def ShowMessageBox(message="", title="Message Box", icon='INFO'):

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class AnimaticvsAddonPreferences(AddonPreferences):
    """Animatic Video Sequencer Addon Preferences"""
    bl_idname = __package__

    start_tcursor: bpy.props.BoolProperty(
        name="Start at Time Cursor",
        description="Start inserting images at the time cursor",
        default=False
    )
    last_frame_Len: bpy.props.IntProperty(
        name="Last Frame Length",
        description="Time for the last frame to be visible. Zero is average",
        default=0,
        min=0
    )
    extend_length: bpy.props.BoolProperty(
        name="Extend Scene Length",
        description="Change the scene end frame to include the last frame",
        default=False
    )
    scene_resolution: bpy.props.EnumProperty(
        name="Change Scene Resolution",
        description="Change the scene resolution",
        items=[
            ('DONT', "No",
             "Do not change the scene resolution"),
            ('FILE', "FPS File",
             "Use the scene resolution defined in the FPS.txt file"),
        ],
        default='DONT'
    )
    scene_fps: bpy.props.EnumProperty(
        name="Change Scene Frame Rate",
        description="Change the scene frame rate (FPS)",
        items=[
            ('DONT', "No",
             "Do not change the scene frame rate"),
            ('FILE', "FPS File",
             "Use the scene frame rate defined in the FPS.txt file"),
        ],
        default='DONT'
    )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        cola = row.column()
        cola.prop(self, 'start_tcursor')
        colb = row.column()
        colb.alignment = 'RIGHT'
        colb.prop(self, 'extend_length')

        row = layout.row()
        row.label(text="Last Image Frame Length:")
        row.prop(self, 'last_frame_Len', text=" ")
        layout.separator()
        row = layout.row()
        cola = row.column()
        cola.label(text="Change Scene Resolution")
        cola.prop(self, 'scene_resolution', text="")
        colb = row.column()
        colb.label(text="Change Scene Frame Rate")
        colb.prop(self, 'scene_fps', text="")
        layout.separator()


class SB_OT_animatic_strip_add(Operator):
    """Add an image sequence as an animatic in the sequencer"""
    bl_idname = "sequencer.animatic_strip_add"
    bl_label = "Images as Animatic"
    bl_description = "Add an image sequence as an animatic in the sequencer"

    directory: bpy.props.StringProperty(
        name="Inputdir Path",
        description="The folder of images",
        default="\\"
    )
    relative_path: bpy.props.BoolProperty(
        name="Relative Path",
        description="Select the file relative to the blend file",
        default=True
    )
    vid_channel: bpy.props.IntProperty(
        name="Channel",
        description="Channel to place this strip into",
        default=2,
        min=1,
        max=32
    )
    # Special fileselect_add options start here
    start_tcursor: bpy.props.BoolProperty(
        name="Start at Time Cursor",
        description="Start inserting images at the time cursor",
        # default=False
    )
    last_frame_Len: bpy.props.IntProperty(
        name="Last Frame Length",
        description="Time for the last frame to be visible. Zero is average",
        # default=30,
        min=0
    )
    extend_length: bpy.props.BoolProperty(
        name="Extend Scene Length",
        description="Change the scene end frame to include the last frame",
        # default=False
    )
    import_fps: bpy.props.BoolProperty(
        name="Change Scene Frame Rate",
        description="Change the scene frame rate if FPS.txt file exists",
        # default=False
    )
    change_res: bpy.props.BoolProperty(
        name="Change Scene Resolution",
        description="Change the scene resolution if FPS.txt file exists",
        # default=False
    )

    _timer = None
    stop = None
    ready_to_add = True
    zpad = -4
    im_list = None
    findex = 0
    f_start = 1
    f_offset = 0
    f_end = None
    total_frames = None
    avg_frame_list = []
    clean_ext_done = False
    img_ext = ['.BMP', '.EXR', '.PNG', '.JPG',
               '.JPEG', '.TIF', '.TIFF', '.TARGA', '.TGA']

    def __init__(self):
        print("Animatic Video Sequencer started...")

    # def __del__(self):
    #     print("Animatic Video Sequencer finished.")

    def invoke(self, context, event):
        preferences = bpy.context.preferences.addons[__name__].preferences
        self.start_tcursor = preferences.start_tcursor
        self.last_frame_Len = preferences.last_frame_Len
        self.extend_length = preferences.extend_length
        if preferences.scene_fps == 'FILE':
            self.import_fps = True
        if preferences.scene_resolution == 'FILE':
            self.change_res = True
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if not self.clean_ext_done:
            im_path = self.directory
            self.im_list = os.listdir(im_path)
            im_index = len(self.im_list)
            while im_index:
                im_index -= 1
                fname, fext = os.path.splitext(self.im_list[im_index])
                if fname[-5:].isnumeric():
                    self.zpad = -5
                if fname[-6:].isnumeric():
                    self.zpad = -6
                fn = fname.upper()
                fe = fext.upper()
                if fn == "FPS" and fe == ".TXT":
                    fps_file = self.directory + self.im_list[im_index]
                    readfile = open(fps_file)
                    for line in readfile:
                        if line.startswith("FPS:") and self.import_fps:
                            fps_line = line.rsplit(": ")
                            if len(fps_line) == 2:
                                fps_num = float(fps_line[1])
                                bpy.context.scene.render.fps = fps_num
                                fps_msg = "Scene frame rate changed to:"
                                print(fps_msg, fps_num)
                        if line.startswith("RES_X:") and self.change_res:
                            srender = bpy.context.scene.render
                            fps_line = line.rsplit(": ")
                            if len(fps_line) == 2:
                                res_x = int(fps_line[1])
                                srender.resolution_x = res_x
                                fps_msg = "Scene frame res X changed to:"
                                print(fps_msg, res_x)
                        if line.startswith("RES_Y:") and self.change_res:
                            srender = bpy.context.scene.render
                            fps_line = line.rsplit(": ")
                            if len(fps_line) == 2:
                                res_y = int(fps_line[1])
                                srender.resolution_y = res_y
                                fps_msg = "Scene frame res Y changed to:"
                                print(fps_msg, res_y)
                    readfile.close()
                    self.im_list.pop(im_index)
                elif fe not in self.img_ext:
                    self.im_list.pop(im_index)
                elif fe in self.img_ext and not fn[self.zpad:].isnumeric():
                    print("Skipping image:", fn)
                    self.im_list.pop(im_index)

            self.total_frames = len(self.im_list)
            if not self.total_frames:
                print("No files to load!")
                print("Animatic Video Sequencer - CANCELLED")
                ShowMessageBox("No files to load!",
                               "Images as Animatic",
                               'ERROR')
                return {'CANCELLED'}
            self.clean_ext_done = True

        if self.start_tcursor:
            self.f_start = bpy.context.scene.frame_current
            self.f_offset = self.f_start
            self.f_end = self.f_start  # VSE frame end
        else:
            fname, fext = os.path.splitext(self.im_list[0])
            self.f_start = int(fname[-4:])
            self.f_end = self.f_start  # VSE frame end

        wm = bpy.context.window_manager
        self._timer = wm.event_timer_add(0.1, window=bpy.context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def modal(self, context, event):

        if event.type in {'ESC'}:
            print("Animatic Video Sequencer - CANCELLED")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self.stop is True:
                bpy.context.window_manager.event_timer_remove(self._timer)
                ShowMessageBox("Finished Adding",
                               "Images as Animatic",
                               'INFO')
                return {"FINISHED"}
            elif self.ready_to_add:
                bpy.context.scene.frame_set(self.f_end + 1)
                self.ready_to_add = False
                fname, fext = os.path.splitext(self.im_list[self.findex])
                if (self.findex + 1) < len(self.im_list):
                    # Peek at next frame number
                    nextimage, fext = os.path.splitext(
                        self.im_list[self.findex + 1])
                    self.f_end = self.f_offset + \
                        (int(nextimage[self.zpad:]) - 1)
                else:
                    print("Last frame being calculated")
                    if self.last_frame_Len == 0:
                        sum_frames = sum(self.avg_frame_list)
                        f_average = int(sum_frames / len(self.avg_frame_list))
                        print("Average frame length", f_average)
                        self.f_end = self.f_start + f_average
                    else:
                        self.f_end = self.f_start + self.last_frame_Len
                bpy.ops.sequencer.image_strip_add(directory=self.directory, files=[
                    {"name": self.im_list[self.findex], "name": self.im_list[self.findex]}], relative_path=self.relative_path, show_multiview=False, frame_start=self.f_start, frame_end=self.f_end, channel=2)
                frame_length = 1 + (self.f_end - self.f_start)
                self.avg_frame_list.append(frame_length)
                self.f_start = self.f_end + 1
                self.findex += 1
                self.ready_to_add = True

        if self.findex >= self.total_frames:
            scn_end = bpy.context.scene.frame_end
            if self.extend_length and (self.f_end > scn_end):
                print("Extended current scene end frame from %s to %s." %
                      (str(scn_end), str(self.f_end)))
                bpy.context.scene.frame_end = self.f_end
            self.stop = True

        return {'PASS_THROUGH'}


classes = (
    AnimaticvsAddonPreferences,
    SB_OT_animatic_strip_add,
)


def menu_func_animatic(self, context):
    self.layout.operator(SB_OT_animatic_strip_add.bl_idname,
                         text="Images as Animatic",
                         icon='FILE_IMAGE')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.SEQUENCER_MT_add.append(menu_func_animatic)


def unregister():
    bpy.types.SEQUENCER_MT_add.remove(menu_func_animatic)
    for cls in classes:
        bpy.utils.unregister_class(cls)
