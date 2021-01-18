'''
	Sega Virtua Processor Blender Plugin
	Copyright 2020 Ralakimus

	Permission is hereby granted, free of charge, to any person obtaining a copy
	of this software and associated documentation files (the "Software"), to deal
	in the Software without restriction, including without limitation the rights
	to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
	copies of the Software, and to permit persons to whom the Software is
	furnished to do so, subject to the following conditions:

	The above copyright notice and this permission notice shall be included in all
	copies or substantial portions of the Software.

	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
	SOFTWARE.
'''

#############################
# See README.md for details #
#############################

# Add-on info
bl_info = {
	"name": "SEGA Virtua Processor format (.svp)",
	"author": "Ralakimus",
	"version": (1, 0, 0),
	"blender": (2, 80, 0),
	"location": "File > Import-Export",
	"description": "Import-Export SVP, Import SVP mesh",
	"category": "Import-Export"}

# Imports
import bpy, bgl, bmesh, struct, os, mathutils;
from bpy.props import (StringProperty)
from bpy_extras.io_utils import (ImportHelper, ExportHelper, orientation_helper, axis_conversion)

# Show message box
def show_message(message, title, icon):
	def draw(self, context):
		self.layout.label(text=message);
	bpy.context.window_manager.popup_menu(draw, title=title, icon=icon);

# MD color to RGB
def md_to_rgb(color):
	r = (color & 0xE) / 14.0;
	g = ((color & 0xE0) >> 4) / 14.0;
	b = ((color & 0xE00) >> 8) / 14.0;
	return r, g, b;

# Import helper
class ImportSVP(bpy.types.Operator, ImportHelper):
	"""Import a SEGA Virtua Processor Model File"""
	bl_idname = "import_scene.svp";
	bl_label = "Import SVP";
	bl_options = {"PRESET", "UNDO"};

	filename_ext = ".svp";
	filter_glob: StringProperty(default="*.svp", options={"HIDDEN"});

	def execute(self, context):
		return import_svp(context, self.filepath);

# Import the model
def import_svp(context, path):
	# Open model
	data = open(path, mode="rb").read();

	# Get face count
	face_count = struct.unpack(">H", data[:2])[0] + 1;
	print("Face count:", face_count);
	
	# Prepare model data
	vert_data = [];
	face_data = [];
	col_data = [];
	dither_data = [];
	cull_data = [];
	flag_data = [];
	cur_vert = 0;
	
	# Parse and load faces
	data_offset = 2;
	for i in range(face_count):
		# Get colors
		color = struct.unpack(">B", data[data_offset:data_offset+1:])[0];
		col_data.append(color);
		data_offset += 1;
		
		# Get flags
		flags = struct.unpack(">B", data[data_offset:data_offset+1:])[0];
		data_offset += 1;
		
		# Square flag
		is_square = (flags & 0x10) == 0;
			
		# Dither pattern
		dither_data.append((flags & 0x20) >> 5);
			
		# Culling
		cull_data.append((flags & 0x40) >> 6);

		# Flags (something to do with Z-sorting it seems)
		flag_data.append(flags & 0xF);
			
		# Get face vertices
		verts = [];
		for j in range(3*3):
			verts.append(struct.unpack(">h", data[data_offset:data_offset+2:])[0] / 256.0);
			data_offset += 2;
		vert_data.append((verts[0], verts[2], verts[1]));
		vert_data.append((verts[3], verts[5], verts[4]));
		vert_data.append((verts[6], verts[8], verts[7]));
			
		# Square
		if (is_square):
			for j in range(3):
				verts.append(struct.unpack(">h", data[data_offset:data_offset+2:])[0] / 256.0);
				data_offset += 2;
			vert_data.append((verts[9], verts[11], verts[10]));
			face_data.append((cur_vert, cur_vert+1, cur_vert+2, cur_vert+3));
			cur_vert += 4;
				
		# Triangle
		else:
			face_data.append((cur_vert, cur_vert+1, cur_vert+2));
			cur_vert += 3;
			
	# Create the object
	view_layer = context.view_layer;
	collection = view_layer.active_layer_collection.collection;
	if bpy.ops.object.select_all.poll():
		bpy.ops.object.select_all(action="DESELECT")
	mesh_data = bpy.data.meshes.new("SVP Model Mesh");
	mesh_data.from_pydata(vert_data, [], face_data);
	mesh_data.update();
	obj = bpy.data.objects.new("SVP Model", mesh_data);
	collection.objects.link(obj);
	obj.select_set(True);
	view_layer.update();

	# Get BMesh
	bm = bmesh.new();
	if obj.mode == "EDIT":
		bm = bmesh.from_edit_mesh(obj.data);
	else:
		bm.from_mesh(obj.data);

	# Assign palette and dither IDs
	pal_tag = bm.faces.layers.int.new("palette_ids");
	dither_tag = bm.faces.layers.int.new("dither_ids");
	cull_tag = bm.faces.layers.int.new("cull_ids");
	flag_tag = bm.faces.layers.int.new("flag_ids");
	if hasattr(bm.faces, "ensure_lookup_table"): 
		bm.faces.ensure_lookup_table();
	for i in range(0, len(face_data)):
		bm.faces[i][pal_tag] = col_data[i];
		bm.faces[i][dither_tag] = dither_data[i];
		bm.faces[i][cull_tag] = cull_data[i];
		bm.faces[i][flag_tag] = flag_data[i];

	# Save changes
	if obj.mode == "EDIT":
		bmesh.update_edit_mesh(obj.data);
	else:
		bm.to_mesh(obj.data);

	return {"FINISHED"};

