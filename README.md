## Overview
Projekt Deezer 3.0 is a music discovery web application. An AI-based tool that isolates vocals and instrumentals from tracks. This project provides a deeper listening experience by allowing users to manipulate audio components separately.

## Requirements

* [Docker Desktop](https://www.docker.com/products/docker-desktop/)
* [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/duffelbagteesh/projekt-deezer3.0.git
   cd projekt-deezer3.0
   ```
2. Build and Start the containers:
   ```bash
   docker-compose up --build
   ```
3. Access the application:
Open your browser and navigate to `http://localhost:3000`.

## Usage
After the application is running, you can upload a song (with in the size limits), isolate the different musical components, and enjoy enhanced music through the web interface.
