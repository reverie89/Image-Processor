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
if os.getenv('UPLOAD_LIMIT') is not None:
    app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('UPLOAD_LIMIT') * 1024 * 1024) # set file upload limit (*.MB)
ALLOWED_IMAGES = {'jpg', 'jpeg', 'gif', 'png', 'webp'}
ALLOWED_ZIP = {'zip'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGES | ALLOWED_ZIP
ALLOWED_EXTENSIONS_WATERMARK_FONT = {'ttf'}
DEFAULT_FONT = 'static/fonts/Roboto-Regular.ttf'
FONT_DIR = 'static/fonts/'
FONTS = [os.path.join(FONT_DIR, f) for f in os.listdir(FONT_DIR) if f.endswith('.ttf')]
font_files = [os.path.basename(f) for f in FONTS]

error_messages = []

def allowed_file(filename, allowed_extensions):
    try:
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    except:
        error_messages.append(f'File type not accepted. Must be {", ".join(allowed_extensions)}')

def delete_file(file_path):
    try:
        os.remove(file_path)
    except OSError as e:
        error_messages.append(f'Error deleting file: {e.filename} - {e.strerror}')
        
def sanitize_input(input_str):
    return escape(input_str)

def resize_image(image, width, height):
    aspect_ratio = float(image.height) / float(image.width)
    if image.width > width:
        new_height = int(width * aspect_ratio)
        image = image.resize((width, new_height))
    if image.height > height:
        new_width = int(height / aspect_ratio)
        image = image.resize((new_width, height))
    return image

def save_image(img, format, quality, width, height):
    output = io.BytesIO()
    img = resize_image(img, width, height)
    if format in {'jpg', 'jpeg'} and img.mode == 'RGBA':
        img = img.convert('RGB')
    if img.format == 'WEBP' and format == 'gif':
        img.info.pop('background', None)
    img.save(output,
             format='jpeg' if format in {'jpg', 'jpeg'} else format,
             quality=quality,
             save_all=False if format in {'jpg', 'jpeg'} else True)
    output.seek(0)
    return output

def process_input(input_file, format, quality, width, height, watermark, opacity, position, text_watermark, text_watermark_color, font_path, font_size):
    
    def process_image(img, format, quality, width, height, watermark, opacity, position, text_watermark, text_watermark_color, font_path, font_size):
        # for name, value in locals().items():
        #     print(f'{name}: {value}')
        if watermark is not None:
            try:
                watermark_image = Image.open(watermark)
                watermark_image = resize_image(watermark_image, int(img.width * 0.2), watermark_image.height)
                watermark_image = watermark_image.convert('RGBA')
                alpha = int(255 * (opacity / 100))
                watermark_image.putalpha(alpha)
                img.paste(watermark_image, position, watermark_image)
            except Exception as e:
                error_messages.append(e)
        if text_watermark:
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                print(f'Error loading font: {e}')
                error_messages.append(e)
            draw.text(position, text_watermark, fill=text_watermark_color, font=font)
        output = save_image(img, format, quality, width, height)
        return output
    
    def ext_zip2mem(zip_file):
        try:
            # Create an in-memory binary stream to hold the file's data
            file_data = io.BytesIO()
            # Read the contents of the ZipExtFile object into memory
            file_data.write(zip_file.read())
            # Reset the stream position to the beginning
            file_data.seek(0)
            return file_data
        except Exception as e:
            error_messages.append(f"Error writing ZIP file to memory: {e}")
            return None
    
    def process_zip(input_zip, format, quality, width, height, watermark, opacity, position, text_watermark, text_watermark_color, font_path, font_size):
        try:
            to_process = []
            print(f'Input object: {input_zip}')
            with zipfile.ZipFile(input_zip, 'r', allowZip64=True) as zipf:
                try:
                    for obj in zipf.infolist():
                        with zipf.open(obj) as obj_file:
                            # recursive support on zip
                            if allowed_file(obj.filename, ALLOWED_ZIP):
                                to_process.append((obj.filename, ext_zip2mem(obj_file)))
                            elif allowed_file(obj.filename, ALLOWED_EXTENSIONS):
                                img = Image.open(io.BytesIO(obj_file.read()))
                                to_process.append((obj.filename, img))
                except Exception as e:
                    error_messages.append(f'Error preparing files: {e}')

            output_zip = io.BytesIO()
            # Process images in 'to_process' list
            with zipfile.ZipFile(output_zip, 'w', allowZip64=True) as output_zipf:
                try:
                    for obj_filename, obj in to_process:
                        if allowed_file(obj_filename, ALLOWED_ZIP):
                            output = process_zip(
                                input_zip=obj,
                                format=format,
                                quality=quality,
                                width=width,
                                height=height,
                                watermark=watermark,
                                opacity=opacity,
                                position=position,
                                text_watermark=text_watermark,
                                text_watermark_color=text_watermark_color,
                                font_path=font_path,
                                font_size=font_size)
                            output_filename = obj_filename
                            output_zipf.writestr(output_filename, output.getvalue())
                        else:
                            output = process_image(
                                img=obj,
                                format=format,
                                quality=quality,
                                width=width,
                                height=height,
                                watermark=watermark,
                                opacity=opacity,
                                position=position,
                                text_watermark=text_watermark,
                                text_watermark_color=text_watermark_color,
                                font_path=font_path,
                                font_size=font_size)
                            output_filename = f'{os.path.splitext(obj_filename)[0]}.{format}'
                            if format in os.path.splitext(obj_filename)[1]:
                                output_filename = f'{obj_filename}.{format}'
                            output_zipf.writestr(output_filename, output.getvalue())
                    output_zip.seek(0)
                except Exception as e:
                    error_messages.append(f'Error processing images: {e}')

            output_zip.seek(0)
            return output_zip
        except zipfile.BadZipFile:
            error_messages.append(f'Could not open zip file: {input_zip.filename}')
        except Exception as e:
            error_messages.append(f'Error processing zip: {e}')
        
    if allowed_file(input_file.filename, ALLOWED_EXTENSIONS):
        if allowed_file(input_file.filename, ALLOWED_ZIP):
            output = process_zip(
                input_zip=input_file,
                format=format,
                quality=quality,
                width=width,
                height=height,
                watermark=watermark,
                opacity=opacity,
                position=position,
                text_watermark=text_watermark,
                text_watermark_color=text_watermark_color,
                font_path=font_path,
                font_size=font_size)
            return output
        else:
            img = Image.open(io.BytesIO(input_file.read()))
            output = process_image(
                img=img,
                format=format,
                quality=quality,
                width=width,
                height=height,
                watermark=watermark,
                opacity=opacity,
                position=position,
                text_watermark=text_watermark,
                text_watermark_color=text_watermark_color,
                font_path=font_path,
                font_size=font_size)
            output.seek(0)
            return output

def obj_exists(input):
    if len(input.read()) == 0:
        raise Exception('Cannot read object')
    input.seek(0)
    return True

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            if obj_exists(request.files.get('file-input')):
                files = request.files.getlist('file-input')
        except Exception as e:
            error_messages.append(f'File input error: {e}')
        
        format = sanitize_input(request.form['format']).lower() if request.form['format'] else 'webp'
        quality = max(int(sanitize_input(request.form['quality'])), 100) if request.form['quality'] else 100
        width = int(sanitize_input(request.form['width'])) if request.form['width'] else 1600
        height = int(sanitize_input(request.form['height'])) if request.form['height'] else 900
        # watermarking
        opacity = int(sanitize_input(request.form['opacity'])) if request.form['opacity'] else 100
        position = (int(sanitize_input(request.form['watermark-position-x'])), int(sanitize_input(request.form['watermark-position-y']))) if request.form['watermark-position-x'] and request.form['watermark-position-y'] else (0,0)
        # if watermarking type is text
        text_watermark = sanitize_input(request.form['text-watermark']) if request.form['text-watermark'] else ""
        text_watermark_color = sanitize_input(request.form['text-watermark-color']) if request.form['text-watermark-color'] and len(request.form['text-watermark-color']) == 7 else "#000000"
        watermark_obj = None
        font_obj = None
        font_path = None
        font_size = None
        if sanitize_input(request.form['watermark-type']) == 'text':
            # pick a font if it should be user uploaded or from the selection list
            selected_font = sanitize_input(request.form['font-select-option']) if request.form['font-select-option'] else font_files[0]
            
            if selected_font == 'upload':
                uploaded_font_path = None
                try:
                    font_obj = request.files.get('watermark-font')
                    if obj_exists(font_obj):
                        if allowed_file(secure_filename(font_obj.filename), ALLOWED_EXTENSIONS_WATERMARK_FONT):
                            uploaded_font_path = os.path.join(app.config['FONT_FOLDER'], secure_filename(font_obj.filename))
                            font_obj.save(uploaded_font_path)
                            font_path = uploaded_font_path
                except Exception as e:
                    font_obj = None
                    error_messages.append(f'Font input error: {e}')
            else:
                font_path = FONTS[font_files.index(selected_font)]
            font_size = int(sanitize_input(request.form['text-watermark-font-size'])) if request.form['text-watermark-font-size'] else 36
        else:
            # save the watermark image
            watermark_path = None

            watermark_obj = None if len(request.files.get('watermark-image').read()) == 0 else request.files.get('watermark-image')
            if sanitize_input(request.form['watermark-type']) == 'image':
                if watermark_obj is None:
                    error_messages.append("No watermark image uploaded")
                else:
                    if allowed_file(secure_filename(watermark_obj.filename), ALLOWED_IMAGES):
                        watermark_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(watermark_obj.filename))
                        watermark_obj.save(watermark_path)
        # process input
        try:
            processed_files = []
            for file in files:
                if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
                    extension = 'zip' if os.path.splitext(file.filename)[1] in {'.zip'} else format
                    filename = f"{os.path.splitext(secure_filename(file.filename))[0]}.{extension}"
                    processed_files.append(
                        (filename, process_input(
                            input_file=file,
                            format=format,
                            quality=quality,
                            width=width,
                            height=height,
                            watermark=watermark_obj,
                            opacity=opacity,
                            position=position,
                            text_watermark=text_watermark,
                            text_watermark_color=text_watermark_color,
                            font_path=font_path,
                            font_size=font_size)
                        ))
            # cleanup user uploaded watermark image/font
            if watermark_obj is not None:
                delete_file(watermark_path)
            if font_obj is not None:
                delete_file(uploaded_font_path)

            # send the processed file(s) back to user
            if len(processed_files) > 1:
                zip_output = io.BytesIO()
                with zipfile.ZipFile(zip_output, 'w', allowZip64=True) as output_zipf:
                    for filename, file in processed_files:
                        output_zipf.writestr(filename, file.read())
                zip_output.seek(0)
                return send_file(zip_output,
                                     mimetype='application/zip',
                                     as_attachment=True,
                                     download_name='output.zip')
            else:
                return send_file(processed_files[0][1],
                                     mimetype='image/' + format,
                                     as_attachment=True,
                                     download_name=processed_files[0][0])
        except Exception as e:
            error_messages.append(f'Error: {e}')
            for messages in error_messages:
                flash(f'{messages}', 'error')
            return redirect(url_for('index'))
    return render_template('index.html', fonts=font_files)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
