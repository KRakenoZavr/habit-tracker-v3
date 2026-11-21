---
covers: [Assets/Scenes/**, Assets/Prefabs/**, Content/**]
verified_at: none
owner: architect
---
# Scene graph (outline)
<!-- Indented outline of scenes/levels and their prefab/actor composition. Agents read this instead of scene files. -->
- MainMenu
  - Canvas (UI)
  - MenuController
- Level01
  - Systems (GameManager, AudioManager)
  - Player (prefab: Player)
    - Camera rig
  - Enemies (spawned by EnemySpawner)
  - UI HUD (prefab: HUD)
