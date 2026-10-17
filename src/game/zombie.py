"""Zombie entity, fast/aggressive AI, ground emergence, and spread wave spawner."""

from __future__ import annotations
from enum import Enum
import math
import random
from typing import TYPE_CHECKING, Callable
import pygame

if TYPE_CHECKING:
    from src.game.camera import Camera
    from src.game.effects import EffectManager
    from src.game.platforms import Platform
    from src.game.player import Player
    from src.game.settings import GameConfig


class ZombieState(Enum):
    """Lifecycle states for a zombie."""
    EMERGING = "emerging"    # Digging / climbing out of the ground
    CHASING = "chasing"      # Aggressively sprinting & navigating toward player
    LUNGING = "lunging"      # High-speed airborne pounce / slash
    STUNNED = "stunned"      # Brief stagger on heavy hit
    DEAD = "dead"            # Defeated, collapsing into bone/decay particles


class Zombie:
    """Fast, hyper-aggressive zombie that climbs out of the ground and relentlessly attacks."""

    def __init__(
        self,
        spawn_pos: tuple[float, float],
        config: GameConfig,
        zombie_id: int = 0,
        emergence_delay: float = 0.0,
    ) -> None:
        self.zombie_id: int = zombie_id
        self.config: GameConfig = config
        self.position: pygame.Vector2 = pygame.Vector2(spawn_pos[0], spawn_pos[1])
        self.spawn_y: float = spawn_pos[1]  # The surface it climbs out of
        self.velocity: pygame.Vector2 = pygame.Vector2(0.0, 0.0)

        # Dimensions & collision
        self.width: int = 24
        self.height: int = 52
        self.prev_bottom: float = self.position.y

        # Stats - fast and lethal
        self.max_health: float = 40.0
        self.health: float = self.max_health
        self.base_speed: float = random.uniform(280.0, 335.0)  # Near player speed (360)
        self.jump_strength: float = 600.0
        self.damage: float = 12.0
        self.lunge_damage: float = 18.0

        # State & timers
        self.state: ZombieState = ZombieState.EMERGING
        self.facing: int = 1 if random.random() > 0.5 else -1
        self.on_ground: bool = True
        self.is_dropping_down: bool = False
        self.drop_timer: float = 0.0

        # Emergence parameters
        self.emergence_delay: float = emergence_delay  # Staggered emergence delay
        self.emergence_duration: float = 1.25          # Time spent climbing out
        self.emergence_timer: float = self.emergence_duration
        self._ground_debris_burst: bool = False

        # Combat & mobility AI timers
        self.lunge_cooldown: float = random.uniform(0.5, 1.5)
        self.lunge_timer: float = 0.0
        self.attack_cooldown: float = 0.0
        self.jump_cooldown: float = 0.0
        self.twitch_timer: float = random.uniform(0.0, 6.28)
        self.damage_flash: float = 0.0
        self.death_timer: float = 0.4
        self.anim_time: float = random.uniform(0.0, 6.28)
        self.run_cycle: float = 0.0
        self.squash_stretch: pygame.Vector2 = pygame.Vector2(1.0, 1.0)

        # Feral eye glow pulse
        self.eye_pulse: float = 0.0

        # Dirt mound visuals for emergence
        self.dirt_mound_points = [
            (-20, 0), (-14, -8), (-6, -14), (0, -16), (8, -12), (16, -6), (22, 0)
        ]

    def bounds(self) -> pygame.Rect:
        """World bounding box for collision detection."""
        if self.state == ZombieState.EMERGING:
            # During emergence, collision box grows as zombie emerges
            progress = max(0.0, 1.0 - (self.emergence_timer / self.emergence_duration))
            eff_height = max(12, int(self.height * progress))
            return pygame.Rect(
                int(self.position.x - self.width / 2),
                int(self.spawn_y - eff_height),
                self.width,
                eff_height,
            )
        return pygame.Rect(
            int(self.position.x - self.width / 2),
            int(self.position.y - self.height),
            self.width,
            self.height,
        )

    def center(self) -> tuple[float, float]:
        """Center coordinates of zombie."""
        return (self.position.x, self.position.y - self.height / 2)

    def alive(self) -> bool:
        """Check if zombie is alive."""
        return self.health > 0 and self.state != ZombieState.DEAD

    def is_active_threat(self) -> bool:
        """Check if zombie has finished emerging and can attack / deal damage."""
        return self.alive() and self.state in (ZombieState.CHASING, ZombieState.LUNGING)

    def take_damage(
        self,
        amount: float,
        knockback: tuple[float, float] = (0, 0),
        effects: EffectManager | None = None,
    ) -> bool:
        """Apply damage and knockback. Returns True if this hit killed the zombie."""
        if not self.alive():
            return False

        self.health -= amount
        self.damage_flash = 0.22
        self.squash_stretch = pygame.Vector2(1.3, 0.75)

        # If emerging, heavy damage may interrupt/finish emergence
        if self.state == ZombieState.EMERGING and self.health <= self.max_health * 0.5:
            self.state = ZombieState.CHASING

        # Apply knockback if chasing/lunging
        if self.state != ZombieState.EMERGING:
            self.velocity.x += knockback[0]
            self.velocity.y += knockback[1]
            self.on_ground = False

        if effects:
            # Green / blood burst on hit
            cx, cy = self.center()
            effects.burst(
                (cx, cy),
                count=10,
                palette=[(160, 40, 40), (60, 140, 50), (30, 80, 30)],
                strength=0.9,
            )

        if self.health <= 0:
            self.die(effects)
            return True
        return False

    def die(self, effects: EffectManager | None = None) -> None:
        """Trigger death state and death effects."""
        self.health = 0.0
        self.state = ZombieState.DEAD
        self.death_timer = 0.35
        if effects:
            cx, cy = self.center()
            effects.burst(
                (cx, cy),
                count=22,
                palette=[(180, 30, 30), (50, 120, 40), (25, 60, 25), (40, 40, 40)],
                strength=1.4,
            )
            effects.request_shake(intensity=4.0, duration=0.18)

    def update(
        self,
        dt: float,
        players: list[Player],
        platforms: list[Platform],
        world_bounds: pygame.Rect,
        effects: EffectManager,
        on_player_hit: Callable[[Player, float], None] | None = None,
    ) -> None:
        """Advance zombie simulation, AI decision tree, and physics."""
        self.anim_time += dt
        self.twitch_timer += dt
        self.prev_bottom = self.position.y

        # Timer decay
        if self.damage_flash > 0:
            self.damage_flash = max(0.0, self.damage_flash - dt)
        if self.attack_cooldown > 0:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        if self.lunge_cooldown > 0:
            self.lunge_cooldown = max(0.0, self.lunge_cooldown - dt)
        if self.jump_cooldown > 0:
            self.jump_cooldown = max(0.0, self.jump_cooldown - dt)
        if self.drop_timer > 0:
            self.drop_timer = max(0.0, self.drop_timer - dt)
        else:
            self.is_dropping_down = False

        # Smooth return of squash/stretch
        self.squash_stretch.x += (1.0 - self.squash_stretch.x) * min(1.0, dt * 14.0)
        self.squash_stretch.y += (1.0 - self.squash_stretch.y) * min(1.0, dt * 14.0)

        # ------------------- STATE: DEAD -------------------
        if self.state == ZombieState.DEAD:
            self.death_timer -= dt
            return

        # ------------------- STATE: EMERGING (Climbing out of ground) -------------------
        if self.state == ZombieState.EMERGING:
            if self.emergence_delay > 0:
                self.emergence_delay -= dt
                return

            self.emergence_timer -= dt
            progress = 1.0 - (self.emergence_timer / self.emergence_duration)

            # Emit dirt & rubble particles as it scratches out of the earth
            if random.random() < 0.35:
                effects.burst(
                    (self.position.x + random.uniform(-16, 16), self.spawn_y - random.uniform(0, 10)),
                    count=3,
                    palette=[(90, 60, 35), (65, 45, 25), (120, 95, 65)],
                    strength=0.6,
                )

            # When reaching apex of emergence, roar burst into chase!
            if self.emergence_timer <= 0:
                self.state = ZombieState.CHASING
                self.position.y = self.spawn_y
                effects.burst(
                    (self.position.x, self.spawn_y - 20),
                    count=14,
                    palette=[(60, 130, 45), (100, 70, 40), (40, 90, 30)],
                    strength=1.1,
                )
                self.velocity.y = -220.0  # Little aggressive pop out of the dirt
                self.on_ground = False
            return

        # ------------------- TARGET ACQUISITION -------------------
        target_player = self._find_nearest_player(players)

        # ------------------- STATE: LUNGING -------------------
        if self.state == ZombieState.LUNGING:
            self.lunge_timer -= dt
            # Airborne trail
            if random.random() < 0.4:
                effects.burst(
                    self.center(),
                    count=2,
                    palette=[(220, 50, 50), (70, 150, 60)],
                    strength=0.5,
                )

            # Check hit during lunge
            if target_player and target_player.alive() and self.bounds().colliderect(target_player.bounds()):
                kb = (self.facing * 420.0, -180.0)
                target_player.take_damage(self.lunge_damage, knockback=kb)
                effects.request_shake(intensity=6.0, duration=0.2)
                effects.burst(target_player.center(), count=12, palette=[(255, 50, 50), (180, 20, 20)])
                if on_player_hit:
                    on_player_hit(target_player, self.lunge_damage)
                # End lunge early on impact
                self.state = ZombieState.CHASING
                self.lunge_cooldown = 1.6
                self.lunge_timer = 0.0

            if self.lunge_timer <= 0:
                self.state = ZombieState.CHASING
                self.lunge_cooldown = random.uniform(1.2, 2.0)

        # ------------------- STATE: CHASING AI -------------------
        elif self.state == ZombieState.CHASING:
            if target_player and target_player.alive():
                dx = target_player.position.x - self.position.x
                dy = target_player.position.y - self.position.y
                dist = math.hypot(dx, dy)

                # Set horizontal facing and run velocity
                if abs(dx) > 12.0:
                    self.facing = 1 if dx > 0 else -1
                    target_vx = self.facing * self.base_speed
                    # Fast responsive acceleration
                    self.velocity.x += (target_vx - self.velocity.x) * min(1.0, dt * 12.0)
                    self.run_cycle += dt * 18.0
                else:
                    self.velocity.x *= 0.8

                # 1. Pounce / Lunge Trigger:
                # When within strike distance (80-140px horizontal, close vertically), initiate leap!
                if (
                    self.lunge_cooldown <= 0
                    and abs(dx) < 140.0
                    and abs(dy) < 55.0
                    and self.on_ground
                    and abs(dx) > 35.0
                ):
                    self.state = ZombieState.LUNGING
                    self.lunge_timer = 0.38
                    self.velocity.x = self.facing * 520.0
                    self.velocity.y = -210.0
                    self.on_ground = False
                    self.squash_stretch = pygame.Vector2(1.35, 0.7)
                    effects.burst(self.center(), count=6, palette=[(255, 60, 60), (80, 160, 60)])

                # 2. Vertical Traversal - Jumping up:
                # If target is above us and we are grounded, jump up to reach their platform!
                elif self.on_ground and self.jump_cooldown <= 0:
                    should_jump = False
                    # Target is higher up
                    if dy < -45.0 and abs(dx) < 260.0:
                        should_jump = True
                    # Obstacle or ledge detection: jumping forward over gaps or onto stepped platforms
                    elif abs(dx) > 40.0 and random.random() < 0.03:
                        should_jump = True

                    if should_jump:
                        self.velocity.y = -self.jump_strength
                        self.on_ground = False
                        self.jump_cooldown = random.uniform(0.6, 1.2)
                        self.squash_stretch = pygame.Vector2(0.8, 1.25)

                # 3. Vertical Traversal - Dropping down through one-way platforms:
                # If target is significantly below us and we are on a one-way platform
                elif self.on_ground and dy > 55.0:
                    self.is_dropping_down = True
                    self.drop_timer = 0.28
                    self.on_ground = False

                # 4. Close-range Melee Claws:
                if self.bounds().colliderect(target_player.bounds()):
                    if self.attack_cooldown <= 0:
                        self.attack_cooldown = 0.55
                        kb = (self.facing * 280.0, -120.0)
                        target_player.take_damage(self.damage, knockback=kb)
                        effects.burst(target_player.center(), count=8, palette=[(255, 80, 80), (160, 30, 30)])
                        if on_player_hit:
                            on_player_hit(target_player, self.damage)
            else:
                # Idle roam if no player alive
                self.velocity.x *= 0.9

        # ------------------- PHYSICS & COLLISION -------------------
        self._apply_physics(dt, platforms, world_bounds)

    def _apply_physics(
        self,
        dt: float,
        platforms: list[Platform],
        world_bounds: pygame.Rect,
    ) -> None:
        """Gravity, horizontal bounds, and platform collision logic."""
        # Gravity
        gravity = self.config.gravity
        self.velocity.y += gravity * dt
        self.velocity.y = min(900.0, self.velocity.y)

        # Horizontal movement & arena clamping
        self.position.x += self.velocity.x * dt
        half_w = self.width / 2.0
        if self.position.x < world_bounds.left + half_w + 10:
            self.position.x = world_bounds.left + half_w + 10
            self.velocity.x = abs(self.velocity.x) * 0.5
            self.facing = 1
        elif self.position.x > world_bounds.right - half_w - 10:
            self.position.x = world_bounds.right - half_w - 10
            self.velocity.x = -abs(self.velocity.x) * 0.5
            self.facing = -1

        # Vertical movement & platform landing
        self.position.y += self.velocity.y * dt
        box = self.bounds()
        was_on_ground = self.on_ground
        self.on_ground = False

        # Arena floor
        floor_y = float(world_bounds.bottom - 90)
        if self.position.y >= floor_y:
            self.position.y = floor_y
            self.velocity.y = 0.0
            self.on_ground = True
            if not was_on_ground:
                self.squash_stretch = pygame.Vector2(1.2, 0.8)
            box = self.bounds()

        # Platforms
        for plat in platforms:
            p_rect = getattr(plat, "rect", plat)
            p_one_way = getattr(plat, "is_one_way", False)

            if box.right > p_rect.left + 2 and box.left < p_rect.right - 2:
                if p_one_way:
                    if not self.is_dropping_down and self.drop_timer <= 0 and self.velocity.y > 0:
                        if self.prev_bottom <= p_rect.top + 16 and self.position.y >= p_rect.top:
                            self.position.y = p_rect.top
                            self.velocity.y = 0.0
                            self.on_ground = True
                            if not was_on_ground:
                                self.squash_stretch = pygame.Vector2(1.18, 0.82)
                            box = self.bounds()
                else:
                    if self.velocity.y > 0 and self.prev_bottom <= p_rect.top + 16 and self.position.y >= p_rect.top:
                        self.position.y = p_rect.top
                        self.velocity.y = 0.0
                        self.on_ground = True
                        box = self.bounds()
                    elif self.velocity.y < 0 and box.top <= p_rect.bottom and box.top >= p_rect.top:
                        self.position.y = p_rect.bottom + self.height
                        self.velocity.y = 0.0
                        box = self.bounds()

    def _find_nearest_player(self, players: list[Player]) -> Player | None:
        """Find the nearest alive player."""
        best_p: Player | None = None
        best_dist = float("inf")
        for p in players:
            if p.alive():
                d = math.hypot(p.position.x - self.position.x, p.position.y - self.position.y)
                if d < best_dist:
                    best_dist = d
                    best_p = p
        return best_p

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Render aggressive, decayed zombie with distinct animations for emerging and running."""
        screen_pos = camera.apply((self.position.x, self.position.y))
        sx, sy = screen_pos
        z = camera.zoom

        # ------------------- DRAW EMERGING FROM DIRT -------------------
        if self.state == ZombieState.EMERGING:
            # Draw ground crack & dirt mound at spawn location
            spawn_s = camera.apply((self.position.x, self.spawn_y))
            mx, my = spawn_s

            mound_pts = [(mx + int(px * z), my + int(py * z)) for px, py in self.dirt_mound_points]
            pygame.draw.polygon(surface, (50, 36, 24), mound_pts)
            pygame.draw.polygon(surface, (80, 56, 38), mound_pts, width=max(1, int(2 * z)))
            # Fissure line
            pygame.draw.line(surface, (20, 14, 10), (mx - int(12 * z), my), (mx + int(12 * z), my - int(4 * z)), width=max(1, int(2 * z)))

            if self.emergence_delay > 0:
                # Pre-emergence rumbling dirt
                shake = math.sin(self.anim_time * 25.0) * (2.0 * z)
                pygame.draw.circle(surface, (110, 75, 45), (int(mx + shake), my - int(4 * z)), max(2, int(4 * z)))
                return

            progress = max(0.0, 1.0 - (self.emergence_timer / self.emergence_duration))

            # Emerging torso & clawing arms rising from the mound
            rise_offset = int((1.0 - progress) * 36.0 * z)
            emerge_sy = my + rise_offset

            # Colors
            skin_color = (65, 115, 55)
            claw_color = (25, 30, 20)
            eye_color = (255, 40, 30)

            head_r = max(2, int(8 * z))
            head_cy = emerge_sy - int(24 * z)

            # Draw clawing hands reaching up out of the dirt
            claw_y = my - int(math.sin(self.anim_time * 12.0) * 8 * z) - int(6 * z)
            pygame.draw.line(surface, skin_color, (mx - int(16 * z), my), (mx - int(18 * z), claw_y), width=max(1, int(3 * z)))
            pygame.draw.line(surface, claw_color, (mx - int(18 * z), claw_y), (mx - int(22 * z), claw_y - int(4 * z)), width=max(1, int(2 * z)))

            pygame.draw.line(surface, skin_color, (mx + int(16 * z), my), (mx + int(18 * z), claw_y), width=max(1, int(3 * z)))
            pygame.draw.line(surface, claw_color, (mx + int(18 * z), claw_y), (mx + int(22 * z), claw_y - int(4 * z)), width=max(1, int(2 * z)))

            # Rising head & torso
            if progress > 0.2:
                pygame.draw.line(surface, skin_color, (mx, my), (mx, emerge_sy - int(16 * z)), width=max(2, int(5 * z)))
                pygame.draw.circle(surface, skin_color, (mx, head_cy), head_r)
                # Glowing red feral eyes
                eye_x = mx + int(self.facing * 3 * z)
                pygame.draw.circle(surface, eye_color, (eye_x, head_cy - int(1 * z)), max(1, int(2.5 * z)))
            return

        # ------------------- DRAW ACTIVE ZOMBIE -------------------
        # Skin & clothes colors
        if self.damage_flash > 0:
            skin_color = (255, 255, 255)
            clothes_color = (240, 240, 240)
            eye_color = (255, 255, 255)
        else:
            skin_color = (55, 110, 48)       # Toxic zombie green
            clothes_color = (42, 45, 52)     # Ragged decayed clothes
            eye_color = (255, 38, 30)        # Glowing feral red

        line_w = max(1, int(3 * z))
        heavy_w = max(2, int(4.5 * z))

        # Squash and stretch
        sq_x = self.squash_stretch.x
        sq_y = self.squash_stretch.y

        # Aggressive hunched forward lean (predatory posture)
        forward_lean = self.facing * (0.32 if self.state == ZombieState.LUNGING else 0.22)
        # Twitching head spasm
        twitch_dx = int(math.sin(self.twitch_timer * 16.0) * 2.5 * z) if random.random() < 0.25 else 0

        hip_y = sy - int(20.0 * sq_y * z)
        neck_y = sy - int(42.0 * sq_y * z)
        head_cy = sy - int(50.0 * sq_y * z)

        hip_x = sx
        neck_x = sx + int(math.sin(forward_lean) * (24.0 * z))
        head_cx = sx + int(math.sin(forward_lean) * (34.0 * z)) + twitch_dx

        # 1. Legs Animation (Frenzied predatory run or airborne lunge)
        if not self.on_ground:
            # Trailing sprint leap
            l_knee = (hip_x - int(8 * self.facing * z), hip_y + int(10 * z))
            l_foot = (hip_x - int(14 * self.facing * z), sy - int(8 * z))
            r_knee = (hip_x + int(6 * self.facing * z), hip_y + int(8 * z))
            r_foot = (hip_x + int(12 * self.facing * z), sy - int(14 * z))
            pygame.draw.lines(surface, clothes_color, False, [(hip_x, hip_y), l_knee, l_foot], width=line_w)
            pygame.draw.lines(surface, clothes_color, False, [(hip_x, hip_y), r_knee, r_foot], width=line_w)
        else:
            # High-cadence running legs
            cycle = self.run_cycle
            l_foot_x = hip_x + int(math.sin(cycle) * 16 * z)
            l_foot_y = sy - max(0, int(math.sin(cycle) * 10 * z))
            r_foot_x = hip_x - int(math.sin(cycle) * 16 * z)
            r_foot_y = sy - max(0, int(-math.sin(cycle) * 10 * z))

            l_knee_x = hip_x + int(math.sin(cycle) * 10 * z)
            l_knee_y = hip_y + int(10 * z)
            r_knee_x = hip_x - int(math.sin(cycle) * 10 * z)
            r_knee_y = hip_y + int(10 * z)

            pygame.draw.lines(surface, clothes_color, False, [(hip_x, hip_y), (l_knee_x, l_knee_y), (l_foot_x, l_foot_y)], width=line_w)
            pygame.draw.lines(surface, clothes_color, False, [(hip_x, hip_y), (r_knee_x, r_knee_y), (r_foot_x, r_foot_y)], width=line_w)

        # 2. Torso (hunched spine)
        pygame.draw.line(surface, clothes_color, (hip_x, hip_y), (neck_x, neck_y), width=heavy_w)

        # 3. Arms & Outstretched Claws
        # Both arms reach aggressively forward towards the victim
        arm_reach = 22.0 if self.state == ZombieState.LUNGING else 16.0
        hand_x = neck_x + int(self.facing * arm_reach * z)
        hand_y = neck_y + int(math.sin(self.anim_time * 8.0) * 5 * z) + int(2 * z)

        # Left claw
        pygame.draw.line(surface, skin_color, (neck_x, neck_y), (hand_x, hand_y), width=line_w)
        pygame.draw.line(surface, (20, 20, 20), (hand_x, hand_y), (hand_x + int(self.facing * 6 * z), hand_y - int(4 * z)), width=max(1, int(2 * z)))
        # Right claw
        hand2_x = neck_x + int(self.facing * (arm_reach - 4.0) * z)
        hand2_y = neck_y + int(6 * z)
        pygame.draw.line(surface, skin_color, (neck_x, neck_y), (hand2_x, hand2_y), width=line_w)
        pygame.draw.line(surface, (20, 20, 20), (hand2_x, hand2_y), (hand2_x + int(self.facing * 6 * z), hand2_y + int(3 * z)), width=max(1, int(2 * z)))

        # 4. Head & Glowing Feral Eyes
        head_radius = max(2, int(8.5 * sq_x * z))
        pygame.draw.circle(surface, skin_color, (head_cx, head_cy), head_radius)
        # Jagged mouth / jaw
        jaw_x = head_cx + int(self.facing * 4 * z)
        jaw_y = head_cy + int(4 * z)
        pygame.draw.line(surface, (15, 15, 15), (jaw_x, jaw_y), (jaw_x + int(self.facing * 4 * z), jaw_y), width=max(1, int(2 * z)))

        # Glowing red predator eye
        eye_x = head_cx + int(self.facing * 3.5 * z)
        eye_y = head_cy - int(1.5 * z)
        pygame.draw.circle(surface, eye_color, (eye_x, eye_y), max(1, int(2.8 * z)))
        # Subtle glow ring around eye
        glow_r = max(2, int(4.5 * z))
        eye_glow_surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
        pygame.draw.circle(eye_glow_surf, (255, 30, 20, 75), (glow_r + 1, glow_r + 1), glow_r)
        surface.blit(eye_glow_surf, (eye_x - glow_r - 1, eye_y - glow_r - 1))

        # 5. Lunge visual swipe arc
        if self.state == ZombieState.LUNGING:
            slash_x = hand_x + int(self.facing * 12 * z)
            slash_pts = [
                (slash_x, hand_y - int(12 * z)),
                (slash_x + int(self.facing * 8 * z), hand_y),
                (slash_x, hand_y + int(12 * z)),
            ]
            pygame.draw.lines(surface, (255, 60, 60), False, slash_pts, width=max(1, int(2 * z)))


class ZombieSpawner:
    """Manages wave progression, spread-out spawning across arena platforms, and checkpoints."""

    def __init__(
        self,
        config: GameConfig,
        platforms: list[Platform],
        world_bounds: pygame.Rect,
    ) -> None:
        self.config: GameConfig = config
        self.platforms: list[Platform] = platforms
        self.world_bounds: pygame.Rect = world_bounds

        self.zombies: list[Zombie] = []
        self.wave_number: int = 0
        self.checkpoints: int = 0
        self.total_kills: int = 0

        # Wave pacing
        self.wave_delay: float = 1.8   # Breather between waves
        self.wave_timer: float = 0.0
        self.wave_in_progress: bool = False
        self.checkpoint_notification_timer: float = 0.0

        # Callbacks for time/arc updates
        self.on_zombie_hit_callback: Callable[[Zombie], None] | None = None
        self.on_zombie_killed_callback: Callable[[Zombie], None] | None = None
        self.on_player_hit_callback: Callable[[Player, float], None] | None = None

        # Start first wave immediately
        self.start_next_wave()

    def reset(self) -> None:
        """Reset wave progression to wave 1 (or last checkpoint)."""
        self.zombies.clear()
        # Checkpoint restores to 5 * checkpoints (e.g. wave 5 or 10), or wave 1 if no checkpoints
        if self.checkpoints > 0:
            self.wave_number = self.checkpoints * 5
        else:
            self.wave_number = 0
        self.wave_timer = 0.5
        self.wave_in_progress = False
        self.checkpoint_notification_timer = 0.0
        self.start_next_wave()

    def get_spread_spawn_points(self, players: list[Player]) -> list[tuple[float, float]]:
        """Calculate 3 well-distributed spawn locations across ground and platforms."""
        w = self.world_bounds.width
        floor_y = float(self.world_bounds.bottom - 90)

        # 3 distinct horizontal zones (Left, Center, Right) to ensure spread
        zones = [
            (180.0, 480.0),    # Zone 1: West arena
            (620.0, 980.0),    # Zone 2: Central arena
            (1120.0, 1420.0),  # Zone 3: East arena
        ]

        # Player avoidance check
        player_x = players[0].position.x if players and players[0].alive() else w / 2.0

        spawn_points: list[tuple[float, float]] = []

        # Find matching platforms or ground in each zone
        for i, (min_x, max_x) in enumerate(zones):
            # Check if there is an elevated platform in this zone to add vertical variety
            eligible_surfaces: list[tuple[float, float]] = []

            for plat in self.platforms:
                p_rect = getattr(plat, "rect", plat)
                # Platform overlaps this zone horizontally
                if p_rect.right > min_x and p_rect.left < max_x:
                    cand_x = max(min_x, min(max_x, (p_rect.left + p_rect.right) / 2.0))
                    # Avoid spawning on apex altar if wave < 3
                    if p_rect.top < self.world_bounds.bottom - 400 and self.wave_number < 3:
                        continue
                    eligible_surfaces.append((cand_x, float(p_rect.top)))

            # Also always have ground floor surface as an option
            ground_cand_x = random.uniform(min_x, max_x)
            eligible_surfaces.append((ground_cand_x, floor_y))

            # Pick a surface that isn't directly on the player
            selected: tuple[float, float] = eligible_surfaces[0]
            best_dist = -1.0
            for cand in eligible_surfaces:
                d = abs(cand[0] - player_x)
                if d > 120.0:  # Far enough from player
                    selected = cand
                    break
                elif d > best_dist:
                    best_dist = d
                    selected = cand

            spawn_points.append(selected)

        return spawn_points

    def start_next_wave(self) -> None:
        """Spawn the next wave of 3 zombies emerging across the arena."""
        self.wave_number += 1
        self.wave_in_progress = True

        # Check for checkpoint (every 5 waves)
        if self.wave_number > 1 and (self.wave_number - 1) % 5 == 0:
            self.checkpoints += 1
            self.checkpoint_notification_timer = 3.0

        # Calculate spread spawn coordinates
        # Note: players can be passed or empty on initial start
        pts = self.get_spread_spawn_points([])

        # Staggered emergence timings (0.0s, 0.2s, 0.4s) for dramatic staggered rumbling
        self.zombies = [
            Zombie(spawn_pos=pts[0], config=self.config, zombie_id=1, emergence_delay=0.0),
            Zombie(spawn_pos=pts[1], config=self.config, zombie_id=2, emergence_delay=0.25),
            Zombie(spawn_pos=pts[2], config=self.config, zombie_id=3, emergence_delay=0.50),
        ]

    def update(
        self,
        dt: float,
        players: list[Player],
        effects: EffectManager,
        platforms: list[Platform],
        world_bounds: pygame.Rect,
    ) -> None:
        """Update all active zombies and advance wave logic."""
        if self.checkpoint_notification_timer > 0:
            self.checkpoint_notification_timer = max(0.0, self.checkpoint_notification_timer - dt)

        # Update each zombie
        for z in self.zombies:
            z.update(
                dt=dt,
                players=players,
                platforms=platforms,
                world_bounds=world_bounds,
                effects=effects,
                on_player_hit=self.on_player_hit_callback,
            )

        # Remove dead zombies after death timer expires
        alive_before = len(self.zombies)
        self.zombies = [z for z in self.zombies if z.alive() or z.death_timer > 0]

        # Check if wave is fully cleared
        active_zombies = [z for z in self.zombies if z.alive()]
        if len(active_zombies) == 0 and self.wave_in_progress:
            self.wave_in_progress = False
            self.wave_timer = self.wave_delay

        # Advance wave countdown when cleared
        if not self.wave_in_progress:
            self.wave_timer -= dt
            if self.wave_timer <= 0:
                self.start_next_wave()

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Render all zombies in the world."""
        for z in self.zombies:
            z.draw(surface, camera)
