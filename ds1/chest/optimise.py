import os
import io
import base64
from PIL import Image
from pygltflib import GLTF2, BufferFormat, Image as GLTFImage, Texture, Material, PbrMetallicRoughness

input_dir = os.getcwd()
output_dir = os.path.join(input_dir, "Optimised")

if not os.path.exists(output_dir):
    os.makedirs(output_dir)

def is_blank_image(image):
    im = image.convert("RGBA")
    pixels = im.getdata()
    first_pixel = pixels[0]
    return all(p == first_pixel for p in pixels)

def is_magenta_image(image):
    im = image.convert("RGBA")
    pixels = im.getdata()
    magenta = (255, 0, 255, 255)
    return all(p == magenta for p in pixels)

def has_alpha_channel(image):
    if image.mode == "RGBA":
        # Check if any pixel has alpha < 255
        alphas = [p[3] for p in image.getdata()]
        return any(a < 255 for a in alphas)
    return False

def compress_image(image):
    # Scale down image by 50% to reduce size even further
    w, h = image.size
    new_size = (max(1, w // 2), max(1, h // 2))
    image = image.resize(new_size, Image.LANCZOS)

    # Decide if image has alpha
    alpha = has_alpha_channel(image)

    output = io.BytesIO()
    if alpha:
        # For alpha images, use PNG with optimization and possibly quantization
        # Quantizing can reduce the number of colors for smaller size
        # This can lose some detail, so adjust as needed
        image = image.convert("P", palette=Image.ADAPTIVE, colors=256)
        image.save(output, format="PNG", optimize=True)
    else:
        # For non-alpha images, use JPEG with a lower quality for higher compression
        image = image.convert("RGB")  # ensure no alpha
        image.save(output, format="JPEG", quality=50, optimize=True)
    output.seek(0)
    return output.read()

def encode_data_uri(data, mime_type):
    return f"data:{mime_type};base64," + base64.b64encode(data).decode('utf-8')

def decode_data_uri(data_uri):
    if not data_uri.startswith("data:"):
        raise ValueError("URI is not a data URI.")
    _, encoded = data_uri.split(",", 1)
    return base64.b64decode(encoded)

def remove_unnecessary_nodes(gltf):
    # Remove animations
    gltf.animations = []

    # Remove nodes that contain 'bone' or 'dummy'
    nodes_to_keep = []
    for i, node in enumerate(gltf.nodes or []):
        name = (node.name or "").lower()
        if "bone" not in name and "dummy" not in name:
            nodes_to_keep.append(i)

    old_to_new = {}
    new_nodes = []
    for new_index, old_index in enumerate(nodes_to_keep):
        new_nodes.append(gltf.nodes[old_index])
        old_to_new[old_index] = new_index

    gltf.nodes = new_nodes

    # Update scene node references
    if gltf.scenes:
        for scene in gltf.scenes:
            if scene.nodes:
                scene.nodes = [old_to_new[n] for n in scene.nodes if n in old_to_new]

    # Update children references
    for node in gltf.nodes:
        if node.children:
            node.children = [old_to_new[ch] for ch in node.children if ch in old_to_new]

    # Remove skins
    gltf.skins = []

    return gltf

def optimize_gltf(input_path, output_path):
    gltf = GLTF2().load(input_path)

    # Convert to DATAURI so we have easy access to images as data URIs
    gltf.convert_buffers(BufferFormat.DATAURI)

    # Remove unnecessary nodes and animations
    gltf = remove_unnecessary_nodes(gltf)

    # Process images:
    if gltf.images:
        for i, img in enumerate(gltf.images):
            if img is None:
                continue

            # Extract image data
            image_data = None
            mime_type = None

            if img.uri and img.uri.startswith("data:"):
                # Already a data URI
                image_data = decode_data_uri(img.uri)
                # Extract mime type from the uri
                # e.g. data:image/png;base64,...
                header_end = img.uri.index(';')
                header_str = img.uri[5:header_end]
                mime_type = header_str
            elif img.bufferView is not None:
                # If still a bufferView after DATAURI conversion, decode from gltf.buffers[0].uri
                if gltf.buffers and gltf.buffers[0].uri and gltf.buffers[0].uri.startswith("data:"):
                    buffer_data = decode_data_uri(gltf.buffers[0].uri)
                    bv = gltf.bufferViews[img.bufferView]
                    start = bv.byteOffset or 0
                    end = start + (bv.byteLength or 0)
                    image_data = buffer_data[start:end]
                    # Guess mime type by signature
                    if image_data.startswith(b'\x89PNG'):
                        mime_type = "image/png"
                    else:
                        mime_type = "image/jpeg"
                else:
                    # Unexpected scenario
                    continue
            else:
                # No data found
                continue

            # Open the image
            try:
                image = Image.open(io.BytesIO(image_data))
            except:
                continue

            # Check if blank or magenta
            if is_blank_image(image) or is_magenta_image(image):
                # Remove this image
                gltf.images[i] = None
            else:
                # Compress image
                compressed = compress_image(image)

                # Determine mime type for compressed image
                # Check first few bytes
                if compressed.startswith(b'\x89PNG'):
                    new_mime_type = "image/png"
                else:
                    new_mime_type = "image/jpeg"

                # Set as data URI
                gltf.images[i].uri = encode_data_uri(compressed, new_mime_type)
                gltf.images[i].bufferView = None
                gltf.images[i].mimeType = new_mime_type

        # Remove images set to None
        old_to_new_img = {}
        new_images = []
        for idx, im in enumerate(gltf.images):
            if im is not None:
                old_to_new_img[idx] = len(new_images)
                new_images.append(im)
        gltf.images = new_images

        # Update textures
        if gltf.textures:
            new_textures = []
            old_to_new_tex = {}
            for t_i, tex in enumerate(gltf.textures):
                if tex.source in old_to_new_img:
                    new_index = len(new_textures)
                    old_to_new_tex[t_i] = new_index
                    tex.source = old_to_new_img[tex.source]
                    new_textures.append(tex)
            gltf.textures = new_textures

            # Update materials
            if gltf.materials:
                for mat in gltf.materials:
                    if mat.pbrMetallicRoughness and mat.pbrMetallicRoughness.baseColorTexture:
                        old_index = mat.pbrMetallicRoughness.baseColorTexture.index
                        if old_index in old_to_new_tex:
                            mat.pbrMetallicRoughness.baseColorTexture.index = old_to_new_tex[old_index]
                        else:
                            mat.pbrMetallicRoughness.baseColorTexture = None

                    if mat.normalTexture:
                        old_index = mat.normalTexture.index
                        if old_index in old_to_new_tex:
                            mat.normalTexture.index = old_to_new_tex[old_index]
                        else:
                            mat.normalTexture = None

                    if mat.emissiveTexture:
                        old_index = mat.emissiveTexture.index
                        if old_index in old_to_new_tex:
                            mat.emissiveTexture.index = old_to_new_tex[old_index]
                        else:
                            mat.emissiveTexture = None

                    if mat.occlusionTexture:
                        old_index = mat.occlusionTexture.index
                        if old_index in old_to_new_tex:
                            mat.occlusionTexture.index = old_to_new_tex[old_index]
                        else:
                            mat.occlusionTexture = None

    # Convert buffers back to BINARYBLOB to produce a proper GLB
    gltf.convert_buffers(BufferFormat.BINARYBLOB)

    # Save as GLB
    gltf.save(output_path)

def main():
    for file in os.listdir(input_dir):
        if file.lower().endswith(".glb"):
            input_path = os.path.join(input_dir, file)
            output_path = os.path.join(output_dir, file)
            print(f"Optimizing {file}...")
            optimize_gltf(input_path, output_path)
            print(f"Saved optimized file to {output_path}")

if __name__ == "__main__":
    main()
