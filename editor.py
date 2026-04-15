# Cavern Engine - 2D Game Engine & Editor
# Copyright (c) 2026 caperuisseau
# Licensed under the MIT License

import sys, os, subprocess, re, math, time, struct
from pathlib import Path
import urllib.request, urllib.parse, json

import pygame
import pygame.gfxdraw

from PyQt6.QtCore import Qt, QSize, QRegularExpression, QRect, QThread, pyqtSignal, QProcess, QTimer, QMimeData, QUrl
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

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

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
        import random
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

class Particle:
    def __init__(self, x, y, vx, vy, color, life, size=3, gravity=0):
        self.x = float(x)
        self.y = float(y)
        self.vx = float(vx)
        self.vy = float(vy)
        self.color = color
        self.life = float(life)
        self.max_life = float(life)
        self.size = float(size)
        self.gravity = float(gravity)
        self.alive = True

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if not self.alive:
            return
        alpha = max(0, min(255, int(255 * (self.life / self.max_life))))
        sx = int((self.x - cam_x) * zoom)
        sy = int((self.y - cam_y) * zoom)
        sz = max(1, int(self.size * zoom * (self.life / self.max_life)))
        if 0 <= sx < screen.get_width() and 0 <= sy < screen.get_height():
            try:
                surf = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                col = (*self.color[:3], alpha)
                pygame.draw.circle(surf, col, (sz, sz), sz)
                screen.blit(surf, (sx - sz, sy - sz))
            except Exception:
                pass

class ParticleEmitter:
    def __init__(self, x, y, ptype="fire", color=(255, 200, 50), speed=100, count=20, spread=360, life=1.0, gravity=0, size=3):
        import random
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
        self.emit_rate = 0.05

    def burst(self):
        import random
        for _ in range(self.count):
            angle = math.radians(random.uniform(0, self.spread))
            spd = self.speed * random.uniform(0.5, 1.5)
            vx = math.cos(angle) * spd
            vy = -math.sin(angle) * spd
            c = tuple(max(0, min(255, ch + random.randint(-30, 30))) for ch in self.color[:3])
            p = Particle(self.x, self.y, vx, vy, c, self.life * random.uniform(0.5, 1.2), self.size, self.gravity)
            self.particles.append(p)

    def goto(self, x, y):
        self.x, self.y = float(x), float(y)

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def update(self, dt):
        import random
        if self.continuous and self.active:
            self.emit_timer += dt
            while self.emit_timer >= self.emit_rate:
                self.emit_timer -= self.emit_rate
                angle = math.radians(random.uniform(0, self.spread))
                spd = self.speed * random.uniform(0.5, 1.5)
                vx = math.cos(angle) * spd
                vy = -math.sin(angle) * spd
                c = tuple(max(0, min(255, ch + random.randint(-30, 30))) for ch in self.color[:3])
                p = Particle(self.x, self.y, vx, vy, c, self.life * random.uniform(0.5, 1.2), self.size, self.gravity)
                self.particles.append(p)

        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        for p in self.particles:
            p.draw(screen, cam_x, cam_y, zoom)

class Light:
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

    def draw(self, light_surface, cam_x=0, cam_y=0, zoom=1.0):
        import random
        if not self.visible:
            return
        sx = int((self.x - cam_x) * zoom)
        sy = int((self.y - cam_y) * zoom)
        r = int(self.radius * zoom)
        if self.flicker:
            r += random.randint(-int(self.flicker_amount), int(self.flicker_amount))
        if r <= 0:
            return
        light_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -2):
            alpha = int(self.intensity * (i / r))
            alpha = max(0, min(255, alpha))
            col = (*self.color[:3], alpha)
            pygame.draw.circle(light_surf, col, (r, r), i)
        light_surface.blit(light_surf, (sx - r, sy - r), special_flags=pygame.BLEND_RGBA_ADD)

