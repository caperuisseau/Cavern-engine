# 🦇 Cavern Engine

A lightweight 2D game engine with a custom DSL (`.cave` files) and a built-in editor. Built with Python, Pygame, and PyQt6.

**Create 2D games without writing Python** — use the simple Cavern DSL and hit F5 to play!

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Engine](https://img.shields.io/badge/Engine-Pygame-orange?logo=python)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎮 **Custom DSL** | Write games in `.cave` files with a simple, readable syntax |
| 🖥️ **Built-in Editor** | Full IDE with syntax highlighting, autocompletion, and themes |
| 🎨 **Multiple Themes** | Tokyo Night, Monokai, GitHub Light, Dracula |
| 💡 **2D Lighting** | Dynamic lights with ambient lighting system |
| ✨ **Particle System** | Fire, explosions, continuous emitters |
| 📷 **Camera System** | Follow, zoom, shake effects |
| 🎵 **Audio Engine** | Music, sound effects, spatial audio, fade in/out |
| 🖼️ **Parallax Backgrounds** | Multi-layer scrolling backgrounds |
| 🎭 **Animated Sprites** | Spritesheet-based animations |
| ⚙️ **Physics** | Gravity, friction, velocity, forces |
| 🔲 **Shape Drawing** | Rectangles, circles, lines |
| 🎬 **Post-Processing** | Bloom, blur, grayscale effects |
| 🕹️ **Joystick Support** | Gamepad buttons, axes, and hats |
| 📁 **Asset Explorer** | Drag & drop images and sounds into your project |
| 🏗️ **PyInstaller Export** | Build standalone executables |

---

## 🚀 Installation

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
git clone https://github.com/caperuisseau/cavern-engine.git
cd cavern-engine
pip install pygame PyQt6
```

### Run the Editor

```bash
python editor.py
```

---

## 📖 Quick Start

Create a new `.cave` file in the editor and write your first game:

```
SCREEN 800 600
BACKGROUND 20 20 40

SPRITE hero "hero.png" AT 400 300
TEXT score "Score: 0" AT 10 10

WHEN UPDATE:
IF KEY RIGHT: MOVE hero 5 0
IF KEY LEFT: MOVE hero -5 0
IF KEY UP: MOVE hero 0 -5
IF KEY DOWN: MOVE hero 0 5
```

Press **F5** to run your game!

---

## 📘 DSL Reference

### Initialization (before `WHEN UPDATE:`)

| Command | Example |
|---|---|
| `SPRITE` | `SPRITE name "image.png" AT x y` |
| `ANIMATED_SPRITE` | `ANIMATED_SPRITE name "sheet.png" FRAMES w h count fps AT x y` |
| `TEXT` | `TEXT name "text" AT x y` |
| `BACKGROUND` | `BACKGROUND R G B` |
| `MUSIC` | `MUSIC "file.mp3"` |
| `VAR` | `VAR score = 0` |
| `CONST` | `CONST SPEED = 5` |
| `LIGHT` | `LIGHT name AT x y RADIUS r COLOR r g b` |
| `AMBIENT` | `AMBIENT R G B` |
| `PARALLAX` | `PARALLAX "bg.png" speed_factor` |
| `GROUP` | `GROUP enemies` |
| `DRAW_RECT` | `DRAW_RECT name x y w h COLOR r g b` |
| `DRAW_CIRCLE` | `DRAW_CIRCLE name x y radius COLOR r g b` |
| `DRAW_LINE` | `DRAW_LINE name x1 y1 x2 y2 COLOR r g b` |
| `PHYSICS` | `PHYSICS obj GRAVITY g FRICTION f` |
| `CAMERA FOLLOW` | `CAMERA FOLLOW obj` |
| `CAMERA ZOOM` | `CAMERA ZOOM z` |
| `SCREEN` | `SCREEN 800 600` |
| `TICKRATE` | `TICKRATE 60` |
| `FUNCTION` | `FUNCTION name(args): ... END` |
| `IMPORT` | `IMPORT "other_file.cave"` |

### Game Loop (`WHEN UPDATE:`)

| Command | Example |
|---|---|
| `IF KEY` | `IF KEY SPACE: MOVE hero 0 -10` |
| `IF MOUSE CLICK:` | `IF MOUSE CLICK: PLAY_SOUND "click.wav"` |
| `ON_COLLIDE` | `ON_COLLIDE hero enemy: DESTROY enemy` |
| `ON_COLLIDE_GROUP` | `ON_COLLIDE_GROUP hero enemies: DESTROY hit` |
| `IF / ELIF / ELSE` | `IF score > 10: SET_COLOR txt 0 255 0` |
| `FOR / WHILE` | `FOR i IN RANGE(10): ...` |

### Actions

| Command | Description |
|---|---|
| `MOVE obj dx dy` | Move relative |
| `GOTO obj x y` | Move absolute |
| `SCALE obj factor` | Resize |
| `SIZE obj w h` | Set exact size |
| `ROTATE obj angle` | Set rotation |
| `ALPHA obj value` | Set transparency |
| `CENTER obj` | Center anchor point |
| `SHOW / HIDE obj` | Toggle visibility |
| `DESTROY obj` | Remove from engine |
| `SET var = value` | Update variable |
| `UPDATE_TEXT obj value` | Change text content |
| `VELOCITY obj vx vy` | Set velocity |
| `FORCE obj fx fy` | Apply force |
| `LERP_TO obj x y t` | Smooth movement |
| `SHAKE intensity duration` | Camera shake |
| `SPAWN_PARTICLES x y r g b count` | Burst particles |
| `CAMERA_FOLLOW obj` | Camera follow |
| `CAMERA_ZOOM z` | Camera zoom |
| `CAMERA_SHAKE i d` | Camera shake |
| `ADD_TO_GROUP group obj` | Add to group |
| `PLAY_SOUND "file"` | Play sound |
| `SPATIAL_SOUND "file" sx sy lx ly` | 3D audio |
| `FADE_OUT_MUSIC ms` | Fade out |
| `FADE_IN_MUSIC "file" ms` | Fade in |
| `STOP_MUSIC / PAUSE_MUSIC / RESUME_MUSIC` | Music controls |
| `BLOOM / BLUR / GRAYSCALE / NO_EFFECTS` | Post-processing |
| `FONT_SIZE obj size` | Change font size |
| `PLAY_ANIM / PAUSE_ANIM obj` | Animation control |
| `SET_FRAME obj n` | Set animation frame |

### Math & System Variables

| Symbol | Description |
|---|---|
| `SIN, COS, TAN, ABS, SQRT, FLOOR, CEIL` | Math functions |
| `CLAMP(x, lo, hi)` | Clamp value |
| `LERP(a, b, t)` | Linear interpolation |
| `DISTANCE(x1, y1, x2, y2)` | Distance between points |
| `ANGLE(x1, y1, x2, y2)` | Angle between points |
| `RANDINT(a, b)` | Random integer |
| `RANDF(a, b)` | Random float |
| `MOUSE_X, MOUSE_Y` | Mouse position |
| `TIME` | Elapsed time (seconds) |
| `SCREEN_WIDTH, SCREEN_HEIGHT` | Screen dimensions |
| `FPS` | Current framerate |

---

## ⌨️ Editor Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New file |
| `Ctrl+S` | Save |
| `Ctrl+Space` | Autocomplete |
| `Ctrl+Shift+F` | Auto-format |
| `F5` | Run game |
| `F6` | Build executable |
| `F3` | Toggle hitbox debug (in-game) |

---

## 🎨 Themes

The editor ships with 4 themes accessible via **View → Thème**:
- **Tokyo Night** (default)
- **Monokai**
- **GitHub Light**
- **Dracula**

---

## 📄 License

MIT License — Copyright (c) 2026 caperuisseau

See [LICENSE](LICENSE) for details.
