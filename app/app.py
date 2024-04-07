from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from markupsafe import escape
from PIL import Image
import os
import zipfile
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'gif', 'png', 'webp', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_input(input_str):
    return escape(input_str)

def resize_image(image, width):
    aspect_ratio = float(image.height) / float(image.width)
    new_height = int(width * aspect_ratio)
    return image.resize((width, new_height))

def save_image(img, format, quality, width):
    output = io.BytesIO()
    # Resize image only if its width exceeds the specified width
    if img.width > width:
        img = resize_image(img, width)
    # Convert image to RGB mode only when saving as JPEG
    if format.lower() == 'jpg':
        format = 'jpeg'
        if img.mode == 'RGBA':
            img = img.convert('RGB')
    if format.lower() == 'jpeg':
        if img.mode == 'RGBA':
            img = img.convert('RGB')
    img.save(output, format=format, quality=quality)
    output.seek(0)
    return output

def process_image_recursively(zip_file, directory, processed_images):
    for filename in zip_file.namelist():
        if filename.startswith(directory):
            # Skip directories
            if filename.endswith('/'):
                continue
            try:
                # Extract file from the zip
                if allowed_file(filename):
                    with zip_file.open(filename) as image_file:
                        img = Image.open(io.BytesIO(image_file.read()))
                        processed_images.append((filename, img))
            except Exception as e:
                print(f"Error processing {filename}: {e}")

def process_image(file, format, quality, width):
    if file.filename.endswith('.zip'):
        processed_images = []
        zip_file = zipfile.ZipFile(file, 'r')
        for filename in zip_file.namelist():
            if filename.startswith(''):
                # Skip directories
                if filename.endswith('/'):
                    continue
                try:
                    # Extract file from the zip
                    if allowed_file(filename):
                        with zip_file.open(filename) as image_file:
                            img = Image.open(io.BytesIO(image_file.read()))
                            processed_images.append((filename, img))
                except Exception as e:
                    print(f"Error processing {filename}: {e}")
        zip_file.close()
        zip_output = io.BytesIO()
        with zipfile.ZipFile(zip_output, 'w') as output_zip_file:
            processed_filenames = set()
            for filename, img in processed_images:
                output = save_image(img, format, quality, width)
                base_filename, ext = os.path.splitext(filename)
                output_filename = f"{base_filename}.{format.lower()}"
                # Ensure the processed filename is unique
                count = 1
                while output_filename in processed_filenames:
                    output_filename = f"{base_filename}_{count}.{format.lower()}"
                    count += 1
                processed_filenames.add(output_filename)
                output_zip_file.writestr(output_filename, output.getvalue())
        zip_output.seek(0)
        return zip_output
    else:
        img = Image.open(io.BytesIO(file.read()))
        output = save_image(img, format, quality, width)
        output.seek(0)
        return output
        


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        format = sanitize_input(request.form['format'])
        quality = int(sanitize_input(request.form['quality']))
        width = int(sanitize_input(request.form['width']))
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            processed_file = process_image(file, format, quality, width)
            if filename.endswith('.zip'):
                return send_file(processed_file, mimetype='application/zip', as_attachment=True, download_name=os.path.splitext(filename)[0] + '.zip')
            else:
                return send_file(processed_file, mimetype='image/' + format, as_attachment=True, download_name=os.path.splitext(filename)[0] + "." + format.lower())
        else:
            flash(f'Invalid file format.\nAllowed formats are JPG, JPEG, GIF, PNG, WEBP, ZIP.', 'error')
            flash(f'File uploaded was: {file.filename}', 'error')
            return redirect(url_for('index'))  # Redirect back to the index page
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)