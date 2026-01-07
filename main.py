import customtkinter
import threading
import subprocess
import json
import os

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader")
        self.geometry("800x600")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- State ---
        self.download_process = None
        self.is_stopping = False
        self.video_checkboxes = []

        # --- Widgets ---
        # URL Frame
        self.url_frame = customtkinter.CTkFrame(self)
        self.url_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.url_frame.grid_columnconfigure(0, weight=1)

        self.url_entry = customtkinter.CTkEntry(self.url_frame, placeholder_text="Enter YouTube URL (video or playlist)")
        self.url_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.fetch_button = customtkinter.CTkButton(self.url_frame, text="Fetch Videos", command=self.on_fetch_videos)
        self.fetch_button.grid(row=0, column=1, padx=10, pady=10)

        # Controls Frame
        self.controls_frame = customtkinter.CTkFrame(self)
        self.controls_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.format_label = customtkinter.CTkLabel(self.controls_frame, text="Format:")
        self.format_label.grid(row=0, column=0, padx=10, pady=10)
        
        self.format_menu = customtkinter.CTkOptionMenu(self.controls_frame, values=["mp4", "mp3"])
        self.format_menu.grid(row=0, column=1, padx=10, pady=10)

        self.download_button = customtkinter.CTkButton(self.controls_frame, text="Download Selected", command=self.on_download_selected)
        self.download_button.grid(row=0, column=2, padx=10, pady=10)

        self.stop_button = customtkinter.CTkButton(self.controls_frame, text="Stop Download", command=self.on_stop_download, state="disabled")
        self.stop_button.grid(row=0, column=3, padx=10, pady=10)

        # Video List Frame
        self.video_list_frame = customtkinter.CTkScrollableFrame(self, label_text="Videos")
        self.video_list_frame.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # Status Frame
        self.status_textbox = customtkinter.CTkTextbox(self, height=100)
        self.status_textbox.grid(row=3, column=0, padx=10, pady=10, sticky="ew")

    def log(self, message):
        self.status_textbox.insert("end", message + "\n")
        self.status_textbox.see("end")

    def clear_video_list(self):
        for checkbox in self.video_checkboxes:
            checkbox.destroy()
        self.video_checkboxes.clear()

    def on_fetch_videos(self):
        url = self.url_entry.get()
        if not url:
            self.log("Please enter a URL.")
            return
        
        self.log(f"Fetching videos from: {url}...")
        self.fetch_button.configure(state="disabled")
        self.clear_video_list()
        
        thread = threading.Thread(target=self._fetch_videos_thread, args=(url,))
        thread.start()

    def _fetch_videos_thread(self, url):
        try:
            command = [
                'yt-dlp',
                '--dump-json',
                '-i', # ignore errors
                '--flat-playlist',
                url
            ]
            process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=True)
            
            videos = []
            for line in process.stdout.strip().split('\n'):
                videos.append(json.loads(line))

            self.after(0, self._populate_video_list, videos)

        except subprocess.CalledProcessError as e:
            self.after(0, self.log, f"Error fetching videos: {e.stderr}")
        except Exception as e:
            self.after(0, self.log, f"An unexpected error occurred: {e}")
        finally:
            self.after(0, self.fetch_button.configure, {"state": "normal"})

    def _populate_video_list(self, videos):
        if not videos:
            self.log("No videos found at the URL.")
            return

        self.log(f"Found {len(videos)} videos.")
        for i, video_info in enumerate(videos):
            title = video_info.get('title', 'Untitled')
            video_id = video_info.get('id')
            checkbox = customtkinter.CTkCheckBox(self.video_list_frame, text=title)
            checkbox.grid(row=i, column=0, padx=10, pady=5, sticky="w")
            checkbox.select() # Select by default
            self.video_checkboxes.append((checkbox, video_id))

    def on_download_selected(self):
        selected_videos = [video_id for checkbox, video_id in self.video_checkboxes if checkbox.get() == 1]
        
        if not selected_videos:
            self.log("No videos selected for download.")
            return

        download_format = self.format_menu.get()
        
        self.download_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.is_stopping = False

        thread = threading.Thread(target=self._download_thread, args=(selected_videos, download_format))
        thread.start()

    def _download_thread(self, video_ids, download_format):
        self.log(f"Starting download of {len(video_ids)} videos in '{download_format}' format...")
        
        # Create downloads directory if it doesn't exist
        download_dir = "downloads"
        os.makedirs(download_dir, exist_ok=True)
        
        for i, video_id in enumerate(video_ids):
            if self.is_stopping:
                self.log("Download process stopped by user.")
                break

            self.log(f"Downloading video {i+1}/{len(video_ids)} (ID: {video_id})...")
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            if download_format == 'mp3':
                command = [
                    'yt-dlp',
                    '-x',  # Extract audio
                    '--audio-format', 'mp3',
                    '--output', os.path.join(download_dir, '%(title)s.%(ext)s'),
                    url
                ]
            else: # mp4
                command = [
                    'yt-dlp',
                    '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    '--output', os.path.join(download_dir, '%(title)s.%(ext)s'),
                    url
                ]

            try:
                self.download_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
                
                for line in iter(self.download_process.stdout.readline, ''):
                    if self.is_stopping:
                        break
                    self.log(line.strip())
                
                self.download_process.wait()
                if self.is_stopping:
                    self.log(f"Stopped download for video ID: {video_id}")
                elif self.download_process.returncode == 0:
                    self.log(f"Successfully downloaded video ID: {video_id}")
                else:
                    self.log(f"Error downloading video ID: {video_id}. yt-dlp exited with code {self.download_process.returncode}")

            except Exception as e:
                self.log(f"An error occurred during download: {e}")
            
            self.download_process = None
        
        self.log("Download process finished.")
        self.after(0, self.reset_ui_after_download)

    def on_stop_download(self):
        if self.download_process:
            self.log("Stopping download...")
            self.is_stopping = True
            # The download thread will handle the termination
            self.download_process.terminate()
        else:
            self.log("No active download to stop.")
        
        self.stop_button.configure(state="disabled")

    def reset_ui_after_download(self):
        self.download_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.is_stopping = False


if __name__ == "__main__":
    app = App()
    app.mainloop()
