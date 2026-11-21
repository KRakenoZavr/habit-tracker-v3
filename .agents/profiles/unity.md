# Profile: Unity
## Project settings (once, by the human)
- Editor Settings: Asset Serialization = Force Text; Version Control = Visible Meta Files.
- Git LFS for binaries (textures, audio, models). Use Unity's official `.gitignore`.

## Hard rules for agents
- Never text-edit `*.unity`, `*.prefab`, `*.asset`, `*.meta`, `*.controller`, `*.anim`. Add these to `protected_globs`.
- Never move, rename or delete assets from the shell: `.meta` GUIDs break references. Moves happen in the Editor.
- Scene/prefab changes are done through Editor scripts in `Assets/Editor/AgentTasks/` that a human runs from a menu item, or through Unity's official MCP/plugin when available.
- Only one "scene lane" ticket at a time: put `Assets/Scenes/**` and `Assets/Prefabs/**` in `lock_resources`.

## Code structure
- Assembly definitions (`.asmdef`) = modules in `modules.yaml` = ticket-ownership boundaries.
- Gameplay logic in plain C# classes (testable in EditMode); MonoBehaviours stay thin.
- Contracts: C# interfaces in `docs/ai/contracts/` mirrored by `I*.cs` files in the code.

## Gates
- `Unity -batchmode -nographics -projectPath . -runTests -testPlatform EditMode -testResults results.xml`
- PlayMode tests for the tester role.
- The `read_guard` hook in `.agents/config.json` blocks whole-file reads of YAML assets >32 KB.
- `.gitignore`: `Library/ Temp/ Obj/ Build/ Builds/ Logs/ UserSettings/ MemoryCaptures/`