# Export helper
class ExportSVP(bpy.types.Operator, ExportHelper):
	"""Export a SEGA Virtua Processor Model File"""
	bl_idname = "export_scene.svp";
	bl_label = "Export SVP";
	bl_options = {"PRESET"};

	filename_ext = ".svp"
	filter_glob: StringProperty(default="*.svp", options={"HIDDEN"});

	def execute(self, context):
		return export_svp(context, self.filepath);

# Export the model
def export_svp(context, path):
	# Prepare output data
	out_data = [];

	# Go through each object
	for obj in context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Set face count
			out_data.append(((len(bm.faces) - 1) >> 8) & 0xFF);
			out_data.append(((len(bm.faces) - 1)) & 0xFF);

			# Get layers
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			layers_created = False;
			pal_tag = bm.faces.layers.int.get("palette_ids");
			dither_tag = bm.faces.layers.int.get("dither_ids");
			cull_tag = bm.faces.layers.int.get("cull_ids");
			if (pal_tag is None):
				layers_created = True;
				pal_tag = bm.faces.layers.int.new("palette_ids");
			if (dither_tag is None):
				dither_tag = bm.faces.layers.int.new("dither_ids");
			if (cull_tag is None):
				cull_tag = bm.faces.layers.int.new("cull_ids");

			# Go through each face
			face_id = 0;
			for face in bm.faces:
				if (len(face.verts) == 3) or (len(face.verts) == 4):
					# Color
					if (layers_created):
						bm.faces[face_id][pal_tag] = 0x11;
					out_data.append(bm.faces[face_id][pal_tag]);

					# Flags
					flags = (bm.faces[face_id][dither_tag] << 5) | (bm.faces[face_id][cull_tag] << 6);
					if (len(face.verts) == 3):
						flags |= 0x10;
					out_data.append(flags);

					# Vertices
					for vertex in range(0, len(face.verts)):
						pos = int(face.verts[vertex].co[0] * 256.0);
						out_data.append((pos >> 8) & 0xFF);
						out_data.append(pos & 0xFF);

						pos = int(face.verts[vertex].co[2] * 256.0);
						out_data.append((pos >> 8) & 0xFF);
						out_data.append(pos & 0xFF);

						pos = int(face.verts[vertex].co[1] * 256.0);
						out_data.append((pos >> 8) & 0xFF);
						out_data.append(pos & 0xFF);

				else:
					show_message("SVP models cannot have more than 4 vertices.", "Error", "ERROR");
					file.close();
					return;
				face_id += 1;

	# Save
	file = open(path, "wb");
	file.write(bytearray(out_data));
	file.close();

	return {"FINISHED"};

# SVP palette
class SVPPalette(bpy.types.PropertyGroup):
	color0: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color1: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color2: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color3: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color4: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color5: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color6: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color7: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color8: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color9: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color10: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color11: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color12: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color13: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color14: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);
	color15: bpy.props.FloatVectorProperty(name="", subtype="COLOR", default=[0.0,0.0,0.0]);

