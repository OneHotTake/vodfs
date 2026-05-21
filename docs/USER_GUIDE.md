# VOD HTTP Filesystem Plugin - User Guide

## Overview

The VOD HTTP Filesystem plugin exposes your Dispatcharr VOD library as a mountable HTTP filesystem. This allows Plex to scan and stream content from multiple providers through a unified virtual filesystem.

## Features

- **Virtual filesystem** - Movies and Series appear as directories with subcategories
- **All directories** - `/Movies/All` and `/Series/All` contain all content
- **Category browsing** - Content organized by genre (Action, Comedy, Drama, etc.)
- **Multi-stream support** - Multiple providers appear as separate files
- **Episode hydration** - Series episodes fetched on-demand when browsing
- **302 redirects** - Playback streams directly from Dispatcharr proxy URLs
- **Large library support** - Optimized for 10K+ items

## Installation

1. Place the plugin in your Dispatcharr plugins directory
2. Configure the plugin settings:
   - **HTTP Port**: Port for the HTTP filesystem server (default: 8888)
   - **Auto-hydrate Empty Series**: Fetch episodes when browsing Series directories (default: true)

## rclone Mount

### Configuration

Add this to your rclone config file:

```ini
[vodfs]
type = http
url = http://127.0.0.1:8888/
```

### Mount Command

```bash
rclone mount vodfs: /path/to/mount --allow-other --read-only
```

### Plex Library Setup

1. Point Plex to the rclone mount directory
2. Set library type to "Movies" or "TV Shows"
3. Plex will scan `/Movies/All` for all movies
4. Plex will scan `/Movies/Action`, `/Movies/Comedy`, etc. for categories

## Filesystem Structure

```
/
├── Movies/
│   ├── All/                    # All movies
│   ├── Action/                 # Action movies
│   ├── Comedy/                 # Comedy movies
│   ├── Drama/                  # Drama movies
│   └── ...                     # Other genres
└── Series/
    ├── All/                    # All series
    ├── Action/                 # Action series
    ├── Comedy/                 # Comedy series
    └── ...                     # Other genres
        └── Show Name/
            ├── S01/            # Season 1
            │   ├── S01E01 - Episode Title.mkv
            │   └── S01E02 - Episode Title.mkv
            └── S02/            # Season 2
                └── ...
```

## Multi-Stream Files

When multiple providers have the same content, each stream appears as a separate file:

```
Movies/All/
├── Inception (2010) - Provider1-12345.mkv
├── Inception (2010) - Provider2-67890.mkv
└── Inception (2010) - Provider3-54321.mkv
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.