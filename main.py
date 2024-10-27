from flask import Flask, request, send_file, make_response
import os
from openai import OpenAI
import boto3
from botocore.exceptions import NoCredentialsError
import hashlib
from dotenv import load_dotenv
import re
import random

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
You are an API that generates strange, cryptic, and even hauntingly creepy "web art" pages similar to superbad.com or jodi.org. The input will be a filename, and the output should exclusively consist of an HTML document with embedded CSS and optional JavaScript. Ensure that the content features arbitrary, disconnected text that may resemble free verse, discuss a completely arbitrary topic, or seem like it was copied out of context from another source or even belongs on another website entirely, and includes random links to other HTML documents following the {word}.html format.

# Steps

1. **HTML Structure**: 
   - Begin with a basic HTML structure, starting with `<!DOCTYPE html>`.
   - Important: After the opening <html> tag, you can write a few sentences in a comment as a scratchpad to work through developing the concept for your page
   - Incorporate surreal elements within the `<body>` tag.
   - Structure ideas:
      - Format like a personal homepage
      - Fake product listings
      - A simple minigame or puzzle in JavaScript
      - A news article
      - Corporate website
      - Government form
      - Control panel
      - Any type of HTML page you can think of! The sky is the limit!

2. **Styling with CSS**:
   - Embed CSS within the `<style>` tag within the `<head>` to create a visually unique and abstract layout.
   - Use properties like colors, fonts, and layout styles that contribute to a surreal appearance.

3. **JavaScript (Optional)**:
   - Optionally include `<script>` tags for interactive, dynamic, or animated effects.
   - Ensure that any JavaScript included is inline and contributes to the page's surreal nature.

4. **Content Generation**:
   - Create paragraphs of text that are randomly assembled to emulate free verse or feel like out-of-context quotations.
      - Ideas for content:
         - Short stories
         - Essays
         - Poems
         - Cryptic instructions
         - Out of context snippets of mundane conversations
         - Lists
         - Strange news-like content
         - Odd "jokes" that make no sense
         - Fake listings for imaginary products
         - Etc.
   - Create strange visual and interactive elements.
   - Only use relative links and do not reference any other site!
   - To include images, you must embed SVG code.

5. **Hyperlink Incorporation**:
   - Include links to other randomly generated HTML filenames using anchor tags.
   - Format links as {word}.html, ensuring they reflect the surreal theme of the website.

# Output Format

The output should be a single string representing an HTML document. The response must not include additional JSON or text around the HTML.

# Notes

- The content should evoke an experience of strangeness and dislocation, fitting the weird aesthetic.
- Ensure that all CSS and optional JavaScript are directly embedded within the HTML.
- Do not mention "surreal", "web art", or any other site.
- Create novel and exciting interactive elements! They can be fairly complex!
- NEVER use base64.
- Avoid using alert(). Do something more creative and aesthetic!
- Include 1 comment somewhere in the HTML. You can use a longer comment to draft the concept for your webpage.
- DON'T be "monkey cheese spork banana"-style "random". Be CREATIVE.
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

    model = "gpt-4o-mini"

    # Generate page using OpenAI Chat Completions API
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{filename}.html"}
        ],
        max_tokens=4095,
        temperature=random.uniform(1.1, 1.22)
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