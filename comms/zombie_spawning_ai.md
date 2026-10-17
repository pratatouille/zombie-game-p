# Zombie Spawning & AI - Feature Specification & Status

**Owner:** Pratyush  
**Scope:** Fast/aggressive Zombie AI, ground emergence animation, spread-out wave spawner, and combat integration hooks.

---

## 1. Objectives & Implemented Features

### Fast & Hyper-Aggressive Zombie AI (`ZombieState`)
* **Break away from sluggish zombie tropes**:
  * Base movement speeds: ~280 - 335 px/s (rapid sprint close to player's 360 px/s).
  * Rapid turn rate and dynamic acceleration toward player.
* **Mobility & Platform Navigation**:
  * **Jumping**: Automatically jumps upwards when targeting a player on higher platforms or clearing gaps/ledges (`velocity.y = -600.0`).
  * **Drop Down**: Drops down through one-way platforms (`is_dropping_down = True`) when pursuing a player on lower platforms or ground.
* **Aggressive Attacks**:
  * **Airborne Pounce / Lunge (`ZombieState.LUNGING`)**: When within 140px horizontal and 55px vertical strike distance, initiates a high-speed airborne leap (`velocity.x = 520`, `velocity.y = -210`) with swipe slash trails, dealing 18 damage and heavy knockback on collision.
  * **Close-range Melee Claws**: Rapid scratch/bite (12 damage + knockback) every 0.55s on contact.

### Ground Emergence Animation (`ZombieState.EMERGING`)
* When spawned, zombies do not instantly appear standing:
  * Spawn point is anchored to the arena floor or platform surface.
  * Ground fissure cracks and a dirt/rubble mound form at the spawn coordinates.
  * Digging/clawing arms emerge first and pull the torso up from the earth.
  * Rubble and dirt particle bursts fly out around the emergence hole.
  * Staggered emergence delays (0.0s, 0.25s, 0.5s) produce an organic, terrifying sequence of zombies crawling out across the arena.
  * Transitions into active `CHASING` sprint once fully climbed out.

### Spread-Out Wave Spawning (`ZombieSpawner`)
* **Arena Distribution**:
  * Separates the 1600px arena into 3 distinct zones: West (180–480px), Central (620–980px), and East (1120–1420px).
  * Spawns 3 zombies per wave spread across platforms and ground surfaces.
  * **Player Avoidance**: Ensures zombies do not spawn right on top of the player (minimum clearance buffer maintained so player can see them emerging).
* **Wave Progression & Checkpoints**:
  * Tracks `wave_number` (starts at Wave 1).
  * 3 zombies per wave.
  * Advances to the next wave upon defeating all 3 zombies after a brief 1.8s clear breather.
  * Checkpoint counter: increments every 5 waves (Wave 5, 10, 15), accompanied by a checkpoint banner.

---

## 2. Integration Hooks for Teammates

### Callbacks for Timer Arc & Scoring (`src/game/zombie.py`)
Teammates implementing the infection/timer arc can bind their functions to:
* `zombie_spawner.on_zombie_hit_callback = my_on_hit`:
  * Called whenever player hits a zombie (attack punch or weapon projectile).
  * **Expected Timer Effect**: `+1` unit of time.
* `zombie_spawner.on_zombie_killed_callback = my_on_kill`:
  * Called whenever a zombie reaches 0 HP and dies.
  * **Expected Timer Effect**: `+3` units of time.
* `zombie_spawner.on_player_hit_callback = my_on_player_hit`:
  * Called whenever a zombie attacks or lunges into the player.
  * **Expected Timer Effect**: `-5` units of time.

### Entity Methods
* `zombie.take_damage(amount, knockback, effects)`: applies damage, triggers hurt flash, blood/decay bursts, and returns `True` if fatal.
* `zombie.alive()`: returns whether zombie is still alive.
* `zombie.is_active_threat()`: returns whether zombie has finished emerging and is actively attacking.

---

## 3. Progress Status
- [x] Initial design and communication doc created.
- [x] Implement `Zombie` class with emergence animation and high-mobility chase/lunge AI (`src/game/zombie.py`).
- [x] Implement `ZombieSpawner` with spread-out spawn locations across arena zones and wave progression (`src/game/zombie.py`).
- [x] Integrate zombie collisions into projectiles (`src/game/projectiles.py`) and player melee punch (`src/game/player.py`).
- [x] Integrate into `World` simulation loop and wave HUD rendering (`src/game/world.py`).
- [x] Comprehensive test suite created (`tests/test_zombie.py`) — 7/7 tests passing.
