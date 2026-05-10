# Cavern Engine - 2D Game Engine & Editor
# Copyright (c) 2026 caperuisseau
# Licensed under the MIT License

import sys, os, subprocess, re, math, time, struct, random
from pathlib import Path
import urllib.request, urllib.parse, json

import pygame
import pygame.gfxdraw

from PyQt6.QtCore import Qt, QSize, QRegularExpression, QRect, QThread, pyqtSignal, QProcess, QTimer, QMimeData, QUrl, QStringListModel
from PyQt6.QtGui import (
    QColor, QFont, QTextCharFormat, QSyntaxHighlighter,
    QKeySequence, QPainter, QAction, QShortcut, QFileSystemModel, QPixmap, QIcon, QDragEnterEvent, QDropEvent
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTextEdit, QStatusBar, QLabel, QPlainTextEdit,
    QWidget, QMessageBox, QLineEdit, QSplitter, QTreeView,
    QStyleFactory, QFrame, QPushButton, QDialog, QCompleter, QMenu, QInputDialog,
    QListWidget, QListWidgetItem, QComboBox, QCheckBox, QSlider, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout, QGroupBox,
    QScrollArea
)

CAVERN_VERSION = "2026.3"

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

MAX_COLOR_VALUE = 255
COLOR_VARIATION = 30
PARTICLE_SPEED_MIN_FACTOR = 0.5
PARTICLE_SPEED_MAX_FACTOR = 1.5
PARTICLE_LIFE_MIN_FACTOR = 0.5
PARTICLE_LIFE_MAX_FACTOR = 1.2
PARTICLE_EMIT_RATE = 0.05
CACHE_SIZE_LIMIT = 1000

_IMAGE_CACHE = {}

def _load_image_cached(path):
    if path in _IMAGE_CACHE:
        return _IMAGE_CACHE[path]
    img = pygame.image.load(path).convert_alpha()
    _IMAGE_CACHE[path] = img
    return img

class Camera:
    def __init__(self, width, height):
        self.x = 0
        self.y = 0
        self.target = None
        self.zoom = 1.0
        self.shake_intensity = 0
        self.shake_duration = 0
        self.shake_timer = 0
        self.width = width
        self.height = height
        self.lerp_speed = 0.1

    def follow(self, sprite):
        self.target = sprite

    def set_zoom(self, z):
        self.zoom = max(0.1, float(z))

    def shake(self, intensity, duration):
        self.shake_intensity = float(intensity)
        self.shake_duration = float(duration)
        self.shake_timer = 0

    def update(self, dt):
        if self.target:
            target_x = self.target.x - self.width / (2 * self.zoom)
            target_y = self.target.y - self.height / (2 * self.zoom)
            self.x += (target_x - self.x) * self.lerp_speed
            self.y += (target_y - self.y) * self.lerp_speed

        offset_x, offset_y = 0, 0
        if self.shake_timer < self.shake_duration:
            self.shake_timer += dt
            intensity = self.shake_intensity * (1 - self.shake_timer / self.shake_duration)
            offset_x = random.uniform(-intensity, intensity)
            offset_y = random.uniform(-intensity, intensity)

        return self.x + offset_x, self.y + offset_y

    def apply(self, x, y):
        return (x - self.x) * self.zoom, (y - self.y) * self.zoom

class ParticleEmitter:
    def __init__(
        self, x, y, ptype="fire", color=(255, 200, 50), speed=100,
        count=20, spread=360, life=1.0, gravity=0, size=3
    ):
        self.x = float(x)
        self.y = float(y)
        self.ptype = ptype
        self.color = color
        self.speed = float(speed)
        self.count = int(count)
        self.spread = float(spread)
        self.life = float(life)
        self.gravity = float(gravity)
        self.size = float(size)
        
        self.particles = []
        self.active = True
        self.continuous = False
        self.emit_timer = 0
        self.emit_rate = PARTICLE_EMIT_RATE

        if not hasattr(ParticleEmitter, '_surf_cache'):
            from collections import OrderedDict
            ParticleEmitter._surf_cache = OrderedDict()

    def _emit_particle(self):
        angle = math.radians(random.uniform(0, self.spread))
        spd = self.speed * random.uniform(PARTICLE_SPEED_MIN_FACTOR, PARTICLE_SPEED_MAX_FACTOR)
        vx = math.cos(angle) * spd
        vy = -math.sin(angle) * spd
        color_var = random.randint(-COLOR_VARIATION, COLOR_VARIATION)
        r = max(0, min(MAX_COLOR_VALUE, self.color[0] + color_var))
        g = max(0, min(MAX_COLOR_VALUE, self.color[1] + color_var))
        b = max(0, min(MAX_COLOR_VALUE, self.color[2] + color_var))
        max_life = self.life * random.uniform(PARTICLE_LIFE_MIN_FACTOR, PARTICLE_LIFE_MAX_FACTOR)
        self.particles.append([self.x, self.y, vx, vy, max_life, max_life, r, g, b, self.size])

    def burst(self):
        for _ in range(self.count):
            self._emit_particle()

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def update(self, dt):
        if self.continuous and self.active:
            self.emit_timer += dt
            while self.emit_timer >= self.emit_rate:
                self.emit_timer -= self.emit_rate
                self._emit_particle()

        i = 0
        while i < len(self.particles):
            p = self.particles[i]
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += self.gravity * dt
            p[4] -= dt
            if p[4] <= 0:
                self.particles.pop(i)
            else:
                i += 1

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        sw, sh = screen.get_width(), screen.get_height()
        cache = ParticleEmitter._surf_cache
        blit = screen.blit

        for p in self.particles:
            life_ratio = p[4] / p[5] if p[5] > 0 else 0
            alpha = max(0, min(MAX_COLOR_VALUE, int(MAX_COLOR_VALUE * life_ratio)))
            sx = int((p[0] - cam_x) * zoom)
            sy = int((p[1] - cam_y) * zoom)
            sz = max(1, int(p[9] * zoom * life_ratio))

            if -sz <= sx < sw + sz and -sz <= sy < sh + sz:
                cache_key = (sz, p[6], p[7], p[8], alpha)
                surf = cache.get(cache_key)
                if surf is None:
                    if len(cache) >= CACHE_SIZE_LIMIT:
                        cache.popitem(last=False)
                    surf = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                    pygame.draw.circle(surf, (p[6], p[7], p[8], alpha), (sz, sz), sz)
                    cache[cache_key] = surf
                else:
                    cache.move_to_end(cache_key)
                blit(surf, (sx - sz, sy - sz))

class Light:
    _gradient_cache = {}

    def __init__(self, x, y, radius=150, color=(255, 255, 200), intensity=200):
        self.x = float(x)
        self.y = float(y)
        self.radius = float(radius)
        self.color = color
        self.intensity = int(intensity)
        self.visible = True
        self.flicker = False
        self.flicker_amount = 10

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    @classmethod
    def _get_gradient(cls, r, color, intensity):
        key = (r, color[0], color[1], color[2], intensity)
        surf = cls._gradient_cache.get(key)
        if surf is not None:
            return surf
        if len(cls._gradient_cache) > 256:
            cls._gradient_cache.clear()
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        cr, cg, cb = color[0], color[1], color[2]
        for i in range(r, 0, -2):
            alpha = max(0, min(255, int(intensity * (i / r))))
            pygame.draw.circle(surf, (cr, cg, cb, alpha), (r, r), i)
        cls._gradient_cache[key] = surf
        return surf

    def draw(self, light_surface, cam_x=0, cam_y=0, zoom=1.0):
        if not self.visible:
            return
        sx = int((self.x - cam_x) * zoom)
        sy = int((self.y - cam_y) * zoom)
        r = int(self.radius * zoom)
        if self.flicker:
            r += random.randint(-int(self.flicker_amount), int(self.flicker_amount))
        if r <= 0:
            return
        sw, sh = light_surface.get_width(), light_surface.get_height()
        if sx + r < 0 or sy + r < 0 or sx - r > sw or sy - r > sh:
            return
        light_surf = Light._get_gradient(r, self.color, self.intensity)
        light_surface.blit(light_surf, (sx - r, sy - r), special_flags=pygame.BLEND_RGBA_ADD)

