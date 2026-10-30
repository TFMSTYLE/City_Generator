# SPDX-FileCopyrightText: 2025-2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "City",
    "author": "The French Monkey",
    "version": (1, 0, 3),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > City",
    "description": "Generate procedural city blocks",
    "category": "Add Mesh",
    "license": "GPL-3.0-or-later",
}

import bpy
import bmesh
import random
import hashlib
from mathutils import Matrix, Vector
from math import sqrt, pi, sin, cos

try:
    from . import relay_updater
except ImportError:  # the Addon Collection has its own updates
    relay_updater = None

MASTER_NAME = "City_Master"
INSTANCE_COLLECTION_NAME = "City_Buildings_Collection"

# ------------------------------------------------------------------------
# Building Shape Templates
# ------------------------------------------------------------------------

def create_cube_vertices(width, depth):
    return [
        Vector((-width/2, -depth/2)),
        Vector((width/2, -depth/2)),
        Vector((width/2, depth/2)),
        Vector((-width/2, depth/2))
    ]

# ------------------------------------------------------------------------
# Zoning Profiles
# ------------------------------------------------------------------------

def get_zoning_profile(zoning_type):
    """Returns detailed zoning characteristics"""
    profiles = {
        "DOWNTOWN": {
            "height_min": 30.0,
            "height_max": 80.0,
            "variation": 15.0,
            "density": 8,
            "lot_coverage": 0.8,
            "setback": 0.05,
            "layout": "GRID"  # Square grid layout
        },
        "COMMERCIAL": {
            "height_min": 15.0,
            "height_max": 35.0,
            "variation": 8.0,
            "density": 6,
            "lot_coverage": 0.7,
            "setback": 0.1,
            "layout": "OFFSET_GRID"  # Offset grid (brick pattern)
        },
        "MIXED_USE": {
            "height_min": 12.0,
            "height_max": 25.0,
            "variation": 6.0,
            "density": 5,
            "lot_coverage": 0.65,
            "setback": 0.12,
            "layout": "HEXAGONAL"  # Hexagonal pattern
        },
        "RESIDENTIAL": {
            "height_min": 8.0,
            "height_max": 15.0,
            "variation": 4.0,
            "density": 4,
            "lot_coverage": 0.5,
            "setback": 0.15,
            "layout": "ORGANIC"  # Organic/curved streets
        },
        "INDUSTRIAL": {
            "height_min": 8.0,
            "height_max": 18.0,
            "variation": 5.0,
            "density": 3,
            "lot_coverage": 0.75,
            "setback": 0.08,
            "layout": "IRREGULAR"  # Irregular large blocks
        },
        "SUBURBAN": {
            "height_min": 4.0,
            "height_max": 8.0,
            "variation": 2.0,
            "density": 2,
            "lot_coverage": 0.4,
            "setback": 0.2,
            "layout": "CURVED_GRID"  # Curved suburban streets
        },
        "OFFICE_PARK": {
            "height_min": 12.0,
            "height_max": 28.0,
            "variation": 7.0,
            "density": 4,
            "lot_coverage": 0.55,
            "setback": 0.18,
            "layout": "RADIAL"  # Radial pattern from center
        }
    }
    return profiles.get(zoning_type, profiles["MIXED_USE"])

# ------------------------------------------------------------------------
# Block Layout Generators
# ------------------------------------------------------------------------

def generate_grid_layout(g, b, o):
    return [{'x': i*b - o, 'y': j*b - o, 'rotation': 0, 'scale': 1.0, 'block_idx': (i, j)}
            for i in range(g) for j in range(g)]

def generate_offset_grid_layout(g, b, o, rng):
    return [{'x': i*b - o + (b*0.5 if j%2 else 0), 'y': j*b - o, 'rotation': 0, 'scale': 1.0, 'block_idx': (i, j)}
            for i in range(g) for j in range(g)]

def generate_hexagonal_layout(g, b, o, rng):
    hw, hh = b, b * 0.866
    rows, cols = int(g * 1.2), g
    return [{'x': col*hw*0.75 - (cols*hw*0.75)/2,
             'y': row*hh + (hh*0.5 if col%2 else 0) - (rows*hh)/2,
             'rotation': rng.uniform(-0.1, 0.1),
             'scale': rng.uniform(0.9, 1.1),
             'block_idx': (col, row)}
            for row in range(rows) for col in range(cols)]

