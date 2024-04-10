from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from markupsafe import escape
from PIL import Image, ImageDraw, ImageFont
import os
import zipfile
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['FONT_FOLDER'] = 'usr_fonts'
app.secret_key = 'your_secret_key'

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'gif', 'png', 'webp', 'zip'}
ALLOWED_EXTENSIONS_WATERMARK = {'jpg', 'jpeg', 'gif', 'png', 'webp'}
DEFAULT_FONT = 'static/fonts/Roboto-Regular.ttf'
FONT_DIR = 'static/fonts/'
FONTS = [os.path.join(FONT_DIR, f) for f in os.listdir(FONT_DIR) if f.endswith('.ttf')]

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def delete_file(file_path):
    try:
        os.remove(file_path)
    except OSError as e:
        print(f"Error deleting file: {e.filename} - {e.strerror}")
        
def sanitize_input(input_str):
    return escape(input_str)

def resize_image(image, width):
    aspect_ratio = float(image.height) / float(image.width)
    new_height = int(width * aspect_ratio)
    return image.resize((width, new_height))

def save_image(img, format, quality, width):
    output = io.BytesIO()
    if img.width > width:
        img = resize_image(img, width)
    if format.lower() in {'jpg', 'jpeg'} and img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(output, format=format, quality=quality)
    output.seek(0)
    return output

def process_image(file, format, quality, width, watermark=None, opacity=50, position=(0, 0), text_watermark="", text_watermark_color="#ffffff", font_path=DEFAULT_FONT, font_size=36):
    def process_single_image(img, format, quality, width, watermark=None, opacity=50, position=position, text_watermark=text_watermark, text_watermark_color=text_watermark_color, font_path=font_path, font_size=font_size):
        if watermark:
            watermark_image = Image.open(watermark)
            watermark_image = resize_image(watermark_image, int(img.width * 0.2))
            watermark_image = watermark_image.convert('RGBA')
            alpha = int(255 * (opacity / 100))
            watermark_image.putalpha(alpha)
            img.paste(watermark_image, position, watermark_image)
        if text_watermark:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(font_path, font_size)
            draw.text(position, text_watermark, fill=text_watermark_color, font=font)
        output = save_image(img, format, quality, width)
        print(position)
        return output

    if file.filename.endswith('.zip'):
        processed_images = []
        with zipfile.ZipFile(file, 'r') as zip_file:
            for filename in zip_file.namelist():
                if allowed_file(filename, ALLOWED_EXTENSIONS):
                    with zip_file.open(filename) as image_file:
                        img = Image.open(io.BytesIO(image_file.read()))
                        processed_images.append((filename, img))

        zip_output = io.BytesIO()
        with zipfile.ZipFile(zip_output, 'w') as output_zip_file:
            for filename, img in processed_images:
                output = process_single_image(img, format, quality, width, watermark, opacity)
                output_filename = f"{os.path.splitext(filename)[0]}.{format.lower()}"
                output_zip_file.writestr(output_filename, output.getvalue())

        zip_output.seek(0)
        return zip_output
    else:
        img = Image.open(io.BytesIO(file.read()))
        output = process_single_image(img, format, quality, width, watermark, opacity)
        output.seek(0)
        return output

@app.route('/', methods=['GET', 'POST'])
def index():
    font_files = [os.path.basename(f) for f in FONTS]
    if request.method == 'POST':
        print(request.files)
        file = request.files['file-input']
        format = sanitize_input(request.form['format'])
        quality = int(sanitize_input(request.form['quality']))
        width = int(sanitize_input(request.form['width']))
        
        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
            filename = secure_filename(file.filename)
            watermark = None
            opacity = int(sanitize_input(request.form['opacity']))
            position = (int(sanitize_input(request.form['watermark-position-x'])), int(sanitize_input(request.form['watermark-position-y'])))
            text_watermark = sanitize_input(request.form['text-watermark'])
            text_watermark_color = sanitize_input(request.form['text-watermark-color'])
            selected_font = sanitize_input(request.form['font-select-option'])
            uploaded_font = request.files['watermark-font']
            uploaded_font_path = None
            if selected_font == 'upload' and uploaded_font:
                uploaded_font_path = os.path.join(app.config['FONT_FOLDER'], secure_filename(uploaded_font.filename))
                uploaded_font.save(uploaded_font_path)
                font_path = uploaded_font_path
            else:
                font_path = FONTS[font_files.index(selected_font)]
            font_size = int(sanitize_input(request.form['text-watermark-font-size']))
            watermark_path = None
            if request.form['watermark-type'] == 'image':
                
                watermark_file = request.files['watermark-image']
                if watermark_file and allowed_file(watermark_file.filename, ALLOWED_EXTENSIONS_WATERMARK):
                    watermark_filename = secure_filename(watermark_file.filename)
                    watermark_path = os.path.join(app.config['UPLOAD_FOLDER'], watermark_filename)
                    watermark_file.save(watermark_path)
                    watermark = watermark_path
                
            processed_file = process_image(file, format, quality, width, watermark=watermark, opacity=opacity, position=position, text_watermark=text_watermark, text_watermark_color=text_watermark_color, font_path=font_path, font_size=font_size)
            
            if filename.endswith('.zip'):
                response = send_file(processed_file, mimetype='application/zip', as_attachment=True, download_name=os.path.splitext(filename)[0] + '.zip')
                if watermark_path != None:
                    delete_file(watermark_path)
                if uploaded_font_path != None:
                    delete_file(uploaded_font_path)
                return response
            else:
                response = send_file(processed_file, mimetype='image/' + format, as_attachment=True, download_name=os.path.splitext(filename)[0] + "." + format.lower())
                if watermark_path != None:
                    delete_file(watermark_path)
                if uploaded_font_path != None:
                    delete_file(uploaded_font_path)
                return response
        else:
            flash(f'Invalid file format.\nAllowed formats are {", ".join({extension} for extension in ALLOWED_EXTENSIONS)}.', 'error')
            flash(f'File uploaded was: {file.filename}', 'error')
            return redirect(url_for('index'))
    return render_template('index.html', fonts=font_files)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
