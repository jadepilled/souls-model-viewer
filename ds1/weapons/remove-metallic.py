import os
from pygltflib import GLTF2
from PIL import Image, UnidentifiedImageError
import numpy as np
import io

def extract_image_data(buffer_data, buffer_view):
    """
    Extract binary image data from the buffer using bufferView properties.
    """
    start = buffer_view.byteOffset or 0
    end = start + buffer_view.byteLength
    return buffer_data[start:end]

def invert_image(image_data):
    """
    Invert an image (1 - pixel value).
    """
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # Convert to grayscale
            img = img.convert("L")
            # Invert pixel values
            inverted = Image.fromarray(255 - np.array(img))
            # Save to bytes
            byte_arr = io.BytesIO()
            inverted.save(byte_arr, format="PNG")
            return byte_arr.getvalue()
    except UnidentifiedImageError as e:
        print(f"Warning: Could not process image data - {e}")
        print("Hex dump of first 32 bytes of data:")
        print(image_data[:32].hex())
        return None

def process_glb_files(input_folder, output_folder):
    """
    Process .glb files in the input folder, inverting gloss/roughness maps in metallicRoughnessTexture.
    Save the modified files to the output folder.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.endswith('.glb'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            print(f"Processing {filename}...")

            # Load the GLB file
            gltf = GLTF2().load(input_path)

            # Load binary buffer
            with open(input_path, "rb") as f:
                buffer_data = f.read()

            # Iterate through materials
            for material in gltf.materials:
                if material.pbrMetallicRoughness and material.pbrMetallicRoughness.metallicRoughnessTexture:
                    texture_info = material.pbrMetallicRoughness.metallicRoughnessTexture
                    texture_index = texture_info.index
                    texture = gltf.textures[texture_index]
                    image_index = texture.source
                    image = gltf.images[image_index]

                    # Check the mimeType
                    print(f"Material: {material.name}, Image mimeType: {image.mimeType}")
                    if image.mimeType not in ["image/png", "image/jpeg"]:
                        print(f"Unsupported image format: {image.mimeType}")
                        continue

                    if image.bufferView is not None:
                        buffer_view = gltf.bufferViews[image.bufferView]
                        image_data = extract_image_data(buffer_data, buffer_view)

                        # Invert the roughness map in the metallicRoughnessTexture
                        inverted_data = invert_image(image_data)
                        if inverted_data:
                            # Replace the buffer with the inverted texture
                            new_buffer_view_index = len(gltf.bufferViews)
                            gltf.bufferViews.append(buffer_view)
                            gltf.buffers[0].uri = None  # Mark as binary buffer

                            # Update image to point to the new buffer view
                            image.bufferView = new_buffer_view_index

                            print(f"Inverted roughness map for material: {material.name}")
                        else:
                            print(f"Failed to invert texture for material: {material.name}")

            # Save the modified GLB file
            gltf.save_binary(output_path)
            print(f"Saved modified file to {output_path}")

# Define input and output directories
input_folder = "."
output_folder = "./processed"

process_glb_files(input_folder, output_folder)
