using UnrealBuildTool;
public class DelayReviewEditorTarget : TargetRules {
 public DelayReviewEditorTarget(TargetInfo Target) : base(Target) {
  Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.V7; IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8;
  ExtraModuleNames.Add("DelayReview");
 }
}
