using UnrealBuildTool;
public class DelayReviewTarget : TargetRules {
 public DelayReviewTarget(TargetInfo Target) : base(Target) {
  Type=TargetType.Game; DefaultBuildSettings=BuildSettingsVersion.V7; IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8;
  ExtraModuleNames.Add("DelayReview");
 }
}