def generate_organic_layout(g, b, o, rng):
    return [{'x': i*b - o + rng.uniform(-b*0.2, b*0.2) + sin(j*0.5)*b*0.15,
             'y': j*b - o + rng.uniform(-b*0.2, b*0.2) + cos(i*0.5)*b*0.15,
             'rotation': rng.uniform(-0.2, 0.2),
             'scale': rng.uniform(0.85, 1.15),
             'block_idx': (i, j)}
            for i in range(g) for j in range(g)]

def generate_irregular_layout(g, b, o, rng):
    step, ag = 1.4, int(g / 1.4) + 1
    return [{'x': i*b*step - o + rng.uniform(-b*0.3, b*0.3),
             'y': j*b*step - o + rng.uniform(-b*0.3, b*0.3),
             'rotation': rng.uniform(-0.15, 0.15),
             'scale': rng.uniform(1.2, 1.8),
             'block_idx': (i, j)}
            for i in range(ag) for j in range(ag)]

def generate_curved_grid_layout(g, b, o, rng):
    cf = 0.3
    return [{'x': i*b - o + sin(j*0.8)*b*cf,
             'y': j*b - o + cos(i*0.8)*b*cf,
             'rotation': rng.uniform(-0.1, 0.1),
             'scale': rng.uniform(0.9, 1.1),
             'block_idx': (i, j)}
            for i in range(g) for j in range(g)]

def generate_radial_layout(g, b, o, rng):
    return [{'x': cos(a := (i/nb)*2*pi + rng.uniform(-0.1,0.1)) * (rv := (r+1)*b*0.8 + rng.uniform(-b*0.1,b*0.1)),
             'y': sin(a) * rv, 'rotation': a, 'scale': rng.uniform(0.85,1.0), 'block_idx': (r,i)}
            for r in range(g) for nb in [1 if r==0 else max(6,r*6)] for i in range(nb)]

def get_block_layout(t, g, b, o, rng):
    f = {
        "GRID": lambda: generate_grid_layout(g, b, o),
        "OFFSET_GRID": lambda: generate_offset_grid_layout(g, b, o, rng),
        "HEXAGONAL": lambda: generate_hexagonal_layout(g, b, o, rng),
        "ORGANIC": lambda: generate_organic_layout(g, b, o, rng),
        "IRREGULAR": lambda: generate_irregular_layout(g, b, o, rng),
        "CURVED_GRID": lambda: generate_curved_grid_layout(g, b, o, rng),
        "RADIAL": lambda: generate_radial_layout(g, b, o, rng),
    }
    return f.get(t, f["GRID"])()

def create_building_instance(w, d, h, rng):
    bm = bmesh.new()
    fp = create_cube_vertices(w, d)
    bv = [bm.verts.new((v.x, v.y, 0)) for v in fp]; bm.faces.new(bv)
    tv = [bm.verts.new((v.x, v.y, h)) for v in fp]; bm.faces.new(tv[::-1])
    for i in range(len(bv)):
        n = (i + 1) % len(bv)
        bm.faces.new([bv[i], bv[n], tv[n], tv[i]])
    mesh = bpy.data.meshes.new("Building_Cube")
    bm.to_mesh(mesh); bm.free(); mesh.update()
    return mesh

def find_or_create_master(context):
    sel = get_selected_city_master(context)
    if sel:
        return sel

    for obj in bpy.data.objects:
        if obj.name.startswith(MASTER_NAME):
            return obj

    mesh = bpy.data.meshes.new(MASTER_NAME)
    name = get_next_city_master_name(MASTER_NAME)
    master = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(master)
    return master

def clear_master_mesh(master):
    if master and master.type == "MESH":
        old = master.data
        empty = bpy.data.meshes.new(f"{master.name}_Mesh")
        master.data = empty
        if old and old.users == 0:
            bpy.data.meshes.remove(old)

def _stable_pick_index(x, y, building_seed, n):
    key = f"{building_seed}_{x:.4f}_{y:.4f}"
    digest = hashlib.sha256(key.encode()).hexdigest()
    val = int(digest[:8], 16)  
    return val % n

