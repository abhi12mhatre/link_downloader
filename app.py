import os
import re
import tempfile
import time

import streamlit as st
import yt_dlp
from selenium import webdriver

# Assuming these are your custom imports that work correctly
from scribd import (
    get_filename_from_url, build_chrome_options, hide_cookie_dialogs,
    prepare_document_for_print, inject_print_styles, save_pdf_pages_individually
)

def process_url(input_url, quality=None):
    """Routes the URL to the correct processor and returns the file path, mime type, and filename."""
    if "scribd" in input_url:
        match = re.search(r"https://www\.scribd\.com/(?:document|doc)/(\d+)/", input_url)
        if not match:
            raise ValueError("Invalid Scribd URL")
        return process_scribd_url(f"https://www.scribd.com/embeds/{match.group(1)}/content")

    elif "youtube.com" in input_url or "youtu.be" in input_url:
        match = re.search(
            r"(?:youtube\.com/.*[?&]v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
            input_url
        )
        if not match:
            raise ValueError("Invalid YouTube URL")
        return process_yt_url(input_url, quality)

    raise ValueError("URL not supported. Please provide a valid Scribd or YouTube link.")

def process_scribd_url(input_url):
    """Processes Scribd documents using Selenium and returns the saved file path."""
    pdf_filename = get_filename_from_url(input_url)

    # Save to a temporary directory to avoid cluttering the server
    temp_dir = tempfile.gettempdir()
    output_filepath = os.path.join(temp_dir, pdf_filename)

    with tempfile.TemporaryDirectory(prefix="scribd-chrome-profile-") as runtime_profile_dir:
        driver = None
        try:
            options = build_chrome_options(runtime_profile_dir)
            driver = webdriver.Chrome(options=options)

            driver.get(input_url)
            time.sleep(2) # Increased slightly to ensure page load

            hide_cookie_dialogs(driver)

            total_pages = driver.execute_script("return document.querySelectorAll('.outer_page').length;")
            if total_pages == 0:
                raise RuntimeError("No printable document pages were detected.")

            prepare_document_for_print(driver)
            inject_print_styles(driver)
            driver.execute_script("window.scrollTo(0, 0)")

            saved_path = save_pdf_pages_individually(driver, output_filepath)

            if not saved_path:
                raise RuntimeError("PDF export failed.")

            return saved_path, "application/pdf", pdf_filename

        finally:
            if driver:
                driver.quit()

def process_yt_url(input_url, quality=None):
    """Downloads a YouTube video to a temporary folder and returns the file path."""
    # Ensure it downloads as mp4
    format_string = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    if quality:
        # Strip 'p' if present (e.g., '1080p' -> '1080')
        res = quality.replace("p", "")
        format_string = f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    temp_dir = tempfile.gettempdir()

    ydl_opts = {
        'format': format_string,
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4', # Force MP4 container
        'quiet': True,
        'no_warnings': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract info and download in one step
        info = ydl.extract_info(input_url, download=True)
        filepath = ydl.prepare_filename(info)
        filename = os.path.basename(filepath)

        # Adjust extension if yt-dlp merged it differently
        if not filepath.endswith('.mp4'):
            filepath = filepath.rsplit('.', 1)[0] + '.mp4'
            filename = filename.rsplit('.', 1)[0] + '.mp4'

    return filepath, "video/mp4", filename


# --- STREAMLIT UI CODE ---

st.title("📚 Scribd PDF & YouTube Video Downloader")

raw_url = st.text_input(
    "Paste URL:",
    placeholder="https://www.scribd.com/document/... OR https://www.youtube.com/watch?v=..."
)

# Parse quality safely
quality_selection = st.selectbox("Choose video quality (YouTube only):", ["Best", "1080p", "720p", "480p"])
selected_quality = None if quality_selection == 'Best' else quality_selection

# Session state to hold download data so it survives reruns
if 'download_ready' not in st.session_state:
    st.session_state.download_ready = None

if st.button("Process File", type="primary"):
    url = raw_url.strip()

    if not url:
        st.warning("Please enter a valid URL.")
    else:
        with st.spinner(f"Processing URL... This may take a minute."):
            try:
                filepath, mime_type, filename = process_url(url, quality=selected_quality)

                # Save to session state
                st.session_state.download_ready = {
                    "path": filepath,
                    "mime": mime_type,
                    "name": filename
                }
                st.success("✅ File processed successfully! Click below to download.")

            except Exception as e:
                st.error(f"Failed to process URL: {str(e)}")
                st.session_state.download_ready = None

# Show download button if data is ready
if st.session_state.download_ready:
    file_info = st.session_state.download_ready

    try:
        with open(file_info["path"], "rb") as file_data:
            st.download_button(
                label=f"⬇️ Download {file_info['name']}",
                data=file_data,
                file_name=file_info["name"],
                mime=file_info["mime"]
            )
    except FileNotFoundError:
        st.error("Temporary file was lost. Please process the URL again.")
        st.session_state.download_ready = None