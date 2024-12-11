import os
from pygltflib import GLTF2

input_dir =r"C:\Users\Jade\Desktop\souls.tools\Model Viewer\souls-model-viewer\ds1\head"
output_dir =r"C:\Users\Jade\Desktop\souls.tools\Model Viewer\souls-model-viewer\ds1\head\culled"

os.makedirs(output_dir, exist_ok=True)

for filename in os.listdir(input_dir):
    if filename.endswith(".glb"):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        gltf = GLTF2().load(input_path)
        # Set all materials to doubleSided = true
        if gltf.materials:
            for mat in gltf.materials:
                mat.doubleSided = True

        gltf.save(output_path)
