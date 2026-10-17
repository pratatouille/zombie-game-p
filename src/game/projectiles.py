"""Projectiles, weapon shots, collision, bomb trails, and explosions."""

from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.game.camera import Camera
    from src.game.effects import EffectManager
    from src.game.player import Player


class Projectile:
    """Individual projectile entity with custom aerodynamics, trails, and detonations."""

    def __init__(
        self,
        owner_id: int,
        position: tuple[float, float],
        velocity: tuple[float, float],
        damage: float,
        kind: str,
        radius: int = 6,
    ) -> None:
        self.owner_id: int = owner_id
        self.position: pygame.Vector2 = pygame.Vector2(position[0], position[1])
        self.velocity: pygame.Vector2 = pygame.Vector2(velocity[0], velocity[1])
        self.damage: float = damage
        self.kind: str = kind
        self.radius: int = radius
        self._expired: bool = False
        self._detonated: bool = False
        self.time_alive: float = 0.0

    def expired(self) -> bool:
        """Check if projectile has detonated or expired."""
        return self._expired

    def bounds(self) -> pygame.Rect:
        """World bounding box for collision detection."""
        r = self.radius
        return pygame.Rect(int(self.position.x - r), int(self.position.y - r), r * 2, r * 2)

    def detonate(
        self,
        position: tuple[float, float],
        effects: EffectManager,
        players: list[Player],
        zombies: list[any] | None = None,
        on_zombie_hit: any = None,
        on_zombie_kill: any = None,
    ) -> None:
        """Detonate explosive projectile, damaging nearby opponents and triggering visual effects."""
        if self._detonated:
            return
        self._detonated = True
        self._expired = True

        blast_pos = (self.position.x, self.position.y)

        if self.kind == "bomb":
            # Rich fiery explosion
            bomb_palette = [(255, 240, 160), (255, 140, 30), (220, 50, 20), (90, 40, 20)]
            effects.explosion(blast_pos, radius=85.0, palette=bomb_palette)

            # Radial damage to non-owner players
            blast_radius = 100.0
            for p in players:
                if p.player_id == self.owner_id or not p.alive():
                    continue
                pc = p.center()
                dx = pc[0] - blast_pos[0]
                dy = pc[1] - blast_pos[1]
                dist = math.hypot(dx, dy)
                if dist <= blast_radius:
                    falloff = max(0.3, 1.0 - (dist / blast_radius))
                    actual_dmg = self.damage * falloff
                    # Knockback calculation
                    push_dir = pygame.Vector2(dx, dy)
                    if push_dir.length_squared() > 0:
                        push_dir = push_dir.normalize()
                    else:
                        push_dir = pygame.Vector2(0, -1)
                    kb_power = 480.0 * falloff
                    p.take_damage(actual_dmg, knockback=(push_dir.x * kb_power, push_dir.y * kb_power - 120.0))

            # Radial damage to zombies
            if zombies:
                for z in zombies:
                    if not z.alive():
                        continue
                    zc = z.center()
                    dx = zc[0] - blast_pos[0]
                    dy = zc[1] - blast_pos[1]
                    dist = math.hypot(dx, dy)
                    if dist <= blast_radius:
                        falloff = max(0.3, 1.0 - (dist / blast_radius))
                        actual_dmg = self.damage * falloff
                        push_dir = pygame.Vector2(dx, dy)
                        if push_dir.length_squared() > 0:
                            push_dir = push_dir.normalize()
                        else:
                            push_dir = pygame.Vector2(0, -1)
                        kb_power = 520.0 * falloff
                        killed = z.take_damage(actual_dmg, knockback=(push_dir.x * kb_power, push_dir.y * kb_power - 140.0), effects=effects)
                        if on_zombie_hit:
                            on_zombie_hit(z)
                        if killed and on_zombie_kill:
                            on_zombie_kill(z)

        else:
            # Impact spark burst for standard projectiles
            palette = [(255, 230, 100), (255, 120, 40)]
            if self.kind == "wand":
                palette = [(120, 240, 255), (220, 100, 255), (255, 255, 255)]
            effects.burst(blast_pos, count=14, palette=palette, strength=0.8)

    def update(
        self,
        dt: float,
        platforms: list[pygame.Rect],
        world_bounds: pygame.Rect,
        players: list[Player],
        effects: EffectManager,
        zombies: list[any] | None = None,
        on_zombie_hit: any = None,
        on_zombie_kill: any = None,
    ) -> None:
        """Update projectile physics, trails, and collision detection."""
        if self._expired:
            return

        self.time_alive += dt

        # Apply aerodynamics / gravity
        if self.kind == "bomb":
            self.velocity.y += 680.0 * dt
            # Persistent spark and smoke trail
            fuse_pos = (
                self.position.x - self.velocity.x * 0.02,
                self.position.y - self.radius - 2,
            )
            effects.burst(fuse_pos, count=2, palette=[(255, 180, 50), (255, 80, 20)], strength=0.4)
        elif self.kind == "wand":
            # Magic energy trail
            effects.burst((self.position.x, self.position.y), count=1, palette=[(100, 220, 255), (240, 120, 255)], strength=0.3)

        # Move position
        self.position += self.velocity * dt
        box = self.bounds()

        # Check world bounds collision
        if not world_bounds.colliderect(box):
            if self.kind == "bomb":
                self.detonate((self.position.x, self.position.y), effects, players, zombies, on_zombie_hit, on_zombie_kill)
            else:
                self._expired = True
            return

        # Check platform collisions
        hit_platform = False
        for plat in platforms:
            if box.colliderect(plat):
                hit_platform = True
                break

        if hit_platform:
            if self.kind == "bomb":
                self.detonate((self.position.x, self.position.y), effects, players, zombies, on_zombie_hit, on_zombie_kill)
            else:
                effects.burst((self.position.x, self.position.y), count=8, palette=[(200, 200, 200), (255, 220, 100)])
                self._expired = True
            return

        # Check zombie collisions
        if zombies:
            for z in zombies:
                if not z.alive():
                    continue
                if box.colliderect(z.bounds()):
                    if self.kind == "bomb":
                        self.detonate((self.position.x, self.position.y), effects, players, zombies, on_zombie_hit, on_zombie_kill)
                    else:
                        kb_dir = 1 if self.velocity.x >= 0 else -1
                        kb = (kb_dir * 300.0, -150.0)
                        killed = z.take_damage(self.damage, knockback=kb, effects=effects)
                        effects.burst((self.position.x, self.position.y), count=12, palette=[(180, 50, 50), (60, 150, 60)])
                        effects.request_shake(intensity=4.0, duration=0.12)
                        self._expired = True
                        if on_zombie_hit:
                            on_zombie_hit(z)
                        if killed and on_zombie_kill:
                            on_zombie_kill(z)
                    return

        # Check player collisions
        for p in players:
            if p.player_id == self.owner_id or not p.alive():
                continue
            if box.colliderect(p.bounds()):
                if self.kind == "bomb":
                    self.detonate((self.position.x, self.position.y), effects, players, zombies, on_zombie_hit, on_zombie_kill)
                else:
                    # Direct bullet or wand hit
                    kb_dir = 1 if self.velocity.x >= 0 else -1
                    kb = (kb_dir * 280.0, -140.0)
                    p.take_damage(self.damage, knockback=kb)
                    effects.burst((self.position.x, self.position.y), count=12, palette=[(255, 60, 60), (255, 220, 80)])
                    effects.request_shake(intensity=5.0, duration=0.15)
                    self._expired = True
                return

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Draw projectile using procedural geometric shapes with camera zoom scaling."""
        if self._expired:
            return

        screen_pos = camera.apply((self.position.x, self.position.y))
        sx, sy = screen_pos
        z = camera.zoom
        r = max(2, int(self.radius * z))

        if self.kind == "bomb":
            # Bomb body: dark sphere with shine
            pygame.draw.circle(surface, (25, 25, 30), (sx, sy), r)
            pygame.draw.circle(surface, (80, 80, 95), (sx - max(1, int(2 * z)), sy - max(1, int(2 * z))), max(1, r // 3))
            pygame.draw.circle(surface, (10, 10, 12), (sx, sy), r, width=max(1, int(2 * z)))
            # Fuse cap and burning spark
            fuse_cap_w = max(2, int(4 * z))
            fuse_cap_h = max(2, int(3 * z))
            fuse_cap_rect = pygame.Rect(sx - fuse_cap_w // 2, sy - r - fuse_cap_h, fuse_cap_w, fuse_cap_h)
            pygame.draw.rect(surface, (120, 90, 50), fuse_cap_rect)
            # Fuse spark
            pygame.draw.circle(surface, (255, 200, 50), (sx, sy - r - fuse_cap_h - 1), max(1, int(3 * z)))
            pygame.draw.circle(surface, (255, 80, 20), (sx, sy - r - fuse_cap_h - 1), max(1, int(1.5 * z)))

        elif self.kind == "wand":
            # Glowing magical arcane star bolt
            glow_surf = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            c = glow_surf.get_rect().center
            pygame.draw.circle(glow_surf, (80, 220, 255, 120), c, r * 2)
            pygame.draw.circle(glow_surf, (220, 120, 255, 200), c, r)
            pygame.draw.circle(glow_surf, (255, 255, 255, 255), c, max(1, r // 2))
            surface.blit(glow_surf, (sx - c[0], sy - c[1]))

        elif self.kind == "machine_gun":
            # Small, fast bright tracer
            vx, vy = self.velocity.x, self.velocity.y
            speed = math.hypot(vx, vy)
            if speed > 0:
                dx = (vx / speed) * (14.0 * z)
                dy = (vy / speed) * (14.0 * z)
                pygame.draw.line(surface, (255, 220, 90), (sx, sy), (int(sx - dx), int(sy - dy)), width=max(1, int(3 * z)))
                pygame.draw.line(surface, (255, 255, 220), (sx, sy), (int(sx - dx * 0.5), int(sy - dy * 0.5)), width=max(1, int(1.5 * z)))
            else:
                sz = max(2, int(6 * z))
                pygame.draw.rect(surface, (255, 210, 80), (sx - sz // 2, sy - sz // 2, sz, sz))

        else:  # pistol or default
            # Solid energy bullet
            sz = max(3, int(8 * z))
            pygame.draw.rect(surface, (255, 255, 255), (sx - sz // 2, sy - sz // 2, sz, sz), border_radius=2)
            pygame.draw.rect(surface, (240, 80, 50), (sx - sz // 2 - 1, sy - sz // 2 - 1, sz + 2, sz + 2), width=1, border_radius=2)


class ProjectileManager:
    """Manages active projectiles collection, batch updates, and rendering."""

    def __init__(self) -> None:
        self.projectiles: list[Projectile] = []

    def spawn(self, projectile: Projectile) -> None:
        """Add a new projectile to be tracked."""
        self.projectiles.append(projectile)

    def update(
        self,
        dt: float,
        platforms: list[pygame.Rect],
        world_bounds: pygame.Rect,
        players: list[Player],
        effects: EffectManager,
        zombies: list[any] | None = None,
        on_zombie_hit: any = None,
        on_zombie_kill: any = None,
    ) -> None:
        """Update all active projectiles."""
        for proj in self.projectiles:
            proj.update(dt, platforms, world_bounds, players, effects, zombies, on_zombie_hit, on_zombie_kill)
        self.remove_expired()

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Draw all active projectiles."""
        for proj in self.projectiles:
            proj.draw(surface, camera)

    def remove_expired(self) -> None:
        """Prune expired and detonated projectiles."""
        self.projectiles = [p for p in self.projectiles if not p.expired()]
