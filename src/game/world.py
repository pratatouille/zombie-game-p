"""Game world simulation: orchestrates players, arena, spawner, projectiles, effects, and camera."""

from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame

from src.game.camera import Camera
from src.game.effects import EffectManager
from src.game.items import Item, ItemSpawner
from src.game.platforms import create_arena, platform_rects, Platform
from src.game.player import Player
from src.game.projectiles import ProjectileManager
from src.game.zombie import ZombieSpawner

if TYPE_CHECKING:
    from src.game.assets import AssetManager
    from src.game.settings import GameConfig


class World:
    """Orchestrates all game entities, physics simulation, collisions, and world rendering."""

    def __init__(self, config: GameConfig, assets: AssetManager) -> None:
        self.config: GameConfig = config
        self.assets: AssetManager = assets

        # Arena world bounds (spacious arena for cinematic panning)
        self.world_bounds: pygame.Rect = pygame.Rect(0, 0, 1600, 860)

        self.camera: Camera = Camera(config.screen_size, self.world_bounds)
        self.effects: EffectManager = EffectManager()
        self.projectile_manager: ProjectileManager = ProjectileManager()
        self.platforms: list[Platform] = create_arena(self.world_bounds)
        self.spawner: ItemSpawner = ItemSpawner(config)
        self.items: list[Item] = []
        self.zombie_spawner: ZombieSpawner = ZombieSpawner(config, self.platforms, self.world_bounds)

        self.players: list[Player] = []
        self.left_player: Player
        self.right_player: Player

        self.reset()

    def reset(self) -> None:
        """Reset match state, spawn fresh players, and initiate cinematic intro camera."""
        self.effects.clear()
        self.projectile_manager = ProjectileManager()
        self.items.clear()
        self.platforms = create_arena(self.world_bounds)
        self.spawner = ItemSpawner(self.config)
        self.zombie_spawner = ZombieSpawner(self.config, self.platforms, self.world_bounds)

        # Spawn Player 1 (hero) on arena ground
        floor_y = float(self.world_bounds.bottom - 90)
        spawn_left = (self.world_bounds.width / 2.0, floor_y)
        p1 = Player(
            player_id=1,
            spawn=spawn_left,
            controls=self.config.controls.left,
            assets=self.assets,
            config=self.config,
        )
        p1.on_ground = True

        # Keep p2 reference so existing HUD code functions smoothly
        spawn_right = (float(self.world_bounds.right - 240), floor_y)
        p2 = Player(
            player_id=2,
            spawn=spawn_right,
            controls=self.config.controls.right,
            assets=self.assets,
            config=self.config,
        )
        p2.health = 0.0  # Solo PvE mode: player 1 is the solitary survivor

        self.players = [p1]
        self.left_player = p1
        self.right_player = p2

        # Start non-blocking intro pan sequence
        self.camera.start_intro(p1.center(), p1.center())

    def handle_event(self, event: pygame.event.Event) -> None:
        """Route input events to players."""
        for p in self.players:
            p.handle_event(event)

    def update(self, dt: float) -> None:
        """Advance world simulation adhering to integration collision order."""
        plat_boxes = platform_rects(self.platforms)
        keys = pygame.key.get_pressed()

        # Input handling for players
        for p in self.players:
            p.handle_input(keys, dt)

            # Check continuous attack hold
            att_key = p.controls.get("attack", -1)
            att_alt = p.controls.get("attack_alt", -1)
            is_attacking = p._attack_held or (att_key != -1 and keys[att_key]) or (att_alt != -1 and keys[att_alt])
            if is_attacking:
                p.attack(
                    self.projectile_manager.projectiles,
                    self.effects,
                    self.zombie_spawner.zombies,
                    self.zombie_spawner.on_zombie_hit_callback,
                    self.zombie_spawner.on_zombie_killed_callback,
                )

        # 1. Update players and platform collisions
        for p in self.players:
            p.update(dt, self.platforms, self.world_bounds)

        # 2. Update zombies and AI
        self.zombie_spawner.update(
            dt=dt,
            players=self.players,
            effects=self.effects,
            platforms=self.platforms,
            world_bounds=self.world_bounds,
        )

        # 3. Update pickups and collect
        newly_spawned = self.spawner.update(dt, self.world_bounds)
        self.items.extend(newly_spawned)

        for item in self.items:
            item.update(dt, plat_boxes, self.world_bounds)
            if item.active:
                item_box = item.bounds
                for p in self.players:
                    if p.alive() and p.bounds().colliderect(item_box):
                        item.collect(p)
                        self.effects.burst(
                            (item.position.x, item.position.y),
                            count=12,
                            palette=[(255, 230, 80), (100, 240, 255)],
                        )
                        break

        self.items = [it for it in self.items if it.active]

        # 4. Update projectiles and apply damage to players and zombies
        self.projectile_manager.update(
            dt=dt,
            platforms=plat_boxes,
            world_bounds=self.world_bounds,
            players=self.players,
            effects=self.effects,
            zombies=self.zombie_spawner.zombies,
            on_zombie_hit=self.zombie_spawner.on_zombie_hit_callback,
            on_zombie_kill=self.zombie_spawner.on_zombie_killed_callback,
        )

        # 5. Update effects and camera
        self.effects.update(dt)
        self.camera.set_shake(self.effects.shake_offset())
        self.camera.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        """Render world objects adhering to integration rendering order."""
        # 1. Background (Atmospheric magical starry sky & distant battlements)
        self._draw_background(surface)

        # 2. Platforms
        for plat in self.platforms:
            plat.draw(surface, self.camera)

        # 3. Pickups
        for it in self.items:
            it.draw(surface, self.camera)

        # 4. Projectiles
        self.projectile_manager.draw(surface, self.camera)

        # 5. Zombies
        self.zombie_spawner.draw(surface, self.camera)

        # 6. Players
        for p in self.players:
            p.draw(surface, self.camera)

        # 7. World visual effects
        self.effects.draw(surface, self.camera)

        # 8. Wave and Checkpoint HUD
        self._draw_wave_hud(surface)

    def _draw_background(self, surface: pygame.Surface) -> None:
        """Render procedural background with layered battlements and stars."""
        # Deep night gradient fill
        surface.fill((12, 16, 26))

        # Distant stars (parallax)
        cam_tl = self.camera.top_left
        for i in range(50):
            star_wx = (i * 97) % self.world_bounds.width
            star_wy = (i * 53) % (self.world_bounds.height - 200)
            sx = int((star_wx - self.camera.center.x) * 0.4 + self.config.screen_width / 2) % self.config.screen_width
            sy = int((star_wy - self.camera.center.y) * 0.4 + self.config.screen_height / 2) % self.config.screen_height
            brightness = 140 + (i * 17) % 115
            pygame.draw.circle(surface, (brightness, brightness, min(255, brightness + 20)), (sx, sy), 2)

        # Distant silhouette towers / battlements
        tower_color = (20, 24, 38)
        tower_spacing = 280
        z = self.camera.zoom
        for x in range(0, self.world_bounds.width + 100, tower_spacing):
            tw_rect = pygame.Rect(x, self.world_bounds.bottom - 420, 150, 420)
            s_rect = self.camera.apply_rect(tw_rect)
            if s_rect.colliderect(surface.get_rect()):
                pygame.draw.rect(surface, tower_color, s_rect)
                emb_w = max(8, int(20 * z))
                emb_h = max(5, int(14 * z))
                step = max(14, int(35 * z))
                for bx in range(s_rect.left, s_rect.right, step):
                    pygame.draw.rect(surface, (14, 18, 28), (bx, s_rect.top - emb_h, emb_w, emb_h))

    def _draw_wave_hud(self, surface: pygame.Surface) -> None:
        """Render in-game wave banner, zombie counter, and checkpoint notifications."""
        pygame.font.init()
        font = pygame.font.SysFont("georgia", 18, bold=True)
        small_font = pygame.font.SysFont("georgia", 13, bold=True)

        sw = self.config.screen_width
        wave_num = self.zombie_spawner.wave_number
        active_count = sum(1 for z in self.zombie_spawner.zombies if z.alive())

        # Top Center Wave Badge
        badge_w, badge_h = 180, 32
        badge_rect = pygame.Rect((sw - badge_w) // 2, 14, badge_w, badge_h)
        pygame.draw.rect(surface, (18, 22, 30, 220), badge_rect, border_radius=6)
        pygame.draw.rect(surface, (180, 40, 40), badge_rect, width=2, border_radius=6)

        w_text = font.render(f"WAVE  {wave_num}", True, (255, 215, 80))
        surface.blit(w_text, w_text.get_rect(center=badge_rect.center))

        # 3 zombie indicator pips below the wave badge
        pip_spacing = 18
        pip_start_x = sw // 2 - ((3 - 1) * pip_spacing) // 2
        for i in range(3):
            px = pip_start_x + i * pip_spacing
            py = badge_rect.bottom + 12
            color = (255, 50, 40) if i < active_count else (55, 60, 70)
            pygame.draw.circle(surface, color, (px, py), 5)
            pygame.draw.circle(surface, (15, 15, 15), (px, py), 5, width=1)

        # Checkpoint milestone banner (pulses gold when achieved)
        if self.zombie_spawner.checkpoint_notification_timer > 0:
            cp_w, cp_h = 320, 44
            cp_rect = pygame.Rect((sw - cp_w) // 2, 85, cp_w, cp_h)
            pulse = math.sin(pygame.time.get_ticks() * 0.01) * 25 + 230
            pygame.draw.rect(surface, (30, 25, 12, 230), cp_rect, border_radius=6)
            pygame.draw.rect(surface, (int(pulse), 200, 50), cp_rect, width=2, border_radius=6)
            cp_text = font.render(f"CHECKPOINT {self.zombie_spawner.checkpoints} REACHED!", True, (255, 225, 90))
            surface.blit(cp_text, cp_text.get_rect(center=cp_rect.center))

    def finished(self) -> bool:
        """Check if round has concluded due to the player dying."""
        return not self.left_player.alive()

    def winner(self) -> Player | None:
        """Retrieve the winning player entity or None if defeated."""
        if not self.finished():
            return None
        if self.left_player.alive():
            return self.left_player
        return None