# Operator for loading an SVP palette
class SVPPalLoadOperator(bpy.types.Operator, ImportHelper):
	bl_idname = "svp.load_palette";
	bl_label = "Load Palette";
	bl_options = {"PRESET"};

	filename_ext = ".pal";
	filter_glob: StringProperty(default="*.pal", options={"HIDDEN"});

	def execute(self, context):
		return svp_load_palette(context, self.filepath);

# Load an SVP palette
def svp_load_palette(context, path):
	# Get scene
	scene = bpy.context.scene;

	# Load palette data
	data = open(path, mode="rb").read();
	data_offset = 0;
	for i in range (0, 16):
		try:
			color = md_to_rgb(struct.unpack(">H", data[data_offset:data_offset+2:])[0]);
		except:
			return {"FINISHED"};

		# UGH!!!!
		if (i == 0):
			scene.svp_palette.color0 = color;
		elif (i == 1):
			scene.svp_palette.color1 = color;
		elif (i == 2):
			scene.svp_palette.color2 = color;
		elif (i == 3):
			scene.svp_palette.color3 = color;
		elif (i == 4):
			scene.svp_palette.color4 = color;
		elif (i == 5):
			scene.svp_palette.color5 = color;
		elif (i == 6):
			scene.svp_palette.color6 = color;
		elif (i == 7):
			scene.svp_palette.color7 = color;
		elif (i == 8):
			scene.svp_palette.color8 = color;
		elif (i == 9):
			scene.svp_palette.color9 = color;
		elif (i == 10):
			scene.svp_palette.color10 = color;
		elif (i == 11):
			scene.svp_palette.color11 = color;
		elif (i == 12):
			scene.svp_palette.color12 = color;
		elif (i == 13):
			scene.svp_palette.color13 = color;
		elif (i == 14):
			scene.svp_palette.color14 = color;
		elif (i == 15):
			scene.svp_palette.color15 = color;

		# Next color
		data_offset += 2;

	return {"FINISHED"};

# SVP palette panel
class SVPPalettePanel(bpy.types.Panel):
	bl_idname = "SVP_PT_Palette_Panel";
	bl_label = "Palette";
	bl_category = "SVP";
	bl_space_type = "VIEW_3D";
	bl_region_type = "UI";

	def draw(self, context):
		layout = self.layout;

		for i in range(0, 4):
			row = layout.row();
			col = row.column();
			split = col.split();
			for j in range(i*4, (i*4)+4):
				split.prop(context.scene.svp_palette, "color" + str(j));

		row = layout.row();
		layout.operator(SVPPalLoadOperator.bl_idname);

# SVP panel
class SVPPanel(bpy.types.Panel):
	bl_idname = "SVP_PT_Panel";
	bl_label = "Face Properties";
	bl_category = "SVP";
	bl_space_type = "VIEW_3D";
	bl_region_type = "UI";

	def draw(self, context):
		layout = self.layout;

		if context.mode == "EDIT_MESH":
			obj = context.edit_object;
		else:
			obj = context.active_object;

		if context.mode == "EDIT_MESH":
			layout.prop(obj.data, "checker_dither");
			layout.prop(obj.data, "cull_enabled");
			layout.prop(obj.data, "color1", slider=True);
			layout.prop(obj.data, "color2", slider=True);
			layout.prop(obj.data, "flags", slider=True);

