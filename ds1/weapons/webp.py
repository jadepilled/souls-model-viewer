import os
import subprocess

def convert_textures_to_webp(input_dir, output_dir):
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Iterate through all GLB files in the input directory
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".glb"):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)

            print(f"Processing: {filename}")

            # Build the glTF-Transform command
            cmd = [
                r"C:\Users\Jade\AppData\Roaming\npm\gltf-transform.cmd",
                "webp",  # Convert textures to WEBP
                input_path,
                output_path,
                "--lossless"  # Use lossless WEBP compression
            ]

            # Run the command and check for errors
            try:
                subprocess.run(cmd, check=True)
                print(f"Converted: {filename} -> {output_path}")
            except subprocess.CalledProcessError as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    # Set directories
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(current_dir, "output")

    # Run the conversion
    convert_textures_to_webp(current_dir, output_dir)
