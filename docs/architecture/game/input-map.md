---
covers: [src/**]
verified_at: none
owner: architect
---
# Input map
| Device input | Action | Context | Handler |
|---|---|---|---|
| WASD / left stick | Move | Gameplay | `PlayerController.OnMove` |
| Space / A | Jump | Gameplay | `PlayerController.OnJump` |
| Esc / Start | Pause | Gameplay, Menu | `PauseMenu.Toggle` |