class ParallaxLayer:
    def __init__(self, image_path, speed_factor=0.5):
        self.speed_factor = float(speed_factor)
        try:
            self.image = _load_image_cached(image_path)
        except Exception:
            self.image = pygame.Surface((800, 600), pygame.SRCALPHA)
            self.image.fill((40, 40, 60, 100))
        self.offset_x = 0
        self.offset_y = 0

    def draw(self, screen, cam_x=0, cam_y=0):
        w = self.image.get_width()
        h = self.image.get_height()
        ox = int(-cam_x * self.speed_factor) % w
        oy = int(-cam_y * self.speed_factor) % h
        for x_tile in range(-1, (screen.get_width() // w) + 2):
            for y_tile in range(-1, (screen.get_height() // h) + 2):
                screen.blit(self.image, (x_tile * w + ox, y_tile * h + oy))

class Shape:
    def __init__(self, shape_type, x, y, w, h, color=(255, 255, 255), filled=True):
        self.shape_type = shape_type
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)
        self.color = color
        self.filled = filled
        self.visible = True
        self.line_width = 2
        self.alpha = 255
        self.rect = pygame.Rect(int(x), int(y), int(w), int(h))

    def update_rect(self):
        self.rect = pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        self.update_rect()

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)
        self.update_rect()

    def hide(self): self.visible = False
    def show(self): self.visible = True

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if not self.visible:
            return
        sx = int((self.x - cam_x) * zoom)
        sy = int((self.y - cam_y) * zoom)
        sw = int(self.w * zoom)
        sh = int(self.h * zoom)

        if self.alpha < 255:
            surf = pygame.Surface((abs(sw) + 4, abs(sh) + 4), pygame.SRCALPHA)
            offset = (2, 2)
        else:
            surf = screen
            offset = (sx, sy)

        col = self.color[:3]
        if self.shape_type == "rect":
            if self.filled:
                pygame.draw.rect(surf, col, pygame.Rect(offset[0] if self.alpha < 255 else sx, offset[1] if self.alpha < 255 else sy, sw, sh))
            else:
                pygame.draw.rect(surf, col, pygame.Rect(offset[0] if self.alpha < 255 else sx, offset[1] if self.alpha < 255 else sy, sw, sh), self.line_width)
        elif self.shape_type == "circle":
            r = max(1, sw // 2)
            cx = (offset[0] + r) if self.alpha < 255 else (sx + r)
            cy = (offset[1] + sh // 2) if self.alpha < 255 else (sy + sh // 2)
            if self.filled:
                pygame.draw.circle(surf, col, (cx, cy), r)
            else:
                pygame.draw.circle(surf, col, (cx, cy), r, self.line_width)
        elif self.shape_type == "line":
            ex = int((self.w - cam_x) * zoom)
            ey = int((self.h - cam_y) * zoom)
            pygame.draw.line(surf if self.alpha >= 255 else surf, col,
                             (offset[0], offset[1]) if self.alpha < 255 else (sx, sy),
                             (ex - sx + offset[0], ey - sy + offset[1]) if self.alpha < 255 else (ex, ey),
                             self.line_width)

        if self.alpha < 255:
            surf.set_alpha(self.alpha)
            screen.blit(surf, (sx - 2, sy - 2))

class AnimatedSprite:
    def __init__(self, sheet_path, x, y, frame_w, frame_h, frame_count, fps=10):
        self.x = float(x)
        self.y = float(y)
        self.visible = True
        self.angle = 0
        self.alpha = 255
        self.is_centered = False
        self.frame_w = int(frame_w)
        self.frame_h = int(frame_h)
        self.frame_count = int(frame_count)
        self.anim_fps = float(fps)
        self.current_frame = 0
        self.anim_timer = 0
        self.playing = True
        self.loop = True
        self.scale_factor = 1.0
        self.frames = []

        try:
            sheet = _load_image_cached(sheet_path)
            cols = sheet.get_width() // self.frame_w
            for i in range(self.frame_count):
                col = i % cols
                row = i // cols
                frame = sheet.subsurface(pygame.Rect(col * self.frame_w, row * self.frame_h, self.frame_w, self.frame_h))
                self.frames.append(frame)
        except Exception:
            fallback = pygame.Surface((self.frame_w, self.frame_h), pygame.SRCALPHA)
            fallback.fill((255, 0, 0, 255))
            self.frames = [fallback]
            self.frame_count = 1

        self.image = self.frames[0]
        self.original_image = self.image
        self.rect = self.image.get_rect(topleft=(int(self.x), int(self.y)))
        self._scaled_frames = None
        self._scaled_factor = 1.0

    def update_rect(self):
        if self.is_centered:
            self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
        else:
            self.rect = self.image.get_rect(topleft=(int(self.x), int(self.y)))

    def update(self, dt):
        if self.playing and self.frame_count > 1:
            self.anim_timer += dt
            frame_duration = 1.0 / self.anim_fps if self.anim_fps > 0 else 1.0
            if self.anim_timer >= frame_duration:
                self.anim_timer -= frame_duration
                self.current_frame += 1
                if self.current_frame >= self.frame_count:
                    if self.loop:
                        self.current_frame = 0
                    else:
                        self.current_frame = self.frame_count - 1
                        self.playing = False
                self.original_image = self.frames[self.current_frame]
                if self.scale_factor != 1.0:
                    if self._scaled_frames is None or self._scaled_factor != self.scale_factor:
                        w = int(self.frame_w * self.scale_factor)
                        h = int(self.frame_h * self.scale_factor)
                        self._scaled_frames = [pygame.transform.scale(f, (w, h)) for f in self.frames]
                        self._scaled_factor = self.scale_factor
                    self.image = self._scaled_frames[self.current_frame]
                else:
                    self.image = self.original_image
                self.update_rect()

    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        self.update_rect()

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)
        self.update_rect()

    def set_scale(self, factor):
        self.scale_factor = float(factor)
        if self.scale_factor == 1.0:
            self._scaled_frames = None
            self.image = self.original_image
        else:
            w = int(self.frame_w * self.scale_factor)
            h = int(self.frame_h * self.scale_factor)
            self._scaled_frames = [pygame.transform.scale(f, (w, h)) for f in self.frames]
            self._scaled_factor = self.scale_factor
            self.image = self._scaled_frames[self.current_frame]
        self.update_rect()

    def set_size(self, w, h):
        self.image = pygame.transform.scale(self.original_image, (int(w), int(h)))
        self.update_rect()

    def set_rotation(self, angle): self.angle = float(angle)
    def set_alpha(self, alpha): self.alpha = max(0, min(255, int(alpha)))
    def center(self): self.is_centered = True; self.update_rect()
    def hide(self): self.visible = False
    def show(self): self.visible = True
    def play(self): self.playing = True
    def pause(self): self.playing = False
    def set_frame(self, f):
        self.current_frame = max(0, min(int(f), self.frame_count - 1))
        self.original_image = self.frames[self.current_frame]
        if self.scale_factor != 1.0 and self._scaled_frames is not None:
            self.image = self._scaled_frames[self.current_frame]
        else:
            self.image = self.original_image
        self.update_rect()

    def _get_drawn_image(self, zoom):
        if not hasattr(self, '_cache_state'):
            self._cache_state = None
            self._cached_image = self.image

        current_state = (self.image, self.angle, zoom, self.alpha)
        if self._cache_state != current_state:
            temp_img = self.image
            if self.angle != 0:
                temp_img = pygame.transform.rotate(temp_img, self.angle)
            if zoom != 1.0:
                zw = int(temp_img.get_width() * zoom)
                zh = int(temp_img.get_height() * zoom)
                if zw > 0 and zh > 0:
                    temp_img = pygame.transform.scale(temp_img, (zw, zh))
            if self.alpha < 255:
                temp_img = temp_img.copy()
                temp_img.set_alpha(self.alpha)
                
            self._cached_image = temp_img
            self._cache_state = current_state
            
        return self._cached_image

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if self.visible:
            temp_img = self._get_drawn_image(zoom)
            if temp_img.get_width() <= 0 or temp_img.get_height() <= 0: return

            sx = (self.x - cam_x) * zoom
            sy = (self.y - cam_y) * zoom

            if self.angle != 0 or self.is_centered:
                draw_rect = temp_img.get_rect(center=(int(sx), int(sy)))
            else:
                draw_rect = temp_img.get_rect(topleft=(int(sx), int(sy)))
            screen.blit(temp_img, draw_rect)

class SpriteGroup:
    def __init__(self):
        self.members = []

    def add(self, sprite):
        if sprite not in self.members:
            self.members.append(sprite)

    def remove(self, sprite):
        if sprite in self.members:
            self.members.remove(sprite)

    def __iter__(self):
        return iter(self.members)

    def __len__(self):
        return len(self.members)

    def __getitem__(self, index):
        return self.members[index]

class Tileset:
    def __init__(self, image_path, tile_size=32):
        self.tile_size = int(tile_size)
        self.tiles = []
        try:
            sheet = _load_image_cached(image_path)
            cols = sheet.get_width() // self.tile_size
            rows = sheet.get_height() // self.tile_size
            for row in range(rows):
                for col in range(cols):
                    tile = sheet.subsurface(pygame.Rect(
                        col * self.tile_size, row * self.tile_size,
                        self.tile_size, self.tile_size
                    ))
                    self.tiles.append(tile)
        except Exception as e:
            print(f"Tileset error: {e}")
            fallback = pygame.Surface((self.tile_size, self.tile_size), pygame.SRCALPHA)
            fallback.fill((200, 0, 200, 255))
            self.tiles = [fallback]

    def get_tile(self, index):
        if 0 <= index < len(self.tiles):
            return self.tiles[index]
        return self.tiles[0] if self.tiles else None

class Tilemap:
    def __init__(self, tileset, data, x=0, y=0):
        self.tileset = tileset
        self.data = data
        self.x = float(x)
        self.y = float(y)
        self.tile_size = tileset.tile_size
        self.visible = True
        self._cache = {}

    def _iter_overlapping_tiles(self, sr):
        ts = self.tile_size
        if ts <= 0 or not self.data:
            return
        ox = int(self.x)
        oy = int(self.y)
        col_min = max(0, (sr.left - ox) // ts)
        col_max = (sr.right - ox) // ts
        row_min = max(0, (sr.top - oy) // ts)
        row_max = (sr.bottom - oy) // ts
        for row_idx in range(row_min, row_max + 1):
            if row_idx < 0 or row_idx >= len(self.data):
                continue
            row = self.data[row_idx]
            for col_idx in range(col_min, col_max + 1):
                if col_idx < 0 or col_idx >= len(row):
                    continue
                yield row_idx, col_idx, row[col_idx]

    def collides(self, sprite, solid_ids=None):
        """Returns True if the sprite collides with any solid tile."""
        sr = sprite.rect
        ts = self.tile_size
        ox = int(self.x)
        oy = int(self.y)
        solid_set = set(solid_ids) if solid_ids is not None else None
        for row_idx, col_idx, tile_id in self._iter_overlapping_tiles(sr):
            if solid_set is None:
                if tile_id <= 0:
                    continue
            elif tile_id not in solid_set:
                continue
            tile_rect = pygame.Rect(ox + col_idx * ts, oy + row_idx * ts, ts, ts)
            if sr.colliderect(tile_rect):
                return True
        return False

    def get_colliding_tile(self, sprite, solid_ids=None):
        sr = sprite.rect
        ts = self.tile_size
        ox = int(self.x)
        oy = int(self.y)
        solid_set = set(solid_ids) if solid_ids is not None else None
        for row_idx, col_idx, tile_id in self._iter_overlapping_tiles(sr):
            if solid_set is None:
                if tile_id <= 0:
                    continue
            elif tile_id not in solid_set:
                continue
            tile_rect = pygame.Rect(ox + col_idx * ts, oy + row_idx * ts, ts, ts)
            if sr.colliderect(tile_rect):
                return tile_rect
        return None

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if not self.visible:
            return
        ts = self.tile_size
        sw, sh = screen.get_width(), screen.get_height()
        for row_idx, row in enumerate(self.data):
            for col_idx, tile_id in enumerate(row):
                if tile_id <= 0:
                    continue
                wx = self.x + col_idx * ts
                wy = self.y + row_idx * ts
                sx = int((wx - cam_x) * zoom)
                sy = int((wy - cam_y) * zoom)
                if sx + ts * zoom < 0 or sy + ts * zoom < 0 or sx > sw or sy > sh:
                    continue
                tile_surf = self.tileset.get_tile(tile_id - 1)
                if tile_surf is None:
                    continue
                if zoom != 1.0:
                    zw = max(1, int(ts * zoom))
                    zh = max(1, int(ts * zoom))
                    cache_key = (tile_id, zw, zh)
                    if cache_key not in self._cache:
                        self._cache[cache_key] = pygame.transform.scale(tile_surf, (zw, zh))
                    screen.blit(self._cache[cache_key], (sx, sy))
                else:
                    screen.blit(tile_surf, (sx, sy))

class Button:
    def __init__(self, text, x, y, w=200, h=50,
                 color=(80, 130, 240), hover_color=(110, 160, 255),
                 text_color=(255, 255, 255), font_size=22):
        self.text = text
        self.x = float(x)
        self.y = float(y)
        self.w = int(w)
        self.h = int(h)
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.visible = True
        self.hovered = False
        self.clicked = False
        self._was_pressed = False
        self.rect = pygame.Rect(int(x), int(y), self.w, self.h)
        pygame.font.init()
        self.font = pygame.font.SysFont("Verdana", font_size, bold=True)
        self._surf = None
        self._hover_surf = None
        self._build_surfaces()

    def _build_surfaces(self):
        self._surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(self._surf, (*self.color, 255), (0, 0, self.w, self.h), border_radius=10)
        pygame.draw.rect(self._surf, (255, 255, 255, 40), (0, 0, self.w, self.h), 2, border_radius=10)
        txt = self.font.render(self.text, True, self.text_color)
        tr = txt.get_rect(center=(self.w // 2, self.h // 2))
        self._surf.blit(txt, tr)

        self._hover_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        pygame.draw.rect(self._hover_surf, (*self.hover_color, 255), (0, 0, self.w, self.h), border_radius=10)
        pygame.draw.rect(self._hover_surf, (255, 255, 255, 80), (0, 0, self.w, self.h), 2, border_radius=10)
        self._hover_surf.blit(txt, tr)

    def update_rect(self):
        self.rect = pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)
        self.update_rect()

    def update(self, events=None):
        mx, my = pygame.mouse.get_pos()
        self.hovered = self.rect.collidepoint(mx, my)
        pressed = pygame.mouse.get_pressed()[0]
        self.clicked = self.hovered and pressed and not self._was_pressed
        self._was_pressed = pressed and self.hovered

    def is_clicked(self):
        return self.clicked

    def hide(self): self.visible = False
    def show(self): self.visible = True

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if not self.visible:
            return
        sx = int((self.x - cam_x) * zoom)
        sy = int((self.y - cam_y) * zoom)
        surf = self._hover_surf if self.hovered else self._surf
        screen.blit(surf, (sx, sy))

class ProgressBar:
    def __init__(self, x, y, w=200, h=20, value=100, max_value=100,
                 color=(80, 200, 100), bg_color=(40, 40, 60), border_color=(255, 255, 255)):
        self.x = float(x)
        self.y = float(y)
        self.w = int(w)
        self.h = int(h)
        self.value = float(value)
        self.max_value = float(max_value)
        self.color = color
        self.bg_color = bg_color
        self.border_color = border_color
        self.visible = True
        self.rect = pygame.Rect(int(x), int(y), self.w, self.h)

    def set_value(self, v):
        self.value = max(0.0, min(float(v), self.max_value))

    def update_rect(self):
        self.rect = pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)
        self.update_rect()

    def hide(self): self.visible = False
    def show(self): self.visible = True

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if not self.visible:
            return
        sx = int((self.x - cam_x) * zoom)
        sy = int((self.y - cam_y) * zoom)
        sw = max(1, int(self.w * zoom))
        sh = max(1, int(self.h * zoom))
        ratio = max(0.0, min(1.0, self.value / self.max_value)) if self.max_value > 0 else 0.0
        pygame.draw.rect(screen, self.bg_color, (sx, sy, sw, sh), border_radius=5)
        if ratio > 0:
            fill_w = max(1, int(sw * ratio))
            pygame.draw.rect(screen, self.color, (sx, sy, fill_w, sh), border_radius=5)
        pygame.draw.rect(screen, self.border_color, (sx, sy, sw, sh), 2, border_radius=5)

class Sprite:
    def __init__(self, image_path, x, y):
        self.x = float(x)
        self.y = float(y)
        self.visible = True
        self.angle = 0
        self.alpha = 255
        self.is_centered = False
        self.vx = 0.0
        self.vy = 0.0
        self.gravity = 0.0
        self.friction = 1.0
        self.bounce = 0.0
        self.mass = 1.0
        self.physics_enabled = False
        try:
            self.original_image = _load_image_cached(image_path).copy()
            self.image = self.original_image
        except Exception:
            self.original_image = pygame.Surface((50, 50), pygame.SRCALPHA)
            self.original_image.fill((255, 0, 0, 255))
            self.image = self.original_image
        self.rect = self.image.get_rect()
        self.collision_radius = max(self.rect.width, self.rect.height) // 2
        self.update_rect()

    def update_rect(self):
        if self.is_centered:
            self.rect = self.image.get_rect(center=(int(self.x), int(self.y)))
        else:
            self.rect = self.image.get_rect(topleft=(int(self.x), int(self.y)))
        self.collision_radius = max(self.rect.width, self.rect.height) // 2

    def update_physics(self, dt):
        if not self.physics_enabled:
            return
        self.vy += self.gravity * dt
        self.vx *= self.friction
        self.vy *= self.friction
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.update_rect()

    def move(self, dx, dy):
        self.x += dx
        self.y += dy
        self.update_rect()

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)
        self.update_rect()

    def set_velocity(self, vx, vy):
        self.vx = float(vx)
        self.vy = float(vy)

    def apply_force(self, fx, fy):
        self.vx += fx / self.mass
        self.vy += fy / self.mass

    def set_scale(self, factor):
        f = float(factor)
        w = int(self.original_image.get_width() * f)
        h = int(self.original_image.get_height() * f)
        self.set_size(w, h)

    def set_size(self, w, h):
        self.image = pygame.transform.scale(self.original_image, (int(w), int(h)))
        self.update_rect()

    def set_chroma(self, r, g, b):
        curr_w, curr_h = self.image.get_width(), self.image.get_height()
        self.original_image = self.original_image.convert()
        self.original_image.set_colorkey((int(r), int(g), int(b)))
        self.set_size(curr_w, curr_h)

    def set_rotation(self, angle):
        self.angle = float(angle)

    def set_alpha(self, alpha):
        self.alpha = max(0, min(255, int(alpha)))

    def center(self):
        self.is_centered = True
        self.update_rect()

    def hide(self): self.visible = False
    def show(self): self.visible = True

    def distance_to(self, other):
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def angle_to(self, other):
        return math.degrees(math.atan2(other.y - self.y, other.x - self.x))

    def lerp_to(self, target_x, target_y, t):
        t = max(0, min(1, float(t)))
        self.x += (float(target_x) - self.x) * t
        self.y += (float(target_y) - self.y) * t
        self.update_rect()

    def collides_circle(self, other):
        dist = math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)
        return dist < (self.collision_radius + other.collision_radius)

    def _get_drawn_image(self, zoom):
        if not hasattr(self, '_cache_state'):
            self._cache_state = None
            self._cached_image = self.image

        current_state = (self.image, self.angle, zoom, self.alpha)
        if self._cache_state != current_state:
            temp_img = self.image
            if self.angle != 0:
                temp_img = pygame.transform.rotate(temp_img, self.angle)
            if zoom != 1.0:
                zw = int(temp_img.get_width() * zoom)
                zh = int(temp_img.get_height() * zoom)
                if zw > 0 and zh > 0:
                    temp_img = pygame.transform.scale(temp_img, (zw, zh))
            if self.alpha < 255:
                temp_img = temp_img.copy()
                temp_img.set_alpha(self.alpha)
                
            self._cached_image = temp_img
            self._cache_state = current_state
            
        return self._cached_image

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if self.visible:
            temp_img = self._get_drawn_image(zoom)
            if temp_img.get_width() <= 0 or temp_img.get_height() <= 0: return

            sx = (self.x - cam_x) * zoom
            sy = (self.y - cam_y) * zoom

            if self.is_centered:
                draw_rect = temp_img.get_rect(center=(int(sx), int(sy)))
            else:
                draw_rect = temp_img.get_rect(topleft=(int(sx), int(sy)))

            screen.blit(temp_img, draw_rect)

class Text(Sprite):
    def __init__(self, text, x, y):
        super().__init__("", x, y)
        pygame.font.init()
        self.font = pygame.font.SysFont("Verdana", 24, bold=True)
        self.raw_text = text
        self.color = (255, 255, 255)
        self.scale_factor = 1.0
        self.update_image()

    def update_image(self):
        self.original_image = self.font.render(self.raw_text, True, self.color)
        self.set_scale(self.scale_factor)

    def set_color(self, r, g, b):
        self.color = (int(r), int(g), int(b))
        self.update_image()

    def set_font_size(self, size):
        self.font = pygame.font.SysFont("Verdana", int(size), bold=True)
        self.update_image()

    def set_scale(self, factor):
        self.scale_factor = float(factor)
        super().set_scale(factor)

class MiniEngine:
    _pending_scene = None  # Class-level flag for LOAD_SCENE
    def __init__(self, width=800, height=600):
        self.splash_duration = 3000  # ms
        
        pygame.init()
        pygame.mixer.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Cavern Engine")
        self.clock = pygame.time.Clock()
        self.sprites = []
        self.update_func = None
        self.bg_color = (30, 30, 30)
        self.sounds = {}
        self.fps = 60

        self.camera = Camera(width, height)
        self.particles = []
        self.lights = []
        self.parallax_layers = []
        self.shapes = []
        self.sprite_groups = {}
        self.ambient_light = (30, 30, 40)
        self.use_lighting = False
        self.debug_hitbox = False

        self.bloom_enabled = False
        self.bloom_intensity = 1.5
        self.blur_enabled = False
        self.grayscale_enabled = False
        self.crt_enabled = False
        self.crt_intensity = 0.5
        self.glitch_enabled = False
        self.glitch_intensity = 0.3
        self.glitch_timer = 0.0

        self.tilesets = {}
        self.tilemaps = {}
        self.buttons = []
        self.progress_bars = []

        self.sound_volume = 1.0
        self.music_volume = 1.0
        pygame.mixer.set_num_channels(16)

        self.joysticks = []
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            j = pygame.joystick.Joystick(i)
            j.init()
            self.joysticks.append(j)

        self.wait_timers = []
        self.every_timers = []
        
        self.scenes = {}
        self.current_scene = None

        self.watched_vars = {}
        
        self.fade_alpha = 0
        self.fade_target = 0
        self.fade_speed = 0
        
        self.dialog_active = False
        self.dialog_speaker = ""
        self.dialog_text = ""
        self.dialog_visible_chars = 0
        self.dialog_timer = 0
        self.dialog_speed = 0.05
        pygame.font.init()
        self.dialog_font = pygame.font.SysFont("Verdana", 20, bold=True)
        self.dialog_body_font = pygame.font.SysFont("Verdana", 18)

        self._light_surface = None
        self._fade_surface = None
        self._scanline_surface = None
        self._scanline_intensity_cached = -1.0

    def set_fps(self, fps):
        self.fps = int(fps)

    def set_bg(self, r, g, b):
        self.bg_color = (int(r), int(g), int(b))

    def set_screen_size(self, w, h):
        self.width = int(w)
        self.height = int(h)
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.camera.width = self.width
        self.camera.height = self.height

    def set_window_title(self, title):
        pygame.display.set_caption(title)

    def set_window_icon(self, icon_path):
        try:
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)
        except Exception as e:
            print(f"Erreur chargement icône: {e}")

    def add_sprite(self, sprite):
        self.sprites.append(sprite)

    def destroy(self, sprite):
        if sprite in self.sprites:
            self.sprites.remove(sprite)
        for g in self.sprite_groups.values():
            g.remove(sprite)
            
    def kill(self, sprite):
        self.destroy(sprite)

    def create_group(self, name):
        self.sprite_groups[name] = SpriteGroup()
        return self.sprite_groups[name]

    def add_to_group(self, name, sprite):
        if name not in self.sprite_groups:
            self.create_group(name)
        self.sprite_groups[name].add(sprite)

    def get_group(self, name):
        return self.sprite_groups.get(name, SpriteGroup())

    def on_collide_group(self, sprite, group_name):
        group = self.sprite_groups.get(group_name, SpriteGroup())
        for member in group:
            if member in self.sprites and sprite.rect.colliderect(member.rect):
                return member
        return None

    def play_sound(self, path, volume=1.0):
        if path not in self.sounds:
            try:
                self.sounds[path] = pygame.mixer.Sound(path)
            except Exception as e:
                print(f"Musique/Son introuvable : {path} - {e}")
                return
        snd = self.sounds[path]
        snd.set_volume(float(volume) * self.sound_volume)
        snd.play()

    def play_music(self, path, loops=-1):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(int(loops))
        except Exception as e:
            print(f"Musique introuvable : {path} - {e}")

    def stop_music(self):
        pygame.mixer.music.stop()

    def pause_music(self):
        pygame.mixer.music.pause()

    def resume_music(self):
        pygame.mixer.music.unpause()

    def set_sound_volume(self, vol):
        self.sound_volume = max(0, min(1, float(vol)))

    def set_music_volume(self, vol):
        self.music_volume = max(0, min(1, float(vol)))
        pygame.mixer.music.set_volume(self.music_volume)

    def fade_out_music(self, ms=1000):
        pygame.mixer.music.fadeout(int(ms))

    def fade_in_music(self, path, ms=1000):
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1, fade_ms=int(ms))
        except Exception as e:
            print(f"Musique introuvable : {path} - {e}")

    def set_sound_pitch(self, path, pitch):
        pass

    def spatial_sound(self, path, source_x, source_y, listener_x, listener_y, max_dist=500):
        dist = math.sqrt((source_x - listener_x) ** 2 + (source_y - listener_y) ** 2)
        volume = max(0, 1.0 - dist / float(max_dist))
        if volume > 0:
            self.play_sound(path, volume)

    def on_collide(self, obj1, obj2):
        if obj1 in self.sprites and obj2 in self.sprites:
            return obj1.rect.colliderect(obj2.rect)
        return False

    def on_collide_circle(self, obj1, obj2):
        if obj1 in self.sprites and obj2 in self.sprites:
            return obj1.collides_circle(obj2)
        return False

    def camera_follow(self, sprite):
        self.camera.follow(sprite)

    def camera_zoom(self, z):
        self.camera.set_zoom(z)

    def camera_shake(self, intensity, duration):
        self.camera.shake(intensity, duration)

    def add_particles(self, emitter):
        self.particles.append(emitter)

    def spawn_particles(
        self, x, y, ptype="fire", color=(255, 200, 50), count=20,
        speed=100, life=1.0, gravity=0, size=3
    ):
        em = ParticleEmitter(x, y, ptype, color, speed, count, 360, life, gravity, size)
        em.burst()
        self.particles.append(em)
        return em

    def set_splash_duration(self, ms):
        self.splash_duration = int(ms)

    def create_tileset(self, name, image_path, tile_size=32):
        ts = Tileset(image_path, tile_size)
        self.tilesets[name] = ts
        return ts

    def create_tilemap(self, name, tileset_name, data, x=0, y=0):
        ts = self.tilesets.get(tileset_name)
        if ts is None:
            print(f"Tileset '{tileset_name}' introuvable.")
            return None
        tm = Tilemap(ts, data, x, y)
        self.tilemaps[name] = tm
        return tm

    def tilemap_collide(self, sprite, tilemap_name):
        tm = self.tilemaps.get(tilemap_name)
        if tm is None:
            return False
        return tm.collides(sprite)

    def create_button(self, name, text, x, y, w=200, h=50):
        btn = Button(text, x, y, w, h)
        self.buttons.append((name, btn))
        return btn

    def create_progress_bar(self, name, x, y, w=200, h=20, value=100, max_val=100):
        pb = ProgressBar(x, y, w, h, value, max_val)
        self.progress_bars.append((name, pb))
        return pb

    def load_scene(self, cave_path):
        MiniEngine._pending_scene = cave_path

    def add_light(self, light):
        self.lights.append(light)
        self.use_lighting = True

    def create_light(self, x, y, radius=150, color=(255, 255, 200), intensity=200):
        l = Light(x, y, radius, color, intensity)
        self.add_light(l)
        return l

    def set_ambient(self, r, g, b):
        self.ambient_light = (int(r), int(g), int(b))

    def add_parallax(self, image_path, speed_factor=0.5):
        layer = ParallaxLayer(image_path, speed_factor)
        self.parallax_layers.append(layer)
        return layer

    def draw_rect(self, x, y, w, h, r=255, g=255, b=255, filled=True):
        s = Shape("rect", x, y, w, h, (int(r), int(g), int(b)), filled)
        self.shapes.append(s)
        return s

    def draw_circle(self, x, y, radius, r=255, g=255, b=255, filled=True):
        s = Shape("circle", x - radius, y - radius, radius * 2, radius * 2, (int(r), int(g), int(b)), filled)
        self.shapes.append(s)
        return s

    def draw_line(self, x1, y1, x2, y2, r=255, g=255, b=255, width=2):
        s = Shape("line", x1, y1, x2, y2, (int(r), int(g), int(b)), True)
        s.line_width = int(width)
        self.shapes.append(s)
        return s

    def screen_shake(self, intensity=10, duration=0.3):
        self.camera.shake(intensity, duration)

    def raycast(self, x1, y1, x2, y2, targets=None, step=4):
        if targets is None:
            targets = self.sprites
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0:
            return None
        step = max(1, int(step))
        steps = max(1, int(length / step))
        step_x = dx / steps
        step_y = dy / steps
        rect_targets = [t for t in targets if hasattr(t, 'rect')]
        px, py = x1, y1
        for _ in range(steps + 1):
            ipx, ipy = int(px), int(py)
            for t in rect_targets:
                if t.rect.collidepoint(ipx, ipy):
                    return t
            px += step_x
            py += step_y
        return None

    def wait(self, seconds, callback):
        self.wait_timers.append({"remaining": float(seconds), "callback": callback})

    def every(self, seconds, callback):
        self.every_timers.append({"interval": float(seconds), "remaining": float(seconds), "callback": callback})

    def _update_timers(self, dt):
        finished = []
        for timer in self.wait_timers:
            timer["remaining"] -= dt
            if timer["remaining"] <= 0:
                timer["callback"]()
                finished.append(timer)
        for t in finished:
            self.wait_timers.remove(t)
            
        for timer in self.every_timers:
            timer["remaining"] -= dt
            if timer["remaining"] <= 0:
                timer["callback"]()
                timer["remaining"] += timer["interval"]

    def blink(self, sprite, duration):
        if sprite in self.sprites:
            sprite.visible = not sprite.visible
            self.wait(duration, lambda: self.blink(sprite, duration))
        
    def bounce(self, sprite, force):
        sprite.apply_force(0, -float(force))
    
    def play_sound_at(self, path, source_x, source_y, listener_x, listener_y, max_dist=500):
        self.spatial_sound(path, source_x, source_y, listener_x, listener_y, max_dist)
        
    def fade_screen(self, direction, duration):
        if direction.upper() == "OUT":
            self.fade_target = 255
        else:
            self.fade_target = 0
        self.fade_speed = 255.0 / max(0.01, float(duration))

    def show_dialog(self, speaker, text, speed=0.05):
        self.dialog_active = True
        self.dialog_speaker = speaker
        self.dialog_text = text
        self.dialog_visible_chars = 0
        self.dialog_timer = 0
        self.dialog_speed = float(speed)

    def save_var(self, name, val, path):
        try:
            data = {}
            if os.path.exists(path):
                with open(path, 'r') as f: data = json.load(f)
            data[name] = val
            with open(path, 'w') as f: json.dump(data, f)
        except (IOError, OSError, ValueError) as e:
            print(f"save_var failed for '{name}' -> {path}: {e}")

    def load_var(self, path, name, default=0):
        try:
            with open(path, 'r') as f: data = json.load(f)
            return data.get(name, default)
        except FileNotFoundError:
            return default
        except (IOError, OSError, ValueError) as e:
            print(f"load_var failed for '{name}' from {path}: {e}")
            return default

    def lerp(self, a, b, t):
        return a + (b - a) * max(0, min(1, float(t)))

    def enable_bloom(self, intensity=1.5):
        self.bloom_enabled = True
        self.bloom_intensity = float(intensity)

    def enable_blur(self):
        self.blur_enabled = True

    def enable_grayscale(self):
        self.grayscale_enabled = True

    def enable_crt(self, intensity=0.5):
        self.crt_enabled = True
        self.crt_intensity = float(intensity)

    def enable_glitch(self, intensity=0.3):
        self.glitch_enabled = True
        self.glitch_intensity = float(intensity)

    def disable_effects(self):
        self.bloom_enabled = False
        self.blur_enabled = False
        self.grayscale_enabled = False
        self.crt_enabled = False
        self.glitch_enabled = False

    def _any_effects_enabled(self):
        return (
            self.bloom_enabled or self.blur_enabled or self.grayscale_enabled
            or self.crt_enabled or self.glitch_enabled
        )

    def _apply_post_processing(self, surface):
        if self.blur_enabled:
            try:
                small = pygame.transform.smoothscale(surface, (surface.get_width() // 4, surface.get_height() // 4))
                surface = pygame.transform.smoothscale(small, (surface.get_width(), surface.get_height()))
            except Exception:
                pass

        if self.grayscale_enabled:
            try:
                arr = pygame.surfarray.pixels3d(surface)
                gray = arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114
                arr[:, :, 0] = gray
                arr[:, :, 1] = gray
                arr[:, :, 2] = gray
                del arr
            except Exception:
                pass

        if self.bloom_enabled:
            try:
                small = pygame.transform.smoothscale(surface, (surface.get_width() // 8, surface.get_height() // 8))
                bright = pygame.transform.smoothscale(small, surface.get_size())
                bright.set_alpha(int(60 * self.bloom_intensity))
                surface.blit(bright, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            except Exception:
                pass

        if self.crt_enabled:
            try:
                w, h = surface.get_width(), surface.get_height()
                if (self._scanline_surface is None
                        or self._scanline_surface.get_size() != (w, h)
                        or self._scanline_intensity_cached != self.crt_intensity):
                    scanline_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                    alpha = max(10, min(120, int(120 * self.crt_intensity)))
                    for y in range(0, h, 2):
                        pygame.draw.line(scanline_surf, (0, 0, 0, alpha), (0, y), (w, y))
                    base = min(w, h) // 3
                    if base > 0:
                        for dist in range(base, 0, -10):
                            a_v = max(0, min(120, int(alpha * (1 - dist / base))))
                            pygame.draw.ellipse(scanline_surf, (0, 0, 0, a_v // 4),
                                                (w // 2 - dist, h // 2 - dist, dist * 2, dist * 2), 30)
                    self._scanline_surface = scanline_surf
                    self._scanline_intensity_cached = self.crt_intensity
                surface.blit(self._scanline_surface, (0, 0))
            except Exception:
                pass

        if self.glitch_enabled:
            try:
                w, h = surface.get_width(), surface.get_height()
                num_glitches = max(1, int(8 * self.glitch_intensity))
                for _ in range(num_glitches):
                    gy = random.randint(0, h - 1)
                    gh = random.randint(1, max(1, int(h * 0.04 * self.glitch_intensity)))
                    gh = min(gh, h - gy)
                    if gh <= 0:
                        continue
                    offset = random.randint(-int(w * 0.06 * self.glitch_intensity), int(w * 0.06 * self.glitch_intensity))
                    strip = surface.subsurface(pygame.Rect(0, gy, w, gh)).copy()
                    surface.blit(strip, (offset, gy))
                if random.random() < self.glitch_intensity * 0.3:
                    color_shift = pygame.Surface((w, h), pygame.SRCALPHA)
                    shift_x = random.randint(-3, 3)
                    try:
                        red_strip = surface.copy()
                        red_strip.fill((255, 0, 0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                        red_strip.set_alpha(60)
                        surface.blit(red_strip, (shift_x, 0))
                    except Exception:
                        pass
            except Exception:
                pass

        return surface

    def on_update(self, func):
        self.update_func = func
        return func

    def is_key_pressed(self, key_name):
        keys = pygame.key.get_pressed()
        key_map = {
            "LEFT": pygame.K_LEFT, "RIGHT": pygame.K_RIGHT, "UP": pygame.K_UP, "DOWN": pygame.K_DOWN,
            "SPACE": pygame.K_SPACE, "ENTER": pygame.K_RETURN, "ESCAPE": pygame.K_ESCAPE,
            "A": pygame.K_a, "B": pygame.K_b, "C": pygame.K_c, "D": pygame.K_d,
            "E": pygame.K_e, "F": pygame.K_f, "G": pygame.K_g, "H": pygame.K_h,
            "I": pygame.K_i, "J": pygame.K_j, "K": pygame.K_k, "L": pygame.K_l,
            "M": pygame.K_m, "N": pygame.K_n, "O": pygame.K_o, "P": pygame.K_p,
            "Q": pygame.K_q, "R": pygame.K_r, "S": pygame.K_s, "T": pygame.K_t,
            "U": pygame.K_u, "V": pygame.K_v, "W": pygame.K_w, "X": pygame.K_x,
            "Y": pygame.K_y, "Z": pygame.K_z,
            "0": pygame.K_0, "1": pygame.K_1, "2": pygame.K_2, "3": pygame.K_3,
            "4": pygame.K_4, "5": pygame.K_5, "6": pygame.K_6, "7": pygame.K_7,
            "8": pygame.K_8, "9": pygame.K_9,
            "TAB": pygame.K_TAB, "SHIFT": pygame.K_LSHIFT, "CTRL": pygame.K_LCTRL,
            "F1": pygame.K_F1, "F2": pygame.K_F2, "F3": pygame.K_F3, "F4": pygame.K_F4,
        }
        return keys[key_map.get(key_name.upper())] if key_name.upper() in key_map else False

    def is_mouse_clicked(self):
        return any(pygame.mouse.get_pressed())

    def get_mouse_button(self, button=0):
        return pygame.mouse.get_pressed()[button]

    def get_joy_axis(self, joy_id=0, axis=0):
        if joy_id < len(self.joysticks):
            return self.joysticks[joy_id].get_axis(axis)
        return 0.0

    def is_joy_button(self, joy_id=0, button=0):
        if joy_id < len(self.joysticks):
            return self.joysticks[joy_id].get_button(button)
        return False

    def get_joy_hat(self, joy_id=0, hat=0):
        if joy_id < len(self.joysticks):
            return self.joysticks[joy_id].get_hat(hat)
        return (0, 0)

    def toggle_hitbox_debug(self):
        self.debug_hitbox = not self.debug_hitbox

    def _draw_debug_hitboxes(self):
        for sprite in self.sprites:
            if hasattr(sprite, 'rect') and sprite.visible:
                pygame.draw.rect(self.screen, (0, 255, 0), sprite.rect, 1)
                if hasattr(sprite, 'collision_radius'):
                    cx, cy = sprite.rect.center
                    pygame.draw.circle(self.screen, (0, 255, 255), (cx, cy), sprite.collision_radius, 1)

    _splash_shown = False

    def run(self):
        import os, sys
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        try:
            logo_img = pygame.image.load(logo_path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            try:
                logo_img = pygame.image.load("logo.png").convert_alpha()
            except (pygame.error, FileNotFoundError):
                print("CRITICAL: Protection Cavern-Engine activated. Cannot start without logo.png at root.")
                sys.exit(1)

        logo_img = pygame.transform.scale(logo_img, (300, 300))
        logo_rect = logo_img.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 - 30))

        pygame.font.init()
        font_splash = pygame.font.SysFont("Verdana", 24, bold=True)
        text_splash = font_splash.render(f"BUILT WITH CAVERN-ENGINE V{CAVERN_VERSION}", True, (255, 255, 255))
        text_rect = text_splash.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 + 150))

        font_easter = pygame.font.SysFont("Verdana", 24, bold=False, italic=True)
        easter_surf = font_easter.render("caperuisseau | Cavern-Engine", True, (150, 150, 255))
        easter_rect = easter_surf.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 + 200))

        show_splash = not MiniEngine._splash_shown
        if show_splash:
            MiniEngine._splash_shown = True
        splash_start = pygame.time.get_ticks()
        caperuisseau_activated = False

        while show_splash:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                    caperuisseau_activated = True

            self.screen.fill((10, 10, 12))
            self.screen.blit(logo_img, logo_rect)
            self.screen.blit(text_splash, text_rect)

            if caperuisseau_activated:
                self.screen.blit(easter_surf, easter_rect)

            pygame.display.flip()

            if pygame.time.get_ticks() - splash_start > self.splash_duration:
                show_splash = False

        MiniEngine._pending_scene = None
        running = True
        self.clock.tick(self.fps)
        while running:
            dt = self.clock.tick(self.fps) / 1000.0
            self.glitch_timer += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F3:
                        self.toggle_hitbox_debug()

            self._update_timers(dt)

            cam_x, cam_y = self.camera.update(dt)

            for sprite in self.sprites:
                if hasattr(sprite, 'update_physics'):
                    sprite.update_physics(dt)
                if isinstance(sprite, AnimatedSprite):
                    sprite.update(dt)

            for em in self.particles:
                em.update(dt)
            self.particles = [em for em in self.particles if em.particles or em.continuous]

            for _name, btn in self.buttons:
                btn.update()

            if self.update_func:
                self.update_func(dt)

            if MiniEngine._pending_scene is not None:
                running = False
                import importlib.util, sys as _sys
                cave_path = MiniEngine._pending_scene
                out_py = cave_path.replace(".cave", "_genere.py")
                try:
                    parser_langage_caverne(cave_path, out_py)
                    spec = importlib.util.spec_from_file_location("scene_module", out_py)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                except Exception as e_sc:
                    print(f"Erreur LOAD_SCENE: {e_sc}")
                return

            if self.fade_alpha != self.fade_target:
                if self.fade_alpha < self.fade_target:
                    self.fade_alpha = min(self.fade_target, self.fade_alpha + self.fade_speed * dt)
                else:
                    self.fade_alpha = max(self.fade_target, self.fade_alpha - self.fade_speed * dt)

            if self.dialog_active:
                self.dialog_timer += dt
                if self.dialog_timer >= self.dialog_speed:
                    self.dialog_timer = 0
                    if self.dialog_visible_chars < len(self.dialog_text):
                        self.dialog_visible_chars += 1

            self.screen.fill(self.bg_color)

            for layer in self.parallax_layers:
                layer.draw(self.screen, cam_x, cam_y)

            for _name, tm in self.tilemaps.items():
                tm.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            for s in self.shapes:
                s.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            for sprite in self.sprites:
                sprite.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            for em in self.particles:
                em.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            for _name, pb in self.progress_bars:
                pb.draw(self.screen, 0, 0, 1.0)

            for _name, btn in self.buttons:
                btn.draw(self.screen, 0, 0, 1.0)

            if self.use_lighting and self.lights:
                if self._light_surface is None or self._light_surface.get_size() != (self.width, self.height):
                    self._light_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                self._light_surface.fill((*self.ambient_light, 255))
                for light in self.lights:
                    light.draw(self._light_surface, cam_x, cam_y, self.camera.zoom)
                self.screen.blit(self._light_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            if self.debug_hitbox:
                self._draw_debug_hitboxes()

            if self._any_effects_enabled():
                self.screen = self._apply_post_processing(self.screen)

            if self.dialog_active:
                dw, dh = self.width - 100, 150
                dx, dy = 50, self.height - 200
                pygame.draw.rect(self.screen, (20, 20, 40, 230), (dx, dy, dw, dh), border_radius=10)
                pygame.draw.rect(self.screen, (100, 100, 250), (dx, dy, dw, dh), 3, border_radius=10)
                
                s_surf = self.dialog_font.render(self.dialog_speaker, True, (255, 255, 100))
                self.screen.blit(s_surf, (dx + 20, dy + 15))
                
                current_text = self.dialog_text[:self.dialog_visible_chars]
                t_surf = self.dialog_body_font.render(current_text, True, (255, 255, 255))
                self.screen.blit(t_surf, (dx + 20, dy + 50))
                
                if self.is_key_pressed("SPACE") or self.is_mouse_clicked():
                    if self.dialog_visible_chars < len(self.dialog_text):
                        self.dialog_visible_chars = len(self.dialog_text)
                    else:
                        self.dialog_active = False

            if self.fade_alpha > 0:
                if self._fade_surface is None or self._fade_surface.get_size() != (self.width, self.height):
                    self._fade_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                self._fade_surface.fill((0, 0, 0, int(self.fade_alpha)))
                self.screen.blit(self._fade_surface, (0, 0))

            pygame.display.flip()
        pygame.quit()

def translate_condition(cond):
    cond = cond.strip()
    if cond.startswith("KEY "):
        touche = cond[4:].strip()
        return f'engine.is_key_pressed("{touche}")'
    if cond == "MOUSE CLICK":
        return 'engine.is_mouse_clicked()'

    if "TILEMAP_COLLIDE" in cond:
        m = re.search(r'TILEMAP_COLLIDE\s+(\w+)\s+(\w+)', cond)
        if m:
            return f'engine.tilemap_collide({m.group(1)}, "{m.group(2)}")'

    if "BUTTON_CLICKED" in cond:
        m = re.search(r'BUTTON_CLICKED\s+(\w+)', cond)
        if m:
            return f'{m.group(1)}.is_clicked()'

    touches_communes = ["SPACE", "ESCAPE", "ENTER", "LEFT", "RIGHT", "UP", "DOWN", "SHIFT", "CONTROL"]
    if cond in touches_communes:
        return f'engine.is_key_pressed("{cond}")'

    return cond

def split_cave_args(s):
    args = []
    current = []
    level = 0
    in_quote = False
    for char in s:
        if char == '"': in_quote = not in_quote
        if not in_quote:
            if char == '(': level += 1
            elif char == ')': level -= 1

        if char == ' ' and level == 0 and not in_quote:
            if current:
                args.append("".join(current))
                current = []
        else:
            current.append(char)
    if current:
        args.append("".join(current))
    return args

def parse_action(act_str, dt=False):
    if act_str.startswith("IF "):
        m = re.match(r'IF\s+(.*?)\s*:\s*(.*)', act_str)
        if m:
            cond = translate_condition(m.group(1))
            action_restante = m.group(2).strip()
            return f'if {cond}: {parse_action(action_restante, dt=dt)}'

    m = split_cave_args(act_str)
    if not m: return "pass"
    try:
        if m[0] == "MOVE":
            mult = " * dt" if dt else ""
            return f'{m[1]}.move({m[2]}{mult}, {m[3]}{mult})'
        elif m[0] == "GOTO": return f'{m[1]}.goto({m[2]}, {m[3]})'
        elif m[0] == "DESTROY" or m[0] == "KILL": return f'engine.kill({m[1]})'
        elif m[0] == "PLAY_SOUND":
            vol = m[2] if len(m) > 2 else "1.0"
            return f'engine.play_sound({m[1]}, {vol})'
        elif m[0] == "PLAY_SOUND_AT":
            return f'engine.play_sound_at({m[1]}, {m[2]}, {m[3]}, {m[4]}, {m[5]})'
        elif m[0] == "BOUNCE": return f'engine.bounce({m[1]}, {m[2]})'
        elif m[0] == "BLINK": return f'engine.blink({m[1]}, {m[2]})'
        elif m[0] == "SET_COLOR": return f'{m[1]}.set_color({m[2]}, {m[3]}, {m[4]})'
        elif m[0] == "SHOW": return f'{m[1]}.show()'
        elif m[0] == "HIDE": return f'{m[1]}.hide()'
        elif m[0] == "SCALE": return f'{m[1]}.set_scale({m[2]})'
        elif m[0] == "SIZE": return f'{m[1]}.set_size({m[2]}, {m[3]})'
        elif m[0] == "CHROMA": return f'{m[1]}.set_chroma({m[2]}, {m[3]}, {m[4]})'
        elif m[0] == "ROTATE": return f'{m[1]}.set_rotation({m[2]})'
        elif m[0] == "ALPHA": return f'{m[1]}.set_alpha({m[2]})'
        elif m[0] == "CENTER": return f'{m[1]}.center()'
        elif m[0] == "QUIT": return f'sys.exit(0)'
        elif m[0] == "UPDATE_TEXT":
            return f'{m[1]}.raw_text = str({m[2]}); {m[1]}.update_image()'
        elif m[0] == "FORCE":
            mult = " * dt" if dt else ""
            return f'{m[1]}.apply_force({m[2]}{mult}, {m[3]}{mult})'
        elif m[0] == "VELOCITY": return f'{m[1]}.set_velocity({m[2]}, {m[3]})'
        elif m[0] == "LERP_TO": return f'{m[1]}.lerp_to({m[2]}, {m[3]}, {m[4]})'
        elif m[0] == "SHAKE": return f'engine.screen_shake({m[1]}, {m[2]})'
        elif m[0] == "SPAWN_PARTICLES":
            return f'engine.spawn_particles({m[1]}, {m[2]}, "fire", ({m[3]}, {m[4]}, {m[5]}), {m[6] if len(m) > 6 else 20})'
        elif m[0] == "CAMERA_FOLLOW": return f'engine.camera_follow({m[1]})'
        elif m[0] == "CAMERA_ZOOM": return f'engine.camera_zoom({m[1]})'
        elif m[0] == "CAMERA_SHAKE": return f'engine.camera_shake({m[1]}, {m[2]})'
        elif m[0] == "ADD_TO_GROUP": return f'engine.add_to_group("{m[1]}", {m[2]})'
        elif m[0] == "SPATIAL_SOUND": return f'engine.spatial_sound({m[1]}, {m[2]}, {m[3]}, {m[4]}, {m[5]})'
        elif m[0] == "FADE_OUT_MUSIC": return f'engine.fade_out_music({m[1] if len(m) > 1 else 1000})'
        elif m[0] == "FADE_IN_MUSIC": return f'engine.fade_in_music({m[1]}, {m[2] if len(m) > 2 else 1000})'
        elif m[0] == "FADE_SCREEN": return f'engine.fade_screen("{m[1]}", {m[2]})'
        elif m[0] == "SHOW_DIALOG":
            speed = m[3] if len(m) > 3 else "0.05"
            return f'engine.show_dialog({m[1]}, {m[2]}, {speed})'
        elif m[0] == "SAVE_VAR": return f'engine.save_var({repr(m[1])}, {m[1]}, {m[2]})'
        elif m[0] == "LOAD_VAR": return f'globals().update({{{repr(m[1])}: engine.load_var({m[2]}, {repr(m[1])}, {m[1]})}})'
        elif m[0] == "STOP_MUSIC": return f'engine.stop_music()'
        elif m[0] == "PAUSE_MUSIC": return f'engine.pause_music()'
        elif m[0] == "RESUME_MUSIC": return f'engine.resume_music()'
        elif m[0] == "SOUND_VOLUME": return f'engine.set_sound_volume({m[1]})'
        elif m[0] == "MUSIC_VOLUME": return f'engine.set_music_volume({m[1]})'
        elif m[0] == "BLOOM": return f'engine.enable_bloom({m[1] if len(m) > 1 else 1.5})'
        elif m[0] == "BLUR": return f'engine.enable_blur()'
        elif m[0] == "GRAYSCALE": return f'engine.enable_grayscale()'
        elif m[0] == "NO_EFFECTS": return f'engine.disable_effects()'
        elif m[0] == "CRT": return f'engine.enable_crt({m[1] if len(m) > 1 else 0.5})'
        elif m[0] == "GLITCH": return f'engine.enable_glitch({m[1] if len(m) > 1 else 0.3})'
        elif m[0] == "LOAD_SCENE": return f'engine.load_scene({m[1]})'
        elif m[0] == "TILEMAP_COLLIDE": return f'engine.tilemap_collide({m[1]}, "{m[2]}")'
        elif m[0] == "BUTTON_CLICKED": return f'{m[1]}.is_clicked()'
        elif m[0] == "SET_PROGRESS": return f'{m[1]}.set_value({m[2]})'
        elif m[0] == "FONT_SIZE": return f'{m[1]}.set_font_size({m[2]})'
        elif m[0] == "PLAY_ANIM": return f'{m[1]}.play()'
        elif m[0] == "PAUSE_ANIM": return f'{m[1]}.pause()'
        elif m[0] == "SET_FRAME": return f'{m[1]}.set_frame({m[2]})'
        elif m[0] == "BACKGROUND": return f'engine.set_bg({m[1]}, {m[2]}, {m[3]})'
        elif m[0] == "AMBIENT": return f'engine.set_ambient({m[1]}, {m[2]}, {m[3]})'
        elif m[0] == "TITLE": return f'engine.set_window_title({m[1]})'
        elif m[0] == "ICON": return f'engine.set_window_icon({m[1]})'
        elif m[0] == "TICKRATE": return f'engine.set_fps({m[1]})'
        elif m[0] == "CAMERA" and len(m) > 1 and m[1] == "FOLLOW": return f'engine.camera_follow({m[2]})'
        elif m[0] == "WAIT":
            wait_parts = act_str.split(":", 1)
            time_val = wait_parts[0].strip().split()[1]
            sub_action = parse_action(wait_parts[1].strip(), dt=False)
            return f'engine.wait({time_val}, lambda: {sub_action})'
        elif m[0] == "SET":
            parts = act_str.split("=", 1)
            if len(parts) < 2:
                raise Exception("SET requires format: SET name = value")
            head_tokens = parts[0].strip().split(None, 1)
            if len(head_tokens) < 2:
                raise Exception("SET requires a target name before '='")
            nom = head_tokens[1].strip()
            val = parts[1].strip()
            if not val:
                raise Exception("SET requires a value after '='")
            if "." in nom:
                obj, attr = nom.rsplit(".", 1)
                return f"setattr({obj}, '{attr}', {val})"
            else:
                return f"globals().update({{{repr(nom)}: {val}}})"
    except Exception:
        return "pass"
    return "pass"

def parser_langage_caverne(chemin_source, chemin_destination):
    with open(chemin_source, 'r') as f:
        lignes_brutes = f.readlines()

    lignes = []
    for lb in lignes_brutes:
        lb_strip = lb.strip()
        if lb_strip.startswith("IMPORT "):
            match = re.search(r'IMPORT\s+"([^"]+)"', lb_strip)
            if match:
                try:
                    with open(match.group(1), 'r') as imp_f:
                        lignes.extend(imp_f.readlines())
                except (IOError, OSError) as e:
                    print(f"IMPORT '{match.group(1)}' a échoué : {e}")
        else:
            lignes.append(lb)

    code = [
        ("from editor import MiniEngine, Sprite, Text, AnimatedSprite, SpriteGroup, "
         "Shape, Light, ParticleEmitter, ParallaxLayer, Camera, Tileset, Tilemap, "
         "Button, ProgressBar, parser_langage_caverne"),
        "import sys", "import math", "import random", "import pygame",
        "", "# Fonctions math", "SIN = math.sin", "COS = math.cos", "TAN = math.tan", "ABS = abs", "SQRT = math.sqrt",
        "FLOOR = math.floor", "CEIL = math.ceil", "CLAMP = lambda x, lo, hi: max(lo, min(hi, x))",
        "LERP = lambda a, b, t: a + (b - a) * max(0, min(1, t))",
        "DISTANCE = lambda x1, y1, x2, y2: math.sqrt((x2 - x1)**2 + (y2 - y1)**2)",
        "ANGLE = lambda x1, y1, x2, y2: math.degrees(math.atan2(y2 - y1, x2 - x1))",
        "RANDINT = random.randint", "RANDF = random.uniform", "", "engine = MiniEngine()"
    ]

    screen_w, screen_h = 800, 600
    dans_update = False
    dans_block = False
    current_indent = ""
    indentation = 0
    global_vars = []
    user_functions = []
    block_stack = []
    block_counter = 0

    for i, ligne in enumerate(lignes):
        ligne = ligne.split("#")[0].strip()
        if not ligne: continue
        mots = ligne.split()
        num_ligne = i + 1
        ind = current_indent if (dans_block or dans_update) else ""

        try:
            if ligne.endswith(":") and not ligne.startswith("WHEN UPDATE"):
                if ligne.startswith("FUNCTION "):
                    m = re.match(r'FUNCTION\s+(\w+)\s*\((.*?)\)\s*:', ligne)
                    if m:
                        nom, args = m.groups()
                        code.append(f"def {nom}({args}):")
                        user_functions.append(nom)
                elif ligne.startswith("FOR "):
                    m = re.match(r'FOR\s+(\w+)\s+IN\s+(.*?)\s*:', ligne)
                    if m:
                        it_range = m.group(2).lower().replace('range', 'range')
                        code.append(f"{ind}for {m.group(1)} in {it_range}:")
                elif ligne.startswith("IF "):
                    cond = translate_condition(ligne[3:-1].strip())
                    code.append(f"{ind}if {cond}:")
                elif ligne.startswith("WHILE "):
                    code.append(f"{ind}while {ligne[6:-1].strip()}:")
                elif ligne.startswith("ELSE"):
                    code.append(f"{ind[:-4]}else:")
                elif ligne.startswith("ELIF "):
                    cond = translate_condition(ligne[5:-1].strip())
                    code.append(f"{ind[:-4]}elif {cond}:")
                    block_stack.append(("ELIF",))
                elif ligne.startswith("AFTER "):
                    time_val = ligne[6:-1].strip()
                    cb_name = f"_cb_block_{block_counter}"
                    block_counter += 1
                    code.append(f"{ind}def {cb_name}():")
                    block_stack.append(("AFTER", time_val, cb_name))
                elif ligne.startswith("EVERY "):
                    time_val = ligne[6:-1].strip()
                    cb_name = f"_cb_block_{block_counter}"
                    block_counter += 1
                    code.append(f"{ind}def {cb_name}():")
                    block_stack.append(("EVERY", time_val, cb_name))
                elif ligne.startswith("KEY_PRESSED "):
                    key_val = ligne[12:-1].strip()
                    code.append(f"{ind}if engine.is_key_pressed('{key_val}'):")
                    block_stack.append(("KEY_PRESSED",))
                elif ligne == "MOUSE_CLICKED:":
                    code.append(f"{ind}if engine.is_mouse_clicked():")
                    block_stack.append(("MOUSE_CLICKED",))
                else:
                    block_stack.append(("OTHER",))

                if not (ligne.startswith("ELSE") or ligne.startswith("ELIF ")):
                    indentation += 1

                dans_block = True
                current_indent = "    " * indentation
                continue

            elif ligne == "END":
                indentation -= 1
                dans_block = indentation > 0
                current_indent = "    " * indentation
                
                if block_stack:
                    b_info = block_stack.pop()
                    if b_info[0] == "AFTER":
                        code.append(f"{current_indent}engine.wait({b_info[1]}, {b_info[2]})")
                    elif b_info[0] == "EVERY":
                        code.append(f"{current_indent}engine.every({b_info[1]}, {b_info[2]})")

                continue

            if ligne == "WHEN UPDATE:":
                dans_update = True
                indentation = 1
                current_indent = "    "
                code.extend(["", "@engine.on_update", "def update(dt):"])
                code.append("    MOUSE_X, MOUSE_Y = pygame.mouse.get_pos()")
                code.append("    TIME = pygame.time.get_ticks() / 1000.0")
                code.append(f"    SCREEN_WIDTH, SCREEN_HEIGHT = {screen_w}, {screen_h}")
                code.append("    FPS = engine.fps")
                if global_vars: code.append("    global " + ", ".join(set(global_vars)))
                continue

            if ligne.startswith("VAR "):
                p_var = ligne[4:].split("=", 1)
                if len(p_var) < 2:
                    raise Exception(f"VAR requires format: VAR name = value")
                nom, val = p_var[0].strip(), p_var[1].strip()
                if nom not in global_vars:
                    global_vars.append(nom)
                    code.insert(7, f"{nom} = 0")
                code.append(f"{ind}{nom} = {val}")

            elif ligne.startswith("CONST "):
                p_const = ligne[6:].split("=", 1)
                if len(p_const) < 2:
                    raise Exception(f"CONST requires format: CONST name = value")
                nom, val = p_const[0].strip(), p_const[1].strip()
                global_vars.append(nom)
                code.insert(7, f"{nom} = {val}")

            elif mots[0] == "SPRITE" and len(mots) >= 6:
                args_c = split_cave_args(ligne)
                if len(args_c) < 6:
                    raise Exception(f"SPRITE requires at least 6 arguments")
                nom, img, x, y = args_c[1], args_c[2], args_c[4], args_c[5]
                code.extend([f'{ind}{nom} = Sprite({img}, {x}, {y})', f'{ind}engine.add_sprite({nom})'])
                if nom not in global_vars: global_vars.append(nom)

            elif mots[0] == "TEXT" and len(mots) >= 6:
                args_c = split_cave_args(ligne)
                if len(args_c) < 6:
                    raise Exception(f"TEXT requires at least 6 arguments")
                nom, txt, x, y = args_c[1], args_c[2], args_c[4], args_c[5]
                code.extend([f'{ind}{nom} = Text({txt}, {x}, {y})', f'{ind}engine.add_sprite({nom})'])
                if nom not in global_vars: global_vars.append(nom)

            elif mots[0] == "LIGHT" and len(mots) >= 6:
                args_c = split_cave_args(ligne)
                if len(args_c) < 7:
                    raise Exception(f"LIGHT requires at least 7 arguments")
                nom = args_c[1]
                x, y = args_c[3], args_c[4]
                r = args_c[6]
                col = "(255, 255, 200)"
                if "COLOR" in args_c:
                    idx = args_c.index("COLOR")
                    if len(args_c) > idx + 3:
                        col = f"({args_c[idx+1]}, {args_c[idx+2]}, {args_c[idx+3]})"
                code.append(f'{ind}{nom} = engine.create_light({x}, {y}, {r}, {col})')
                if nom not in global_vars: global_vars.append(nom)

            elif ligne.startswith("GROUP "):
                if len(mots) < 2:
                    raise Exception(f"GROUP requires a name")
                code.append(f'{ind}{mots[1]} = engine.create_group("{mots[1]}")')
                if mots[1] not in global_vars: global_vars.append(mots[1])

            elif ligne.startswith("TITLE "):
                args_c = split_cave_args(ligne)
                if len(args_c) < 2:
                    raise Exception(f"TITLE requires a title string")
                code.append(f'engine.set_window_title({args_c[1]})')

            elif ligne.startswith("ICON "):
                args_c = split_cave_args(ligne)
                if len(args_c) < 2:
                    raise Exception(f"ICON requires an icon file path")
                code.append(f'engine.set_window_icon({args_c[1]})')

            elif ligne.startswith("SCREEN "):
                if len(mots) < 3:
                    raise Exception(f"SCREEN requires width and height")
                screen_w, screen_h = int(mots[1]), int(mots[2])
                code.append(f'engine.set_screen_size({screen_w}, {screen_h})')

            elif ligne.startswith("TICKRATE "):
                if len(mots) < 2:
                    raise Exception(f"TICKRATE requires a value")
                code.append(f'engine.set_fps({mots[1]})')

            elif ligne.startswith("LESS_LOGO"):
                code.append('engine.set_splash_duration(500)')

            elif ligne.startswith("BACKGROUND "):
                if len(mots) < 4:
                    raise Exception(f"BACKGROUND requires RGB values")
                code.append(f'{ind}engine.set_bg({mots[1]}, {mots[2]}, {mots[3]})')

            elif ligne.startswith("AMBIENT "):
                if len(mots) < 4:
                    raise Exception(f"AMBIENT requires RGB values")
                code.append(f'{ind}engine.set_ambient({mots[1]}, {mots[2]}, {mots[3]})')

            elif ligne.startswith("PHYSICS "):
                if len(mots) < 2:
                    raise Exception(f"PHYSICS requires a sprite name")
                nom = mots[1]
                code.append(f'{ind}{nom}.physics_enabled = True')
                if "GRAVITY" in ligne: 
                    g_match = re.search(r"GRAVITY\s+([0-9.-]+)", ligne)
                    if g_match: code.append(f'{ind}{nom}.gravity = {g_match.group(1)}')
                if "FRICTION" in ligne: 
                    f_match = re.search(r"FRICTION\s+([0-9.-]+)", ligne)
                    if f_match: code.append(f'{ind}{nom}.friction = {f_match.group(1)}')

            elif ligne.startswith("CAMERA FOLLOW "):
                if len(mots) < 3:
                    raise Exception(f"CAMERA FOLLOW requires a sprite name")
                code.append(f'{ind}engine.camera_follow({mots[2]})')

            elif mots[0] == "TILESET":
                args_c = split_cave_args(ligne)
                if len(args_c) < 3:
                    raise Exception(f"TILESET requires at least 3 arguments")
                nom = args_c[1]
                img = args_c[2]
                tile_size = 32
                if "TILE_SIZE" in args_c:
                    idx = args_c.index("TILE_SIZE")
                    if len(args_c) > idx + 1:
                        tile_size = args_c[idx + 1]
                code.append(f'{ind}{nom}_tileset = engine.create_tileset("{nom}", {img}, {tile_size})')
                if f'{nom}_tileset' not in global_vars: global_vars.append(f'{nom}_tileset')

            elif mots[0] == "TILEMAP":
                args_c = split_cave_args(ligne)
                if len(args_c) < 2:
                    raise Exception(f"TILEMAP requires at least 2 arguments")
                nom = args_c[1]
                if len(args_c) > 2 and args_c[2] == "FROM":
                    if len(args_c) < 4:
                        raise Exception(f"TILEMAP FROM requires file path")
                    # TILEMAP name FROM "file.json" TILESET tileset_name
                    json_path = args_c[3]
                    ts_name = args_c[5] if len(args_c) > 5 else f'"{nom}"'
                    code.append(f'{ind}import json as _json_tm')
                    code.append(f'{ind}with open({json_path}, "r") as _f_tm: _tm_data_{nom} = _json_tm.load(_f_tm)')
                    code.append(f'{ind}{nom} = engine.create_tilemap("{nom}", {ts_name}, _tm_data_{nom})')
                else:
                    # TILEMAP name TILESET ts_name DATA [[...]] AT x y
                    ts_name = args_c[3] if len(args_c) > 3 else f'"{nom}"'
                    rest = ligne
                    data_match = re.search(r'DATA\s+(\[\[.*?\]\])', rest)
                    data_str = data_match.group(1) if data_match else '[[]]'
                    x_val, y_val = '0', '0'
                    if 'AT' in args_c:
                        at_idx = args_c.index('AT')
                        if len(args_c) > at_idx + 2:
                            x_val, y_val = args_c[at_idx + 1], args_c[at_idx + 2]
                    code.append(f'{ind}{nom} = engine.create_tilemap("{nom}", "{ts_name}", {data_str}, {x_val}, {y_val})')
                if nom not in global_vars: global_vars.append(nom)

            elif mots[0] == "BUTTON":
                args_c = split_cave_args(ligne)
                if len(args_c) < 3:
                    raise Exception(f"BUTTON requires at least 3 arguments")
                nom = args_c[1]
                text_val = args_c[2]
                x_val, y_val = '100', '100'
                w_val, h_val = '200', '50'
                if 'AT' in args_c:
                    at_idx = args_c.index('AT')
                    if len(args_c) > at_idx + 2:
                        x_val, y_val = args_c[at_idx + 1], args_c[at_idx + 2]
                if 'SIZE' in args_c:
                    sz_idx = args_c.index('SIZE')
                    if len(args_c) > sz_idx + 2:
                        w_val, h_val = args_c[sz_idx + 1], args_c[sz_idx + 2]
                code.append(f'{ind}{nom} = engine.create_button("{nom}", {text_val}, {x_val}, {y_val}, {w_val}, {h_val})')
                if nom not in global_vars: global_vars.append(nom)

            elif mots[0] == "PROGRESS_BAR":
                args_c = split_cave_args(ligne)
                if len(args_c) < 2:
                    raise Exception(f"PROGRESS_BAR requires at least 2 arguments")
                nom = args_c[1]
                x_val, y_val = '100', '100'
                w_val, h_val = '200', '20'
                max_val = '100'
                init_val = '100'
                if 'AT' in args_c:
                    at_idx = args_c.index('AT')
                    if len(args_c) > at_idx + 2:
                        x_val, y_val = args_c[at_idx + 1], args_c[at_idx + 2]
                if 'MAX' in args_c:
                    max_idx = args_c.index('MAX')
                    if len(args_c) > max_idx + 1:
                        max_val = args_c[max_idx + 1]
                if 'VAR' in args_c:
                    var_idx = args_c.index('VAR')
                    if len(args_c) > var_idx + 1:
                        init_val = args_c[var_idx + 1]
                code.append(f'{ind}{nom} = engine.create_progress_bar("{nom}", {x_val}, {y_val}, {w_val}, {h_val}, {init_val}, {max_val})')
                if nom not in global_vars: global_vars.append(nom)

            else:
                action = parse_action(ligne, dt=dans_update)
                if action != "pass":
                    code.append(f"{ind}{action}")
                elif len(mots) > 0 and mots[0] in user_functions:
                    args_func = split_cave_args(ligne)[1:]
                    code.append(f"{ind}{mots[0]}({', '.join(args_func)})")
                elif len(mots) > 0 and (mots[0] in global_vars or "(" in ligne):
                    code.append(f"{ind}{ligne}")

        except Exception as e_ligne:
            raise Exception(f"Erreur de syntaxe ligne {num_ligne}: {e_ligne}")

    code.append("engine.run()")
    with open(chemin_destination, 'w', encoding='utf-8') as f:
        f.write("\n".join(code) + "\n")

THEMES = {
    "tokyo_night": {
        "name": "Tokyo Night",
        "bg": "#1a1b26",
        "sidebar": "#16161e",
        "editor_bg": "#1a1b26",
        "editor_fg": "#a9b1d6",
        "accent": "#7aa2f7",
        "accent2": "#bb9af7",
        "success": "#9ece6a",
        "warning": "#e0af68",
        "error": "#f7768e",
        "comment": "#565f89",
        "string": "#9ece6a",
        "number": "#ff9e64",
        "keyword": "#bb9af7",
        "splitter": "#12121a",
        "tab_bg": "#16161e",
        "tab_active_border": "#7aa2f7",
        "menu_bg": "#16161e",
        "menu_hover": "rgba(122,162,247,0.15)",
        "input_border": "rgba(255,255,255,0.08)",
        "button": "#7aa2f7",
        "button_hover": "#89b0ff",
        "panel_border": "rgba(255,255,255,0.05)",
    },
    "dracula": {
        "name": "Dracula",
        "bg": "#282a36",
        "sidebar": "#21222c",
        "editor_bg": "#282a36",
        "editor_fg": "#f8f8f2",
        "accent": "#8be9fd",
        "accent2": "#bd93f9",
        "success": "#50fa7b",
        "warning": "#f1fa8c",
        "error": "#ff5555",
        "comment": "#6272a4",
        "string": "#f1fa8c",
        "number": "#bd93f9",
        "keyword": "#ff79c6",
        "splitter": "#191a21",
        "tab_bg": "#21222c",
        "tab_active_border": "#bd93f9",
        "menu_bg": "#21222c",
        "menu_hover": "rgba(189,147,249,0.2)",
        "input_border": "rgba(255,255,255,0.1)",
        "button": "#bd93f9",
        "button_hover": "#caa4fa",
        "panel_border": "rgba(255,255,255,0.05)",
    },
    "monokai": {
        "name": "Monokai",
        "bg": "#272822",
        "sidebar": "#1e1f1c",
        "editor_bg": "#272822",
        "editor_fg": "#f8f8f2",
        "accent": "#66d9ef",
        "accent2": "#ae81ff",
        "success": "#a6e22e",
        "warning": "#e6db74",
        "error": "#f92672",
        "comment": "#75715e",
        "string": "#e6db74",
        "number": "#ae81ff",
        "keyword": "#f92672",
        "splitter": "#1a1a15",
        "tab_bg": "#1e1f1c",
        "tab_active_border": "#66d9ef",
        "menu_bg": "#1e1f1c",
        "menu_hover": "rgba(102,217,239,0.2)",
        "input_border": "rgba(255,255,255,0.1)",
        "button": "#66d9ef",
        "button_hover": "#7ae4f6",
        "panel_border": "rgba(255,255,255,0.05)",
    },
    "github_light": {
        "name": "GitHub Light",
        "bg": "#ffffff",
        "sidebar": "#f6f8fa",
        "editor_bg": "#ffffff",
        "editor_fg": "#24292e",
        "accent": "#0366d6",
        "accent2": "#6f42c1",
        "success": "#22863a",
        "warning": "#b08800",
        "error": "#d73a49",
        "comment": "#6a737d",
        "string": "#032f62",
        "number": "#005cc5",
        "keyword": "#d73a49",
        "splitter": "#e1e4e8",
        "tab_bg": "#f6f8fa",
        "tab_active_border": "#0366d6",
        "menu_bg": "#f6f8fa",
        "menu_hover": "rgba(3,102,214,0.1)",
        "input_border": "#e1e4e8",
        "button": "#0366d6",
        "button_hover": "#0057b7",
        "panel_border": "rgba(0,0,0,0.05)",
    },
    "cyberpunk": {
        "name": "Cyberpunk 2077",
        "bg": "#0d0d0d",
        "sidebar": "#080808",
        "editor_bg": "#0d0d0d",
        "editor_fg": "#fdfd96",
        "accent": "#ff003c",
        "accent2": "#00f0ff",
        "success": "#00ff9f",
        "warning": "#fcee0a",
        "error": "#ff003c",
        "comment": "#555555",
        "string": "#00f0ff",
        "number": "#fcee0a",
        "keyword": "#ff003c",
        "splitter": "#1a1a1a",
        "tab_bg": "#080808",
        "tab_active_border": "#ff003c",
        "menu_bg": "#0d0d0d",
        "menu_hover": "rgba(255, 0, 60, 0.15)",
        "input_border": "rgba(255,0,60,0.3)",
        "button": "#ff003c",
        "button_hover": "#ff3363",
        "panel_border": "rgba(255,0,60,0.1)",
    }
}

def build_qss(theme_name):
    t = THEMES.get(theme_name, THEMES["tokyo_night"])
    return f"""
    * {{
        font-family: "Inter", "Segoe UI", "Roboto", sans-serif;
        outline: none;
    }}
    QMainWindow {{
        background: {t['bg']};
    }}
    QWidget {{
        color: {t['editor_fg']};
    }}
    QSplitter::handle {{
        background: transparent;
        width: 1px;
        height: 1px;
    }}
    QSplitter::handle:hover {{
        background: {t['accent']};
    }}

    /* ScrollBars */
    QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: rgba(255, 255, 255, 0.1);
        min-height: 20px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t['accent']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        border: none;
        background: transparent;
        height: 10px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: rgba(255, 255, 255, 0.1);
        min-width: 20px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {t['accent']};
    }}

    /* Sidebar and Trees */
    QTreeView {{
        background: {t['sidebar']};
        border-right: 1px solid {t['panel_border']};
        color: {t['editor_fg']};
        font-size: 13px;
        padding: 10px;
    }}
    QTreeView::item {{
        padding: 6px;
        border-radius: 6px;
        margin-bottom: 2px;
    }}
    QTreeView::item:hover {{
        background: {t['menu_hover']};
    }}
    QTreeView::item:selected {{
        background: {t['menu_hover']};
        color: {t['accent']};
        font-weight: bold;
    }}

    /* Tabs */
    QTabWidget::pane {{
        border-top: 1px solid {t['panel_border']};
        background: {t['editor_bg']};
    }}
    QTabBar {{
        background: {t['sidebar']};
        border-bottom: 1px solid {t['panel_border']};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {t['comment']};
        padding: 12px 20px;
        border-bottom: 3px solid transparent;
        font-size: 12px;
        font-weight: 600;
        min-width: 80px;
    }}
    QTabBar::tab:hover {{
        color: {t['editor_fg']};
        background: rgba(255, 255, 255, 0.03);
    }}
    QTabBar::tab:selected {{
        color: {t['accent']};
        border-bottom: 3px solid {t['accent']};
        background: rgba(122, 162, 247, 0.05);
    }}
    QTabBar::close-button {{
        image: none;
        background: transparent;
    }}
    QTabBar::close-button:hover {{
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
    }}

    /* Editor */
    QPlainTextEdit {{
        background: {t['editor_bg']};
        color: {t['editor_fg']};
        border: none;
        font-family: "JetBrains Mono", "Cascadia Code", monospace;
        font-size: 15px;
        line-height: 1.5;
        selection-background-color: {t['menu_hover']};
        padding: 15px;
    }}

    /* Buttons */
    QPushButton {{
        background: {t['button']};
        color: {t['bg']};
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: bold;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }}
    QPushButton:hover {{
        background: {t['button_hover']};
    }}
    QPushButton:pressed {{
        background: {t['accent']};
        padding-top: 10px;
        padding-bottom: 6px;
    }}

    /* Inputs */
    QLineEdit, QSpinBox, QComboBox {{
        background: rgba(255, 255, 255, 0.05);
        color: {t['editor_fg']};
        border: 1px solid {t['input_border']};
        border-radius: 8px;
        padding: 8px;
        font-size: 13px;
    }}
    QLineEdit:focus {{
        border: 1px solid {t['accent']};
        background: rgba(255, 255, 255, 0.08);
    }}

    /* MenuBar & Menus */
    QMenuBar {{
        background: {t['bg']};
        color: {t['editor_fg']};
        padding: 5px;
        border-bottom: 1px solid {t['panel_border']};
    }}
    QMenuBar::item {{
        padding: 6px 12px;
        border-radius: 6px;
    }}
    QMenuBar::item:selected {{
        background: {t['menu_hover']};
    }}
    QMenu {{
        background: {t['sidebar']};
        color: {t['editor_fg']};
        border: 1px solid {t['panel_border']};
        border-radius: 10px;
        padding: 5px;
    }}
    QMenu::item {{
        padding: 8px 30px 8px 10px;
        border-radius: 6px;
    }}
    QMenu::item:selected {{
        background: {t['menu_hover']};
        color: {t['accent']};
    }}

    /* Toolbar */
    QToolBar {{
        background: {t['bg']};
        border-bottom: 1px solid {t['panel_border']};
        spacing: 10px;
        padding: 8px;
    }}
    QToolButton {{
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 6px 12px;
        font-weight: 500;
        color: {t['editor_fg']};
    }}
    QToolButton:hover {{
        background: {t['menu_hover']};
        border: 1px solid {t['accent']};
    }}

    /* Lists and Tables */
    QListWidget, QTableWidget {{
        background: {t['sidebar']};
        border: 1px solid {t['panel_border']};
        border-radius: 10px;
        padding: 5px;
    }}
    QHeaderView::section {{
        background: {t['sidebar']};
        color: {t['comment']};
        border: none;
        padding: 8px;
        font-weight: bold;
        border-bottom: 1px solid {t['panel_border']};
    }}

    /* GroupBox */
    QGroupBox {{
        border: 1px solid {t['panel_border']};
        border-radius: 10px;
        margin-top: 20px;
        padding: 15px;
        font-weight: bold;
        color: {t['accent2']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px;
    }}

    /* Console & Documentation */
    QTextEdit, #Console {{
        background: {t['sidebar']};
        color: {t['editor_fg']};
        border: none;
        border-top: 1px solid {t['panel_border']};
        font-family: "JetBrains Mono", monospace;
        font-size: 13px;
        padding: 10px;
    }}
    """

class Highlighter(QSyntaxHighlighter):
    def __init__(self, doc, theme_name="tokyo_night"):
        super().__init__(doc)
        self.theme_name = theme_name
        self.rules = []
        self._build_rules()

    def _build_rules(self):
        t = THEMES.get(self.theme_name, THEMES["tokyo_night"])
        self.rules = []

        fmt_kw = QTextCharFormat()
        fmt_kw.setForeground(QColor(t['keyword']))
        fmt_kw.setFontWeight(QFont.Weight.Bold)
        fmt_str = QTextCharFormat()
        fmt_str.setForeground(QColor(t['string']))
        fmt_num = QTextCharFormat()
        fmt_num.setForeground(QColor(t['number']))
        fmt_comment = QTextCharFormat()
        fmt_comment.setForeground(QColor(t['comment']))
        fmt_comment.setFontItalic(True)
        fmt_builtin = QTextCharFormat()
        fmt_builtin.setForeground(QColor(t['accent']))

        keywords = [
            'SPRITE', 'ANIMATED_SPRITE', 'ANIM_SPRITE', 'WHEN', 'UPDATE', 'IF', 'ELIF', 'ELSE', 'KEY', 'MOVE', 'AT',
            'BACKGROUND', 'PLAY_SOUND', 'ON_COLLIDE', 'ON_COLLIDE_CIRCLE', 'ON_COLLIDE_GROUP', 'DESTROY',
            'TEXT', 'SET_COLOR', 'SHOW', 'HIDE', 'SCALE', 'SIZE', 'GOTO', 'MUSIC', 'MOUSE', 'CLICK',
            'VAR', 'CONST', 'SET', 'UPDATE_TEXT', 'FUNCTION', 'END', 'WHILE', 'FOR', 'IN', 'RANGE',
            'IMPORT', 'PARALLAX', 'LIGHT', 'AMBIENT', 'PHYSICS', 'GRAVITY', 'FRICTION', 'BOUNCE',
            'CAMERA', 'FOLLOW', 'ZOOM', 'GROUP', 'ADD_TO_GROUP',
            'DRAW_RECT', 'DRAW_CIRCLE', 'DRAW_LINE', 'COLOR',
            'VELOCITY', 'FORCE', 'LERP_TO', 'SHAKE', 'SPAWN_PARTICLES',
            'BLOOM', 'BLUR', 'GRAYSCALE', 'NO_EFFECTS', 'CRT', 'GLITCH',
            'FADE_OUT_MUSIC', 'FADE_IN_MUSIC', 'STOP_MUSIC', 'PAUSE_MUSIC', 'RESUME_MUSIC',
            'SOUND_VOLUME', 'MUSIC_VOLUME', 'SPATIAL_SOUND',
            'FONT_SIZE', 'PLAY_ANIM', 'PAUSE_ANIM', 'SET_FRAME',
            'TITLE', 'ICON', 'TICKRATE', 'SCREEN', 'CHROMA', 'CENTER', 'ROTATE', 'ALPHA', 'QUIT',
            'CAMERA_FOLLOW', 'CAMERA_ZOOM', 'CAMERA_SHAKE',
            'IF JOY_BUTTON', 'RADIUS', 'FRAMES',
            'TILESET', 'TILEMAP', 'TILEMAP_COLLIDE', 'TILE_SIZE', 'DATA', 'FROM',
            'BUTTON', 'PROGRESS_BAR', 'ON_CLICK', 'BUTTON_CLICKED', 'SET_PROGRESS',
            'LOAD_SCENE', 'MAX', 'LESS_LOGO',
        ]
        for w in keywords:
            self.rules.append((QRegularExpression(rf'\b{w}\b'), fmt_kw))

        builtins = [
            'SIN', 'COS', 'TAN', 'ABS', 'SQRT', 'FLOOR', 'CEIL', 'CLAMP', 'LERP',
            'DISTANCE', 'ANGLE', 'RANDINT', 'RANDF',
            'MOUSE_X', 'MOUSE_Y', 'TIME', 'SCREEN_WIDTH', 'SCREEN_HEIGHT', 'FPS',
        ]
        for w in builtins:
            self.rules.append((QRegularExpression(rf'\b{w}\b'), fmt_builtin))

        self.rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt_str))
        self.rules.append((QRegularExpression(r'\b[-+]?[0-9]*\.?[0-9]+\b'), fmt_num))
        self.rules.append((QRegularExpression(r'#.*$'), fmt_comment))

    def set_theme(self, theme_name):
        self.theme_name = theme_name
        self._build_rules()
        self.rehighlight()

    def highlightBlock(self, text):
        for pat, fmt in self.rules:
            it = pat.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor._line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor._paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, path=None, parent=None):
        super().__init__(parent)
        self.file_path = path
        self._modified = False
        self.setFont(QFont("JetBrains Mono", 13))
        self.highlighter = Highlighter(self.document())
        self.document().modificationChanged.connect(self._on_modified_changed)
        self.setAcceptDrops(True)

        self._line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self._update_line_number_area_width(0)

        kws = [
            "SPRITE", "ANIMATED_SPRITE", "ANIM_SPRITE", "TEXT", "BACKGROUND", "MUSIC", "AT",
            "WHEN UPDATE:", "IF KEY", "IF MOUSE CLICK:", "ELIF", "ELSE:",
            "MOVE", "GOTO", "LEFT", "RIGHT", "UP", "DOWN", "SPACE", "ENTER",
            "PLAY_SOUND", "ON_COLLIDE", "ON_COLLIDE_CIRCLE", "ON_COLLIDE_GROUP",
            "DESTROY", "SET_COLOR", "SHOW", "HIDE", "SCALE", "SIZE",
            "VAR", "CONST", "SET", "UPDATE_TEXT", "FUNCTION", "END",
            "WHILE", "FOR", "IN", "RANGE", "IMPORT",
            "PARALLAX", "LIGHT", "AMBIENT", "PHYSICS", "GRAVITY", "FRICTION", "BOUNCE",
            "CAMERA FOLLOW", "CAMERA ZOOM", "GROUP", "ADD_TO_GROUP",
            "DRAW_RECT", "DRAW_CIRCLE", "DRAW_LINE", "COLOR",
            "VELOCITY", "FORCE", "LERP_TO", "SHAKE", "SPAWN_PARTICLES",
            "BLOOM", "BLUR", "GRAYSCALE", "NO_EFFECTS", "CRT", "GLITCH",
            "FADE_OUT_MUSIC", "FADE_IN_MUSIC", "STOP_MUSIC", "PAUSE_MUSIC", "RESUME_MUSIC",
            "SOUND_VOLUME", "MUSIC_VOLUME", "SPATIAL_SOUND",
            "FONT_SIZE", "PLAY_ANIM", "PAUSE_ANIM", "SET_FRAME",
            "TITLE", "ICON", "TICKRATE", "SCREEN", "CHROMA", "CENTER", "ROTATE", "ALPHA", "QUIT",
            "CAMERA_FOLLOW", "CAMERA_ZOOM", "CAMERA_SHAKE",
            "SIN", "COS", "TAN", "ABS", "SQRT", "FLOOR", "CEIL", "CLAMP", "LERP",
            "DISTANCE", "ANGLE", "RANDINT", "RANDF",
            "MOUSE_X", "MOUSE_Y", "TIME", "SCREEN_WIDTH", "SCREEN_HEIGHT", "FPS",
            "RADIUS", "FRAMES",
            "TILESET", "TILEMAP", "TILEMAP_COLLIDE", "TILE_SIZE", "DATA",
            "BUTTON", "PROGRESS_BAR", "ON_CLICK", "BUTTON_CLICKED", "SET_PROGRESS",
            "LOAD_SCENE", "MAX", "LESS_LOGO",
        ]
        self.completer = QCompleter(kws, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self._insertCompletion)

    def _on_modified_changed(self, modified):
        self._modified = modified
        # Bubble up to MainWindow to update tab title
        w = self.window()
        if hasattr(w, '_update_tab_title'):
            w._update_tab_title(self)

    def _line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self._line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(0, rect.y(), self._line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(QRect(cr.left(), cr.top(), self._line_number_area_width(), cr.height()))

    def _paint_line_numbers(self, event):
        painter = QPainter(self._line_number_area)
        t = THEMES.get(self.highlighter.theme_name, THEMES["tokyo_night"])
        
        painter.fillRect(event.rect(), QColor(t['sidebar']))
        
        # Subtle border
        painter.setPen(QColor(t['panel_border']))
        painter.drawLine(self._line_number_area.width() - 1, 0, self._line_number_area.width() - 1, self.height())
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        current_line = self.textCursor().blockNumber()
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_current = (block_number == current_line)
                color = QColor(t['accent']) if is_current else QColor(t['comment'])
                
                font = painter.font()
                font.setBold(is_current)
                painter.setFont(font)
                
                painter.setPen(color)
                painter.drawText(0, top, self._line_number_area.width() - 8,
                                 self.fontMetrics().height(), Qt.AlignmentFlag.AlignRight,
                                 str(block_number + 1))
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape,
                               Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.ignore()
                return

        # Auto-indent on Enter
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            line = cursor.block().text()
            indent = len(line) - len(line.lstrip())
            extra = 4 if line.rstrip().endswith(':') else 0
            super().keyPressEvent(event)
            self.textCursor().insertText(' ' * (indent + extra))
            return

        is_shortcut = (event.modifiers() == Qt.KeyboardModifier.ControlModifier
                       and event.key() == Qt.Key.Key_Space)
        if not is_shortcut:
            super().keyPressEvent(event)

        if not self.completer:
            return
        is_ctrl_or_shift = event.modifiers() in (Qt.KeyboardModifier.ControlModifier,
                                                  Qt.KeyboardModifier.ShiftModifier)
        if is_ctrl_or_shift and not is_shortcut:
            return

        self.update_completions()
        line_text = self.textCursor().block().text()
        words = line_text.split()
        completionPrefix = words[-1] if words else ""
        if not is_shortcut and (not completionPrefix or len(completionPrefix) < 1):
            self.completer.popup().hide()
            return
        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            self.completer.popup().setCurrentIndex(self.completer.completionModel().index(0, 0))
        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0)
                    + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)
        return  # prevent duplicate call below

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def _insertCompletion(self, completion):
        tc = self.textCursor()
        prefix_len = len(self.completer.completionPrefix())
        tc.movePosition(tc.MoveOperation.Left, tc.MoveMode.KeepAnchor, prefix_len)
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(tc.SelectionType.WordUnderCursor)
        return tc.selectedText()

    def update_completions(self):
        """Met à jour les complétions avec les noms de sprites trouvés dans le code."""
        text = self.toPlainText()
        sprite_names = re.findall(r'(?:SPRITE|TEXT|ANIMATED_SPRITE|ANIM_SPRITE)\s+(\w+)', text)
        var_names = re.findall(r'VAR\s+(\w+)', text)
        func_names = re.findall(r'FUNCTION\s+(\w+)', text)
        group_names = re.findall(r'GROUP\s+(\w+)', text)

        current_words = [self.completer.model().data(self.completer.model().index(i, 0))
                         for i in range(self.completer.model().rowCount())]

        all_words = list(set(current_words + sprite_names + var_names + func_names + group_names))
        self.completer.setModel(QStringListModel(sorted(all_words)))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path:
                    name = Path(file_path).stem
                    ext = Path(file_path).suffix.lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        text = f'SPRITE {name} "{Path(file_path).name}" AT 100 100'
                        self.textCursor().insertText(text)
                    elif ext in ['.mp3', '.wav', '.ogg']:
                        text = f'MUSIC "{Path(file_path).name}"'
                        self.textCursor().insertText(text)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

class FindReplaceDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Chercher / Remplacer")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        grid = QGridLayout()
        grid.setSpacing(10)
        
        grid.addWidget(QLabel("🔍 Chercher:"), 0, 0)
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Texte à trouver...")
        grid.addWidget(self.find_input, 0, 1)

        grid.addWidget(QLabel("🔄 Remplacer:"), 1, 0)
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Texte de remplacement...")
        grid.addWidget(self.replace_input, 1, 1)
        
        layout.addLayout(grid)

        self.case_cb = QCheckBox("Respecter la casse")
        layout.addWidget(self.case_cb)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        b_find = QPushButton("Suivant")
        b_repl = QPushButton("Remplacer")
        b_all  = QPushButton("Tout remplacer")
        b_find.clicked.connect(self.find_next)
        b_repl.clicked.connect(self.replace_one)
        b_all.clicked.connect(self.replace_all)
        
        b_find.setDefault(True)
        
        for b in (b_find, b_repl, b_all):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.find_input.returnPressed.connect(self.find_next)

    def _flags(self):
        from PyQt6.QtGui import QTextDocument
        flags = QTextDocument.FindFlag(0)
        if self.case_cb.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        return flags

    def find_next(self):
        text = self.find_input.text()
        if not text:
            return
        found = self.editor.find(text, self._flags())
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(text, self._flags())

    def replace_one(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
        self.find_next()

    def replace_all(self):
        text = self.toPlainText() if hasattr(self, 'toPlainText') else self.editor.toPlainText()
        old = self.find_input.text()
        new = self.replace_input.text()
        if not old:
            return
        flags = re.IGNORECASE if not self.case_cb.isChecked() else 0
        result = re.sub(re.escape(old), new, self.editor.toPlainText(), flags=flags)
        self.editor.setPlainText(result)


class VariableMonitor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("  📊  Variables Monitor")
        header.setStyleSheet("font-weight: bold; color: palette(highlight); font-size: 14px; padding: 10px 5px;")
        layout.addWidget(header)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Variable", "Valeur"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def update_vars(self, var_dict):
        self.table.setRowCount(len(var_dict))
        for row, (name, value) in enumerate(var_dict.items()):
            self.table.setItem(row, 0, QTableWidgetItem(str(name)))
            self.table.setItem(row, 1, QTableWidgetItem(str(value)))

class SceneManager(QWidget):
    scene_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("  🎬  Scènes")
        header.setStyleSheet("font-weight: bold; color: palette(link); font-size: 14px; padding: 10px 5px;")
        layout.addWidget(header)

        self.scene_list = QListWidget()
        self.scene_list.itemDoubleClicked.connect(self._on_select)
        layout.addWidget(self.scene_list)

        btn_layout = QHBoxLayout()
        btn_new = QPushButton("+ Scène")
        btn_new.clicked.connect(self._new_scene)
        btn_layout.addWidget(btn_new)
        layout.addLayout(btn_layout)

    def _new_scene(self):
        name, ok = QInputDialog.getText(self, "Nouvelle Scène", "Nom de la scène:")
        if ok and name:
            self.scene_list.addItem(name + ".cave")
            self.scene_selected.emit(name + ".cave")

    def _on_select(self, item):
        self.scene_selected.emit(item.text())

    def refresh(self, directory):
        self.scene_list.clear()
        if directory and os.path.isdir(directory):
            for f in sorted(os.listdir(directory)):
                if f.endswith('.cave'):
                    self.scene_list.addItem(f)

class AssetExplorer(QWidget):
    asset_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("  🎨  Assets")
        header.setStyleSheet("font-weight: bold; color: #9ece6a; font-size: 14px; padding: 10px 5px;")
        layout.addWidget(header)

        self.asset_list = QListWidget()
        self.asset_list.setIconSize(QSize(48, 48))
        self.asset_list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.asset_list)

    def refresh(self, directory):
        self.asset_list.clear()
        if not directory or not os.path.isdir(directory):
            return

        extensions_img = ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
        extensions_audio = ['.mp3', '.wav', '.ogg']

        for f in sorted(os.listdir(directory)):
            ext = Path(f).suffix.lower()
            fp = os.path.join(directory, f)
            if ext in extensions_img:
                item = QListWidgetItem(f)
                try:
                    pixmap = QPixmap(fp).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    item.setIcon(QIcon(pixmap))
                except Exception:
                    pass
                item.setData(Qt.ItemDataRole.UserRole, fp)
                self.asset_list.addItem(item)
            elif ext in extensions_audio:
                item = QListWidgetItem(f"🔊 {f}")
                item.setData(Qt.ItemDataRole.UserRole, fp)
                self.asset_list.addItem(item)

    def _on_double_click(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.asset_dropped.emit(path)

class ProjectSettingsDialog(QDialog):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Paramètres du projet")
        self.setMinimumWidth(500)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Section Fenêtre ---
        win_group = QGroupBox("Configuration de la Fenêtre")
        win_layout = QGridLayout(win_group)
        win_layout.setSpacing(10)
        
        win_layout.addWidget(QLabel("Titre:"), 0, 0)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Mon Super Jeu")
        win_layout.addWidget(self.title_input, 0, 1)

        win_layout.addWidget(QLabel("Icône:"), 1, 0)
        icon_row = QHBoxLayout()
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText("logo.png")
        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(40)
        btn_browse.clicked.connect(self._browse_icon)
        icon_row.addWidget(self.icon_input)
        icon_row.addWidget(btn_browse)
        win_layout.addLayout(icon_row, 1, 1)

        main_layout.addWidget(win_group)

        # --- Section Rendu & Performance ---
        perf_group = QGroupBox("Rendu & Performance")
        perf_layout = QGridLayout(perf_group)
        perf_layout.setSpacing(10)

        perf_layout.addWidget(QLabel("Résolution:"), 0, 0)
        res_row = QHBoxLayout()
        self.width_spin = QSpinBox(); self.width_spin.setRange(160, 7680); self.width_spin.setValue(800)
        self.height_spin = QSpinBox(); self.height_spin.setRange(120, 4320); self.height_spin.setValue(600)
        res_row.addWidget(self.width_spin)
        res_row.addWidget(QLabel("x"))
        res_row.addWidget(self.height_spin)
        perf_layout.addLayout(res_row, 0, 1)

        perf_layout.addWidget(QLabel("FPS (Cible):"), 1, 0)
        self.fps_spin = QSpinBox(); self.fps_spin.setRange(1, 240); self.fps_spin.setValue(60)
        perf_layout.addWidget(self.fps_spin, 1, 1)

        main_layout.addWidget(perf_group)

        # --- Section Couleurs ---
        col_group = QGroupBox("Environnement")
        col_layout = QGridLayout(col_group)
        col_layout.setSpacing(10)

        def add_color_row(label, r_spin, g_spin, b_spin, row_idx):
            col_layout.addWidget(QLabel(label), row_idx, 0)
            row = QHBoxLayout()
            for s in (r_spin, g_spin, b_spin):
                s.setRange(0, 255)
                row.addWidget(s)
            col_layout.addLayout(row, row_idx, 1)

        self.bg_r = QSpinBox(); self.bg_g = QSpinBox(); self.bg_b = QSpinBox()
        add_color_row("Fond (RGB):", self.bg_r, self.bg_g, self.bg_b, 0)

        self.amb_r = QSpinBox(); self.amb_g = QSpinBox(); self.amb_b = QSpinBox()
        add_color_row("Ambiance (RGB):", self.amb_r, self.amb_g, self.amb_b, 1)

        main_layout.addWidget(col_group)

        self._load_from_editor()

        # --- Boutons ---
        main_layout.addStretch()
        btns = QHBoxLayout()
        btns.setSpacing(10)
        b_ok = QPushButton("Appliquer les changements")
        b_ok.setDefault(True)
        b_cancel = QPushButton("Annuler")
        b_ok.clicked.connect(self._apply)
        b_cancel.clicked.connect(self.reject)
        btns.addWidget(b_ok); btns.addWidget(b_cancel)
        main_layout.addLayout(btns)

    def _browse_icon(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choisir icône", "", "Images (*.png *.jpg *.ico *.bmp)")
        if p:
            self.icon_input.setText(Path(p).name)

    def _load_from_editor(self):
        text = self.editor.toPlainText()
        m = re.search(r'^TITLE\s+"([^"]*)"', text, re.MULTILINE)
        if m: self.title_input.setText(m.group(1))
        m = re.search(r'^ICON\s+"([^"]*)"', text, re.MULTILINE)
        if m: self.icon_input.setText(m.group(1))
        m = re.search(r'^SCREEN\s+(\d+)\s+(\d+)', text, re.MULTILINE)
        if m: self.width_spin.setValue(int(m.group(1))); self.height_spin.setValue(int(m.group(2)))
        m = re.search(r'^TICKRATE\s+(\d+)', text, re.MULTILINE)
        if m: self.fps_spin.setValue(int(m.group(1)))
        m = re.search(r'^BACKGROUND\s+(\d+)\s+(\d+)\s+(\d+)', text, re.MULTILINE)
        if m: self.bg_r.setValue(int(m.group(1))); self.bg_g.setValue(int(m.group(2))); self.bg_b.setValue(int(m.group(3)))
        m = re.search(r'^AMBIENT\s+(\d+)\s+(\d+)\s+(\d+)', text, re.MULTILINE)
        if m: self.amb_r.setValue(int(m.group(1))); self.amb_g.setValue(int(m.group(2))); self.amb_b.setValue(int(m.group(3)))

    def _apply(self):
        text = self.editor.toPlainText()

        def replace_or_prepend(pattern, new_line, txt):
            if re.search(pattern, txt, re.MULTILINE):
                return re.sub(pattern, new_line, txt, flags=re.MULTILINE)
            return new_line + '\n' + txt

        if self.title_input.text():
            text = replace_or_prepend(r'^TITLE\s+"[^"]*"', f'TITLE "{self.title_input.text()}"', text)
        if self.icon_input.text():
            text = replace_or_prepend(r'^ICON\s+"[^"]*"', f'ICON "{self.icon_input.text()}"', text)
        text = replace_or_prepend(r'^SCREEN\s+\d+\s+\d+',
                                   f'SCREEN {self.width_spin.value()} {self.height_spin.value()}', text)
        text = replace_or_prepend(r'^TICKRATE\s+\d+', f'TICKRATE {self.fps_spin.value()}', text)
        text = replace_or_prepend(r'^BACKGROUND\s+\d+\s+\d+\s+\d+',
                                   f'BACKGROUND {self.bg_r.value()} {self.bg_g.value()} {self.bg_b.value()}', text)
        text = replace_or_prepend(r'^AMBIENT\s+\d+\s+\d+\s+\d+',
                                   f'AMBIENT {self.amb_r.value()} {self.amb_g.value()} {self.amb_b.value()}', text)
        self.editor.setPlainText(text)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.game_process = None
        self.current_theme = "tokyo_night"

        self.recent_files = []
        self.setWindowTitle('Cavern Engine')
        self.resize(1600, 950)
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setStyleSheet(build_qss(self.current_theme))
        self._buildUI()
        self._buildMenus()
        self._buildToolbar()

    def _buildUI(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        left_panel = QSplitter(Qt.Orientation.Vertical)

        self.fsmodel = QFileSystemModel()
        self.fsmodel.setRootPath(str(Path(__file__).parent))
        self.tree = QTreeView()
        self.tree.setModel(self.fsmodel)
        self.tree.setRootIndex(self.fsmodel.index(str(Path(__file__).parent)))
        for col in (1, 2, 3): self.tree.setColumnHidden(col, True)
        self.tree.setHeaderHidden(True)
        self.tree.doubleClicked.connect(self._openFromTree)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._treeContextMenu)
        left_panel.addWidget(self.tree)

        self.scene_manager = SceneManager()
        self.scene_manager.scene_selected.connect(self._open_scene)
        self.scene_manager.refresh(str(Path(__file__).parent))
        left_panel.addWidget(self.scene_manager)

        self.asset_explorer = AssetExplorer()
        self.asset_explorer.asset_dropped.connect(self._insert_asset)
        self.asset_explorer.refresh(str(Path(__file__).parent))
        left_panel.addWidget(self.asset_explorer)

        left_panel.setSizes([300, 150, 200])
        self.splitter.addWidget(left_panel)

        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._closeTab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        cl.addWidget(self.tabs, stretch=3)

        self.console = QTextEdit()
        self.console.setObjectName("Console")
        self.console.setReadOnly(True)
        self.console.setFixedHeight(140)
        cl.addWidget(self.console)
        self.splitter.addWidget(center)

        self._status_bar = self.statusBar()
        self._status_bar.setStyleSheet("QStatusBar { background: #16161e; color: #565f89; border-top: 1px solid rgba(255,255,255,0.05); }")
        self._status_line_col = QLabel("  Ln 1, Col 1  ")
        self._status_file = QLabel("  Prêt  ")
        self._status_bar.addPermanentWidget(self._status_file)
        self._status_bar.addPermanentWidget(self._status_line_col)

        right_panel = QSplitter(Qt.Orientation.Vertical)

        doc_html = self._build_doc_html()
        doc_wid = QTextEdit()
        doc_wid.setReadOnly(True)
        doc_wid.setHtml(doc_html)

        doc_cont = QWidget()
        dl = QVBoxLayout(doc_cont)
        dl.addWidget(QLabel("<b style='color:#565f89; font-size: 14px;'>Documentation</b>"))
        dl.addWidget(doc_wid)
        right_panel.addWidget(doc_cont)

        self.var_monitor = VariableMonitor()
        right_panel.addWidget(self.var_monitor)

        right_panel.setSizes([500, 250])
        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([250, 1000, 400])

    def _build_doc_html(self):
        return """
        <style>
            .container { font-family: 'Inter', sans-serif; color: #a9b1d6; padding: 15px; }
            .header { text-align: center; margin-bottom: 25px; border-bottom: 2px solid #7aa2f7; padding-bottom: 10px; }
            .header h1 { color: #7aa2f7; margin: 0; font-size: 22px; }
            .header p { color: #565f89; margin: 5px 0 0 0; font-size: 14px; }
            
            .section { margin-bottom: 30px; }
            .card { background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 18px; margin-bottom: 15px; }
            .card h3 { margin-top: 0; color: #bb9af7; font-size: 17px; display: flex; align-items: center; gap: 8px; }
            
            .cmd { margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.03); }
            .cmd:last-child { border-bottom: none; }
            .syntax { font-family: 'JetBrains Mono', monospace; color: #ff9e64; font-weight: bold; font-size: 13px; display: block; margin-bottom: 4px; }
            .desc { color: #9aa5ce; font-size: 12px; line-height: 1.4; display: block; }
            
            .tip { background: rgba(122,162,247,0.1); border-left: 4px solid #7aa2f7; padding: 12px; border-radius: 6px; font-size: 13px; margin-bottom: 20px; color: #7aa2f7; }
            b { color: #bb9af7; }
            code { background: rgba(0,0,0,0.4); padding: 2px 6px; border-radius: 4px; color: #9ece6a; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
        </style>
        <div class='container'>
            <div class='header'>
                <h1>📘 Guide de Référence Cavern</h1>
                <p>Moteur de jeu 2D - Version 2026.3</p>
            </div>
            
            <div class='tip'>
                💡 <b>Astuce :</b> Appuyez sur <code>F5</code> pour lancer le jeu. Utilisez <code>F3</code> en cours de jeu pour afficher les boîtes de collision (hitboxes).
            </div>

            <div class='section'>
                <div class='card'>
                    <h3>🏗️ Objets & Initialisation</h3>
                    <div class='cmd'>
                        <span class='syntax'>SPRITE [nom] "[image].png" AT [x] [y]</span>
                        <span class='desc'>Crée un objet image fixe. Par défaut, l'origine est en haut à gauche.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>ANIM_SPRITE [nom] "[sheet].png" FRAMES [w] [h] [n] [fps] AT [x] [y]</span>
                        <span class='desc'>Crée un sprite animé à partir d'une feuille de sprites (tilesheet). <i>w/h</i>: taille d'une frame, <i>n</i>: nombre total, <i>fps</i>: vitesse.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>TEXT [nom] "[contenu]" AT [x] [y]</span>
                        <span class='desc'>Affiche du texte à l'écran. Modifiable dynamiquement via <code>UPDATE_TEXT</code>.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>TILEMAP [nom] "[data].json" TILESET "[ts].png" SIZE [s]</span>
                        <span class='desc'>Charge une carte de tuiles. Le fichier JSON doit contenir une matrice d'IDs.</span>
                    </div>
                </div>

                <div class='card'>
                    <h3>🌍 Environnement & Audio</h3>
                    <div class='cmd'>
                        <span class='syntax'>BACKGROUND [r] [g] [b]</span>
                        <span class='desc'>Définit la couleur de fond par défaut (0-255).</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>AMBIENT [r] [g] [b]</span>
                        <span class='desc'>Définit la couleur de la lumière ambiante globale (système d'éclairage).</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>MUSIC "[fichier].mp3" [VOLUME v]</span>
                        <span class='desc'>Lance une musique en boucle. Volume de 0.0 à 1.0.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>PARALLAX "[image].png" [vitesse]</span>
                        <span class='desc'>Ajoute un fond qui défile à une vitesse différente de la caméra.</span>
                    </div>
                </div>

                <div class='card'>
                    <h3>⚡ Événements & Contrôle</h3>
                    <div class='cmd'>
                        <span class='syntax'>WHEN UPDATE: [bloc]</span>
                        <span class='desc'>Le bloc de code exécuté à chaque image (frame). C'est ici que l'on place la logique de jeu.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>IF KEY "[touche]": [action]</span>
                        <span class='desc'>Déclenche une action si une touche est pressée (ex: "space", "left", "w").</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>ON_COLLIDE [obj1] [obj2]: [action]</span>
                        <span class='desc'>Déclenche une action quand deux objets se touchent (AABB collision).</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>IF MOUSE CLICK: [action]</span>
                        <span class='desc'>Déclenche une action lors d'un clic gauche de souris.</span>
                    </div>
                </div>

                <div class='card'>
                    <h3>🛠️ Actions & Mouvements</h3>
                    <div class='cmd'>
                        <span class='syntax'>MOVE [obj] [dx] [dy]</span>
                        <span class='desc'>Déplace un objet relativement à sa position actuelle.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>GOTO [obj] [x] [y]</span>
                        <span class='desc'>Téléporte un objet à des coordonnées précises.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>LERP_TO [obj] [x] [y] [t]</span>
                        <span class='desc'>Déplace fluidement un objet vers une cible (interpolation linéaire). <i>t</i> entre 0 et 1.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>SHAKE [intensité] [durée]</span>
                        <span class='desc'>Fait trembler la caméra pour un effet d'impact.</span>
                    </div>
                </div>

                <div class='card'>
                    <h3>🧪 Physique & Particules</h3>
                    <div class='cmd'>
                        <span class='syntax'>PHYSICS [obj] GRAVITY [g] FRICTION [f] BOUNCE [b]</span>
                        <span class='desc'>Active la physique sur un objet. <i>g</i>: force vers le bas, <i>f</i>: ralentissement, <i>b</i>: rebond.</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>VELOCITY [obj] [vx] [vy] / FORCE [obj] [fx] [fy]</span>
                        <span class='desc'>Modifie la vitesse actuelle ou applique une force instantanée (nécessite PHYSICS).</span>
                    </div>
                    <div class='cmd'>
                        <span class='syntax'>SPAWN_PARTICLES [x] [y] COLOR [r g b] COUNT [n]</span>
                        <span class='desc'>Génère une explosion de particules colorées à une position donnée.</span>
                    </div>
                </div>

                <div class='card' style='background: rgba(158,238,106,0.05); border-color: rgba(158,238,106,0.1);'>
                    <h3 style='color:#9ece6a;'>🧮 Fonctions Mathématiques</h3>
                    <div class='cmd'>
                        <span class='desc'>
                            <code>SIN(a)</code>, <code>COS(a)</code>, <code>TAN(a)</code> (angles en degrés)<br>
                            <code>ABS(x)</code>, <code>SQRT(x)</code>, <code>FLOOR(x)</code>, <code>CEIL(x)</code><br>
                            <code>CLAMP(val, min, max)</code>, <code>DISTANCE(x1,y1,x2,y2)</code><br>
                            <code>RANDINT(min, max)</code>, <code>RANDF(min, max)</code>
                        </span>
                    </div>
                    <div class='cmd'>
                        <span class='desc' style='color:#565f89;'>
                            Variables système : <code>MOUSE_X</code>, <code>MOUSE_Y</code>, <code>TIME</code> (secondes écoulées), 
                            <code>FPS</code>, <code>SCREEN_WIDTH</code>, <code>SCREEN_HEIGHT</code>
                        </span>
                    </div>
                </div>
            </div>
        </div>
        """

    def _buildMenus(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        a = QAction("Nouveau Fichier", self); a.setShortcut("Ctrl+N"); a.triggered.connect(self.newFile); fm.addAction(a)
        a = QAction("Ouvrir…", self); a.setShortcut("Ctrl+O"); a.triggered.connect(self._openFile); fm.addAction(a)
        a = QAction("Sauvegarder", self); a.setShortcut("Ctrl+S"); a.triggered.connect(self.saveFile); fm.addAction(a)
        a = QAction("Sauvegarder sous…", self); a.setShortcut("Ctrl+Shift+S"); a.triggered.connect(self._saveAs); fm.addAction(a)
        fm.addSeparator()
        self._recent_menu = fm.addMenu("Fichiers récents")
        fm.addSeparator()
        a = QAction("Quitter", self); a.triggered.connect(self.close); fm.addAction(a)

        bm = mb.addMenu("Build")
        a = QAction("Run jeu .cave", self); a.setShortcut("F5"); a.triggered.connect(self._runCave); bm.addAction(a)
        a = QAction("Créer exécutable PyInstaller", self); a.setShortcut("F6"); a.triggered.connect(self._buildExe); bm.addAction(a)

        em = mb.addMenu("Edit")
        a = QAction("Auto-Format", self); a.setShortcut("Ctrl+Shift+F"); a.triggered.connect(self._autoFormat); em.addAction(a)
        a = QAction("Chercher / Remplacer", self); a.setShortcut("Ctrl+F"); a.triggered.connect(self._openFindReplace); em.addAction(a)
        em.addSeparator()
        a = QAction("Dupliquer la ligne", self); a.setShortcut("Ctrl+D"); a.triggered.connect(self._duplicateLine); em.addAction(a)
        a = QAction("Commenter / Décommenter", self); a.setShortcut("Ctrl+/"); a.triggered.connect(self._toggleComment); em.addAction(a)
        em.addSeparator()
        a = QAction("Paramètres du projet…", self); a.setShortcut("Ctrl+,"); a.triggered.connect(self._projectSettings); em.addAction(a)

        vm = mb.addMenu("View")
        tm = vm.addMenu("Thème")
        for theme_key, theme_data in THEMES.items():
            a = QAction(theme_data["name"], self)
            a.setData(theme_key)
            a.triggered.connect(self._changeTheme)
            tm.addAction(a)

    def _buildToolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        def act(label, icon_char, shortcut, slot, tip):
            a = QAction(label, self)
            a.setText(f"{icon_char} {label}")
            if shortcut: a.setShortcut(shortcut)
            a.setToolTip(tip)
            a.triggered.connect(slot)
            tb.addAction(a)

        from PyQt6.QtWidgets import QSizePolicy
        act("Nouveau", "📄", "Ctrl+N", self.newFile, "Nouveau fichier (Ctrl+N)")
        act("Ouvrir", "📂", "Ctrl+O", self._openFile, "Ouvrir un fichier (Ctrl+O)")
        act("Sauvegarder", "💾", "Ctrl+S", self.saveFile, "Sauvegarder (Ctrl+S)")
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        act("Run Jeu", "▶", "F5", self._runCave, "Lancer le projet (F5)")
        
        spacer2 = QWidget()
        spacer2.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer2)

        act("Auto-Format", "✨", "Ctrl+Shift+F", self._autoFormat, "Nettoyer le code")
        act("Build EXE", "📦", "F6", self._buildExe, "Créer un exécutable")
        act("Chercher", "🔍", "Ctrl+F", self._openFindReplace, "Chercher / Remplacer")
        tb.addSeparator()
        act("Projet", "⚙", "Ctrl+,", self._projectSettings, "Paramètres du projet")

    def _openFile(self):
        p, _ = QFileDialog.getOpenFileName(self, "Ouvrir", "", "Cave (*.cave);;Python (*.py);;Tous (*)")
        if p:
            self._open_path(p)

    def _open_path(self, p):
        e = CodeEditor(path=p)
        try:
            with open(p, 'r', encoding='utf-8') as f:
                e.setPlainText(f.read())
        except Exception:
            return
        self.tabs.addTab(e, Path(p).name)
        self.tabs.setCurrentWidget(e)
        self._add_recent(p)

    def _saveAs(self):
        e = self.currentEditor()
        if not e:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Sauvegarder sous", "", "Cave (*.cave);;All (*)")
        if p:
            e.file_path = p
            self.saveFile()

    def _add_recent(self, path):
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self._recent_menu.clear()
        for p in self.recent_files:
            a = QAction(Path(p).name, self)
            a.setData(p)
            a.setToolTip(p)
            a.triggered.connect(lambda checked, fp=p: self._open_path(fp))
            self._recent_menu.addAction(a)

    def _duplicateLine(self):
        e = self.currentEditor()
        if not e:
            return
        cursor = e.textCursor()
        cursor.select(cursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText()
        cursor.movePosition(cursor.MoveOperation.EndOfLine)
        cursor.insertText('\n' + line)
        e.setTextCursor(cursor)

    def _toggleComment(self):
        e = self.currentEditor()
        if not e:
            return
        cursor = e.textCursor()
        if cursor.hasSelection():
            start = cursor.selectionStart()
            end = cursor.selectionEnd()
            cursor.setPosition(start)
            cursor.movePosition(cursor.MoveOperation.StartOfLine)
            cursor.setPosition(end, cursor.MoveMode.KeepAnchor)
            cursor.movePosition(cursor.MoveOperation.EndOfLine, cursor.MoveMode.KeepAnchor)
            text = cursor.selectedText()
            lines = text.split(' ')
        else:
            cursor.select(cursor.SelectionType.LineUnderCursor)
            text = cursor.selectedText()
            lines = [text]

        toggled = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('# '):
                toggled.append(line.replace('# ', '', 1))
            elif stripped.startswith('#'):
                toggled.append(line.replace('#', '', 1))
            else:
                indent = len(line) - len(stripped)
                toggled.append(line[:indent] + '# ' + stripped)
        cursor.insertText(' '.join(toggled))

    def _projectSettings(self):
        e = self.currentEditor()
        if not e:
            return
        dlg = ProjectSettingsDialog(e, self)
        if dlg.exec():
            self._log("Paramètres du projet mis à jour ✨", "#9ece6a")

    def _changeTheme(self):
        action = self.sender()
        theme_key = action.data()
        self.current_theme = theme_key
        app = QApplication.instance()
        app.setStyleSheet(build_qss(theme_key))
        for i in range(self.tabs.count()):
            e = self.tabs.widget(i)
            if isinstance(e, CodeEditor):
                e.highlighter.set_theme(theme_key)
        self._log(f"Thème changé: {THEMES[theme_key]['name']}", "#9ece6a")

    def _autoFormat(self):
        e = self.currentEditor()
        if not e:
            return
        lines = e.toPlainText().split('\n')
        formatted = []
        indent = 0
        block_openers = {'WHEN UPDATE:', 'ELSE:', 'ELSE'}
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                formatted.append(stripped)
                continue
            if stripped == 'END':
                indent = max(0, indent - 1)
                formatted.append('    ' * indent + stripped)
                continue
            if stripped.startswith(('ELIF ', 'ELSE')):
                formatted.append('    ' * max(0, indent - 1) + stripped)
            else:
                formatted.append('    ' * indent + stripped)
            if stripped.endswith(':') or stripped in block_openers:
                indent += 1
        e.setPlainText('\n'.join(formatted))
        self._log("Code auto-formaté ✨", "#9ece6a")

    def _openFindReplace(self):
        e = self.currentEditor()
        if not e:
            return
        dlg = FindReplaceDialog(e, self)
        dlg.show()

    def _update_tab_title(self, editor):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) is editor:
                name = Path(editor.file_path).name if editor.file_path else "untitled.cave"
                self.tabs.setTabText(i, ("* " if editor._modified else "") + name)
                break

    def _on_tab_changed(self, _):
        e = self.currentEditor()
        if e:
            e.cursorPositionChanged.connect(self._update_status_bar)
            self._update_status_bar()
            self._status_file.setText(Path(e.file_path).name if e.file_path else "untitled")

    def _update_status_bar(self):
        e = self.currentEditor()
        if not e:
            return
        cursor = e.textCursor()
        ln = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self._status_line_col.setText(f"Ln {ln}, Col {col}")

    def _open_scene(self, scene_name):
        base = str(Path(__file__).parent)
        full = os.path.join(base, scene_name)
        if os.path.exists(full):
            e = CodeEditor(path=full)
            try:
                with open(full, 'r', encoding='utf-8') as f:
                    e.setPlainText(f.read())
            except Exception:
                return
            self.tabs.addTab(e, scene_name)
            self.tabs.setCurrentWidget(e)
        else:
            with open(full, 'w', encoding='utf-8') as f:
                f.write(f"# Scène: {scene_name}\nSCREEN 800 600\nBACKGROUND 20 20 30\n\nWHEN UPDATE:\n")
            e = CodeEditor(path=full)
            e.setPlainText(f"# Scène: {scene_name}\nSCREEN 800 600\nBACKGROUND 20 20 30\n\nWHEN UPDATE:\n")
            self.tabs.addTab(e, scene_name)
            self.tabs.setCurrentWidget(e)
            self.scene_manager.refresh(str(Path(__file__).parent))

    def _insert_asset(self, path):
        e = self.currentEditor()
        if not e:
            return
        name = Path(path).stem
        ext = Path(path).suffix.lower()
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            text = f'\nSPRITE {name} "{Path(path).name}" AT 100 100\n'
        elif ext in ['.mp3', '.wav', '.ogg']:
            text = f'\nMUSIC "{Path(path).name}"\n'
        else:
            return
        cursor = e.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        e.setTextCursor(cursor)
        self._log(f"Asset inséré: {Path(path).name}", "#9ece6a")

    def currentEditor(self):
        return self.tabs.currentWidget() if isinstance(self.tabs.currentWidget(), CodeEditor) else None

    def _openFromTree(self, i):
        p = self.fsmodel.filePath(i)
        if not self.fsmodel.isDir(i):
            self._open_path(p)

    def _treeContextMenu(self, pos):
        idx = self.tree.indexAt(pos)
        path_str = self.fsmodel.filePath(idx) if idx.isValid() else self.fsmodel.rootPath()
        menu = QMenu(self)
        a_nf = menu.addAction("Nouveau Fichier")
        a_nd = menu.addAction("Nouveau Dossier")
        a_ren = menu.addAction("Renommer") if idx.isValid() else None
        a_del = menu.addAction("Supprimer") if idx.isValid() else None
        action = menu.exec(self.tree.mapToGlobal(pos))
        if action == a_nf:
            name, ok = QInputDialog.getText(self, "Nouveau Fichier", "Nom du fichier:")
            if ok and name:
                new_p = Path(path_str) / name if os.path.isdir(path_str) else Path(path_str).parent / name
                new_p.touch()
                self.scene_manager.refresh(str(Path(__file__).parent))
                self.asset_explorer.refresh(str(Path(__file__).parent))
        elif action == a_nd:
            name, ok = QInputDialog.getText(self, "Nouveau Dossier", "Nom du dossier:")
            if ok and name:
                new_p = Path(path_str) / name if os.path.isdir(path_str) else Path(path_str).parent / name
                new_p.mkdir(exist_ok=True)
        elif a_del and action == a_del:
            ans = QMessageBox.question(self, "Supprimer", f"Voulez-vous vraiment supprimer {Path(path_str).name}?")
            if ans == QMessageBox.StandardButton.Yes:
                import shutil
                if os.path.isdir(path_str): shutil.rmtree(path_str)
                else: os.remove(path_str)
                self.scene_manager.refresh(str(Path(__file__).parent))
                self.asset_explorer.refresh(str(Path(__file__).parent))
        elif a_ren and action == a_ren:
            name, ok = QInputDialog.getText(self, "Renommer", "Nouveau nom:", text=Path(path_str).name)
            if ok and name:
                os.rename(path_str, Path(path_str).parent / name)

    def newFile(self):
        e = CodeEditor()
        self.tabs.addTab(e, "untitled.cave")
        self.tabs.setCurrentWidget(e)

    def saveFile(self):
        e = self.currentEditor()
        if e and e.file_path:
            with open(e.file_path, 'w', encoding='utf-8') as f: f.write(e.toPlainText())
            e.document().setModified(False)
            self._log(f"Sauvegardé: {Path(e.file_path).name}", "#9ece6a")
            self._add_recent(e.file_path)
            self.scene_manager.refresh(str(Path(__file__).parent))
            self.asset_explorer.refresh(str(Path(__file__).parent))
        elif e:
            p, _ = QFileDialog.getSaveFileName(self, "Save", "", "Cave (*.cave);;All (*)")
            if p:
                e.file_path = p
                self.saveFile()
        if e:
            self._update_tab_title(e)

    def _closeTab(self, i):
        e = self.tabs.widget(i)
        if isinstance(e, CodeEditor) and e._modified:
            ans = QMessageBox.question(self, "Fermer",
                                       "Ce fichier a des modifications non sauvegardées. Fermer quand même ?")
            if ans != QMessageBox.StandardButton.Yes:
                return
        self.tabs.removeTab(i)

    def _log(self, text, color="#a9b1d6"):
        self.console.append(f"<span style='color:{color}'>{text}</span>")

    def _runCave(self):
        e = self.currentEditor()
        if not e or not e.file_path: return self._log("Sauvegardez d'abord le fichier.", "#e0af68")
        self.saveFile()
        p = e.file_path
        if not p.endswith(".cave"): return self._log("Il faut un fichier .cave actif !", "#f7768e")
        out_py = p.replace(".cave", "_genere.py")
        self._log("Parser v2 analyse le code magique...", "#bb9af7")
        try:
            parser_langage_caverne(p, out_py)
        except Exception as ex:
            return self._log(str(ex), "#f7768e")

        self._log("Lancement de la grotte (Moteur Python v2)...", "#7aa2f7")
        try:
            if self.game_process:
                self.game_process.kill()
            self.game_process = QProcess(self)
            self.game_process.setProgram(sys.executable)
            self.game_process.setArguments([out_py])
            self.game_process.readyReadStandardError.connect(self._on_game_error)
            self.game_process.readyReadStandardOutput.connect(self._on_game_output)
            self.game_process.finished.connect(
                lambda exitCode, exitStatus: self._log(f"Jeu terminé proprement.", "#9aa5ce")
                if exitCode == 0 else self._log(f"Le jeu s'est arrêté avec une erreur (Code: {exitCode})", "#f7768e")
            )
            self.game_process.start()
        except Exception as ex:
            self._log(f"Échec lancement: {str(ex)}", "#f7768e")

    def _on_game_error(self):
        if self.game_process:
            err = self.game_process.readAllStandardError().data().decode('utf-8', 'replace').strip()
            if err:
                self._log(f"[CRASH DU JEU] : {err}", "#f7768e")

    def _on_game_output(self):
        if self.game_process:
            out = self.game_process.readAllStandardOutput().data().decode('utf-8', 'replace').strip()
            if out: self._log(f"[LOG JEU] : {out}", "#9aa5ce")

    def _buildExe(self):
        e = self.currentEditor()
        if not e or not e.file_path: return self._log("Sauvegardez d'abord !", "#e0af68")
        p = e.file_path.replace(".cave", "_genere.py")
        if not Path(p).exists(): return self._log("Appuyez sur F5 (Run) d'abord pour générer le code !", "#f7768e")
        self._log("Création de l'EXE PyInstaller (patientez... ça peut prendre 1min)", "#e0af68")
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", f"{sys.executable} -m PyInstaller --onefile --noconsole {p}; echo Fini; sleep 5"])

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

