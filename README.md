# Image-Processor
 
Docker https://hub.docker.com/r/reverie89/image-processor

Coded with ChatGPT

## Features:

- Upload single image or zip file of images for batch conversion. Now with recursive support!

- Convert jpg, png, gif, webp images. Animated gif/webp supported.

- Choose conversion quality [0 - 100].

- Resize image's width / height while keeping aspect ratio

- Watermark with user supplied image or text with user supplied font file (.ttf)

- Set ENV VAR `UPLOAD_LIMIT` to limit file size upload in MB (numbers only). No limit if not set

## How to use

1. Run as a docker container:
`docker --rm -it -e UPLOAD_LIMIT=100 -p 8000:8000 reverie89/image-processor`

2. Access on the web: http://localhost:8000