# ------------------------------------------------------------------------
# City Geometry Builder
# ------------------------------------------------------------------------

def build_city_mesh(grid_size, block_size, zoning_type, road_width, seed, 
                   center_falloff, height_variation_scale,
                   density_multiplier, building_gap, building_tilt,
                   custom_buildings_collection, inner_radius):
    rng = random.Random(int(seed))
    prof = get_zoning_profile(zoning_type)
    
    height_min = prof["height_min"]
    height_max = prof["height_max"]
    var = prof["variation"] * height_variation_scale
    density = max(1, int(prof["density"] * density_multiplier))
    lot_coverage = prof["lot_coverage"]
    setback = prof["setback"]
    
    total_city = grid_size * block_size
    offset = total_city * 0.5 - block_size * 0.5
    
    center_block = grid_size // 2
    
    return build_city_merged_geometry(
        grid_size, block_size, road_width, center_falloff, center_block,
        prof, height_min, height_max, var, density,
        lot_coverage, setback, building_gap, building_tilt,
        rng, offset, custom_buildings_collection, inner_radius
    )

def build_city_merged_geometry(g, b, r, c, cb, prof, hmin, hmax, var, dens, cov, setback, gap, tilt, rng, off, custom, inner_radius):
    bm = bmesh.new()
    layout = prof.get("layout", "GRID")
    blocks = get_block_layout(layout, g, b, off, rng)
    tilt_range = tilt * 0.785
    inner_radius_sq = float(inner_radius) * float(inner_radius)

    custom_objs = []
    if custom:
        coll = custom
        custom_objs = [o for o in coll.objects if o.type == 'MESH']

    for bl in blocks:
        bx, by, rot, scl, idx = (
            bl['x'], bl['y'], bl.get('rotation', 0),
            bl.get('scale', 1.0), bl.get('block_idx', (0, 0))
        )

        if layout == "GRID":
            i, j = idx
            dist = max(abs(i - cb), abs(j - cb))
        elif layout == "RADIAL":
            dist = idx[0]
        else:
            d = sqrt(bx * bx + by * by)
            maxd = g * b * 0.7
            dist = int((d / maxd) * g) if maxd > 0 else 0

        max_dist = max(cb, g - cb - 1) if layout == "GRID" else g
        step = 1.0 - (dist / max_dist) * c if c > 0 and max_dist > 0 else 1.0

        space = (b * scl - r) * (1.0 - setback * 2)
        lot = space / dens
        size = lot * cov - gap

        for a in range(dens):
            for bb in range(dens):
                lx = -space * 0.5 + lot * 0.5 + a * lot
                ly = -space * 0.5 + lot * 0.5 + bb * lot
                if rot != 0:
                    cosr, sinr = cos(rot), sin(rot)
                    lx, ly = bx + lx * cosr - ly * sinr, by + lx * sinr + ly * cosr
                else:
                    lx, ly = bx + lx, by + ly

                if (lx * lx + ly * ly) < inner_radius_sq:
                    continue

                hr = hmax - hmin
                base = hmin + hr * step
                h = max(0.5, base + rng.uniform(-var, var))
                if h < 1.0:
                    continue

                w, dpth = size * rng.uniform(0.8, 1.0), size * rng.uniform(0.8, 1.0)
                brot = rot + rng.uniform(-tilt_range, tilt_range)

                if custom_objs:
                    src = custom_objs[rng.randint(0, len(custom_objs) - 1)]
                    temp_mesh = src.to_mesh()
                    if temp_mesh:
                        temp_bm = bmesh.new()
                        temp_bm.from_mesh(temp_mesh)

                        sx = w / src.dimensions.x if src.dimensions.x else 1
                        sy = dpth / src.dimensions.y if src.dimensions.y else 1
                        sz = h / src.dimensions.z if src.dimensions.z else 1
                        scale_mat = (
                            Matrix.Scale(sx, 4, Vector((1, 0, 0))) @
                            Matrix.Scale(sy, 4, Vector((0, 1, 0))) @
                            Matrix.Scale(sz, 4, Vector((0, 0, 1)))
                        )
                        rot_mat = Matrix.Rotation(brot, 4, 'Z')
                        trans_mat = Matrix.Translation((lx, ly, 0))

                        temp_bm.transform(trans_mat @ rot_mat @ scale_mat)
                        bmesh.ops.recalc_face_normals(temp_bm, faces=temp_bm.faces)
                        bm.from_mesh(temp_mesh)
                        temp_bm.free()
                else:
                    foot = create_cube_vertices(w, dpth)
                    bv, tv = [], []
                    for v in foot:
                        cosr, sinr = cos(brot), sin(brot)
                        rx, ry = v.x * cosr - v.y * sinr, v.x * sinr + v.y * cosr
                        bv.append(bm.verts.new((lx + rx, ly + ry, 0)))
                        tv.append(bm.verts.new((lx + rx, ly + ry, h)))
                    if len(bv) >= 3:
                        bm.faces.new(bv)
                    if len(tv) >= 3:
                        bm.faces.new(tv[::-1])
                    for k in range(len(bv)):
                        n = (k + 1) % len(bv)
                        bm.faces.new([bv[k], bv[n], tv[n], tv[k]])

    mesh = bpy.data.meshes.new(MASTER_NAME)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def build_city_with_instances(context):
    p = context.scene.citygen_props
    rng = random.Random(int(p.seed) + int(p.building_seed) * 7919)
    prof = get_zoning_profile(p.zoning_type)

    hmin, hmax, var = prof["height_min"], prof["height_max"], prof["variation"] * p.height_variation_scale
    density = max(1, int(prof["density"] * p.density_multiplier))
    lot_cov, setback = prof["lot_coverage"], prof["setback"]

    g, b, r, c, gap, tilt = (
        p.grid_size, p.block_size, p.road_width, p.center_falloff, p.building_gap, p.building_tilt
    )
    offset, center = g * b * 0.5 - b * 0.5, g // 2
    tilt_range = tilt * 0.785
    inner_radius = float(p.inner_clear_radius)
    inner_radius_sq = inner_radius * inner_radius

    master = find_or_create_master(context)
    clear_master_mesh(master)

    def collect_meshes(collection):
        meshes = [o for o in collection.objects if o.type == 'MESH']
        for sub in collection.children:
            meshes.extend(collect_meshes(sub))
        return meshes

    custom = []
    if p.custom_buildings_collection:
        custom = collect_meshes(p.custom_buildings_collection)

    for child in list(master.children):
        bpy.data.objects.remove(child, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith("Building_Cube") and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    blocks = get_block_layout(prof.get("layout", "GRID"), g, b, offset, rng)
    inst = []
    for bl in blocks:
        bx, by, rot, scl, idx = (
            bl['x'], bl['y'], bl.get('rotation', 0),
            bl.get('scale', 1.0), bl.get('block_idx', (0, 0))
        )

        if prof["layout"] == "GRID":
            i, j = idx
            dist = max(abs(i - center), abs(j - center))
        elif prof["layout"] == "RADIAL":
            dist = idx[0]
        else:
            d = sqrt(bx * bx + by * by)
            maxd = g * b * 0.7
            dist = int((d / maxd) * g) if maxd > 0 else 0

        max_dist = max(center, g - center - 1) if prof["layout"] == "GRID" else g
        step = 1.0 - (dist / max_dist) * c if c > 0 and max_dist > 0 else 1.0

        space = (b * scl - r) * (1.0 - setback * 2)
        lot = space / density
        size = lot * lot_cov - gap

        for a in range(density):
            for bb in range(density):
                lx = -space * 0.5 + lot * 0.5 + a * lot
                ly = -space * 0.5 + lot * 0.5 + bb * lot
                if rot != 0:
                    cosr, sinr = cos(rot), sin(rot)
                    lx, ly = bx + lx * cosr - ly * sinr, by + lx * sinr + ly * cosr
                else:
                    lx, ly = bx + lx, by + ly

                if (lx * lx + ly * ly) < inner_radius_sq:
                    continue

                hr = hmax - hmin
                base = hmin + hr * step
                h = max(0.5, base + rng.uniform(-var, var))
                if h < 1.0:
                    continue

                w, dpth = size * rng.uniform(0.8, 1.0), size * rng.uniform(0.8, 1.0)
                inst.append({
                    'pos': (lx, ly, 0),
                    'width': w,
                    'depth': dpth,
                    'height': h,
                    'rotation': rot + rng.uniform(-tilt_range, tilt_range)
                })

    if custom:
        for i, d in enumerate(inst):
            idx = _stable_pick_index(d['pos'][0], d['pos'][1], int(p.building_seed), len(custom))
            src = custom[idx]

            if p.keep_ratio:
                base_scale = min(
                    d['width'] / src.dimensions.x if src.dimensions.x else 1,
                    d['depth'] / src.dimensions.y if src.dimensions.y else 1,
                    d['height'] / src.dimensions.z if src.dimensions.z else 1
                )
                sx = sy = sz = base_scale
            else:
                sx = d['width'] / src.dimensions.x if src.dimensions.x else 1
                sy = d['depth'] / src.dimensions.y if src.dimensions.y else 1
                sz = d['height'] / src.dimensions.z if src.dimensions.z else 1

            new_obj = bpy.data.objects.new(f"Building_{i}", src.data.copy())
            new_obj.location = d['pos']
            new_obj.scale = (sx, sy, sz)
            new_obj.rotation_euler.z = d['rotation']
            context.collection.objects.link(new_obj)
            new_obj.parent = master
    else:
        cube_mesh = create_building_instance(1, 1, 1, rng)
        for i, d in enumerate(inst):
            new_obj = bpy.data.objects.new(f"Building_{i}", cube_mesh)
            new_obj.location = d['pos']
            new_obj.scale = (d['width'], d['depth'], d['height'])
            new_obj.rotation_euler.z = d['rotation']
            context.collection.objects.link(new_obj)
            new_obj.parent = master

    return master

# ------------------------------------------------------------------------
# Generation Logic
# ------------------------------------------------------------------------

def get_selected_city_master(context):
    o = context.object
    if not o or not o.select_get():
        return None
    if o.name.startswith(MASTER_NAME):
        return o
    return None

def get_next_city_master_name(base_name):
    count = 0
    while True:
        name = f"{base_name}" if count == 0 else f"{base_name}.{count:03d}"
        if name not in bpy.data.objects:
            return name
        count += 1

def delete_city():
    master = bpy.context.object
    if not master or not master.name.startswith(MASTER_NAME):
        master = None
        for obj in reversed(bpy.data.objects):
            if obj.name.startswith(MASTER_NAME):
                master = obj
                break

    if not master:
        return

    for child in list(master.children):
        try:
            bpy.data.objects.remove(child, do_unlink=True)
        except Exception as e:
            print(f"Warning: couldn't delete child {child.name}: {e}")

    mesh = master.data if master.type == "MESH" else None
    try:
        bpy.data.objects.remove(master, do_unlink=True)
    except Exception as e:
        print(f"Warning: couldn't delete master: {e}")

    for mesh_data in list(bpy.data.meshes):
        if (mesh_data.name.startswith("Building_Cube") or
            mesh_data.name.startswith(MASTER_NAME)) and mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

    coll = bpy.data.collections.get(INSTANCE_COLLECTION_NAME)
    if coll:
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(coll)

def rebuild_city(context):
    p = context.scene.citygen_props
    selected_master = get_selected_city_master(context)

    if selected_master:
        master = selected_master
    else:
        mesh = bpy.data.meshes.new(MASTER_NAME)
        name = get_next_city_master_name(MASTER_NAME)
        master = bpy.data.objects.new(name, mesh)
        context.collection.objects.link(master)

    def collect_meshes(collection):
        meshes = [o for o in collection.objects if o.type == 'MESH']
        for sub in collection.children:
            meshes.extend(collect_meshes(sub))
        return meshes

    use_custom = False
    custom_meshes = []
    if p.custom_buildings_collection:
        custom_meshes = collect_meshes(p.custom_buildings_collection)
        use_custom = len(custom_meshes) > 0

    if use_custom:
        for child in list(master.children):
            bpy.data.objects.remove(child, do_unlink=True)

        bpy.ops.object.select_all(action='DESELECT')
        master.select_set(True)
        context.view_layer.objects.active = master

        build_city_with_instances(context)
        return True

    for child in list(master.children):
        bpy.data.objects.remove(child, do_unlink=True)

    mesh = build_city_mesh(
        grid_size=p.grid_size,
        block_size=p.block_size,
        zoning_type=p.zoning_type,
        road_width=p.road_width,
        seed=p.seed,
        center_falloff=p.center_falloff,
        height_variation_scale=p.height_variation_scale,
        density_multiplier=p.density_multiplier,
        building_gap=p.building_gap,
        building_tilt=p.building_tilt,
        custom_buildings_collection=None,
        inner_radius=p.inner_clear_radius 
    )

    old_mesh = master.data if master.type == "MESH" else None
    master.data = mesh
    mesh.name = master.name
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    bpy.ops.object.select_all(action='DESELECT')
    master.select_set(True)
    context.view_layer.objects.active = master

    return True

def generate_city(context):
    selected_master = get_selected_city_master(context)

    if selected_master:
        rebuild_city(context)
        master = selected_master
    else:
        existing_masters = [obj for obj in bpy.data.objects if obj.name.startswith(MASTER_NAME)]

        rebuild_city(context)

        new_masters = [obj for obj in bpy.data.objects if obj.name.startswith(MASTER_NAME)]
        master = None
        for obj in new_masters:
            if obj not in existing_masters:
                master = obj
                break

    if master:
        bpy.ops.object.select_all(action='DESELECT')
        master.select_set(True)
        context.view_layer.objects.active = master

    return {"FINISHED"}

# ------------------------------------------------------------------------
# Live Update
# ------------------------------------------------------------------------

def update_city(self, context):
    p = context.scene.citygen_props

    if not p.live_update:
        return

    master = get_selected_city_master(context)
    if not master:
        return

    rebuild_city(context)

# ------------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------------

class CityGenProperties(bpy.types.PropertyGroup):
    live_update: bpy.props.BoolProperty(name="Live Update", default=False, description="Auto-regenerate city on change")
    zoning_type: bpy.props.EnumProperty(
        name="Zoning Type",
        items=[
            ("DOWNTOWN", "Downtown", "High-density urban core"),
            ("COMMERCIAL", "Commercial", "Mid-rise business area"),
            ("MIXED_USE", "Mixed Use", "Residential and commercial blend"),
            ("RESIDENTIAL", "Residential", "Low to mid-rise housing"),
            ("INDUSTRIAL", "Industrial", "Warehouses and factories"),
            ("SUBURBAN", "Suburban", "Low-density housing"),
            ("OFFICE_PARK", "Office Park", "Corporate campus")
        ],
        default="DOWNTOWN", update=update_city
    )
    grid_size: bpy.props.IntProperty(name="Grid Size", default=6, min=1, max=50, subtype='FACTOR', update=update_city)
    block_size: bpy.props.FloatProperty(name="Block Size", default=50.0, min=10.0, max=200.0, subtype='FACTOR', update=update_city)
    road_width: bpy.props.FloatProperty(name="Road Width", default=5.0, min=0.0, max=50.0, subtype='FACTOR', update=update_city)
    center_falloff: bpy.props.FloatProperty(name="Center Height Falloff", default=0.5, min=0.0, max=5.0, subtype='FACTOR', update=update_city)
    height_variation_scale: bpy.props.FloatProperty(name="Height Variation", default=1.0, min=0.0, max=3.0, subtype='FACTOR', update=update_city)
    density_multiplier: bpy.props.FloatProperty(name="Building Density", default=0.3, min=0.2, max=2.0, subtype='FACTOR', update=update_city)
    building_gap: bpy.props.FloatProperty(name="Building Gap", default=1.0, min=0.0, max=10.0, subtype='FACTOR', update=update_city)
    building_tilt: bpy.props.FloatProperty(name="Building Tilt", default=0.1, min=0.0, max=1.0, subtype='FACTOR', update=update_city)
    custom_buildings_collection: bpy.props.PointerProperty(name="Custom Buildings", type=bpy.types.Collection, description="Collection containing custom building models")
    seed: bpy.props.IntProperty(name="Seed", default=1, min=0, max=10000, subtype='FACTOR', update=update_city)
    building_seed: bpy.props.IntProperty(name="Building Seed", description="Random seed for randomizing building placement", default=0, min=0, max=100000, subtype='FACTOR', update=update_city)
    inner_clear_radius: bpy.props.FloatProperty(name="Inner Radius", description="No buildings will be created within this radius from the city center (0,0)", default=0.0, min=0.0, soft_max=2000.0, subtype='DISTANCE', update=update_city)
    show_custom_buildings: bpy.props.BoolProperty(name="Custom Buildings", description="Show or hide the custom building settings", default=False)
    keep_ratio: bpy.props.BoolProperty(name="Keep Ratio", description="Keep the original scale ratio of custom buildings (prevent stretching or skewing)", default=False, update=update_city)

# ------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------

class CITYGEN_OT_generate(bpy.types.Operator):
    bl_idname = "city.generate"
    bl_label = "Generate City"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Generate or regenerate the city with current settings"
    
    def execute(self, context):
        generate_city(context)
        self.report({'INFO'}, "Generated city geometry")
        return {"FINISHED"}

class CITYGEN_OT_clear(bpy.types.Operator):
    bl_idname = "city.clear"
    bl_label = "Delete City"
    bl_options = {"REGISTER", "UNDO"}
    bl_description = "Delete the city and all building instances"
    
    def execute(self, context):
        delete_city()
        self.report({'INFO'}, "Deleted city geometry")
        return {"FINISHED"}

class CITYGEN_OT_reset(bpy.types.Operator):
    bl_idname = "city.reset"
    bl_label = "Reset Settings"
    bl_description = "Reset city generator sliders to default values (keeps custom building and live update settings)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.citygen_props

        exclude = {"live_update", "custom_buildings_collection", "show_custom_buildings"}

        for prop_name, prop in props.bl_rna.properties.items():
            if prop.is_readonly or prop_name in exclude or prop_name == "rna_type":
                continue

            try:
                setattr(props, prop_name, prop.default)
            except Exception:
                pass  

        self.report({'INFO'}, "City generator settings reset to defaults")
        return {'FINISHED'}
    
# ------------------------------------------------------------------------
# UI
# ------------------------------------------------------------------------

class VIEW3D_PT_city_generator(bpy.types.Panel):
    bl_label = "City"
    bl_idname = "VIEW3D_PT_city_generator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "City"

    def draw(self, context):
        if relay_updater:
            relay_updater.draw(self.layout)
        layout = self.layout
        p = context.scene.citygen_props
        master = get_selected_city_master(context)

        layout.operator("city.generate", icon="FILE_VOLUME", text="Generate City")

        row = layout.row(align=True)
        row.prop(p, "live_update", toggle=True, text="Live Update")
        row.operator("city.reset", text="Reset")

        layout.separator(factor=0.5)

        layout.prop(p, "zoning_type")
        layout.prop(p, "seed")
        layout.prop(p, "grid_size")
        layout.prop(p, "block_size")
        layout.prop(p, "road_width")

        layout.separator(factor=0.5)

        layout.prop(p, "center_falloff")
        layout.prop(p, "height_variation_scale")

        layout.separator(factor=0.5)

        layout.prop(p, "density_multiplier")
        layout.prop(p, "building_gap")
        layout.prop(p, "inner_clear_radius", slider=True)
        layout.prop(p, "building_tilt")

        layout.prop(p, "show_custom_buildings", text="Custom Buildings", toggle=True)

        if p.show_custom_buildings:
            col = layout.column(align=True)
            col.separator(factor=0.5)
            col.prop(p, "custom_buildings_collection", text="Collection")

            if p.custom_buildings_collection and master and len(master.children) > 0:
                col.separator(factor=0.5)
                col.prop(p, "building_seed", slider=True)
                col.prop(p, "keep_ratio", toggle=True)

        layout.separator(factor=0.5)

        if master:
            row = layout.row(align=True)
            row.operator("city.clear", icon="TRASH", text="Delete City")
            layout.label(text=f"Editing City: {master.name}", icon="FILE_VOLUME")
        else:
            layout.label(text="No generated city selected", icon="INFO")

# ------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------

classes = (
    CityGenProperties,
    CITYGEN_OT_generate,
    CITYGEN_OT_clear,
    CITYGEN_OT_reset,
    VIEW3D_PT_city_generator, 
)

def register():
    if relay_updater:
        relay_updater.register("blender-city")
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.citygen_props = bpy.props.PointerProperty(type=CityGenProperties)

def unregister():
    if relay_updater:
        relay_updater.unregister()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.citygen_props

if __name__ == "__main__":
    register()