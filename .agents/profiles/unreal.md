# Profile: Unreal Engine
## Hard rules for agents
- Never touch `*.uasset`, `*.umap` (binary, opaque to text agents). Add them to `protected_globs`.
- New behavior goes in C++ exposed with `UFUNCTION(BlueprintCallable)` / `UPROPERTY(EditAnywhere, BlueprintReadWrite)`.
- Blueprint wiring is a human ticket (`difficulty: L`, owner: human) or done through Epic's Unreal MCP if enabled.
- `*.uproject`, `*.Build.cs`, `*.Target.cs` are lock resources.

## Structure
- Game modules / plugins = modules in `modules.yaml` = ticket-ownership boundaries.
- Keep logic in plain C++ (or UObject) classes that can be unit-tested; Actors/Components stay thin.
- Contracts: headers (`*.h`) copied into tickets; interfaces as `UINTERFACE` where Blueprints need them.

## Gates
- Build one module/target: `<UE>/Engine/Build/BatchFiles/Build.bat <Project>Editor Win64 Development -Project=<path>.uproject -WaitMutex`
- Automation tests: `UnrealEditor-Cmd.exe <path>.uproject -ExecCmds="Automation RunTests <Filter>;Quit" -unattended -nullrhi`
- Builds are slow: keep tickets very small; prefer Live Coding for the human's iteration.
- `.gitignore`: `Binaries/ Intermediate/ Saved/ DerivedDataCache/ .vs/ *.sln`