class ParallaxLayer:
    def __init__(self, image_path, speed_factor=0.5):
        self.speed_factor = float(speed_factor)
        try:
            self.image = pygame.image.load(image_path).convert_alpha()
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
            sheet = pygame.image.load(sheet_path).convert_alpha()
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
                    w = int(self.original_image.get_width() * self.scale_factor)
                    h = int(self.original_image.get_height() * self.scale_factor)
                    self.image = pygame.transform.scale(self.original_image, (w, h))
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
        w = int(self.original_image.get_width() * self.scale_factor)
        h = int(self.original_image.get_height() * self.scale_factor)
        self.image = pygame.transform.scale(self.original_image, (w, h))
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
        self.image = self.original_image
        if self.scale_factor != 1.0:
            self.set_scale(self.scale_factor)

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if self.visible:
            temp_img = self.image
            if self.angle != 0:
                temp_img = pygame.transform.rotate(self.image, self.angle)

            if zoom != 1.0:
                zw = int(temp_img.get_width() * zoom)
                zh = int(temp_img.get_height() * zoom)
                temp_img = pygame.transform.scale(temp_img, (zw, zh))

            if self.alpha < 255:
                temp_img = temp_img.copy()
                temp_img.set_alpha(self.alpha)

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
            self.original_image = pygame.image.load(image_path).convert_alpha()
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

    def draw(self, screen, cam_x=0, cam_y=0, zoom=1.0):
        if self.visible:
            temp_img = self.image
            if self.angle != 0:
                temp_img = pygame.transform.rotate(self.image, self.angle)

            if zoom != 1.0:
                zw = int(temp_img.get_width() * zoom)
                zh = int(temp_img.get_height() * zoom)
                temp_img = pygame.transform.scale(temp_img, (zw, zh))

            if self.alpha < 255:
                temp_img = temp_img.copy()
                temp_img.set_alpha(self.alpha)

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
    def __init__(self, width=800, height=600):
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

        self.scenes = {}
        self.current_scene = None

        self.watched_vars = {}

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

    def add_sprite(self, sprite):
        self.sprites.append(sprite)

    def destroy(self, sprite):
        if sprite in self.sprites:
            self.sprites.remove(sprite)
        for g in self.sprite_groups.values():
            g.remove(sprite)

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

    def spawn_particles(self, x, y, ptype="fire", color=(255, 200, 50), count=20, speed=100, life=1.0, gravity=0, size=3):
        em = ParticleEmitter(x, y, ptype, color, speed, count, 360, life, gravity, size)
        em.burst()
        self.particles.append(em)
        return em

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

    def raycast(self, x1, y1, x2, y2, targets=None):
        if targets is None:
            targets = self.sprites
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(int(dx)), abs(int(dy)), 1)
        step_x = dx / steps
        step_y = dy / steps
        for i in range(steps):
            px = x1 + step_x * i
            py = y1 + step_y * i
            for t in targets:
                if hasattr(t, 'rect') and t.rect.collidepoint(int(px), int(py)):
                    return t
        return None

    def wait(self, seconds, callback):
        self.wait_timers.append({"remaining": float(seconds), "callback": callback})

    def _update_timers(self, dt):
        finished = []
        for timer in self.wait_timers:
            timer["remaining"] -= dt
            if timer["remaining"] <= 0:
                timer["callback"]()
                finished.append(timer)
        for t in finished:
            self.wait_timers.remove(t)

    def lerp(self, a, b, t):
        return a + (b - a) * max(0, min(1, float(t)))

    def enable_bloom(self, intensity=1.5):
        self.bloom_enabled = True
        self.bloom_intensity = float(intensity)

    def enable_blur(self):
        self.blur_enabled = True

    def enable_grayscale(self):
        self.grayscale_enabled = True

    def disable_effects(self):
        self.bloom_enabled = False
        self.blur_enabled = False
        self.grayscale_enabled = False

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

    def run(self):
        import os, sys
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        try:
            logo_img = pygame.image.load(logo_path).convert_alpha()
        except:
            try:
                logo_img = pygame.image.load("logo.png").convert_alpha()
            except:
                print("CRITICAL: Protection Cavern-Engine activated. Cannot start without logo.png at root.")
                sys.exit(1)

        logo_img = pygame.transform.scale(logo_img, (300, 300))
        logo_rect = logo_img.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 - 30))

        pygame.font.init()
        font_splash = pygame.font.SysFont("Verdana", 24, bold=True)
        text_splash = font_splash.render("BUILT WITH CAVERN-ENGINE 2026.1", True, (255, 255, 255))
        text_rect = text_splash.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 + 150))

        show_splash = True
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
                font_easter = pygame.font.SysFont("Verdana", 24, bold=False, italic=True)
                easter_surf = font_easter.render("caperuisseau | Cavern-Engine", True, (150, 150, 255))
                easter_rect = easter_surf.get_rect(center=(self.screen.get_width()//2, self.screen.get_height()//2 + 200))
                self.screen.blit(easter_surf, easter_rect)

            pygame.display.flip()

            if pygame.time.get_ticks() - splash_start > 3000:
                show_splash = False

        running = True
        self.clock.tick(self.fps)
        while running:
            dt = self.clock.tick(self.fps) / 1000.0

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

            if self.update_func:
                self.update_func(dt)

            self.screen.fill(self.bg_color)

            for layer in self.parallax_layers:
                layer.draw(self.screen, cam_x, cam_y)

            for s in self.shapes:
                s.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            for sprite in self.sprites:
                sprite.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            for em in self.particles:
                em.draw(self.screen, cam_x, cam_y, self.camera.zoom)

            if self.use_lighting and self.lights:
                light_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                light_surface.fill((*self.ambient_light, 255))
                for light in self.lights:
                    light.draw(light_surface, cam_x, cam_y, self.camera.zoom)
                self.screen.blit(light_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            if self.debug_hitbox:
                self._draw_debug_hitboxes()

            if self.bloom_enabled or self.blur_enabled or self.grayscale_enabled:
                self.screen = self._apply_post_processing(self.screen)

            pygame.display.flip()
        pygame.quit()

def translate_condition(cond):
    cond = cond.strip()
    if cond.startswith("KEY "):
        touche = cond[4:].strip()
        return f'engine.is_key_pressed("{touche}")'
    if cond == "MOUSE CLICK":
        return 'engine.is_mouse_clicked()'

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
        elif m[0] == "DESTROY": return f'engine.destroy({m[1]})'
        elif m[0] == "PLAY_SOUND":
            vol = m[2] if len(m) > 2 else "1.0"
            return f'engine.play_sound({m[1]}, {vol})'
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
        elif m[0] == "STOP_MUSIC": return f'engine.stop_music()'
        elif m[0] == "PAUSE_MUSIC": return f'engine.pause_music()'
        elif m[0] == "RESUME_MUSIC": return f'engine.resume_music()'
        elif m[0] == "SOUND_VOLUME": return f'engine.set_sound_volume({m[1]})'
        elif m[0] == "MUSIC_VOLUME": return f'engine.set_music_volume({m[1]})'
        elif m[0] == "BLOOM": return f'engine.enable_bloom({m[1] if len(m) > 1 else 1.5})'
        elif m[0] == "BLUR": return f'engine.enable_blur()'
        elif m[0] == "GRAYSCALE": return f'engine.enable_grayscale()'
        elif m[0] == "NO_EFFECTS": return f'engine.disable_effects()'
        elif m[0] == "FONT_SIZE": return f'{m[1]}.set_font_size({m[2]})'
        elif m[0] == "PLAY_ANIM": return f'{m[1]}.play()'
        elif m[0] == "PAUSE_ANIM": return f'{m[1]}.pause()'
        elif m[0] == "SET_FRAME": return f'{m[1]}.set_frame({m[2]})'
        elif m[0] == "BACKGROUND": return f'engine.set_bg({m[1]}, {m[2]}, {m[3]})'
        elif m[0] == "AMBIENT": return f'engine.set_ambient({m[1]}, {m[2]}, {m[3]})'
        elif m[0] == "TICKRATE": return f'engine.set_fps({m[1]})'
        elif m[0] == "CAMERA" and len(m) > 1 and m[1] == "FOLLOW": return f'engine.camera_follow({m[2]})'
        elif m[0] == "WAIT":
            wait_parts = act_str.split(":", 1)
            time_val = wait_parts[0].strip().split()[1]
            sub_action = parse_action(wait_parts[1].strip(), dt=False)
            return f'engine.wait({time_val}, lambda: {sub_action})'
        elif m[0] == "SET":
            parts = act_str.split("=", 1)
            nom = parts[0].strip().split(None, 1)[1]
            val = parts[1].strip()
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
                except: pass
        else:
            lignes.append(lb)

    code = [
        "from editor import MiniEngine, Sprite, Text, AnimatedSprite, SpriteGroup, Shape, Light, ParticleEmitter, ParallaxLayer, Camera",
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

                if not (ligne.startswith("ELSE") or ligne.startswith("ELIF ")):
                    indentation += 1

                dans_block = True
                current_indent = "    " * indentation
                continue

            elif ligne == "END":
                indentation -= 1
                dans_block = indentation > 0
                current_indent = "    " * indentation
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
                nom, val = p_var[0].strip(), p_var[1].strip()
                if nom not in global_vars:
                    global_vars.append(nom)
                    code.insert(7, f"{nom} = 0")
                code.append(f"{ind}{nom} = {val}")

            elif ligne.startswith("CONST "):
                p_const = ligne[6:].split("=", 1)
                nom, val = p_const[0].strip(), p_const[1].strip()
                global_vars.append(nom)
                code.insert(7, f"{nom} = {val}")

            elif mots[0] == "SPRITE" and len(mots) >= 6:
                args_c = split_cave_args(ligne)
                nom, img, x, y = args_c[1], args_c[2], args_c[4], args_c[5]
                code.extend([f'{ind}{nom} = Sprite({img}, {x}, {y})', f'{ind}engine.add_sprite({nom})'])
                if nom not in global_vars: global_vars.append(nom)

            elif mots[0] == "TEXT" and len(mots) >= 6:
                args_c = split_cave_args(ligne)
                nom, txt, x, y = args_c[1], args_c[2], args_c[4], args_c[5]
                code.extend([f'{ind}{nom} = Text({txt}, {x}, {y})', f'{ind}engine.add_sprite({nom})'])
                if nom not in global_vars: global_vars.append(nom)

            elif mots[0] == "LIGHT" and len(mots) >= 6:
                args_c = split_cave_args(ligne)
                nom = args_c[1]
                x, y = args_c[3], args_c[4]
                r = args_c[6]
                col = "(255, 255, 200)"
                if "COLOR" in args_c:
                    idx = args_c.index("COLOR")
                    col = f"({args_c[idx+1]}, {args_c[idx+2]}, {args_c[idx+3]})"
                code.append(f'{ind}{nom} = engine.create_light({x}, {y}, {r}, {col})')
                if nom not in global_vars: global_vars.append(nom)

            elif ligne.startswith("GROUP "):
                code.append(f'{ind}{mots[1]} = engine.create_group("{mots[1]}")')
                if mots[1] not in global_vars: global_vars.append(mots[1])

            elif ligne.startswith("SCREEN "):
                screen_w, screen_h = int(mots[1]), int(mots[2])
                code.append(f'engine.set_screen_size({screen_w}, {screen_h})')

            elif ligne.startswith("TICKRATE "):
                code.append(f'engine.set_fps({mots[1]})')

            elif ligne.startswith("BACKGROUND "):
                code.append(f'{ind}engine.set_bg({mots[1]}, {mots[2]}, {mots[3]})')

            elif ligne.startswith("AMBIENT "):
                code.append(f'{ind}engine.set_ambient({mots[1]}, {mots[2]}, {mots[3]})')

            elif ligne.startswith("PHYSICS "):
                nom = mots[1]
                code.append(f'{ind}{nom}.physics_enabled = True')
                if "GRAVITY" in ligne: 
                    g_match = re.search(r"GRAVITY\s+([0-9.-]+)", ligne)
                    if g_match: code.append(f'{ind}{nom}.gravity = {g_match.group(1)}')
                if "FRICTION" in ligne: 
                    f_match = re.search(r"FRICTION\s+([0-9.-]+)", ligne)
                    if f_match: code.append(f'{ind}{nom}.friction = {f_match.group(1)}')

            elif ligne.startswith("CAMERA FOLLOW "):
                code.append(f'{ind}engine.camera_follow({mots[2]})')

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
        "menu_hover": "rgba(122,162,247,0.2)",
        "input_border": "rgba(255,255,255,0.1)",
        "button": "#7aa2f7",
        "button_hover": "#89b0ff",
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
    },
}

def build_qss(theme):
    t = THEMES.get(theme, THEMES["tokyo_night"])
    return f"""
    * {{ font-family: "Inter", "Segoe UI", sans-serif; }}
    QMainWindow {{ background: {t['bg']}; }}
    QSplitter {{ background: {t['bg']}; }}
    QSplitter::handle {{ background: {t['splitter']}; width: 2px; }}
    QTreeView {{ background: {t['sidebar']}; border: none; color: {t['comment']}; font-size: 13px; padding-top: 6px; }}
    QTreeView::item {{ padding: 4px; border-radius: 4px; margin: 0 4px; }}
    QTreeView::item:hover {{ background: {t['menu_hover']}; color: {t['editor_fg']}; }}
    QTreeView::item:selected {{ background: {t['menu_hover']}; color: {t['editor_fg']}; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar {{ background: {t['tab_bg']}; }}
    QTabBar::tab {{ background: transparent; color: {t['comment']}; padding: 10px 24px; border-bottom: 2px solid transparent; font-size: 12px; font-weight: bold; }}
    QTabBar::tab:selected {{ color: {t['editor_fg']}; border-bottom: 2px solid {t['tab_active_border']}; background: {t['menu_hover']}; }}
    QPlainTextEdit {{ background: {t['editor_bg']}; color: {t['editor_fg']}; border: none; font-family: "JetBrains Mono", monospace; font-size: 14px; selection-background-color: {t['menu_hover']}; padding: 8px; }}
    QTextEdit {{ background: {t['sidebar']}; color: {t['editor_fg']}; border: none; padding: 10px; font-size: 13px; }}
    QMenuBar {{ background: {t['menu_bg']}; color: {t['editor_fg']}; padding: 4px; }}
    QMenuBar::item:selected {{ background: {t['menu_hover']}; border-radius: 4px; }}
    QMenu {{ background: {t['bg']}; color: {t['editor_fg']}; border-radius: 6px; padding: 4px; }}
    QMenu::item:selected {{ background: {t['menu_hover']}; }}
    QLineEdit {{ background: {t['editor_bg']}; color: {t['editor_fg']}; border: 1px solid {t['input_border']}; border-radius: 6px; padding: 6px; }}
    QPushButton {{ background: {t['button']}; color: white; border-radius: 6px; padding: 6px 12px; font-weight: bold; border: none; }}
    QPushButton:hover {{ background: {t['button_hover']}; }}
    QLabel {{ color: {t['editor_fg']}; }}
    QComboBox {{ background: {t['editor_bg']}; color: {t['editor_fg']}; border: 1px solid {t['input_border']}; border-radius: 4px; padding: 4px; }}
    QCheckBox {{ color: {t['editor_fg']}; }}
    QGroupBox {{ color: {t['accent']}; border: 1px solid {t['input_border']}; border-radius: 6px; margin-top: 8px; padding-top: 12px; font-weight: bold; }}
    QTableWidget {{ background: {t['editor_bg']}; color: {t['editor_fg']}; border: none; gridline-color: {t['splitter']}; }}
    QHeaderView::section {{ background: {t['sidebar']}; color: {t['comment']}; border: none; padding: 4px; }}
    QSlider::groove:horizontal {{ background: {t['splitter']}; height: 4px; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {t['accent']}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
    QScrollArea {{ border: none; background: {t['bg']}; }}
    QListWidget {{ background: {t['sidebar']}; color: {t['editor_fg']}; border: none; }}
    QListWidget::item:hover {{ background: {t['menu_hover']}; }}
    QListWidget::item:selected {{ background: {t['menu_hover']}; }}
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
            'BLOOM', 'BLUR', 'GRAYSCALE', 'NO_EFFECTS',
            'FADE_OUT_MUSIC', 'FADE_IN_MUSIC', 'STOP_MUSIC', 'PAUSE_MUSIC', 'RESUME_MUSIC',
            'SOUND_VOLUME', 'MUSIC_VOLUME', 'SPATIAL_SOUND',
            'FONT_SIZE', 'PLAY_ANIM', 'PAUSE_ANIM', 'SET_FRAME',
            'TICKRATE', 'SCREEN', 'CHROMA', 'CENTER', 'ROTATE', 'ALPHA', 'QUIT',
            'CAMERA_FOLLOW', 'CAMERA_ZOOM', 'CAMERA_SHAKE',
            'IF JOY_BUTTON', 'RADIUS', 'FRAMES',
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

class CodeEditor(QPlainTextEdit):
    def __init__(self, path=None, parent=None):
        super().__init__(parent)
        self.file_path = path
        self._modified = False
        self.setFont(QFont("JetBrains Mono", 13))
        self.highlighter = Highlighter(self.document())
        self.document().modificationChanged.connect(lambda m: setattr(self, "_modified", m))
        self.setAcceptDrops(True)

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
            "BLOOM", "BLUR", "GRAYSCALE", "NO_EFFECTS",
            "FADE_OUT_MUSIC", "FADE_IN_MUSIC", "STOP_MUSIC", "PAUSE_MUSIC", "RESUME_MUSIC",
            "SOUND_VOLUME", "MUSIC_VOLUME", "SPATIAL_SOUND",
            "FONT_SIZE", "PLAY_ANIM", "PAUSE_ANIM", "SET_FRAME",
            "TICKRATE", "SCREEN", "CHROMA", "CENTER", "ROTATE", "ALPHA", "QUIT",
            "CAMERA_FOLLOW", "CAMERA_ZOOM", "CAMERA_SHAKE",
            "SIN", "COS", "TAN", "ABS", "SQRT", "FLOOR", "CEIL", "CLAMP", "LERP",
            "DISTANCE", "ANGLE", "RANDINT", "RANDF",
            "MOUSE_X", "MOUSE_Y", "TIME", "SCREEN_WIDTH", "SCREEN_HEIGHT", "FPS",
            "RADIUS", "FRAMES",
        ]
        self.completer = QCompleter(kws, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self._insertCompletion)

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
        model = self.completer.model()
        from PyQt6.QtCore import QStringListModel
        self.completer.setModel(QStringListModel(sorted(all_words)))

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                event.ignore()
                return

        is_shortcut = (event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Space)

        if not is_shortcut:
            super().keyPressEvent(event)

        if not self.completer:
            return

        is_ctrl_or_shift = event.modifiers() in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier)
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
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) + self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)

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

class VariableMonitor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QLabel("<b style='color:#7aa2f7; font-size: 12px;'>📊 Variables Monitor</b>")
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

        header = QLabel("<b style='color:#bb9af7; font-size: 12px;'>🎬 Scènes</b>")
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

        header = QLabel("<b style='color:#9ece6a; font-size: 12px;'>🎨 Assets</b>")
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.game_process = None
        self.current_theme = "tokyo_night"

        self.setWindowTitle('Cavern Engine')
        self.resize(1600, 950)
        app = QApplication.instance()
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setStyleSheet(build_qss(self.current_theme))
        self._buildUI()
        self._buildMenus()

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
        cl.addWidget(self.tabs, stretch=3)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFixedHeight(140)
        cl.addWidget(self.console)
        self.splitter.addWidget(center)

        right_panel = QSplitter(Qt.Orientation.Vertical)

        doc_html = self._build_doc_html()
        doc_wid = QTextEdit()
        doc_wid.setReadOnly(True)
        doc_wid.setHtml(doc_html)
        doc_wid.setStyleSheet("background: #1a1b26; border: 1px solid rgba(255,255,255,0.05); border-radius: 8px;")

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
        <div style='line-height: 1.6; padding: 5px;'>
        <h2 style='color:#7aa2f7; text-align: center; margin-bottom: 15px;'>📘 Cavern Engine - Documentation</h2>

        <p style='color:#a9b1d6; font-size: 13px; margin-bottom: 15px; padding: 8px; background: rgba(122,162,247,0.05); border-radius: 6px;'>
        Un jeu s'écrit en <b>deux parties distinctes</b>. D'abord l'initialisation (qui charge la carte), puis la boucle temporelle (qui anime le monde).<br><br>
        💡 <b>Astuce :</b> Glissez une image dans l'éditeur pour auto-générer la ligne SPRITE ! Appuyez sur F3 en jeu pour voir les hitboxes.
        </p>

        <h3 style='color:#bb9af7; border-bottom: 1px solid #bb9af7; padding-bottom: 3px;'>PARTIE 1. Initialisation</h3>
        <ul style='margin-top: 5px; margin-bottom: 15px; padding-left: 20px;'>
            <li style='margin-bottom: 5px;'><b>SPRITE</b> <i>nom</i> "image.png" <b>AT</b> x y</li>
            <li style='margin-bottom: 5px;'><b>ANIMATED_SPRITE</b> <i>nom</i> "sheet.png" <b>FRAMES</b> w h count fps <b>AT</b> x y</li>
            <li style='margin-bottom: 5px;'><b>TEXT</b> <i>nom</i> "texte" <b>AT</b> x y</li>
            <li style='margin-bottom: 5px;'><b>BACKGROUND</b> R G B</li>
            <li style='margin-bottom: 5px;'><b>MUSIC</b> "audio.mp3"</li>
            <li style='margin-bottom: 5px;'><b>VAR</b> <i>nom</i> = <i>valeur</i> (Tableaux possibles : VAR inv = [1,2,3])</li>
            <li style='margin-bottom: 5px;'><b>CONST</b> <i>NOM</i> = <i>valeur</i></li>
            <li style='margin-bottom: 5px;'><b>PARALLAX</b> "fond.png" <i>facteur_vitesse</i></li>
            <li style='margin-bottom: 5px;'><b>LIGHT</b> <i>nom</i> AT x y RADIUS r [COLOR r g b]</li>
            <li style='margin-bottom: 5px;'><b>AMBIENT</b> R G B</li>
            <li style='margin-bottom: 5px;'><b>DRAW_RECT</b> <i>nom</i> x y w h [COLOR r g b]</li>
            <li style='margin-bottom: 5px;'><b>DRAW_CIRCLE</b> <i>nom</i> x y rayon [COLOR r g b]</li>
            <li style='margin-bottom: 5px;'><b>DRAW_LINE</b> <i>nom</i> x1 y1 x2 y2 [COLOR r g b]</li>
            <li style='margin-bottom: 5px;'><b>GROUP</b> <i>nom_groupe</i></li>
            <li style='margin-bottom: 5px;'><b>PHYSICS</b> <i>obj</i> [GRAVITY g] [FRICTION f] [BOUNCE b]</li>
            <li style='margin-bottom: 5px;'><b>CAMERA FOLLOW</b> <i>obj</i> / <b>CAMERA ZOOM</b> <i>z</i></li>
            <li style='margin-bottom: 5px;'><b>BLOOM</b> [intensité] / <b>BLUR</b> / <b>GRAYSCALE</b></li>
            <li style='margin-bottom: 5px;'><b>IMPORT</b> "autre_fichier.cave"</li>
            <li style='margin-bottom: 5px;'><b>SOUND_VOLUME</b> 0-1 / <b>MUSIC_VOLUME</b> 0-1</li>
            <li style='margin-bottom: 5px;'><b>FUNCTION</b> nom(args): ... <b>END</b></li>
        </ul>

        <h3 style='color:#7aa2f7; border-bottom: 1px solid #7aa2f7; padding-bottom: 3px;'>PARTIE 2. Boucle (WHEN UPDATE:)</h3>
        <ul style='margin-top: 5px; margin-bottom: 15px; padding-left: 20px;'>
            <li style='margin-bottom: 5px;'><b>IF KEY</b> <i>touche</i>: action</li>
            <li style='margin-bottom: 5px;'><b>IF MOUSE CLICK:</b> action</li>
            <li style='margin-bottom: 5px;'><b>IF JOY_BUTTON</b> joy_id button: action</li>
            <li style='margin-bottom: 5px;'><b>ON_COLLIDE</b> obj1 obj2: action</li>
            <li style='margin-bottom: 5px;'><b>ON_COLLIDE_CIRCLE</b> obj1 obj2: action</li>
            <li style='margin-bottom: 5px;'><b>ON_COLLIDE_GROUP</b> obj groupe: action</li>
            <li style='margin-bottom: 5px;'><b>IF</b> condition: action / <b>ELIF</b> / <b>ELSE:</b></li>
            <li style='margin-bottom: 5px;'><b>FOR</b> i <b>IN RANGE</b>(n): action</li>
            <li style='margin-bottom: 5px;'><b>WHILE</b> condition: action</li>
        </ul>

        <h3 style='color:#bb9af7; border-bottom: 1px solid #bb9af7; padding-bottom: 3px;'>Actions Rapides</h3>
        <ul style='margin-top: 5px; margin-bottom: 15px; padding-left: 20px;'>
            <li><b>MOVE</b> obj dx dy &nbsp; <b>GOTO</b> obj x y &nbsp; <b>SET</b> var = val</li>
            <li><b>VELOCITY</b> obj vx vy &nbsp; <b>FORCE</b> obj fx fy &nbsp; <b>LERP_TO</b> obj x y t</li>
            <li><b>SHAKE</b> intensité durée &nbsp; <b>SPAWN_PARTICLES</b> x y r g b count</li>
            <li><b>CAMERA_FOLLOW</b> obj &nbsp; <b>CAMERA_ZOOM</b> z &nbsp; <b>CAMERA_SHAKE</b> i d</li>
            <li><b>ADD_TO_GROUP</b> groupe obj</li>
            <li><b>SPATIAL_SOUND</b> "son" sx sy lx ly</li>
            <li><b>FADE_OUT_MUSIC</b> ms &nbsp; <b>FADE_IN_MUSIC</b> "f" ms</li>
            <li><b>STOP_MUSIC</b> / <b>PAUSE_MUSIC</b> / <b>RESUME_MUSIC</b></li>
            <li><b>PLAY_ANIM</b> obj / <b>PAUSE_ANIM</b> obj / <b>SET_FRAME</b> obj n</li>
            <li><b>BLOOM</b> / <b>BLUR</b> / <b>GRAYSCALE</b> / <b>NO_EFFECTS</b></li>
        </ul>

        <h3 style='color:#9ece6a; border-bottom: 1px solid #9ece6a; padding-bottom: 3px;'>Maths & Variables Système</h3>
        <ul>
            <li><b>SIN</b>, <b>COS</b>, <b>TAN</b>, <b>ABS</b>, <b>SQRT</b>, <b>FLOOR</b>, <b>CEIL</b></li>
            <li><b>CLAMP</b>(x, lo, hi), <b>LERP</b>(a, b, t), <b>DISTANCE</b>(x1,y1,x2,y2), <b>ANGLE</b>(x1,y1,x2,y2)</li>
            <li><b>RANDINT</b>(a, b), <b>RANDF</b>(a, b)</li>
            <li><b>MOUSE_X</b>, <b>MOUSE_Y</b>, <b>TIME</b>, <b>SCREEN_WIDTH</b>, <b>SCREEN_HEIGHT</b>, <b>FPS</b></li>
        </ul>
        </div>
        """

    def _buildMenus(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        a = QAction("New File", self); a.setShortcut("Ctrl+N"); a.triggered.connect(self.newFile); fm.addAction(a)
        a = QAction("Save", self); a.setShortcut("Ctrl+S"); a.triggered.connect(self.saveFile); fm.addAction(a)
        a = QAction("Quit", self); a.triggered.connect(self.close); fm.addAction(a)

        bm = mb.addMenu("Build")
        a = QAction("Run jeu .cave", self); a.setShortcut("F5"); a.triggered.connect(self._runCave); bm.addAction(a)
        a = QAction("Créer exécutable PyInstaller", self); a.setShortcut("F6"); a.triggered.connect(self._buildExe); bm.addAction(a)

        em = mb.addMenu("Edit")
        a = QAction("Auto-Format", self); a.setShortcut("Ctrl+Shift+F"); a.triggered.connect(self._autoFormat); em.addAction(a)

        vm = mb.addMenu("View")
        tm = vm.addMenu("Thème")
        for theme_key, theme_data in THEMES.items():
            a = QAction(theme_data["name"], self)
            a.setData(theme_key)
            a.triggered.connect(self._changeTheme)
            tm.addAction(a)

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
        for line in lines:
            stripped = line.strip()
            if stripped:
                formatted.append(stripped)
            else:
                formatted.append('')
        e.setPlainText('\n'.join(formatted))
        self._log("Code auto-formaté ✨", "#9ece6a")

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
            e = CodeEditor(path=p)
            try:
                with open(p, 'r', encoding='utf-8') as f: e.setPlainText(f.read())
            except Exception: return
            self.tabs.addTab(e, Path(p).name)
            self.tabs.setCurrentWidget(e)

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
            self._log("Fichier sauvegardé", "#9ece6a")
            self.scene_manager.refresh(str(Path(__file__).parent))
            self.asset_explorer.refresh(str(Path(__file__).parent))
        elif e:
            p, _ = QFileDialog.getSaveFileName(self, "Save", "", "Cave (*.cave);;All (*)")
            if p:
                e.file_path = p
                self.saveFile()
                self.tabs.setTabText(self.tabs.currentIndex(), Path(p).name)

    def _closeTab(self, i): self.tabs.removeTab(i)

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