# Get checkerboard dithering flag
def get_checker_dither(self):
	ret_value = False;
	found_status = 0;

	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get dither layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			dither_tag = bm.faces.layers.int.get("dither_ids");
			if (dither_tag is None):
				dither_tag = bm.faces.layers.int.new("dither_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (face.select):
					if (found_status == 0):
						ret_value = bm.faces[face_id][dither_tag] == 1;
						found_status = 1;
					elif (found_status == 1):
						if (bm.faces[face_id][dither_tag] != ret_value):
							ret_value = False;
							found_status = 2;
				face_id += 1;

	return ret_value;

# Set checkerboard dithering flag
def set_checker_dither(self, value):
	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get dither layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			dither_tag = bm.faces.layers.int.get("dither_ids");
			if (dither_tag is None):
				dither_tag = bm.faces.layers.int.new("dither_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (face.select):
					if (value):
						bm.faces[face_id][dither_tag] = 1;
					else:
						bm.faces[face_id][dither_tag] = 0;
				face_id += 1;

			# Save changes
			if obj.mode == "EDIT":
				bmesh.update_edit_mesh(obj.data);
			else:
				bm.to_mesh(obj.data);

# Get culling flag
def get_culling(self):
	ret_value = False;
	found_status = 0;

	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get culling layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			cull_tag = bm.faces.layers.int.get("cull_ids");
			if (cull_tag is None):
				cull_tag = bm.faces.layers.int.new("cull_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (face.select):
					if (found_status == 0):
						ret_value = bm.faces[face_id][cull_tag] == 1;
						found_status = 1;
					elif (found_status == 1):
						if (bm.faces[face_id][cull_tag] != ret_value):
							ret_value = False;
							found_status = 2;
				face_id += 1;

	return ret_value;

# Set culling flag
def set_culling(self, value):
	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get culling layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			cull_tag = bm.faces.layers.int.get("cull_ids");
			if (cull_tag is None):
				cull_tag = bm.faces.layers.int.new("cull_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (face.select):
					if (value):
						bm.faces[face_id][cull_tag] = 1;
					else:
						bm.faces[face_id][cull_tag] = 0;
				face_id += 1;

			# Save changes
			if obj.mode == "EDIT":
				bmesh.update_edit_mesh(obj.data);
			else:
				bm.to_mesh(obj.data);

# Get color 1
def get_color1(self):
	ret_value = False;
	found_status = 0;

	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get palette layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			layers_created = False;
			pal_tag = bm.faces.layers.int.get("palette_ids");
			if (pal_tag is None):
				layers_created = True;
				pal_tag = bm.faces.layers.int.new("palette_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (layers_created):
					bm.faces[face_id][pal_tag] = 0x11;
				if (face.select):
					if (found_status == 0):
						ret_value = (bm.faces[face_id][pal_tag] >> 4) & 0xF;
						found_status = 1;
					elif (found_status == 1):
						if (((bm.faces[face_id][pal_tag] >> 4) & 0xF) != ret_value):
							ret_value = False;
							found_status = 2;
				face_id += 1;

	return ret_value;

# Set color 1
def set_color1(self, value):
	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get palette layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			layers_created = False;
			pal_tag = bm.faces.layers.int.get("palette_ids");
			if (pal_tag is None):
				layers_created = True;
				pal_tag = bm.faces.layers.int.new("palette_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (layers_created):
					bm.faces[face_id][pal_tag] = 0x11;
				if (face.select):
					bm.faces[face_id][pal_tag] &= 0xF;
					bm.faces[face_id][pal_tag] |= (value << 4);
				face_id += 1;

			# Save changes
			if obj.mode == "EDIT":
				bmesh.update_edit_mesh(obj.data);
			else:
				bm.to_mesh(obj.data);

# Get color 2
def get_color2(self):
	ret_value = False;
	found_status = 0;

	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get palette layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			layers_created = False;
			pal_tag = bm.faces.layers.int.get("palette_ids");
			if (pal_tag is None):
				layers_created = True;
				pal_tag = bm.faces.layers.int.new("palette_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (layers_created):
					bm.faces[face_id][pal_tag] = 0x11;
				if (face.select):
					if (found_status == 0):
						ret_value = bm.faces[face_id][pal_tag] & 0xF;
						found_status = 1;
					elif (found_status == 1):
						if ((bm.faces[face_id][pal_tag] & 0xF) != ret_value):
							ret_value = False;
							found_status = 2;
				face_id += 1;

	return ret_value;

# Set color 2
def set_color2(self, value):
	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get palette layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			layers_created = False;
			pal_tag = bm.faces.layers.int.get("palette_ids");
			if (pal_tag is None):
				layers_created = True;
				pal_tag = bm.faces.layers.int.new("palette_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (layers_created):
					bm.faces[face_id][pal_tag] = 0x11;
				if (face.select):
					bm.faces[face_id][pal_tag] &= 0xF0;
					bm.faces[face_id][pal_tag] |= value;
				face_id += 1;

			# Save changes
			if obj.mode == "EDIT":
				bmesh.update_edit_mesh(obj.data);
			else:
				bm.to_mesh(obj.data);

# Get flags
def get_flags(self):
	ret_value = False;
	found_status = 0;

	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get flag layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			flag_tag = bm.faces.layers.int.get("flag_ids");
			if (flag_tag is None):
				flag_tag = bm.faces.layers.int.new("flag_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (face.select):
					if (found_status == 0):
						ret_value = bm.faces[face_id][flag_tag];
						found_status = 1;
					elif (found_status == 1):
						if (bm.faces[face_id][flag_tag] != ret_value):
							ret_value = False;
							found_status = 2;
				face_id += 1;

	return ret_value;

# Set flags
def set_flags(self, value):
	# Go through each object
	for obj in bpy.context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Get flag layer
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			flag_tag = bm.faces.layers.int.get("flag_ids");
			if (flag_tag is None):
				flag_tag = bm.faces.layers.int.new("flag_ids");

			# Check faces
			face_id = 0;
			for face in bm.faces:
				if (face.select):
					bm.faces[face_id][flag_tag] = value;
				face_id += 1;

			# Save changes
			if obj.mode == "EDIT":
				bmesh.update_edit_mesh(obj.data);
			else:
				bm.to_mesh(obj.data);

# Create a shader
def create_shader(type, code):
	# Compile the shader
	shader = bgl.glCreateShader(type);
	bgl.glShaderSource(shader, code);
	bgl.glCompileShader(shader);

	# Check if compilation was successful
	success = bgl.Buffer(bgl.GL_INT, [1]);
	bgl.glGetShaderiv(shader, bgl.GL_COMPILE_STATUS, success);
	if (success[0] == bgl.GL_TRUE):
		print("Shader successfully compiled.");
		return shader;

	# Create an error log
	bgl.glGetShaderiv(shader, bgl.GL_INFO_LOG_LENGTH, success);
	success[0] = success[0] + 1;
	log = bgl.Buffer(bgl.GL_BYTE, [success[0]]);
	start = bgl.Buffer(bgl.GL_INT, [1]);
	start[0] = 0;
	bgl.glGetShaderInfoLog(shader, success[0]+1, start, log);
	py_log = log[:];
	py_log_str = "";
	for c in py_log:
		py_log_str += str(chr(c));
	print(str(py_log_str));
	bgl.glDeleteShader(shader);

# Create a program
def create_program(vertex, fragment):
	# Compile the shaders and link them
	program = bgl.glCreateProgram();
	bgl.glAttachShader(program, vertex);
	bgl.glAttachShader(program, fragment);
	bgl.glLinkProgram(program);

	# Check if linking was successful
	success = bgl.Buffer(bgl.GL_INT, [1]);
	bgl.glGetProgramiv(program, bgl.GL_LINK_STATUS, success);
	if (success[0] == bgl.GL_TRUE):
		print("Program successfully linked.");
		return program;

	# Create an error log
	bgl.glGetProgramiv(program, bgl.GL_INFO_LOG_LENGTH, success);
	start = bgl.Buffer(bgl.GL_INT, [1]);
	start[0] = 0;
	log = bgl.Buffer(bgl.GL_BYTE, [success[0]]);
	bgl.glGetProgramInfoLog(program, success[0], start, log);
	py_log = log[:];
	py_log_str = "";
	for c in py_log:
		py_log_str += str(chr(c));
	print(str(py_log_str));
	bgl.glDeleteProgram(program);

# Shader
vertex_shader = -1;
fragment_shader = -1;
svp_shader = -1;

# Render engine
class SVPRenderEngine(bpy.types.RenderEngine):
	bl_idname = "SVP_RENDER";
	bl_label = "SVP Render Engine";
	bl_use_preview = True;

	# Initialization
	def __init__(self):
		self.scene_data = None;

	# Destroy
	def __del__(self):
		pass;

	# Final render
	def render(self, depsgraph):
		scene = depsgraph.scene;
		scale = scene.render.resolution_percentage / 100.0;
		self.size_x = int(scene.render.resolution_x * scale);
		self.size_y = int(scene.render.resolution_y * scale);

		if (self.is_preview):
			color = [0.1, 0.2, 0.1, 1.0];
		else:
			color = [0.2, 0.1, 0.1, 1.0];
		pixel_count = self.size_x * self.size_y;
		rect = [color] * pixel_count;

		# Set render result
		result = self.begin_result(0, 0, self.size_x, self.size_y);
		layer = result.layers[0].passes["Combined"];
		layer.rect = rect;
		self.end_result(result);

	# Viewport initialization/change
	def view_update(self, context, depsgraph):
		# Check for updates
		if not self.scene_data:
			self.scene_data = [];
			first_time = True;
			for datablock in depsgraph.ids:
				pass;
		else:
			first_time = False;
			for update in depsgraph.updates:
				print("Datablock updated: ", update.id.name);
			if depsgraph.id_type_updated("MATERIAL"):
				print("Materials updated");
		if first_time or depsgraph.id_type_updated("OBJECT"):
			for instance in depsgraph.object_instances:
				pass;

		# Draw the scene
		self.bind_display_space_shader(depsgraph.scene);
		svp_draw(context);
		self.unbind_display_space_shader();

	# Viewport redraw
	def view_draw(self, context, depsgraph):
		self.bind_display_space_shader(depsgraph.scene);
		svp_draw(context);
		self.unbind_display_space_shader();

# Draw SVP render
def svp_draw(context):
	global svp_shader;

	# Set up settings
	bgl.glEnable(bgl.GL_BLEND);
	bgl.glEnable(bgl.GL_DEPTH_TEST);
	bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE_MINUS_SRC_ALPHA);

	# Get old shader
	old_shader = bgl.Buffer(bgl.GL_INT, 1);
	bgl.glGetIntegerv(bgl.GL_CURRENT_PROGRAM, old_shader);

	# Set up vertex array
	vertex_array = bgl.Buffer(bgl.GL_INT, 1);
	bgl.glGenVertexArrays(1, vertex_array);
	bgl.glBindVertexArray(vertex_array[0]);
	bgl.glEnableVertexAttribArray(0);
	bgl.glEnableVertexAttribArray(1);
	bgl.glEnableVertexAttribArray(2);
	bgl.glEnableVertexAttribArray(3);

	# Use the SVP shader
	bgl.glUseProgram(svp_shader);
	position_location = 0;
	shader_matrix = bgl.glGetUniformLocation(svp_shader, "mat");

	# Get palette
	scene = bpy.context.scene;
	colors = {
		0: scene.svp_palette.color0,
		1: scene.svp_palette.color1,
		2: scene.svp_palette.color2,
		3: scene.svp_palette.color3,
		4: scene.svp_palette.color4,
		5: scene.svp_palette.color5,
		6: scene.svp_palette.color6,
		7: scene.svp_palette.color7,
		8: scene.svp_palette.color8,
		9: scene.svp_palette.color9,
		10: scene.svp_palette.color10,
		11: scene.svp_palette.color11,
		12: scene.svp_palette.color12,
		13: scene.svp_palette.color13,
		14: scene.svp_palette.color14,
		15: scene.svp_palette.color15
	};
	palette = [];
	for i in range(0, 16):
		color = colors.get(i, [0.0,0.0,0.0]);
		color = [color.r, color.g, color.b];
		if (i == 0):
			color.append(0);
		else:
			color.append(1);
		palette.append(color);

	# Go through each object
	for obj in context.scene.objects:
		if hasattr(obj.data, "polygons"):
			# Get BMesh
			bm = bmesh.new();
			if obj.mode == "EDIT":
				bm = bmesh.from_edit_mesh(obj.data);
			else:
				bm.from_mesh(obj.data);

			# Set up matrix
			matrix_buffer = bgl.Buffer(bgl.GL_FLOAT, [4,4], obj.matrix_world.transposed() @ context.region_data.perspective_matrix.transposed())
			bgl.glUniformMatrix4fv(shader_matrix, 1, bgl.GL_FALSE, matrix_buffer[0]);

			# Get layers
			if hasattr(bm.faces, "ensure_lookup_table"): 
				bm.faces.ensure_lookup_table();
			layers_created = False;
			pal_tag = bm.faces.layers.int.get("palette_ids");
			dither_tag = bm.faces.layers.int.get("dither_ids");
			if (pal_tag is None):
				layers_created = True;
				pal_tag = bm.faces.layers.int.new("palette_ids");
			if (dither_tag is None):
				dither_tag = bm.faces.layers.int.new("dither_ids");

			# Create vertex and data buffers
			vertex_buffers = bgl.Buffer(bgl.GL_INT, 4);
			bgl.glGenBuffers(4, vertex_buffers);
			vertex_pos = [];
			vertex_colors1 = [];
			vertex_colors2 = [];
			vertex_dithers = [];

			# Go through each polygon
			face_id = 0;
			for face in bm.faces:
				# Get layer data
				if (layers_created):
					bm.faces[face_id][pal_tag] = 0x11;
				color = bm.faces[face_id][pal_tag];
				color1 = palette[(color >> 4) & 0xF];
				color2 = palette[color & 0xF];
				dither = bm.faces[face_id][dither_tag];

				# Get vertices
				if (len(face.verts) < 5):
					vertex_id = 0;
					for vertex in range(0,len(face.verts)):
						if (vertex_id >= 3):
							vertex_pos.extend(face.verts[vertex-1].co);
							vertex_colors1.extend(color1);
							vertex_colors2.extend(color2);
							vertex_dithers.append(dither);
							vertex_pos.extend(face.verts[vertex].co);
							vertex_colors1.extend(color1);
							vertex_colors2.extend(color2);
							vertex_dithers.append(dither);
							vertex_pos.extend(face.verts[vertex-3].co);
							vertex_colors1.extend(color1);
							vertex_colors2.extend(color2);
							vertex_dithers.append(dither);
						else:
							vertex_pos.extend(face.verts[vertex].co);
							vertex_colors1.extend(color1);
							vertex_colors2.extend(color2);
							vertex_dithers.append(dither);
						vertex_id += 1;

				# Next face
				face_id += 1;

			if (len(vertex_pos) > 0):
				positions = bgl.Buffer(bgl.GL_FLOAT, len(vertex_pos), vertex_pos);
				colors1 = bgl.Buffer(bgl.GL_FLOAT, len(vertex_colors1), vertex_colors1);
				colors2 = bgl.Buffer(bgl.GL_FLOAT, len(vertex_colors2), vertex_colors2);
				dithers = bgl.Buffer(bgl.GL_FLOAT, len(vertex_dithers), vertex_dithers);

				bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffers[0]);
				bgl.glBufferData(bgl.GL_ARRAY_BUFFER, int(len(vertex_pos)*4), positions, bgl.GL_STATIC_DRAW);
				bgl.glVertexAttribPointer(0, 3, bgl.GL_FLOAT, bgl.GL_FALSE, 0, None);

				bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffers[1]);
				bgl.glBufferData(bgl.GL_ARRAY_BUFFER, int(len(vertex_colors1)*4), colors1, bgl.GL_STATIC_DRAW);
				bgl.glVertexAttribPointer(1, 4, bgl.GL_FLOAT, bgl.GL_FALSE, 0, None);

				bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffers[2]);
				bgl.glBufferData(bgl.GL_ARRAY_BUFFER, int(len(vertex_colors2)*4), colors2, bgl.GL_STATIC_DRAW);
				bgl.glVertexAttribPointer(2, 4, bgl.GL_FLOAT, bgl.GL_FALSE, 0, None);

				bgl.glBindBuffer(bgl.GL_ARRAY_BUFFER, vertex_buffers[3]);
				bgl.glBufferData(bgl.GL_ARRAY_BUFFER, int(len(vertex_dithers)*4), dithers, bgl.GL_STATIC_DRAW);
				bgl.glVertexAttribPointer(3, 1, bgl.GL_FLOAT, bgl.GL_FALSE, 0, None);

				bgl.glDrawArrays(bgl.GL_TRIANGLES, 0, len(dithers));

				bgl.glDeleteBuffers(1, positions);
				bgl.glDeleteBuffers(1, colors1);
				bgl.glDeleteBuffers(1, colors2);
				bgl.glDeleteBuffers(1, dithers);

			bgl.glDeleteBuffers(4, vertex_buffers);
			bgl.glDeleteBuffers(1, matrix_buffer);

	# Clean up
	bgl.glDisableVertexAttribArray(0);
	bgl.glDisableVertexAttribArray(1);
	bgl.glDisableVertexAttribArray(2);
	bgl.glDisableVertexAttribArray(3);
	bgl.glBindVertexArray(0);
	bgl.glDeleteVertexArrays(1, vertex_array);

	bgl.glUseProgram(old_shader[0]);
	bgl.glDisable(bgl.GL_BLEND);
	bgl.glDisable(bgl.GL_DEPTH_TEST);

# Get panels
def get_panels():
	exclude_panels = {
		"VIEWLAYER_PT_filter",
		"VIEWLAYER_PT_layer_passes",
	};
	panels = [];
	for panel in bpy.types.Panel.__subclasses__():
		if hasattr(panel, "COMPAT_ENGINES") and "BLENDER_RENDER" in panel.COMPAT_ENGINES:
			if panel.__name__ not in exclude_panels:
				panels.append(panel);

	return panels

# Import menu function
def menu_func_import(self, context):
	self.layout.operator(ImportSVP.bl_idname, text="SEGA Virtua Processor Model (.svp)");

# Export menu function
def menu_func_export(self, context):
	self.layout.operator(ExportSVP.bl_idname, text="SEGA Virtua Processor Model (.svp)");

# Classes
classes = (
	ImportSVP,
	ExportSVP,
	SVPPalette,
	SVPPalLoadOperator,
	SVPPalettePanel,
	SVPPanel,
	SVPRenderEngine,
)

# Register
def register():
	global svp_shader;

	for cls in classes:
		bpy.utils.register_class(cls);

	bpy.types.TOPBAR_MT_file_import.append(menu_func_import);
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export);

	for panel in get_panels():
		panel.COMPAT_ENGINES.add("SVP_RENDER");

	bpy.types.Scene.svp_palette = bpy.props.PointerProperty(name="SVP Color", type=SVPPalette);
	bpy.types.Mesh.checker_dither = bpy.props.BoolProperty(name="Checkerboard Dithering", get=get_checker_dither, set=set_checker_dither);
	bpy.types.Mesh.cull_enabled = bpy.props.BoolProperty(name="Enable Culling", get=get_culling, set=set_culling);
	bpy.types.Mesh.color1 = bpy.props.IntProperty(name="Color 1", get=get_color1, set=set_color1, min=0, max=15);
	bpy.types.Mesh.color2 = bpy.props.IntProperty(name="Color 2", get=get_color2, set=set_color2, min=0, max=15);
	bpy.types.Mesh.flags = bpy.props.IntProperty(name="Flags", get=get_flags, set=set_flags, min=0, max=15);

	# Vertex shader
	vertex_shader = create_shader(bgl.GL_VERTEX_SHADER, 
	"""
	#version 330 core
	layout(location = 0) in vec3 in_pos;
	layout(location = 1) in vec4 in_color1;
	layout(location = 2) in vec4 in_color2;
	layout(location = 3) in float in_dither;
	out vec4 color1;
	out vec4 color2;
	out float dither;
	uniform mat4 mat;
	void main()
	{
		gl_Position = mat * vec4(in_pos,1);
		color1 = in_color1;
		color2 = in_color2;
		dither = in_dither;
	}""")

	# Fragment shader
	fragment_shader = create_shader(bgl.GL_FRAGMENT_SHADER,
	"""
	#version 330 core
	in vec4 color1;
	in vec4 color2;
	in float dither;
	out vec4 color;

	void main()
	{
		color = (mix(1.0, 0.0, sign(mod(floor(gl_FragCoord.x / 3.0) + (floor(gl_FragCoord.y / 3.0) * sign(dither)), 2.0))) == 1.0) ? color1 : color2;
	}
	""")

	# Shader program
	svp_shader = create_program(vertex_shader, fragment_shader);

# Unregister
def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import);
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export);

	for cls in classes:
		bpy.utils.unregister_class(cls);

	for panel in get_panels():
		if "SVP_RENDER" in panel.COMPAT_ENGINES:
			panel.COMPAT_ENGINES.remove("SVP_RENDER");

	del bpy.types.Scene.svp_palette;

	bgl.glDeleteShader(vertex_shader);
	bgl.glDeleteShader(fragment_shader);
	bgl.glDeleteProgram(svp_shader);

# Main
if __name__ == "__main__":
	register();
