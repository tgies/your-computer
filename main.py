from flask import Flask, request, send_file, make_response
import os
from openai import OpenAI
import boto3
from botocore.exceptions import NoCredentialsError
import hashlib
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)

# Configure your OpenAI API key
openai = OpenAI()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configure S3
S3_BUCKET = os.getenv("S3_BUCKET")
s3 = boto3.client('s3')

CACHE_DIR = os.getenv("HTML_CACHE", "/tmp")

system_prompt = """
Create an API that generates surreal "web art" pages similar to superbad.com or jodi.org. The input will be a filename, and the output should exclusively consist of an HTML document with embedded CSS and optional JavaScript. Ensure that the content features random, disconnected text that may resemble free verse, discuss a completely random topic, or seem like it was copied out of context from another source or even belongs on another website entirely, and includes random links to other HTML documents following the {word}.html format.

# Steps

1. **HTML Structure**: 
   - Begin with a basic HTML structure, starting with `<!DOCTYPE html>`.
   - Incorporate surreal elements within the `<body>` tag.

2. **Styling with CSS**:
   - Embed CSS within the `<style>` tag within the `<head>` to create a visually unique and abstract layout.
   - Use properties like colors, fonts, and layout styles that contribute to a surreal appearance.

3. **JavaScript (Optional)**:
   - Optionally include `<script>` tags for interactive, dynamic, or animated effects.
   - Ensure that any JavaScript included is inline and contributes to the page's surreal nature.

4. **Content Generation**:
   - Create paragraphs of text that are randomly assembled to emulate free verse or feel like out-of-context quotations.
   - Create strange visual and interactive elements.
   - Only use relative links and do not reference any other site!
   - To include images, you must embed SVG code.

5. **Hyperlink Incorporation**:
   - Include links to other randomly generated HTML filenames using anchor tags.
   - Format links as {word}.html, ensuring they reflect the surreal theme of the website.

# Output Format

The output should be a single string representing an HTML document. The response must not include additional JSON or text around the HTML.

# Notes

- The content should evoke an experience of randomness and dislocation, fitting the surreal aesthetic.
- Ensure that all CSS and optional JavaScript are directly embedded within the HTML.
- The links provided should not point to actual files but adhere to the {word}.html format to maintain artistic consistency.
"""

@app.route('/')
@app.route('/index.html')
def generate_index():
    return generate_page('index')

@app.route('/<path:filename>.html')
def generate_page(filename):
    # Generate a hash to use for the cache filename
    filename_hash = hashlib.md5(filename.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{filename_hash}.html")

    # Check local cache
    if os.path.exists(cache_path):
        return send_file(cache_path)

    # Check S3
    try:
        s3.download_file(S3_BUCKET, f"{filename_hash}.html", cache_path)
        return send_file(cache_path)
    except NoCredentialsError:
        return "S3 credentials not available", 500
    except Exception as e:
        # Handle file not found or other errors from S3
        pass

    # Generate page using OpenAI Chat Completions API

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{filename}.html"}
        ],
        max_tokens=4095,
        temperature=1.15
    )

    html_content = response.choices[0].message.content.strip()

    # Trim content to only include HTML from <!DOCTYPE> to </html>
    html_match = re.search(r'(<!DOCTYPE html[\s\S]*?</html>)', html_content, re.IGNORECASE)
    if html_match:
        html_content = html_match.group(1)

    # Save to local cache
    with open(cache_path, 'w') as f:
        f.write(html_content)

    # Save to S3 with metadata including the original filename
    try:
        s3.upload_file(
            cache_path, 
            S3_BUCKET, 
            f"{filename_hash}.html", 
            ExtraArgs={"Metadata": {"original-filename": filename}}
        )
    except NoCredentialsError:
        return "S3 credentials not available", 500
    except Exception as e:
        return str(e), 500

    return make_response(html_content, 200, {'Content-Type': 'text/html'})

if __name__ == '__main__':
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    app.run(debug=True)
