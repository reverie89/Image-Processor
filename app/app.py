import traceback
import os
import io
import sys
import zipfile
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
from markupsafe import escape
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['FONT_FOLDER'] = 'usr_fonts'
app.secret_key = 'your_secret_key'
if os.getenv('UPLOAD_LIMIT') is not None:
    app.config['MAX_CONTENT_LENGTH'] = int(
        # set file upload limit (*.MB)
        os.getenv('UPLOAD_LIMIT') * 1024 * 1024)
ALLOWED_IMAGES = {'jpg', 'jpeg', 'gif', 'png', 'webp'}
ALLOWED_ZIP = {'zip'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGES | ALLOWED_ZIP
ALLOWED_EXTENSIONS_WATERMARK_FONT = {'ttf'}
DEFAULT_FONT = 'static/fonts/Roboto-Regular.ttf'
FONT_DIR = 'static/fonts/'
FONTS = [os.path.join(FONT_DIR, f)
         for f in os.listdir(FONT_DIR) if f.endswith('.ttf')]
font_files = [os.path.basename(f) for f in FONTS]

error_messages = []


def allowed_file(filename, allowed_extensions):
    try:
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
    except:
        print(f'File type not accepted. Must be {
              ", ".join(allowed_extensions)}')
        error_messages.append(f'File type not accepted. Must be {
                              ", ".join(allowed_extensions)}')


def delete_file(file_path):
    try:
        os.remove(file_path)
    except OSError as e:
        print(f'Error deleting file: {e.filename} - {e.strerror}')
        error_messages.append(f'Error deleting file: {
                              e.filename} - {e.strerror}')


def sanitize_input(input_str):
    return escape(input_str)


def process_input(input_file, format, quality, width, height, watermark, opacity_text, opacity_bg, position, w_rotation, w_size, resize_w_size, text_watermark, text_watermark_color, font_path):

    def prep_wmark_size(image: Image.Image, wmark_img: Image.Image, wmark_resize: int = 40):

        output = io.BytesIO()
        frames = []

        dimensions = int(image.width), int(image.height)

        if wmark_img.width >= dimensions[0] or wmark_img.height >= dimensions[1]:

            dimensions = int(image.width * (wmark_resize/100)
                             ), int(image.height * (wmark_resize/100))

        # Animated watermark
        if isAnimatedImg(wmark_img):

            for i in range(wmark_img.n_frames):

                frame = process_frame(
                    image=wmark_img.copy(),
                    resize=dimensions
                )
                frames.append(frame.copy())
                wmark_img.seek(i)
            wmark_img.seek(0)

        # Non-animated watermark
        else:

            frame = process_frame(
                image=wmark_img.copy(),
                resize=dimensions
            )
            frames.append(frame.copy())

        frames[0].save(output, format="PNG", save_all=True, append_images=frames[1:],
                       loop=0)

        return Image.open(output)

    def process_frame(image: Image.Image, resize_aspect: bool = True, resize: tuple = None, rotation: int = None, alpha: int = None, wmark_img: Image.Image = None, wmark_pos: tuple = (0, 0)):
        image = image.convert("RGBA")
        if resize is not None:
            # keep aspect ratio
            if resize_aspect:
                aspect_ratio = image.height / image.width
                new_width = image.width
                new_height = image.height

                r_width, r_height = resize

                if image.width > r_width:
                    new_width = r_width
                    new_height = int(r_width * aspect_ratio)
                elif image.height > r_height:
                    new_width = int(r_height / aspect_ratio)
                    new_height = r_height
            else:
                new_width, new_height = resize
            image = image.resize((new_width, new_height))
        if alpha is not None:
            image.putalpha(int(255 * (alpha / 100)))
        if wmark_img is not None:
            image.paste(wmark_img, wmark_pos, wmark_img)
        if rotation is not None:
            image = image.rotate(rotation, expand=True, fillcolor=None)
        return image

    def convertImg(image: Image.Image, resize_aspect: bool = True, resize: tuple = None, rotation: int = None, alpha: int = None, wmark_resize: int = 40, wmark_img: Image.Image = None, wmark_pos: tuple = None):
        output = io.BytesIO()

        frames = []

        # Animated image
        if isAnimatedImg(image):

            # No watermark
            if wmark_img is None:

                for i in range(image.n_frames):

                    frame = process_frame(
                        image=image.copy(),
                        resize_aspect=resize_aspect,
                        resize=resize,
                        rotation=rotation,
                        alpha=alpha
                    )
                    frames.append(frame.copy())

                    image.seek(i)

                image.seek(0)

            # Has watermark
            else:

                # Animated watermark
                if isAnimatedImg(wmark_img):

                    for i in range(image.n_frames):

                        frame = process_frame(
                            image=image.copy(),
                            resize_aspect=resize_aspect,
                            resize=resize,
                            rotation=rotation,
                            alpha=alpha,
                            wmark_img=prep_wmark_size(
                                image=image.copy(),
                                wmark_img=wmark_img.copy(),
                                wmark_resize=wmark_resize),
                            wmark_pos=wmark_pos
                        )
                        frames.append(frame.copy())

                        if i < wmark_img.n_frames:
                            wmark_img.seek(i)
                        image.seek(i)

                    wmark_img.seek(0)
                    image.seek(0)

                # Non-animated watermark
                else:

                    for i in range(image.n_frames):

                        frame = process_frame(
                            image=image.copy(),
                            resize_aspect=resize_aspect,
                            resize=resize,
                            rotation=rotation,
                            alpha=alpha,
                            wmark_img=prep_wmark_size(
                                image=image.copy(),
                                wmark_img=wmark_img.copy(),
                                wmark_resize=wmark_resize),
                            wmark_pos=wmark_pos
                        )
                        frames.append(frame.copy())

                        image.seek(i)

                    image.seek(0)

        # Non-animated image
        else:

            # No watermark
            if wmark_img is None:

                frame = process_frame(
                    image=image.copy(),
                    resize_aspect=resize_aspect,
                    resize=resize,
                    rotation=rotation,
                    alpha=alpha
                )
                frames.append(frame.copy())

            # Has watermark
            else:

                # Animated watermark
                if isAnimatedImg(wmark_img):

                    for i in range(wmark_img.n_frames):

                        frame = process_frame(
                            image=image.copy(),
                            resize_aspect=resize_aspect,
                            resize=resize,
                            rotation=rotation,
                            alpha=alpha,
                            wmark_img=prep_wmark_size(
                                image=image.copy(),
                                wmark_img=wmark_img.copy(),
                                wmark_resize=wmark_resize),
                            wmark_pos=wmark_pos
                        )
                        frames.append(frame.copy())

                        wmark_img.seek(i)

                    wmark_img.seek(0)
                    image.seek(0)

                # Non-animated watermark
                else:

                    frame = process_frame(
                        image=image.copy(),
                        resize_aspect=resize_aspect,
                        resize=resize,
                        rotation=rotation,
                        alpha=alpha,
                        wmark_img=prep_wmark_size(
                            image=image.copy(),
                            wmark_img=wmark_img.copy(),
                            wmark_resize=wmark_resize),
                        wmark_pos=wmark_pos
                    )
                    frames.append(frame.copy())

        frames[0].save(
            output,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            loop=0
        )
        output.seek(0)
        return Image.open(output)

    def isAnimatedImg(image: Image.Image) -> bool:
        return hasattr(image, 'n_frames') and image.n_frames > 1

    def save_image(img, format, quality, width, height):
        output = io.BytesIO()
        if img.format != 'gif':
            img.convert('RGBA')
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

    def process_image(img, format, quality, width, height, watermark, opacity_text, opacity_bg, position, w_rotation, w_size, resize_w_size, text_watermark, text_watermark_color, font_path):
        # Function to add watermark image

        def add_image_watermark(img: Image.Image, watermark: Image.Image, w_rotation: int, w_size: int, resize_w_size: int, opacity_bg: int, position: tuple):
            try:
                watermark_image = Image.open(watermark)
                watermark_image = convertImg(
                    image=watermark_image, resize=(
                        int(watermark_image.width * (w_size/100)), int(watermark_image.height * (w_size/100))), alpha=opacity_bg, rotation=w_rotation)
                new_image = convertImg(
                    image=img, wmark_resize=resize_w_size, wmark_img=watermark_image, wmark_pos=position)
                return new_image
            except Exception as e:
                print(traceback.format_exc())
                error_messages.append(e)

        # Function to add text watermark
        def add_text_watermark(img, wtext, wtext_color, w_rotation, opacity_text, opacity_bg, position, font_path, w_size):
            def hex_to_rgba(hex_color, alpha=255):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4)) + (alpha,)
            # for name, value in locals().items():
            #     print(f'{name}: {value}')
            try:
                font = ImageFont.truetype(font_path, w_size)
                w_left, w_top, w_right, w_bottom = font.getbbox(wtext)
                wtext_w, wtext_h = w_right - w_left, (w_bottom - w_top)*2
            except Exception as e:
                print(traceback.format_exc())
                error_messages.append(f'Error loading font: {e}')
            try:
                text_img = Image.new(
                    'RGBA', (wtext_w, wtext_h))
                text_img.putalpha(int(255 * (opacity_bg / 100)))
                text_draw = ImageDraw.Draw(text_img)
                text_draw.text(xy=(0, 0), text=wtext,
                               fill=hex_to_rgba(wtext_color, int(255 * opacity_text/100)), font=font)
                text_img = convertImg(text_img, resize=(
                    int(img.width * 0.2) * w_size, int(text_img.height * w_size)), rotation=w_rotation)
                img = convertImg(img, wmark_img=text_img, wmark_pos=position)
                return img
            except Exception as e:
                print(traceback.format_exc())
                error_messages.append(e)

        # Add watermark if specified
        if watermark:
            print('watermark image')
            img = add_image_watermark(
                img=img,
                watermark=watermark,
                w_rotation=w_rotation,
                w_size=w_size,
                resize_w_size=resize_w_size,
                opacity_bg=opacity_bg,
                position=position)

        # Add text watermark if specified
        if text_watermark:
            print('watermark text')
            img = add_text_watermark(
                img=img,
                wtext=text_watermark,
                wtext_color=text_watermark_color,
                w_rotation=w_rotation,
                w_size=w_size,
                opacity_bg=opacity_bg,
                opacity_text=opacity_text,
                position=position,
                font_path=font_path)

        output = save_image(img, format, quality, width, height)
        return output

    def process_zip(input_zip, format, quality, width, height, watermark, opacity_text, opacity_bg, position, w_rotation, w_size, resize_w_size, text_watermark, text_watermark_color, font_path):
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
                print(f'Error writing ZIP file to memory: {e}')
                error_messages.append(f'Error writing ZIP file to memory: {e}')
                return None

        try:
            to_process = []
            print(f'Input object: {input_zip}')
            with zipfile.ZipFile(input_zip, 'r', allowZip64=True) as zipf:
                try:
                    for obj in zipf.infolist():
                        with zipf.open(obj) as obj_file:
                            # recursive support on zip
                            if allowed_file(obj.filename, ALLOWED_ZIP):
                                to_process.append(
                                    (obj.filename, ext_zip2mem(obj_file)))
                            elif allowed_file(obj.filename, ALLOWED_EXTENSIONS):
                                img = Image.open(io.BytesIO(obj_file.read()))
                                to_process.append((obj.filename, img))
                except Exception as e:
                    print(f'Error preparing files: {e}')
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
                                opacity_text=opacity_text,
                                opacity_bg=opacity_bg,
                                position=position,
                                w_rotation=w_rotation,
                                w_size=w_size,
                                resize_w_size=resize_w_size,
                                text_watermark=text_watermark,
                                text_watermark_color=text_watermark_color,
                                font_path=font_path)
                            output_zipf.writestr(
                                obj_filename, output.getvalue())
                        else:
                            output = process_image(
                                img=obj,
                                format=format,
                                quality=quality,
                                width=width,
                                height=height,
                                watermark=watermark,
                                opacity_text=opacity_text,
                                opacity_bg=opacity_bg,
                                position=position,
                                w_rotation=w_rotation,
                                w_size=w_size,
                                resize_w_size=resize_w_size,
                                text_watermark=text_watermark,
                                text_watermark_color=text_watermark_color,
                                font_path=font_path)
                            output_zipf.writestr(
                                f'{obj_filename}.{format}', output.getvalue())
                    output_zip.seek(0)
                except Exception as e:
                    print(f'Error processing images: {e}')
                    error_messages.append(f'Error processing images: {e}')

            output_zip.seek(0)
            return output_zip
        except zipfile.BadZipFile:
            print(f'Could not open zip file: {input_zip.filename}')
            error_messages.append(f'Could not open zip file: {
                                  input_zip.filename}')
        except Exception as e:
            print((f'Error processing zip: {e}'))
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
                opacity_text=opacity_text,
                opacity_bg=opacity_bg,
                position=position,
                w_rotation=w_rotation,
                w_size=w_size,
                resize_w_size=resize_w_size,
                text_watermark=text_watermark,
                text_watermark_color=text_watermark_color,
                font_path=font_path)
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
                opacity_text=opacity_text,
                opacity_bg=opacity_bg,
                position=position,
                w_rotation=w_rotation,
                w_size=w_size,
                resize_w_size=resize_w_size,
                text_watermark=text_watermark,
                text_watermark_color=text_watermark_color,
                font_path=font_path)
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
            print(f'File input error: {e}')
            error_messages.append(f'File input error: {e}')

        format = sanitize_input(request.form['format']).lower(
        ) if request.form['format'] else 'webp'
        quality = min(int(sanitize_input(
            request.form['quality'])), 100) if request.form['quality'] else 100
        width = int(sanitize_input(
            request.form['width'])) if request.form['width'] else 1600
        height = int(sanitize_input(
            request.form['height'])) if request.form['height'] else 900
        # watermarking
        opacity_text = int(sanitize_input(
            request.form['opacity-text'])) if request.form['opacity-text'] else 100
        opacity_bg = int(sanitize_input(
            request.form['opacity-bg'])) if request.form['opacity-bg'] else 100
        position = (int(sanitize_input(request.form['watermark-position-x'])), int(sanitize_input(
            request.form['watermark-position-y']))) if request.form['watermark-position-x'] and request.form['watermark-position-y'] else (0, 0)
        w_rotation = int(sanitize_input(request.form['watermark-rotation']))
        w_size = int(sanitize_input(
            request.form['watermark-size'])) if request.form['watermark-size'] else 50
        resize_w_size = int(sanitize_input(
            request.form['resize-watermark-size'])) if request.form['resize-watermark-size'] else 40
        # if watermarking type is text
        text_watermark = sanitize_input(
            request.form['text-watermark']) if request.form['text-watermark'] else ""
        text_watermark_color = sanitize_input(request.form['text-watermark-color']) if request.form['text-watermark-color'] and len(
            request.form['text-watermark-color']) == 7 else "#000000"
        watermark_obj = None
        font_obj = None
        font_path = None
        if sanitize_input(request.form['watermark-type']) == 'text':
            # pick a font if it should be user uploaded or from the selection list
            selected_font = sanitize_input(
                request.form['font-select-option']) if request.form['font-select-option'] else font_files[0]

            if selected_font == 'upload':
                uploaded_font_path = None
                try:
                    font_obj = request.files.get('watermark-font')
                    if obj_exists(font_obj):
                        if allowed_file(secure_filename(font_obj.filename), ALLOWED_EXTENSIONS_WATERMARK_FONT):
                            uploaded_font_path = os.path.join(
                                app.config['FONT_FOLDER'], secure_filename(font_obj.filename))
                            font_obj.save(uploaded_font_path)
                            font_path = uploaded_font_path
                except Exception as e:
                    font_obj = None
                    print(f'Font input error: {e}')
                    error_messages.append(f'Font input error: {e}')
            else:
                font_path = FONTS[font_files.index(selected_font)]
            w_size = int(sanitize_input(
                request.form['watermark-size'])) if request.form['watermark-size'] else 50
        else:
            # save the watermark image
            watermark_path = None

            watermark_obj = None if len(request.files.get(
                'watermark-image').read()) == 0 else request.files.get('watermark-image')
            if sanitize_input(request.form['watermark-type']) == 'image':
                if watermark_obj is None:
                    print('No watermark image uploaded')
                    error_messages.append('No watermark image uploaded')
                else:
                    if allowed_file(secure_filename(watermark_obj.filename), ALLOWED_IMAGES):
                        watermark_path = os.path.join(
                            app.config['UPLOAD_FOLDER'], secure_filename(watermark_obj.filename))
                        watermark_obj.save(watermark_path)
        # process input
        try:
            processed_files = []
            for file in files:
                if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
                    extension = 'zip' if os.path.splitext(file.filename)[1] in {
                        '.zip'} else format
                    filename = f"{os.path.splitext(secure_filename(file.filename))[0]}.{
                        extension}"
                    processed_files.append(
                        (filename, process_input(
                            input_file=file,
                            format=format,
                            quality=quality,
                            width=width,
                            height=height,
                            watermark=watermark_obj,
                            opacity_text=opacity_text,
                            opacity_bg=opacity_bg,
                            position=position,
                            w_rotation=w_rotation,
                            w_size=w_size,
                            resize_w_size=resize_w_size,
                            text_watermark=text_watermark,
                            text_watermark_color=text_watermark_color,
                            font_path=font_path)
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
            print(traceback.format_exc())
            error_messages.append(f'Error: {e}')
            for messages in error_messages:
                flash(f'{messages}', 'error')
            return redirect(url_for('index'))
    return render_template('index.html', fonts=font_files)


if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
